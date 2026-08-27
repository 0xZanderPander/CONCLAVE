import json
from typing import Any

import httpx

from conclave.reviewers.provider_contracts import (
    provider_contract_for,
    validate_provider_context,
)
from conclave.reviewers.runtime import (
    AssessmentClaim,
    PermanentReviewerProviderError,
    ProviderCallResult,
    ProviderUsage,
    RetryableReviewerProviderError,
    ReviewCall,
    ReviewerBudgetExceededError,
)

_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504, 529}
_SUPPORTED_STRING_FORMATS = {
    "date-time",
    "time",
    "date",
    "duration",
    "email",
    "hostname",
    "uri",
    "ipv4",
    "ipv6",
    "uuid",
}


def _output_text(document: dict[str, Any]) -> str:
    chunks = [
        item["text"]
        for item in document.get("content", [])
        if isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text"), str)
    ]
    if not chunks:
        raise PermanentReviewerProviderError("the provider returned no structured output")
    return "".join(chunks)


def _structured_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Transform Pydantic JSON Schema to Anthropic's supported strict subset."""

    remaining = dict(schema)
    transformed: dict[str, Any] = {}

    definitions = remaining.pop("$defs", None)
    if isinstance(definitions, dict):
        transformed["$defs"] = {
            name: _structured_output_schema(definition) for name, definition in definitions.items()
        }

    reference = remaining.pop("$ref", None)
    if reference is not None:
        transformed["$ref"] = reference
        return transformed

    schema_type = remaining.pop("type", None)
    any_of = remaining.pop("anyOf", None)
    one_of = remaining.pop("oneOf", None)
    all_of = remaining.pop("allOf", None)
    if isinstance(any_of, list):
        transformed["anyOf"] = [_structured_output_schema(variant) for variant in any_of]
    elif isinstance(one_of, list):
        transformed["anyOf"] = [_structured_output_schema(variant) for variant in one_of]
    elif isinstance(all_of, list):
        transformed["allOf"] = [_structured_output_schema(variant) for variant in all_of]
    elif schema_type is None:
        raise ValueError("structured output schemas require type, anyOf, oneOf, or allOf")
    else:
        transformed["type"] = schema_type

    enum = remaining.pop("enum", None)
    if isinstance(enum, list):
        transformed["enum"] = enum
    description = remaining.pop("description", None)
    if isinstance(description, str):
        transformed["description"] = description
    title = remaining.pop("title", None)
    if isinstance(title, str):
        transformed["title"] = title

    if schema_type == "object":
        properties = remaining.pop("properties", {})
        transformed["properties"] = {
            name: _structured_output_schema(property_schema)
            for name, property_schema in properties.items()
        }
        remaining.pop("additionalProperties", None)
        transformed["additionalProperties"] = False
        required = remaining.pop("required", None)
        if isinstance(required, list):
            transformed["required"] = required
    elif schema_type == "string":
        string_format = remaining.pop("format", None)
        if string_format in _SUPPORTED_STRING_FORMATS:
            transformed["format"] = string_format
        elif string_format is not None:
            remaining["format"] = string_format
    elif schema_type == "array":
        items = remaining.pop("items", None)
        if isinstance(items, dict):
            transformed["items"] = _structured_output_schema(items)
        min_items = remaining.pop("minItems", None)
        if min_items in {0, 1}:
            transformed["minItems"] = min_items
        elif min_items is not None:
            remaining["minItems"] = min_items

    if remaining:
        constraint_summary = (
            "{" + ", ".join(f"{key}: {value}" for key, value in remaining.items()) + "}"
        )
        existing_description = transformed.get("description")
        transformed["description"] = (
            f"{existing_description}\n\n{constraint_summary}"
            if isinstance(existing_description, str)
            else constraint_summary
        )
    return transformed


class AnthropicMessagesProvider:
    """Stateless, tool-free Anthropic Messages adapter for Conclave reviewers."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("an Anthropic API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def invoke(self, call: ReviewCall) -> ProviderCallResult:
        try:
            contract = provider_contract_for(call)
            validate_provider_context(call)
        except (LookupError, ValueError) as exc:
            raise PermanentReviewerProviderError(str(exc)) from exc

        context = {
            "session_id": call.session_id,
            "snapshot_hash": call.snapshot_hash,
            "reviewer_slot": call.slot.value,
            "review_stage": call.stage.value,
            "round": call.round,
            "role_version": call.role_version,
            "prompt_version": call.prompt_version,
            "schema_version": call.schema_version,
            "snapshot": call.snapshot,
            "prior_claims": [
                (claim.model_dump(mode="json") if isinstance(claim, AssessmentClaim) else claim)
                for claim in call.prior_claims
            ],
            "own_assessment": (
                call.own_assessment.model_dump(mode="json")
                if call.own_assessment is not None
                else None
            ),
            "peer_assessments": [peer.model_dump(mode="json") for peer in call.peer_assessments],
            "cross_review_responses": [
                response.model_dump(mode="json") for response in call.cross_review_responses
            ],
            "comparison_history": list(call.comparison_history),
        }
        input_text = json.dumps(context, sort_keys=True, separators=(",", ":"))
        total_input_characters = len(contract.instructions) + len(input_text)
        policy = call.provider_policy
        if total_input_characters > policy.max_input_characters:
            raise ReviewerBudgetExceededError(
                "the reviewer request exceeds its approved input-size ceiling"
            )
        conservative_cost_ceiling = (
            total_input_characters * policy.input_cost_per_million_usd
            + policy.max_output_tokens * policy.output_cost_per_million_usd
        ) / 1_000_000
        if conservative_cost_ceiling > policy.max_cost_usd:
            raise ReviewerBudgetExceededError(
                "the reviewer request exceeds its approved preflight cost ceiling"
            )

        output_config: dict[str, Any] = {
            "format": {
                "type": "json_schema",
                "schema": _structured_output_schema(contract.output_model.model_json_schema()),
            }
        }
        if policy.reasoning_effort != "none":
            output_config["effort"] = policy.reasoning_effort

        payload = {
            "model": call.model,
            "system": contract.instructions,
            "messages": [{"role": "user", "content": input_text}],
            "max_tokens": policy.max_output_tokens,
            "output_config": output_config,
        }
        if policy.reasoning_effort == "none":
            payload["thinking"] = {"type": "disabled"}
        client_request_id = (
            f"{call.session_id}:{call.slot.value}:{call.stage.value}:"
            f"{call.round}:{call.attempt_number}"
        )
        try:
            response = self._client.post(
                f"{self._base_url}/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                    "x-client-request-id": client_request_id,
                },
                json=payload,
                timeout=policy.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise RetryableReviewerProviderError(
                "the provider request failed before a response was received"
            ) from exc

        provider_request_id = response.headers.get("request-id")
        if response.status_code >= 400:
            error_type = (
                RetryableReviewerProviderError
                if response.status_code in _RETRYABLE_STATUS_CODES
                else PermanentReviewerProviderError
            )
            raise error_type(
                f"the provider returned HTTP {response.status_code}",
                provider_request_id=provider_request_id,
            )
        try:
            document = response.json()
        except ValueError as exc:
            raise PermanentReviewerProviderError(
                "the provider returned an unreadable response",
                provider_request_id=provider_request_id,
            ) from exc
        if not isinstance(document, dict) or document.get("type") != "message":
            raise PermanentReviewerProviderError(
                "the provider returned an invalid response envelope",
                provider_request_id=provider_request_id,
            )
        response_id = document.get("id")
        stop_reason = document.get("stop_reason")
        if stop_reason != "end_turn":
            raise PermanentReviewerProviderError(
                f"the provider response ended with stop reason {stop_reason!r}",
                provider_request_id=provider_request_id,
                provider_response_id=response_id if isinstance(response_id, str) else None,
            )
        try:
            output = json.loads(_output_text(document))
        except json.JSONDecodeError as exc:
            raise PermanentReviewerProviderError(
                "the provider output was not valid JSON",
                provider_request_id=provider_request_id,
                provider_response_id=response_id if isinstance(response_id, str) else None,
            ) from exc

        usage_document = document.get("usage")
        usage_document = usage_document if isinstance(usage_document, dict) else {}
        input_tokens = int(usage_document.get("input_tokens") or 0)
        cached_input_tokens = int(usage_document.get("cache_read_input_tokens") or 0)
        output_tokens = int(usage_document.get("output_tokens") or 0)
        total_tokens = input_tokens + output_tokens
        cost_usd = (
            input_tokens * policy.input_cost_per_million_usd
            + output_tokens * policy.output_cost_per_million_usd
        ) / 1_000_000
        return ProviderCallResult(
            output=output,
            provider_request_id=provider_request_id,
            provider_response_id=(response_id if isinstance(response_id, str) else None),
            finish_status=stop_reason,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=0,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                pricing_version=policy.pricing_version,
            ),
        )

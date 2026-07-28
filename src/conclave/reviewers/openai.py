import json
from copy import deepcopy
from typing import Any

import httpx

from conclave.domain.enums import ReviewerSlot, ReviewStage
from conclave.reviewers.prompts import (
    REVIEWER_A_INSTRUCTIONS,
    REVIEWER_A_PROMPT_VERSION,
    REVIEWER_A_ROLE_VERSION,
    REVIEWER_B_INSTRUCTIONS,
    REVIEWER_B_PROMPT_VERSION,
    REVIEWER_B_ROLE_VERSION,
)
from conclave.reviewers.runtime import (
    Assessment,
    PermanentReviewerProviderError,
    ProviderCallResult,
    ProviderUsage,
    RetryableReviewerProviderError,
    ReviewCall,
    ReviewerBudgetExceededError,
)

_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


def _strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adapt Pydantic JSON Schema to OpenAI's strict structured-output subset."""

    document = deepcopy(schema)

    def normalize(value: Any) -> Any:
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if not isinstance(value, dict):
            return value
        cleaned = {
            key: normalize(item)
            for key, item in value.items()
            if key not in {"default", "examples"}
        }
        properties = cleaned.get("properties")
        if isinstance(properties, dict):
            cleaned["additionalProperties"] = False
            cleaned["required"] = list(properties)
        return cleaned

    return normalize(document)


def _output_text(document: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in document.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise PermanentReviewerProviderError("the provider refused the review request")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    if not chunks:
        raise PermanentReviewerProviderError("the provider returned no structured output")
    return "".join(chunks)


class OpenAIResponsesProvider:
    """Stateless, tool-free OpenAI Responses adapter for Conclave reviewers."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("an OpenAI API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client()

    def invoke(self, call: ReviewCall) -> ProviderCallResult:
        approved = {
            ReviewerSlot.A: (
                REVIEWER_A_ROLE_VERSION,
                REVIEWER_A_PROMPT_VERSION,
                REVIEWER_A_INSTRUCTIONS,
            ),
            ReviewerSlot.B: (
                REVIEWER_B_ROLE_VERSION,
                REVIEWER_B_PROMPT_VERSION,
                REVIEWER_B_INSTRUCTIONS,
            ),
        }
        if call.stage != ReviewStage.INDEPENDENT or call.slot not in approved:
            raise PermanentReviewerProviderError(
                f"the production prompt for reviewer {call.slot.value} during "
                f"{call.stage.value} is not approved"
            )
        if call.prior_claims or call.peer_assessments:
            raise PermanentReviewerProviderError(
                "an independent reviewer call cannot contain peer-review content"
            )
        role_version, prompt_version, instructions = approved[call.slot]
        if (
            call.role_version != role_version
            or call.prompt_version != prompt_version
        ):
            raise PermanentReviewerProviderError(
                f"reviewer {call.slot.value} role or prompt version is not approved"
            )
        output_model = Assessment
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
            "prior_claims": list(call.prior_claims),
            "peer_assessments": [
                peer.model_dump(mode="json") for peer in call.peer_assessments
            ],
        }
        input_text = json.dumps(context, sort_keys=True, separators=(",", ":"))
        total_input_characters = len(instructions) + len(input_text)
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

        format_name = "conclave_assessment"
        payload = {
            "model": call.model,
            "instructions": instructions,
            "input": input_text,
            "store": False,
            "tools": [],
            "max_output_tokens": policy.max_output_tokens,
            "reasoning": {"effort": policy.reasoning_effort},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": format_name,
                    "description": "A validated Conclave reviewer output.",
                    "strict": True,
                    "schema": _strict_output_schema(output_model.model_json_schema()),
                }
            },
        }
        client_request_id = (
            f"{call.session_id}:{call.slot.value}:{call.stage.value}:"
            f"{call.round}:{call.attempt_number}"
        )
        try:
            response = self._client.post(
                f"{self._base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "X-Client-Request-Id": client_request_id,
                },
                json=payload,
                timeout=policy.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise RetryableReviewerProviderError(
                "the provider request failed before a response was received"
            ) from exc

        provider_request_id = response.headers.get("x-request-id")
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
        if not isinstance(document, dict):
            raise PermanentReviewerProviderError(
                "the provider returned an invalid response envelope",
                provider_request_id=provider_request_id,
            )
        response_id = document.get("id")
        status = document.get("status")
        if status != "completed":
            raise PermanentReviewerProviderError(
                f"the provider response ended with status {status!r}",
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
        input_details = usage_document.get("input_tokens_details")
        input_details = input_details if isinstance(input_details, dict) else {}
        output_details = usage_document.get("output_tokens_details")
        output_details = output_details if isinstance(output_details, dict) else {}
        input_tokens = int(usage_document.get("input_tokens") or 0)
        output_tokens = int(usage_document.get("output_tokens") or 0)
        total_tokens = int(usage_document.get("total_tokens") or input_tokens + output_tokens)
        cost_usd = (
            input_tokens * policy.input_cost_per_million_usd
            + output_tokens * policy.output_cost_per_million_usd
        ) / 1_000_000
        return ProviderCallResult(
            output=output,
            provider_request_id=provider_request_id,
            provider_response_id=response_id if isinstance(response_id, str) else None,
            finish_status=status if isinstance(status, str) else None,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                cached_input_tokens=int(input_details.get("cached_tokens") or 0),
                output_tokens=output_tokens,
                reasoning_tokens=int(output_details.get("reasoning_tokens") or 0),
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                pricing_version=policy.pricing_version,
            ),
        )

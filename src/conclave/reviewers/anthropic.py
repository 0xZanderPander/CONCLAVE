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


def _output_text(document: dict[str, Any]) -> str:
    chunks = [
        item["text"]
        for item in document.get("content", [])
        if isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text"), str)
    ]
    if not chunks:
        raise PermanentReviewerProviderError(
            "the provider returned no structured output"
        )
    return "".join(chunks)


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
        self._client = client or httpx.Client()

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
                (
                    claim.model_dump(mode="json")
                    if isinstance(claim, AssessmentClaim)
                    else claim
                )
                for claim in call.prior_claims
            ],
            "own_assessment": (
                call.own_assessment.model_dump(mode="json")
                if call.own_assessment is not None
                else None
            ),
            "peer_assessments": [
                peer.model_dump(mode="json") for peer in call.peer_assessments
            ],
            "cross_review_responses": [
                response.model_dump(mode="json")
                for response in call.cross_review_responses
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

        payload = {
            "model": call.model,
            "system": contract.instructions,
            "messages": [{"role": "user", "content": input_text}],
            "max_tokens": policy.max_output_tokens,
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": contract.output_model.model_json_schema(),
                }
            },
        }
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
        cached_input_tokens = int(
            usage_document.get("cache_read_input_tokens") or 0
        )
        output_tokens = int(usage_document.get("output_tokens") or 0)
        total_tokens = input_tokens + output_tokens
        cost_usd = (
            input_tokens * policy.input_cost_per_million_usd
            + output_tokens * policy.output_cost_per_million_usd
        ) / 1_000_000
        return ProviderCallResult(
            output=output,
            provider_request_id=provider_request_id,
            provider_response_id=(
                response_id if isinstance(response_id, str) else None
            ),
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

"""Vercel AI Gateway adapter: every lab and open-weights host through one key.

The gateway serves the OpenAI Responses API at ``/v1/responses`` with
vendor-prefixed model ids (``openai/gpt-5.6-terra``, ``anthropic/claude-sonnet-5``,
``google/gemini-3.6-flash``, …) and the same ``text.format`` structured
output. So the adapter is the Responses adapter pointed at the gateway: same
preflight ceilings, same budget errors, same usage accounting, same strict
schema. Only the base URL, the key and the model naming differ.

Two things the gateway does differently and this adapter accounts for:

- Schema support varies by vendor behind the gateway; a request still
  succeeds when a model cannot follow a schema. Conclave already validates
  every output against the pack's schema (``pack.parse_output``), so an
  off-schema answer fails the attempt rather than entering the ledger.
- ``reasoning.effort`` is passed through; vendors that do not take it
  ignore it at the gateway. Usage fields follow the Responses shape.

Seats bind to provider ``vercel_gateway`` on a plan revision; nothing
changes for plans still bound to the direct adapters, which stay as the
fallback.
"""

from __future__ import annotations

import httpx

from conclave.reviewers.openai import OpenAIResponsesProvider
from conclave.reviewers.runtime import PermanentReviewerProviderError, ReviewCall

DEFAULT_VERCEL_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
PROVIDER_NAME = "vercel_gateway"


class VercelGatewayProvider(OpenAIResponsesProvider):
    """OpenAI Responses over Vercel AI Gateway, with vendor-prefixed models."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_VERCEL_GATEWAY_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("a Vercel AI Gateway API key is required")
        super().__init__(api_key=api_key, base_url=base_url, client=client)

    def invoke(self, call: ReviewCall):  # type: ignore[override]
        # The gateway routes on the vendor prefix; a bare model name would be
        # a silent mis-route or a 404 with a cost. Refuse it before any call.
        if "/" not in call.model or call.model.startswith("/") or call.model.endswith("/"):
            raise PermanentReviewerProviderError(
                "Vercel AI Gateway models must be vendor-prefixed, e.g. openai/gpt-5.6-terra"
            )
        return super().invoke(call)

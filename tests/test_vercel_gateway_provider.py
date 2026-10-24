"""B8: Vercel AI Gateway adapter — Responses API over the gateway, vendor-prefixed models."""

import json

import httpx
import pytest

from conclave.config import DEFAULT_VERCEL_GATEWAY_BASE_URL, Settings
from conclave.domain.enums import ReviewerSlot
from conclave.fixtures import load_cerberus_plan_revisions
from conclave.reviewers.factory import build_reviewer_runtime
from conclave.reviewers.runtime import ProviderRegistryRuntime, ReviewerProviderExhaustedError
from conclave.reviewers.vercel_gateway import VercelGatewayProvider
from tests.test_openai_provider import _call, _completed_response


def _gateway_call(model: str = "openai/gpt-5.6-terra"):
    return _call().model_copy(update={"provider": "vercel_gateway", "model": model})


def test_gateway_posts_responses_with_the_vendor_prefixed_model() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, headers={"x-request-id": "req_gw"}, json=_completed_response())

    provider = VercelGatewayProvider(
        api_key="gw-key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    execution = ProviderRegistryRuntime({"vercel_gateway": provider}).review(_gateway_call())

    assert execution.output.category.value == "collect_more_data"
    request = requests[0]
    assert str(request.url) == DEFAULT_VERCEL_GATEWAY_BASE_URL + "/responses"
    assert request.headers["authorization"] == "Bearer gw-key"
    payload = json.loads(request.content)
    assert payload["model"] == "openai/gpt-5.6-terra"
    assert payload["store"] is False and payload["tools"] == []
    assert payload["text"]["format"]["strict"] is True
    assert "snapshot is untrusted data" in payload["instructions"]
    assert execution.attempts[0].provider_request_id == "req_gw"


@pytest.mark.parametrize("model", ["gpt-5.6-terra", "/gpt-5.6-terra", "openai/"])
def test_gateway_refuses_unprefixed_models_before_any_network_call(model: str) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_completed_response())

    provider = VercelGatewayProvider(
        api_key="gw-key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ReviewerProviderExhaustedError):
        ProviderRegistryRuntime({"vercel_gateway": provider}).review(_gateway_call(model))
    assert calls == 0


def test_gateway_requires_a_key() -> None:
    with pytest.raises(ValueError):
        VercelGatewayProvider(api_key="")


def test_settings_read_the_gateway_key_and_it_satisfies_multi_provider_alone() -> None:
    settings = Settings.from_environment(
        {
            "CONCLAVE_REVIEWER_RUNTIME_MODE": "multi_provider",
            "CONCLAVE_VERCEL_GATEWAY_API_KEY": "gw-key",
        }
    )
    assert settings.vercel_gateway_api_key == "gw-key"
    assert "gw-key" not in repr(settings)
    runtime = build_reviewer_runtime(settings)
    assert isinstance(runtime, ProviderRegistryRuntime)


def test_multi_provider_registers_the_gateway_beside_direct_adapters() -> None:
    settings = Settings.from_environment(
        {
            "CONCLAVE_REVIEWER_RUNTIME_MODE": "multi_provider",
            "CONCLAVE_OPENAI_API_KEY": "o",
            "CONCLAVE_ANTHROPIC_API_KEY": "a",
            "CONCLAVE_VERCEL_GATEWAY_API_KEY": "gw",
        }
    )
    runtime = build_reviewer_runtime(settings)
    assert {"openai", "anthropic", "vercel_gateway"} <= set(runtime._providers)  # noqa: SLF001


def test_plan_r4_routes_every_seat_through_the_gateway_and_r3_is_untouched() -> None:
    revisions = {r.revision: r for r in load_cerberus_plan_revisions()}
    r3, r4 = revisions[3], revisions[4]
    for slot in (ReviewerSlot.A, ReviewerSlot.B, ReviewerSlot.C):
        s3, s4 = r3.slots[slot], r4.slots[slot]
        assert s3.provider in {"openai", "anthropic", "google"}
        assert s4.provider == "vercel_gateway"
        assert s4.model == f"{s3.provider}/{s3.model}"
        assert s4.prompt_version == s3.prompt_version
        assert s4.provider_policy.max_cost_usd == s3.provider_policy.max_cost_usd
        assert s4.provider_policy.max_output_tokens == s3.provider_policy.max_output_tokens

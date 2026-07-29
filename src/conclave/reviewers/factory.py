from conclave.config import Settings
from conclave.reviewers.anthropic import AnthropicMessagesProvider
from conclave.reviewers.development import DevelopmentReviewerRuntime
from conclave.reviewers.gemini import GeminiInteractionsProvider
from conclave.reviewers.openai import OpenAIResponsesProvider
from conclave.reviewers.runtime import ProviderRegistryRuntime, ReviewerRuntime


def build_reviewer_runtime(settings: Settings) -> ReviewerRuntime:
    """Build the explicitly configured reviewer runtime without fallback."""

    if settings.reviewer_runtime_mode == "fixture":
        return DevelopmentReviewerRuntime()
    if settings.reviewer_runtime_mode == "openai":
        if settings.openai_api_key is None:
            raise ValueError("the OpenAI reviewer runtime requires an API key")
        return ProviderRegistryRuntime(
            {
                "openai": OpenAIResponsesProvider(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                )
            },
            max_attempts=2,
        )
    if settings.reviewer_runtime_mode == "anthropic":
        if settings.anthropic_api_key is None:
            raise ValueError("the Anthropic reviewer runtime requires an API key")
        return ProviderRegistryRuntime(
            {
                "anthropic": AnthropicMessagesProvider(
                    api_key=settings.anthropic_api_key,
                    base_url=settings.anthropic_base_url,
                )
            },
            max_attempts=2,
        )
    if settings.reviewer_runtime_mode == "gemini":
        if settings.google_api_key is None:
            raise ValueError("the Gemini reviewer runtime requires a Google API key")
        return ProviderRegistryRuntime(
            {
                "google": GeminiInteractionsProvider(
                    api_key=settings.google_api_key,
                    base_url=settings.google_base_url,
                )
            },
            max_attempts=2,
        )
    if settings.reviewer_runtime_mode == "multi_provider":
        if settings.openai_api_key is None or settings.anthropic_api_key is None:
            raise ValueError(
                "the multi-provider reviewer runtime requires OpenAI and Anthropic API keys"
            )
        return ProviderRegistryRuntime(
            {
                "openai": OpenAIResponsesProvider(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                ),
                "anthropic": AnthropicMessagesProvider(
                    api_key=settings.anthropic_api_key,
                    base_url=settings.anthropic_base_url,
                ),
            },
            max_attempts=2,
        )
    raise ValueError(
        f"unsupported reviewer runtime mode {settings.reviewer_runtime_mode!r}"
    )

from conclave.config import Settings
from conclave.reviewers.development import DevelopmentReviewerRuntime
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
    raise ValueError(
        f"unsupported reviewer runtime mode {settings.reviewer_runtime_mode!r}"
    )

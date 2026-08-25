from dataclasses import dataclass

from verdictforge.arena import DebateEngine
from verdictforge.config import Settings
from verdictforge.providers import CompletionResult, ProviderError
from verdictforge.schemas import DebateMode, DebateRequest, ModelSpec, ProviderName, Usage


@dataclass
class FakeProviders:
    failing: str | None = None

    def __post_init__(self) -> None:
        self.catalog = {
            model_id: ModelSpec(
                id=model_id,
                display_name=model_id.upper(),
                provider=ProviderName.GROQ,
                model=model_id,
                description="Test model",
                accent="#ff6b35",
                available=True,
            )
            for model_id in ["a", "b", "c"]
        }

    def available_model_ids(self) -> list[str]:
        return list(self.catalog)

    async def complete(self, model_id: str, messages, **kwargs) -> CompletionResult:
        if model_id == self.failing:
            raise ProviderError("Synthetic failure.", model_id=model_id)
        return CompletionResult(
            content=f"{model_id}: {messages[-1]['content'][:20]}",
            latency_ms=10,
            usage=Usage(input_tokens=5, output_tokens=8),
        )


def settings() -> Settings:
    return Settings(
        _env_file=None,
        groq_api_key=None,
        nvidia_api_key=None,
        nvidia_openai_api_key=None,
    )


async def test_direct_mode_collects_all_answers() -> None:
    engine = DebateEngine(FakeProviders(), settings())
    answers = await engine.collect_answers(
        DebateRequest(question="Test the arena", model_ids=["a", "b", "c"], mode=DebateMode.DIRECT)
    )

    assert [answer.model_id for answer in answers] == ["a", "b", "c"]
    assert all(answer.content for answer in answers)


async def test_one_provider_failure_does_not_abort_others() -> None:
    engine = DebateEngine(FakeProviders(failing="b"), settings())
    answers = await engine.collect_answers(
        DebateRequest(question="Test resilience", model_ids=["a", "b", "c"], mode=DebateMode.DIRECT)
    )

    assert answers[1].error == "Synthetic failure."
    assert answers[0].content and answers[2].content


async def test_deliberation_accumulates_round_usage() -> None:
    engine = DebateEngine(FakeProviders(), settings())
    answers = await engine.collect_answers(
        DebateRequest(question="Test two rounds", model_ids=["a", "b"], mode=DebateMode.DELIBERATE)
    )

    assert all(answer.latency_ms == 20 for answer in answers)
    assert all(answer.usage.output_tokens == 16 for answer in answers)

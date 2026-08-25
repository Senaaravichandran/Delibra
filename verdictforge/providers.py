"""Resilient asynchronous adapters for OpenAI-compatible model providers."""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from verdictforge.catalog import build_model_catalog
from verdictforge.config import Settings
from verdictforge.schemas import ModelSpec, Usage

logger = logging.getLogger(__name__)
REASONING_BLOCK = re.compile(
    r"<(think|analysis|reasoning)>.*?</\1>", flags=re.IGNORECASE | re.DOTALL
)


class ProviderError(RuntimeError):
    """A safe, user-facing provider failure."""

    def __init__(self, message: str, *, model_id: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.model_id = model_id
        self.retryable = retryable


class TransientProviderError(ProviderError):
    """A temporary provider failure that can be retried."""

    def __init__(self, message: str, *, model_id: str) -> None:
        super().__init__(message, model_id=model_id, retryable=True)


@dataclass(slots=True)
class CompletionResult:
    content: str
    latency_ms: int
    usage: Usage


class ProviderClient:
    """One async client for an OpenAI-compatible provider endpoint."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        timeout: float,
    ) -> None:
        self.name = name
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
            default_headers={"X-Title": "Delibra"},
        )

    async def complete(
        self,
        *,
        spec: ModelSpec,
        messages: Sequence[dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 1_500,
        json_mode: bool = False,
    ) -> CompletionResult:
        """Request one completion with bounded exponential retries."""

        started = perf_counter()
        retryer = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=0.5, max=4),
            retry=retry_if_exception_type(TransientProviderError),
            reraise=True,
        )

        async for attempt in retryer:
            with attempt:
                try:
                    request: dict[str, Any] = {
                        "model": spec.model,
                        "messages": list(messages),
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if json_mode:
                        request["response_format"] = {"type": "json_object"}
                    response = await self._client.chat.completions.create(**request)
                except (
                    APIConnectionError,
                    APITimeoutError,
                    RateLimitError,
                    InternalServerError,
                ) as exc:
                    logger.warning(
                        "Transient %s failure for %s: %s",
                        self.name,
                        spec.id,
                        type(exc).__name__,
                    )
                    raise TransientProviderError(
                        f"{spec.display_name} is temporarily unavailable.", model_id=spec.id
                    ) from exc
                except APIStatusError as exc:
                    retryable = exc.status_code == 429 or exc.status_code >= 500
                    error_type = TransientProviderError if retryable else ProviderError
                    logger.warning(
                        "Provider %s returned status %s for %s",
                        self.name,
                        exc.status_code,
                        spec.id,
                    )
                    raise error_type(
                        f"{spec.display_name} rejected the request.", model_id=spec.id
                    ) from exc
                except Exception as exc:
                    logger.exception("Unexpected provider failure for %s", spec.id)
                    raise ProviderError(
                        f"{spec.display_name} could not complete the request.", model_id=spec.id
                    ) from exc

        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice and choice.message.content else ""
        content = strip_hidden_reasoning(content)
        if not content.strip():
            raise ProviderError("The model returned an empty response.", model_id=spec.id)

        response_usage = response.usage
        usage = Usage(
            input_tokens=getattr(response_usage, "prompt_tokens", None),
            output_tokens=getattr(response_usage, "completion_tokens", None),
        )
        return CompletionResult(
            content=content.strip(),
            latency_ms=round((perf_counter() - started) * 1000),
            usage=usage,
        )

    async def close(self) -> None:
        await self._client.close()


class ProviderRegistry:
    """Routes public model IDs to configured provider clients."""

    def __init__(self, settings: Settings) -> None:
        self.catalog = build_model_catalog(settings)
        self._clients: dict[str, ProviderClient] = {}

        if settings.groq_api_key:
            self._clients["groq"] = ProviderClient(
                name="Groq",
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=settings.request_timeout_seconds,
            )

        nvidia_key = settings.nvidia_api_key or settings.nvidia_openai_api_key
        if nvidia_key:
            self._clients["nvidia"] = ProviderClient(
                name="NVIDIA NIM",
                api_key=nvidia_key,
                base_url="https://integrate.api.nvidia.com/v1",
                timeout=settings.request_timeout_seconds,
            )

    def available_model_ids(self) -> list[str]:
        return [model.id for model in self.catalog.values() if model.available]

    def resolve(self, model_id: str) -> tuple[ModelSpec, ProviderClient]:
        spec = self.catalog.get(model_id)
        if spec is None:
            raise ProviderError("Unknown model selection.", model_id=model_id)
        client = self._clients.get(spec.provider.value)
        if client is None or not spec.available:
            raise ProviderError(
                f"{spec.display_name} is not configured on this server.", model_id=model_id
            )
        return spec, client

    async def complete(
        self,
        model_id: str,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1_500,
        json_mode: bool = False,
    ) -> CompletionResult:
        spec, client = self.resolve(model_id)
        return await client.complete(
            spec=spec,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()


def strip_hidden_reasoning(content: str) -> str:
    """Remove provider-emitted private reasoning blocks from public answers."""

    return REASONING_BLOCK.sub("", content).strip()

"""LLM client abstraction.

Production note: agents should depend on this interface instead of importing an SDK directly.
"""

import logging
from dataclasses import dataclass

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from multi_agent_research_lab.core.config import get_settings

logger = logging.getLogger(__name__)

# Approximate pricing per 1M tokens
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),      # (input, output) per 1M tokens
    "gpt-4o": (2.50, 10.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # OpenRouter model names
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
}


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate USD cost based on known pricing tiers."""
    pricing = _PRICING.get(model)
    if pricing is None:
        return None
    input_price, output_price = pricing
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class LLMClient:
    """Provider-agnostic LLM client backed by OpenAI."""

    def __init__(self, model: str | None = None, temperature: float = 0.2) -> None:
        settings = get_settings()
        self._model = model or settings.openai_model
        self._temperature = temperature
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.timeout_seconds,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return a model completion with retry, timeout, and token tracking."""

        logger.info("LLM call [model=%s] prompt_len=%d", self._model, len(user_prompt))

        response = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        choice = response.choices[0]
        usage = response.usage

        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        cost = (
            _estimate_cost(self._model, input_tokens, output_tokens)
            if input_tokens and output_tokens
            else None
        )

        logger.info(
            "LLM response [tokens in=%s out=%s cost=$%s]",
            input_tokens,
            output_tokens,
            f"{cost:.6f}" if cost else "N/A",
        )

        return LLMResponse(
            content=choice.message.content or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

"""One structured LLM call with the offline fallback the LLM nodes share (spec D2).

With no provider configured the heuristic answer is used as is; when the provider fails the heuristic answer
is used and the failure is reported in ``fallback_reason``, so the dashboard shows it.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from gridline.llm.base import LLMError, LLMProvider, load_prompt, narrow

log = logging.getLogger(__name__)


@dataclass
class CallMeta:
    provider: Literal["ollama", "mock"]
    model: str | None
    fallback_reason: str | None
    duration_ms: int


async def ask[T: BaseModel](
    provider: LLMProvider | None,
    *,
    prompt: str,
    fields: dict[str, Any],
    output: type[T],
    enums: dict[str, list[str]],
    fallback: Callable[[], T],
) -> tuple[T, CallMeta]:
    started = time.monotonic()

    def elapsed() -> int:
        return int((time.monotonic() - started) * 1000)

    if provider is None:
        return fallback(), CallMeta("mock", None, None, elapsed())
    schema = output.model_json_schema()
    for field, values in enums.items():
        schema = narrow(schema, field, values)
    text = load_prompt(prompt).format(**fields)
    try:
        answer = await provider.complete_structured(
            system="You are a careful emergency-management analyst. Reply only with JSON.",
            user=text,
            schema=schema,
            output=output,
        )
    except LLMError as exc:
        log.warning("LLM %s step fell back to the heuristic reasoner: %s", prompt, exc)
        return fallback(), CallMeta("mock", None, str(exc), elapsed())
    return answer, CallMeta("ollama", provider.model, None, elapsed())

"""The LLM provider contract: structured output only, validated against a Pydantic model.

The JSON schema is passed separately from the output model so a caller can narrow it for one call (for
example ``citation_ids`` restricted to the IDs actually in the input) while validating with the full model.
"""

from importlib.resources import files
from typing import Any, Protocol

from pydantic import BaseModel


class LLMError(Exception):
    """The provider could not produce a valid structured answer (unreachable, timeout, bad output)."""


class LLMProvider(Protocol):
    name: str
    model: str

    async def complete_structured[T: BaseModel](
        self, *, system: str, user: str, schema: dict[str, Any], output: type[T]
    ) -> T: ...


def load_prompt(name: str) -> str:
    """A Markdown prompt from ``gridline/llm/prompts/``."""
    return files("gridline.llm").joinpath("prompts", f"{name}.md").read_text(encoding="utf-8")


def narrow(schema: dict[str, Any], field: str, values: list[str]) -> dict[str, Any]:
    """Copy of ``schema`` where every property called ``field`` only accepts ``values``.

    A string property becomes an enum; an array of strings gets enum items. Ollama compiles the schema into a
    grammar, so the model cannot produce a value outside the list.
    """
    enum = sorted(set(values)) or [""]

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {k: walk(v) for k, v in node.items()}  # pyright: ignore[reportUnknownVariableType]
            props = out.get("properties")
            if isinstance(props, dict) and field in props:
                prop: dict[str, Any] = dict(props[field])  # pyright: ignore[reportUnknownArgumentType]
                if prop.get("type") == "array":
                    prop["items"] = {"type": "string", "enum": enum}
                else:
                    prop = {"type": "string", "enum": enum}
                out["properties"] = {**props, field: prop}
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]  # pyright: ignore[reportUnknownVariableType]
        return node

    return walk(schema)

"""Ollama over its HTTP API (``POST /api/chat``), no client library.

``format`` carries a JSON schema, which Ollama turns into a decoding grammar, so the reply is always
schema-shaped JSON. ``urllib`` runs in a worker thread, as ``gridline.sources.open_meteo`` does.
"""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel, ValidationError

from gridline.llm.base import LLMError

NUM_CTX = 8192
NUM_PREDICT = 1024


class OllamaProvider:
    name = "ollama"

    def __init__(self, host: str, model: str, *, timeout_s: float) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def request_body(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "format": schema,
            "keep_alive": "30m",
            "options": {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT},
        }

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return data

    async def complete_structured[T: BaseModel](
        self, *, system: str, user: str, schema: dict[str, Any], output: type[T]
    ) -> T:
        try:
            data = await asyncio.to_thread(self._post, self.request_body(system, user, schema))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise LLMError(f"Ollama at {self.host} failed: {exc}") from exc
        if data.get("error"):
            raise LLMError(f"Ollama error: {data['error']}")
        content = str(data.get("message", {}).get("content", ""))
        try:
            return output.model_validate_json(content)
        except ValidationError as exc:
            raise LLMError(f"{self.model} returned output that does not fit the schema: {exc}") from exc

"""The Ollama provider (HTTP faked) and schema narrowing; plus one opt-in call to a real local Ollama."""

import json
import urllib.error
import urllib.request
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gridline.agents.state import ReasoningResult
from gridline.city.model import City
from gridline.config import Settings
from gridline.llm.base import LLMError, narrow
from gridline.llm.ollama import OllamaProvider
from gridline.main import create_app

ANSWER = {
    "summary": "s",
    "band": "warning",
    "confidence": 0.5,
    "claims": [{"text": "t", "citation_ids": ["a"]}],
}


def provider() -> OllamaProvider:
    return OllamaProvider("http://127.0.0.1:11434/", "qwen2.5:7b-instruct", timeout_s=5)


def test_narrow_restricts_citation_ids_to_the_given_values() -> None:
    schema = narrow(ReasoningResult.model_json_schema(), "citation_ids", ["b", "a", "a"])
    claim = schema["$defs"]["Claim"]["properties"]["citation_ids"]
    assert claim["items"] == {"type": "string", "enum": ["a", "b"]}


def test_request_body_carries_schema_and_options() -> None:
    body = provider().request_body("sys", "user", {"type": "object"})
    assert body["model"] == "qwen2.5:7b-instruct" and body["stream"] is False
    assert body["format"] == {"type": "object"} and body["options"]["temperature"] == 0
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


async def test_parses_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    p = provider()
    monkeypatch.setattr(p, "_post", lambda body: {"message": {"content": json.dumps(ANSWER)}})
    out = await p.complete_structured(system="s", user="u", schema={}, output=ReasoningResult)
    assert out.band == "warning"


@pytest.mark.parametrize(
    "reply",
    [
        {"error": "model not found"},
        {"message": {"content": "{not json"}},
        {"message": {"content": json.dumps({**ANSWER, "band": "apocalyptic"})}},
    ],
)
async def test_bad_replies_raise_llm_error(monkeypatch: pytest.MonkeyPatch, reply: dict[str, Any]) -> None:
    p = provider()
    monkeypatch.setattr(p, "_post", lambda body: reply)
    with pytest.raises(LLMError):
        await p.complete_structured(system="s", user="u", schema={}, output=ReasoningResult)


async def test_unreachable_server_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    with pytest.raises(LLMError, match="connection refused"):
        await provider().complete_structured(system="s", user="u", schema={}, output=ReasoningResult)


def test_approval_route_404_for_unknown_run_and_snapshot_has_no_run(settings: Settings, city: City) -> None:
    with TestClient(create_app(settings.model_copy(update={"llm_provider": "mock"}), city=city)) as client:
        response = client.post("/api/agent/runs/run-nope/approval", json={"decision": "approve"})
        assert response.status_code == 404
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["payload"]["agent_run"] is None


def _ollama_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=2):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="no local Ollama")
async def test_real_ollama_answers_inside_the_schema() -> None:
    schema = narrow(ReasoningResult.model_json_schema(), "citation_ids", ["event:1", "kg:x"])
    out = await OllamaProvider(
        "http://127.0.0.1:11434", "qwen2.5:7b-instruct", timeout_s=180
    ).complete_structured(
        system="Reply only with JSON.",
        user="[event:1] Slope SL-1 failed. [kg:x] Project P-1 excavates on SL-1. Assess the threat briefly.",
        schema=schema,
        output=ReasoningResult,
    )
    assert {c for claim in out.claims for c in claim.citation_ids} <= {"event:1", "kg:x"}

"""Small provider-neutral LLM client interface, recording, replay, and fake clients."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib import request


class LLMError(RuntimeError):
    """Base class for expected LLM client failures."""


class ReplayMiss(LLMError):
    """Raised when a requested offline recording does not exist."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return the provider's raw text response."""


def cache_key(
    prompt_version: str,
    model: str,
    question: str,
    candidate_ids: list[str],
) -> str:
    canonical = json.dumps(
        [prompt_version, model, question, sorted(candidate_ids)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat-completions client using the stdlib."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int = 180,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def complete(self, system: str, user: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
        except Exception as exc:  # Provider/network shapes vary; caller safely falls back.
            raise LLMError(f"llm_error:{type(exc).__name__}") from exc


class ReplayClient:
    def __init__(self, recording_path: str | Path) -> None:
        self.recording_path = Path(recording_path)

    def complete(self, system: str, user: str) -> str:
        del system, user
        if not self.recording_path.exists():
            raise ReplayMiss("replay_miss")
        try:
            data = json.loads(self.recording_path.read_text(encoding="utf-8"))
            raw = data["raw_response"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise LLMError("invalid_recording") from exc
        if not isinstance(raw, str):
            raise LLMError("invalid_recording")
        return raw


class RecordingClient:
    def __init__(
        self,
        inner: LLMClient,
        recording_path: str | Path,
        model: str,
        prompt_version: str,
        candidate_ids: list[str],
    ) -> None:
        self.inner = inner
        self.recording_path = Path(recording_path)
        self.model = model
        self.prompt_version = prompt_version
        self.candidate_ids = sorted(candidate_ids)

    def complete(self, system: str, user: str) -> str:
        raw = self.inner.complete(system, user)
        record = {
            "model": self.model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_version": self.prompt_version,
            "candidate_ids": self.candidate_ids,
            "raw_response": raw,
        }
        self.recording_path.parent.mkdir(parents=True, exist_ok=True)
        self.recording_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return raw


class FakeClient:
    """Offline client returning canned raw JSON keyed by question."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        try:
            question = json.loads(user)["question"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise LLMError("fake_client_bad_prompt") from exc
        try:
            return self.responses[question]
        except KeyError as exc:
            raise LLMError("fake_client_missing_response") from exc

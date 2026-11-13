"""OpenAI-compatible chat client with a timeout, retries, and JSON checks.

The key never lives in source. Set ``LLM_API_KEY`` in the environment or in
a local ``.env`` file. When the key is missing, callers should skip the
network and use the shelf-life heuristic instead.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from larder import project_root

T = TypeVar("T", bound=BaseModel)

# (payload) -> parsed response body
Transport = Callable[[dict], dict]


class LLMError(Exception):
    """The model call failed, timed out, or returned JSON we cannot use."""


def load_project_env(path: Path | None = None) -> None:
    """Load ``KEY=value`` lines from ``.env`` without overriding real env vars.

    This is a tiny reader so the app does not need an extra package. Blank
    lines and ``#`` comments are ignored.
    """
    env_path = path or (project_root() / ".env")
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


class LLMClient:
    """POST chat completions and parse the reply into a Pydantic model."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        retries: int = 2,
        transport: Transport | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        load_project_env()
        self.api_key = (api_key if api_key is not None else os.environ.get("LLM_API_KEY", "")).strip()
        self.base_url = (
            base_url if base_url is not None else os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.model = model if model is not None else os.environ.get("LLM_MODEL", "gpt-4o-mini")
        if timeout is None:
            timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))
        self.timeout = timeout
        self.retries = retries
        self._transport = transport
        self._sleep = sleep or time.sleep

    @classmethod
    def from_env(cls) -> LLMClient | None:
        """Return a client when a key is configured, otherwise ``None``."""
        load_project_env()
        if not os.environ.get("LLM_API_KEY", "").strip():
            return None
        return cls()

    def complete_json(self, *, system: str, user: str, schema: type[T]) -> T:
        """Call the model and validate the JSON body against ``schema``.

        Transport errors, timeouts, and invalid JSON are retried. An HTTP 401
        or 400 is not retried, because repeating it will not make the request
        valid.
        """
        if not self.api_key:
            raise LLMError("LLM_API_KEY is not set")

        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        attempts = self.retries + 1
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                body = self._post(payload)
                content = body["choices"][0]["message"]["content"]
                parsed = json.loads(_strip_fence(content))
                return schema.model_validate(parsed)
            except LLMError as exc:
                if _is_fatal_http(exc):
                    raise
                last = exc
            except (
                TimeoutError,
                urllib.error.URLError,
                KeyError,
                IndexError,
                json.JSONDecodeError,
                ValidationError,
                TypeError,
            ) as exc:
                last = exc
            if attempt + 1 < attempts:
                self._sleep(0.4 * (2**attempt))
        raise LLMError(f"LLM call failed after {attempts} attempts") from last

    def _post(self, payload: dict) -> dict:
        if self._transport is not None:
            return self._transport(payload)
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise LLMError(f"LLM HTTP {exc.code}: {detail}") from exc


def _strip_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _is_fatal_http(exc: LLMError) -> bool:
    message = str(exc)
    return message.startswith("LLM HTTP 400") or message.startswith("LLM HTTP 401") or message.startswith("LLM HTTP 403")

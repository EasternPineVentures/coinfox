"""Local Ollama provider. Free forever. Zero data leaves your machine."""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

from ..base import AICall, AIResult, Provider, ProviderError


class OllamaProvider:
    name = "ollama"
    cost_tier = "local"
    requires_key_env: Optional[str] = None

    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_OLLAMA_MODEL", "llama3.2")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=2)
            if r.status_code != 200:
                return False
            tags = r.json().get("models", [])
            names = {m.get("name", "").split(":")[0] for m in tags}
            base = self.model.split(":")[0]
            return base in names or any(n.startswith(base) for n in names)
        except requests.RequestException:
            return False

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        try:
            r = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "options": {
                        # Give generous budget; thinking models use tokens internally
                        "num_predict": max(call.max_tokens, 800),
                        "temperature": call.temperature,
                    },
                    "messages": [
                        {"role": "system", "content": call.system},
                        {"role": "user", "content": call.prompt},
                    ],
                },
                timeout=180,
            )
            r.raise_for_status()
            data = r.json()
            msg = data.get("message") or {}
            # qwen3 and other thinking models split content from thinking tokens
            text = (msg.get("content") or "").strip()
            if not text:
                # fallback: try the thinking field (some models put output there)
                text = (msg.get("thinking") or "").strip()
        except requests.RequestException as e:
            raise ProviderError(f"ollama: {e}") from e
        return AIResult(
            provider=self.name,
            model=self.model,
            text=text,
            latency_ms=int((time.time() - start) * 1000),
            cost_tier=self.cost_tier,
        )

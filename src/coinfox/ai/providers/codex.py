"""Codex Pro (OpenAI-compatible) — user-owned key routes here.

Set CODEX_API_KEY. Base URL defaults to OpenAI but can be overridden
with CODEX_BASE_URL for any OpenAI-compatible endpoint.
"""
from __future__ import annotations
import os, time
from typing import Optional
import requests
from ..base import AICall, AIResult, ProviderError

class CodexProvider:
    name = "codex"
    cost_tier = "freemium-with-key"
    requires_key_env = "CODEX_API_KEY"

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_CODEX_MODEL", "codex-mini-latest")
        self.base_url = (base_url or os.environ.get("CODEX_BASE_URL", "https://api.openai.com")).rstrip("/")

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        key = os.environ.get(self.requires_key_env)
        if not key:
            raise ProviderError("codex: no CODEX_API_KEY")
        try:
            r = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [
                    {"role": "system", "content": call.system},
                    {"role": "user", "content": call.prompt},
                ], "max_tokens": call.max_tokens, "temperature": call.temperature},
                timeout=90,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError) as e:
            raise ProviderError(f"codex: {e}") from e
        return AIResult(self.name, self.model, text, int((time.time()-start)*1000), self.cost_tier)

"""Groq free tier — fast, generous, free.

Set GROQ_API_KEY env var. Get a key at https://console.groq.com (free).
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

from ..base import AICall, AIResult, ProviderError


class GroqProvider:
    name = "groq"
    cost_tier = "freemium-with-key"
    requires_key_env = "GROQ_API_KEY"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_GROQ_MODEL", "llama-3.3-70b-versatile")

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        key = os.environ.get(self.requires_key_env)
        if not key:
            raise ProviderError("groq: no GROQ_API_KEY")
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": call.system},
                        {"role": "user", "content": call.prompt},
                    ],
                    "max_tokens": call.max_tokens,
                    "temperature": call.temperature,
                },
                timeout=60,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError) as e:
            raise ProviderError(f"groq: {e}") from e
        return AIResult(self.name, self.model, text,
                        int((time.time() - start) * 1000), self.cost_tier)

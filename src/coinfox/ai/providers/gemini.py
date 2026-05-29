"""Google Gemini free tier. Set GEMINI_API_KEY (https://aistudio.google.com)."""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

from ..base import AICall, AIResult, ProviderError


class GeminiProvider:
    name = "gemini"
    cost_tier = "freemium-with-key"
    requires_key_env = "GEMINI_API_KEY"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_GEMINI_MODEL", "gemini-1.5-flash-latest")

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        key = os.environ.get(self.requires_key_env)
        if not key:
            raise ProviderError("gemini: no GEMINI_API_KEY")
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                params={"key": key},
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": call.system}]},
                    "contents": [{"role": "user", "parts": [{"text": call.prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": call.max_tokens,
                        "temperature": call.temperature,
                    },
                },
                timeout=60,
            )
            r.raise_for_status()
            cand = r.json()["candidates"][0]
            parts = cand["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (requests.RequestException, KeyError, IndexError) as e:
            raise ProviderError(f"gemini: {e}") from e
        return AIResult(self.name, self.model, text,
                        int((time.time() - start) * 1000), self.cost_tier)

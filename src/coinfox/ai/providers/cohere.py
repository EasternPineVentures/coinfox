"""Cohere — free trial tier, good at structured analysis.

Get a free key: https://dashboard.cohere.com
Set COHERE_API_KEY.
"""
from __future__ import annotations
import os, time
from typing import Optional
import requests
from ..base import AICall, AIResult, ProviderError

class CohereProvider:
    name = "cohere"
    cost_tier = "freemium-with-key"
    requires_key_env = "COHERE_API_KEY"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_COHERE_MODEL", "command-r")

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        key = os.environ.get(self.requires_key_env)
        if not key:
            raise ProviderError("cohere: no COHERE_API_KEY")
        try:
            r = requests.post(
                "https://api.cohere.com/v2/chat",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [
                    {"role": "system", "content": call.system},
                    {"role": "user", "content": call.prompt},
                ], "max_tokens": call.max_tokens, "temperature": call.temperature},
                timeout=90,
            )
            r.raise_for_status()
            data = r.json()
            # Cohere v2 returns message.content list
            parts = (data.get("message") or {}).get("content") or []
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if not text:
                text = str(data.get("text", "")).strip()
        except (requests.RequestException, KeyError, TypeError) as e:
            raise ProviderError(f"cohere: {e}") from e
        return AIResult(self.name, self.model, text, int((time.time()-start)*1000), self.cost_tier)

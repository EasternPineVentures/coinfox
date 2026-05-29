"""DeepInfra — free trial credits, OpenAI-compatible.

Get a free key: https://deepinfra.com
Set DEEPINFRA_API_KEY.
"""
from __future__ import annotations
import os, time
from typing import Optional
import requests
from ..base import AICall, AIResult, ProviderError

class DeepInfraProvider:
    name = "deepinfra"
    cost_tier = "freemium-with-key"
    requires_key_env = "DEEPINFRA_API_KEY"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_DEEPINFRA_MODEL", "meta-llama/Llama-3.3-70B-Instruct")

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        key = os.environ.get(self.requires_key_env)
        if not key:
            raise ProviderError("deepinfra: no DEEPINFRA_API_KEY")
        try:
            r = requests.post(
                "https://api.deepinfra.com/v1/openai/chat/completions",
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
            raise ProviderError(f"deepinfra: {e}") from e
        return AIResult(self.name, self.model, text, int((time.time()-start)*1000), self.cost_tier)

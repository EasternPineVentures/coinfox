"""Perplexity Sonar — free tier with live web search grounding.

This is powerful for BTC: the model can search the web as part of its
reasoning. Useful for news-heavy churn cycles.
Get a free key: https://www.perplexity.ai/settings/api
Set PERPLEXITY_API_KEY.
"""
from __future__ import annotations
import os, time
from typing import Optional
import requests
from ..base import AICall, AIResult, ProviderError

class PerplexityProvider:
    name = "perplexity"
    cost_tier = "freemium-with-key"
    requires_key_env = "PERPLEXITY_API_KEY"

    def __init__(self, model: Optional[str] = None):
        # sonar-pro is paid; sonar is the free search-grounded model
        self.model = model or os.environ.get("COINFOX_PERPLEXITY_MODEL", "sonar")

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        key = os.environ.get(self.requires_key_env)
        if not key:
            raise ProviderError("perplexity: no PERPLEXITY_API_KEY")
        try:
            r = requests.post(
                "https://api.perplexity.ai/chat/completions",
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
            raise ProviderError(f"perplexity: {e}") from e
        return AIResult(self.name, self.model, text, int((time.time()-start)*1000), self.cost_tier)

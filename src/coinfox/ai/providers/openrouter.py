"""OpenRouter — restricted to **free** models only.

Set OPENROUTER_API_KEY (https://openrouter.ai — free key, free models exist).
The default model is one of OpenRouter's `:free` tier models. FoxClaw refuses
to route through anything that doesn't end in `:free` here, as a safety net
against accidental spend.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

from ..base import AICall, AIResult, ProviderError


class OpenRouterFreeProvider:
    name = "openrouter-free"
    cost_tier = "freemium-with-key"
    requires_key_env = "OPENROUTER_API_KEY"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get(
            "COINFOX_OPENROUTER_MODEL",
            "meta-llama/llama-3.3-70b-instruct:free",
        )
        if not self.model.endswith(":free"):
            # Refuse to instantiate a non-free model
            raise ValueError(
                f"OpenRouterFreeProvider refuses non-free model {self.model!r}; "
                "must end in ':free'."
            )

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        key = os.environ.get(self.requires_key_env)
        if not key:
            raise ProviderError("openrouter: no OPENROUTER_API_KEY")
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/EasternPineVentures/coinfox",
                    "X-Title": "coinfox",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": call.system},
                        {"role": "user", "content": call.prompt},
                    ],
                    "max_tokens": call.max_tokens,
                    "temperature": call.temperature,
                },
                timeout=90,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError) as e:
            raise ProviderError(f"openrouter: {e}") from e
        return AIResult(self.name, self.model, text,
                        int((time.time() - start) * 1000), self.cost_tier)

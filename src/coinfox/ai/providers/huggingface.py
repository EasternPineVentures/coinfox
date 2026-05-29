"""HuggingFace Inference API. Free tier with token (HF_TOKEN).

Get a token at https://huggingface.co/settings/tokens (free).
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

from ..base import AICall, AIResult, ProviderError


class HuggingFaceProvider:
    name = "huggingface"
    cost_tier = "freemium-with-key"
    requires_key_env = "HF_TOKEN"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_HF_MODEL", "meta-llama/Llama-3.2-3B-Instruct")

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        token = os.environ.get(self.requires_key_env)
        if not token:
            raise ProviderError("hf: no HF_TOKEN")
        # Use the OpenAI-compatible router endpoint (works for most chat models)
        try:
            r = requests.post(
                "https://router.huggingface.co/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}",
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
                timeout=90,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError) as e:
            raise ProviderError(f"hf: {e}") from e
        return AIResult(self.name, self.model, text,
                        int((time.time() - start) * 1000), self.cost_tier)

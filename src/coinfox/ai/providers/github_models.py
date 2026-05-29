"""GitHub Models — free for GitHub users (no card, just your GITHUB_TOKEN).

Uses the Azure AI inference endpoint GitHub exposes for free.
Set GITHUB_TOKEN (your existing GH PAT with no special scopes needed).
"""
from __future__ import annotations
import os, time
from typing import Optional
import requests
from ..base import AICall, AIResult, ProviderError

class GitHubModelsProvider:
    name = "github-models"
    cost_tier = "freemium-with-key"
    requires_key_env = "GITHUB_TOKEN"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_GH_MODEL", "meta-llama-3.3-70b-instruct")

    def is_available(self) -> bool:
        return bool(os.environ.get(self.requires_key_env))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        token = os.environ.get(self.requires_key_env)
        if not token:
            raise ProviderError("github-models: no GITHUB_TOKEN")
        try:
            r = requests.post(
                "https://models.inference.ai.azure.com/chat/completions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [
                    {"role": "system", "content": call.system},
                    {"role": "user", "content": call.prompt},
                ], "max_tokens": call.max_tokens, "temperature": call.temperature},
                timeout=60,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError) as e:
            raise ProviderError(f"github-models: {e}") from e
        return AIResult(self.name, self.model, text, int((time.time()-start)*1000), self.cost_tier)

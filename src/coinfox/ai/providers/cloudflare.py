"""Cloudflare Workers AI — free daily quota, no card required.

Get account ID and token at https://dash.cloudflare.com
Set CF_ACCOUNT_ID and CF_API_TOKEN.
"""
from __future__ import annotations
import os, time
from typing import Optional
import requests
from ..base import AICall, AIResult, ProviderError

class CloudflareProvider:
    name = "cloudflare"
    cost_tier = "freemium-with-key"
    requires_key_env = "CF_API_TOKEN"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("COINFOX_CF_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")

    def is_available(self) -> bool:
        return bool(os.environ.get("CF_API_TOKEN") and os.environ.get("CF_ACCOUNT_ID"))

    def generate(self, call: AICall) -> AIResult:
        start = time.time()
        token = os.environ.get("CF_API_TOKEN")
        account = os.environ.get("CF_ACCOUNT_ID")
        if not token or not account:
            raise ProviderError("cloudflare: need CF_API_TOKEN and CF_ACCOUNT_ID")
        try:
            r = requests.post(
                f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{self.model}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"messages": [
                    {"role": "system", "content": call.system},
                    {"role": "user", "content": call.prompt},
                ], "max_tokens": call.max_tokens},
                timeout=90,
            )
            r.raise_for_status()
            data = r.json()
            text = (data.get("result") or {}).get("response", "").strip()
            if not text:
                raise ProviderError("cloudflare: empty result")
        except (requests.RequestException, KeyError) as e:
            raise ProviderError(f"cloudflare: {e}") from e
        return AIResult(self.name, self.model, text, int((time.time()-start)*1000), self.cost_tier)

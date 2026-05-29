"""FoxClaw — the router.

Tries providers in priority order: local first (Ollama, free forever),
then free-tier APIs. Skips anything not available. Refuses to ever route
through a "paid" cost_tier — that's a hard guardrail.

Tracks per-provider success/failure so flaky endpoints get demoted.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .base import AICall, AIResult, Provider, ProviderError
from .registry import DEFAULT_PROVIDER_ORDER, build_providers, provider_names


@dataclass
class AIResponse:
    text: str
    provider_used: str
    model_used: str
    cost_tier: str
    latency_ms: int
    tried: List[str] = field(default_factory=list)


class NoFreeProviderError(RuntimeError):
    pass


class FoxClaw:
    """Multi-provider free-AI router."""

    ALLOWED_TIERS = {"local", "free", "freemium-with-key"}

    def __init__(self, providers: Optional[List[Provider]] = None):
        if providers is None:
            env_order = os.environ.get("COINFOX_AI_PROVIDERS", "").strip()
            names = [n.strip() for n in env_order.split(",") if n.strip()] if env_order else DEFAULT_PROVIDER_ORDER
            providers = build_providers(names)
        # Hard refusal of paid tiers
        self.providers = [p for p in providers if p.cost_tier in self.ALLOWED_TIERS]
        self.health: Dict[str, Dict[str, int]] = {
            p.name: {"ok": 0, "fail": 0} for p in self.providers
        }

    def available(self) -> List[Provider]:
        return [p for p in self.providers if p.is_available()]

    def status(self) -> List[dict]:
        out = []
        for p in self.providers:
            out.append({
                "name": p.name,
                "tier": p.cost_tier,
                "key_env": getattr(p, "requires_key_env", None),
                "available": p.is_available(),
                "ok": self.health[p.name]["ok"],
                "fail": self.health[p.name]["fail"],
                "model": getattr(p, "model", ""),
            })
        return out

    def configured_provider_names(self) -> List[str]:
        return [p.name for p in self.providers]

    def ask(self, call: AICall) -> AIResponse:
        tried: List[str] = []
        last_err: Optional[str] = None
        # Sort by: available first, then by past success rate
        ordered = sorted(
            self.providers,
            key=lambda p: (
                not p.is_available(),
                -self.health[p.name]["ok"],
                self.health[p.name]["fail"],
            ),
        )
        for p in ordered:
            if not p.is_available():
                continue
            tried.append(p.name)
            try:
                res = p.generate(call)
                if not res.text:
                    raise ProviderError("empty response")
                self.health[p.name]["ok"] += 1
                return AIResponse(
                    text=res.text,
                    provider_used=res.provider,
                    model_used=res.model,
                    cost_tier=res.cost_tier,
                    latency_ms=res.latency_ms,
                    tried=tried,
                )
            except ProviderError as e:
                self.health[p.name]["fail"] += 1
                last_err = str(e)
                continue
        raise NoFreeProviderError(
            "No free AI provider could answer. "
            f"Tried: {tried}. Last error: {last_err}. "
            f"Configured providers: {self.configured_provider_names()}. "
            f"Available provider keys: {provider_names()}. "
            "Install Ollama (local+free) or set any of: "
            "CEREBRAS_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY, "
            "GITHUB_TOKEN, TOGETHER_API_KEY, OPENROUTER_API_KEY, CF_API_TOKEN, "
            "DEEPINFRA_API_KEY, PERPLEXITY_API_KEY, COHERE_API_KEY, CODEX_API_KEY, HF_TOKEN"
        )

    # convenience
    def quick(self, prompt: str, system: str = "You are FoxClaw, the analytical brain of coinfox. Be concise, factual, BTC-focused.",
              max_tokens: int = 400, temperature: float = 0.4) -> AIResponse:
        return self.ask(AICall(system=system, prompt=prompt,
                               max_tokens=max_tokens, temperature=temperature))

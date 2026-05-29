"""Provider interface. Every AI provider implements `Provider`.

Providers must self-report `cost_tier`. FoxClaw refuses to route through
anything other than "free" or "local". The whole point is **never pays**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class AICall:
    system: str
    prompt: str
    max_tokens: int = 400
    temperature: float = 0.4


@dataclass
class AIResult:
    provider: str
    model: str
    text: str
    latency_ms: int
    cost_tier: str          # "local" | "free" | "freemium-with-key" | "paid"


class Provider(Protocol):
    name: str
    cost_tier: str          # MUST be "local" or "free" or "freemium-with-key"
    requires_key_env: Optional[str]   # e.g. "GROQ_API_KEY"; None for keyless/local

    def is_available(self) -> bool: ...
    def generate(self, call: AICall) -> AIResult: ...


class ProviderError(RuntimeError):
    pass

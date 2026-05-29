"""Provider registry for pluggable AI routing.

This keeps provider discovery/config out of the router logic so contributors
can add new providers by registering one class in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Type

from .base import Provider
from .providers import (
    CerebrasProvider,
    CloudflareProvider,
    CodexProvider,
    CohereProvider,
    DeepInfraProvider,
    GeminiProvider,
    GitHubModelsProvider,
    GroqProvider,
    HuggingFaceProvider,
    MistralProvider,
    OllamaProvider,
    OpenRouterFreeProvider,
    PerplexityProvider,
    TogetherProvider,
)


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    cls: Type[Provider]


DEFAULT_PROVIDER_ORDER: List[str] = [
    "ollama",
    "cerebras",
    "groq",
    "gemini",
    "mistral",
    "github-models",
    "together",
    "openrouter-free",
    "cloudflare",
    "deepinfra",
    "perplexity",
    "cohere",
    "codex",
    "huggingface",
]


PROVIDER_REGISTRY: Dict[str, Type[Provider]] = {
    "ollama": OllamaProvider,
    "cerebras": CerebrasProvider,
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "mistral": MistralProvider,
    "github-models": GitHubModelsProvider,
    "together": TogetherProvider,
    "openrouter-free": OpenRouterFreeProvider,
    "cloudflare": CloudflareProvider,
    "deepinfra": DeepInfraProvider,
    "perplexity": PerplexityProvider,
    "cohere": CohereProvider,
    "codex": CodexProvider,
    "huggingface": HuggingFaceProvider,
}


def provider_names() -> List[str]:
    return sorted(PROVIDER_REGISTRY.keys())


def build_providers(names: Iterable[str]) -> List[Provider]:
    out: List[Provider] = []
    for raw in names:
        name = str(raw).strip().lower()
        if not name:
            continue
        cls = PROVIDER_REGISTRY.get(name)
        if cls is None:
            continue
        try:
            out.append(cls())
        except Exception:
            continue
    return out

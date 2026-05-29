"""FoxClaw — coinfox's free-AI claw.

**Not a chat interface.** This subsystem is purely for the system to churn
on its own: a background daemon periodically gathers fresh BTC intel, asks
FoxClaw to analyze it, and stores rolling thoughts that the dashboard and
the probability model consume.

Routing preference: **free local Ollama first**, then free-tier API providers
(HuggingFace, Groq, Google Gemini, OpenRouter free models). FoxClaw will
*never* fall through to a paid provider — that's a hard guardrail.
"""

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "model",
     "added": "2026-05",
     "contribution": "FoxClaw: free-AI router + autonomous churn daemon (Ollama-first, free-tier fallbacks)"},
]

from .router import FoxClaw, AIResponse, NoFreeProviderError  # noqa: F401,E402
from .churn import ChurnDaemon, Thought  # noqa: F401,E402

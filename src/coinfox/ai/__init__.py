"""FoxClaw - CoinFox's internal AI context router.

**Not a chat interface.** This subsystem runs a market pulse on its own:
a background daemon periodically gathers fresh market intel, asks FoxClaw to
analyze it, and stores rolling thoughts that the dashboard and the probability
model consume.

Routing preference: **free local Ollama first**, then free-tier API providers
(HuggingFace, Groq, Google Gemini, OpenRouter free models). FoxClaw will never
fall through to a paid provider. That is a hard guardrail.
"""

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "model",
     "added": "2026-05",
     "contribution": "FoxClaw: free-AI router + autonomous pulse daemon (Ollama-first, free-tier fallbacks)"},
]

from .router import FoxClaw, AIResponse, NoFreeProviderError  # noqa: F401,E402
from .churn import ChurnDaemon, Thought  # noqa: F401,E402
from .regime import RegimeConfig, RegimeDetector, run_regime_benchmark, tune_regime_thresholds  # noqa: F401,E402
from .replay import ReplayThought, evaluate_replay, run_replay_quality_gate  # noqa: F401,E402

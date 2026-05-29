from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FeedbackEvent:
    anonymous_user_id: str
    symbol: str
    bias_shown: str
    confidence_shown: float
    user_feedback: str
    user_invalidation_level: Optional[float] = None
    comment: str = ""
    timestamp: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, object]:
        return {
            "anonymous_user_id": self.anonymous_user_id,
            "symbol": self.symbol,
            "bias_shown": self.bias_shown,
            "confidence_shown": self.confidence_shown,
            "user_feedback": self.user_feedback,
            "user_invalidation_level": self.user_invalidation_level,
            "comment": self.comment,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class FeedbackReport:
    total_events: int
    symbol: Optional[str]
    feedback_counts: Dict[str, int]
    adjusted_invalidation_count: int
    median_user_invalidation_level: Optional[float]
    notes: List[str]

    def as_dict(self) -> Dict[str, object]:
        return {
            "total_events": self.total_events,
            "symbol": self.symbol,
            "feedback_counts": self.feedback_counts,
            "adjusted_invalidation_count": self.adjusted_invalidation_count,
            "median_user_invalidation_level": self.median_user_invalidation_level,
            "notes": self.notes,
        }

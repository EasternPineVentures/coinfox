from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Iterable, List, Optional

from .models import FeedbackEvent, FeedbackReport


SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anonymous_user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    bias_shown TEXT NOT NULL,
    confidence_shown REAL NOT NULL,
    user_feedback TEXT NOT NULL,
    user_invalidation_level REAL,
    comment TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_symbol_ts ON feedback(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_feedback_kind ON feedback(user_feedback);
"""


def default_feedback_db_path() -> Path:
    base = Path.home() / ".coinfox"
    base.mkdir(parents=True, exist_ok=True)
    return base / "feedback.sqlite"


class FeedbackStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else default_feedback_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def record(self, event: FeedbackEvent) -> int:
        clean = _clean_event(event)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "INSERT INTO feedback "
                "(anonymous_user_id, symbol, bias_shown, confidence_shown, user_feedback, "
                "user_invalidation_level, comment, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    clean.anonymous_user_id,
                    clean.symbol,
                    clean.bias_shown,
                    clean.confidence_shown,
                    clean.user_feedback,
                    clean.user_invalidation_level,
                    clean.comment,
                    clean.timestamp,
                ),
            )
            event_id = int(cur.lastrowid)
            cur.close()
            conn.commit()
        finally:
            conn.close()
        return event_id

    def list_events(self, symbol: Optional[str] = None, limit: int = 1000) -> List[FeedbackEvent]:
        sql = (
            "SELECT anonymous_user_id, symbol, bias_shown, confidence_shown, user_feedback, "
            "user_invalidation_level, comment, timestamp FROM feedback"
        )
        params: list[object] = []
        if symbol:
            sql += " WHERE symbol = ?"
            params.append(symbol.strip().upper())
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(max(1, int(limit)))
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            cur.close()
        finally:
            conn.close()
        return [
            FeedbackEvent(
                anonymous_user_id=str(row[0]),
                symbol=str(row[1]),
                bias_shown=str(row[2]),
                confidence_shown=float(row[3]),
                user_feedback=str(row[4]),
                user_invalidation_level=(None if row[5] is None else float(row[5])),
                comment=str(row[6] or ""),
                timestamp=str(row[7]),
            )
            for row in rows
        ]


def record_feedback(event: FeedbackEvent, db_path: Optional[Path] = None) -> int:
    return FeedbackStore(db_path).record(event)


def build_feedback_report(
    db_path: Optional[Path] = None,
    symbol: Optional[str] = None,
    limit: int = 1000,
) -> FeedbackReport:
    store = FeedbackStore(db_path)
    clean_symbol = symbol.strip().upper() if symbol else None
    events = store.list_events(symbol=clean_symbol, limit=limit)
    counts = Counter(event.user_feedback for event in events)
    levels = [
        float(event.user_invalidation_level)
        for event in events
        if event.user_invalidation_level is not None
    ]
    notes: list[str] = []
    if not events:
        notes.append("No feedback events recorded yet.")
    if levels:
        notes.append(
            "User-adjusted thesis-check levels are being collected for reporting only; "
            "they do not automatically change model behavior."
        )
    return FeedbackReport(
        total_events=len(events),
        symbol=clean_symbol,
        feedback_counts=dict(sorted(counts.items())),
        adjusted_invalidation_count=len(levels),
        median_user_invalidation_level=round(float(median(levels)), 4) if levels else None,
        notes=notes,
    )


def format_feedback_report(report: FeedbackReport) -> str:
    scope = report.symbol or "all symbols"
    lines = [
        f"Feedback report for {scope}",
        f"Total events: {report.total_events}",
    ]
    if report.feedback_counts:
        lines.append("Feedback counts:")
        for key, count in report.feedback_counts.items():
            lines.append(f"- {key}: {count}")
    lines.append(f"Adjusted thesis-check levels: {report.adjusted_invalidation_count}")
    if report.median_user_invalidation_level is not None:
        lines.append(f"Median user thesis-check level: {report.median_user_invalidation_level}")
    if report.notes:
        lines.append("Notes:")
        lines.extend(f"- {note}" for note in report.notes)
    return "\n".join(lines)


def _clean_event(event: FeedbackEvent) -> FeedbackEvent:
    symbol = (event.symbol or "").strip().upper()
    if not symbol:
        raise ValueError("symbol is required")
    feedback = (event.user_feedback or "").strip().lower()
    if not feedback:
        raise ValueError("user_feedback is required")
    bias = (event.bias_shown or "").strip().upper()
    if bias not in {"LONG", "SHORT", "NEUTRAL"}:
        raise ValueError("bias_shown must be LONG, SHORT, or NEUTRAL")
    anonymous_user_id = (event.anonymous_user_id or "").strip()
    if not anonymous_user_id:
        raise ValueError("anonymous_user_id is required")
    confidence = max(0.0, min(1.0, float(event.confidence_shown)))
    comment = (event.comment or "")[:1000]
    return FeedbackEvent(
        anonymous_user_id=anonymous_user_id,
        symbol=symbol,
        bias_shown=bias,
        confidence_shown=confidence,
        user_feedback=feedback,
        user_invalidation_level=event.user_invalidation_level,
        comment=comment,
        timestamp=event.timestamp,
    )

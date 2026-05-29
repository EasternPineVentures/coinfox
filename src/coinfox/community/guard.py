"""Explainable abuse guard for issues and pull requests."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from coinfox.utils.json_utils import safe_json_dumps


LEVEL_SCORE = {"info": 0, "low": 5, "medium": 20, "high": 50}
BLOCKING_LEVELS = {"high"}
FIRST_TIMER_ASSOCIATIONS = {"FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(r"\b(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN)\b", re.I),
    re.compile(r"\b(ghp|github_pat|xoxb|sk)-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\b(api[_-]?key|secret|password|private[_-]?key)\s*[:=]\s*[A-Za-z0-9_\-]{12,}\b", re.I),
]

ABUSE_PATTERNS = [
    ("prompt injection", re.compile(r"\b(ignore previous|reveal.*secret|exfiltrate|system prompt)\b", re.I)),
    ("destructive command", re.compile(r"\b(rm\s+-rf|del\s+/s|format\s+[a-z]:|powershell\s+-enc|curl\s+[^|]+[|]\s*(sh|bash))\b", re.I)),
    ("credential request", re.compile(r"\b(send me|post|share).{0,40}\b(token|password|private key|seed phrase)\b", re.I)),
]

SENSITIVE_PATHS = [
    ".github/workflows/",
    "pyproject.toml",
    "requirements.txt",
    "src/coinfox/model.py",
    "src/coinfox/bias.py",
    "src/coinfox/ai/",
]


@dataclass(frozen=True)
class Finding:
    level: str
    title: str
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return {"level": self.level, "title": self.title, "detail": self.detail}


@dataclass(frozen=True)
class GuardReport:
    risk: str
    score: int
    should_block: bool
    findings: List[Finding]

    def as_dict(self) -> Dict[str, object]:
        return {
            "risk": self.risk,
            "score": self.score,
            "should_block": self.should_block,
            "findings": [finding.as_dict() for finding in self.findings],
        }


def assess_request(
    title: str,
    body: str = "",
    author_association: str = "",
    changed_files: Optional[Iterable[str]] = None,
) -> GuardReport:
    text = f"{title}\n{body or ''}"
    files = list(changed_files or [])
    findings: List[Finding] = []

    if not title.strip():
        findings.append(Finding("medium", "missing title", "Community requests need a clear title."))

    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(Finding("high", "possible secret leak", "The request appears to contain a token, key, or credential."))
            break

    for name, pattern in ABUSE_PATTERNS:
        if pattern.search(text):
            findings.append(Finding("high", name, "The request contains wording commonly used for abuse or unsafe automation."))

    urls = re.findall(r"https?://", text)
    if len(urls) > 8:
        findings.append(Finding("medium", "link flood", f"Found {len(urls)} links in one request."))

    if _looks_repetitive(text):
        findings.append(Finding("medium", "repetitive content", "The request repeats the same text unusually often."))

    if author_association.upper() in FIRST_TIMER_ASSOCIATIONS:
        findings.append(Finding("low", "new contributor", "First-time contributors should get normal review plus rate-limit awareness."))

    sensitive = [path for path in files if _is_sensitive_path(path)]
    if sensitive:
        findings.append(
            Finding(
                "medium",
                "sensitive files",
                "Changes touch maintainer-reviewed surfaces: " + ", ".join(sensitive[:5]),
            )
        )

    if len(files) > 50:
        findings.append(Finding("medium", "large change set", f"Request touches {len(files)} files."))

    score = sum(LEVEL_SCORE[finding.level] for finding in findings)
    risk = _risk_for_score(score, findings)
    return GuardReport(
        risk=risk,
        score=score,
        should_block=risk in BLOCKING_LEVELS,
        findings=findings,
    )


def report_from_github_event(path: Path) -> GuardReport:
    event = json.loads(Path(path).read_text(encoding="utf-8"))
    issue = event.get("issue") or event.get("pull_request") or {}
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    author_association = str(issue.get("author_association") or "")
    changed_files = _changed_files_from_event(event)
    return assess_request(title, body, author_association=author_association, changed_files=changed_files)


def format_markdown(report: GuardReport) -> str:
    lines = [
        "## coinfox community guard",
        "",
        f"- Risk: **{report.risk}**",
        f"- Score: `{report.score}`",
        f"- Block: `{'yes' if report.should_block else 'no'}`",
    ]
    if not report.findings:
        lines.append("- Findings: none")
        return "\n".join(lines)
    lines.append("")
    lines.append("Findings:")
    for finding in report.findings:
        lines.append(f"- **{finding.level}**: {finding.title} - {finding.detail}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Assess community request abuse risk.")
    parser.add_argument("--event", type=Path, help="GitHub event JSON path")
    parser.add_argument("--title", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--author-association", default="")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on", choices=["never", "medium", "high"], default="high")
    args = parser.parse_args(argv)

    if args.event:
        report = report_from_github_event(args.event)
    else:
        report = assess_request(
            args.title,
            args.body,
            author_association=args.author_association,
            changed_files=args.changed_file,
        )

    print(safe_json_dumps(report.as_dict(), indent=2, sort_keys=True) if args.json else format_markdown(report))

    if args.fail_on == "never":
        return 0
    if args.fail_on == "medium" and report.risk in {"medium", "high"}:
        return 1
    if args.fail_on == "high" and report.risk == "high":
        return 1
    return 0


def _changed_files_from_event(event: Dict[str, object]) -> List[str]:
    commits = event.get("commits")
    files: List[str] = []
    if isinstance(commits, list):
        for commit in commits:
            if not isinstance(commit, dict):
                continue
            for key in ("added", "modified", "removed"):
                values = commit.get(key)
                if isinstance(values, list):
                    files.extend(str(value) for value in values)
    return files


def _is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(normalized == item or normalized.startswith(item) for item in SENSITIVE_PATHS)


def _looks_repetitive(text: str) -> bool:
    words = re.findall(r"[A-Za-z0-9_]{3,}", text.lower())
    if len(words) < 30:
        return False
    most_common = max(words.count(word) for word in set(words))
    return most_common / len(words) >= 0.25


def _risk_for_score(score: int, findings: Iterable[Finding]) -> str:
    if any(finding.level == "high" for finding in findings):
        return "high"
    if score >= 20:
        return "medium"
    if score > 0:
        return "low"
    return "clear"


if __name__ == "__main__":
    sys.exit(main())

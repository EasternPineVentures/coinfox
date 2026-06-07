"""Shared HTTP helpers for source fetchers."""

from __future__ import annotations

from typing import Any, Optional

import requests

USER_AGENT = "coinfox/0.2 (research; +https://github.com/)"
DEFAULT_TIMEOUT = 8


def get_json(url: str, params: Optional[dict] = None, timeout: int = DEFAULT_TIMEOUT,
             headers: Optional[dict] = None) -> Optional[Any]:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, params=params, timeout=timeout, headers=h)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def get_text(url: str, params: Optional[dict] = None, timeout: int = DEFAULT_TIMEOUT,
             headers: Optional[dict] = None) -> Optional[str]:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, params=params, timeout=timeout, headers=h)
        r.raise_for_status()
        return r.text
    except requests.RequestException:
        return None


def post_json(url: str, payload: Any, timeout: int = DEFAULT_TIMEOUT,
              headers: Optional[dict] = None) -> Optional[Any]:
    """POST a JSON body and return parsed JSON, or None on any failure.

    Used for JSON-RPC style endpoints (e.g. an Ethereum node `eth_call`).
    """
    h = {"User-Agent": USER_AGENT, "Accept": "application/json",
         "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    try:
        r = requests.post(url, json=payload, timeout=timeout, headers=h)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None

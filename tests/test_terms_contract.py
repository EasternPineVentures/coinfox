"""Glossary coverage contract tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


REQUIRED_TERMS = [
    "LONG",
    "SHORT",
    "NEUTRAL",
    "Bias",
    "Thesis check",
    "Invalidation",
    "Source health",
    "Driver",
    "Confidence",
    "Replay gate",
    "Regime",
    "Paper trade",
]


class TestTermsContract(unittest.TestCase):
    def test_required_terms_have_beginner_friendly_definitions(self):
        path = Path(__file__).resolve().parents[1] / "src" / "coinfox" / "assets" / "terms.json"
        terms = json.loads(path.read_text(encoding="utf-8"))

        for term in REQUIRED_TERMS:
            with self.subTest(term=term):
                self.assertIn(term, terms)
                definition = terms[term]
                self.assertIsInstance(definition, str)
                self.assertGreater(len(definition.strip()), 10)
                self.assertNotIn("TODO", definition.upper())
                self.assertNotIn("PLACEHOLDER", definition.upper())


if __name__ == "__main__":
    unittest.main()

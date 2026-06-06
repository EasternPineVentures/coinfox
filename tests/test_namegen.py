"""Username generator + suggestion endpoint tests."""

from __future__ import annotations

import random
import unittest

from coinfox.community import namegen

try:
    from fastapi.testclient import TestClient

    from coinfox.api import app
except Exception:  # pragma: no cover - optional API extras may be absent
    TestClient = None
    app = None


class TestNameGen(unittest.TestCase):
    def test_suggest_is_handle_safe(self):
        rng = random.Random(7)
        for _ in range(200):
            name = namegen.suggest(rng)
            self.assertTrue(name)
            self.assertNotIn(" ", name)
            self.assertTrue(name.isalnum(), name)
            self.assertLessEqual(len(name), 40)

    def test_batch_is_distinct_and_bounded(self):
        rng = random.Random(11)
        names = namegen.suggest_batch(8, rng)
        self.assertEqual(len(names), len(set(names)))
        self.assertLessEqual(len(names), 8)
        self.assertGreaterEqual(len(names), 1)

    def test_batch_clamps_count(self):
        self.assertLessEqual(len(namegen.suggest_batch(999)), 20)
        self.assertEqual(len(namegen.suggest_batch(0)), 1)


@unittest.skipIf(TestClient is None or app is None, "FastAPI extras not installed")
class TestSuggestEndpoint(unittest.TestCase):
    def test_suggest_endpoint_returns_names(self):
        client = TestClient(app)
        res = client.get("/api/username/suggest?count=5")
        self.assertEqual(res.status_code, 200)
        suggestions = res.json()["suggestions"]
        self.assertTrue(1 <= len(suggestions) <= 5)
        self.assertTrue(all(isinstance(name, str) and name for name in suggestions))

    def test_suggest_endpoint_rejects_out_of_range(self):
        client = TestClient(app)
        self.assertEqual(client.get("/api/username/suggest?count=0").status_code, 422)
        self.assertEqual(client.get("/api/username/suggest?count=99").status_code, 422)


if __name__ == "__main__":
    unittest.main()

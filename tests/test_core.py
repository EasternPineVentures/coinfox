"""Unit tests for indicators and trade-idea generator (pure, no network)."""

import math
import unittest

from coinfox.data import Candle, FearGreed
from coinfox.indicators import bollinger, ema, macd, rsi, slope, volume_zscore
from coinfox.model import evaluate
from coinfox.trade import make_idea


def _synthetic_uptrend(n=120, start=20000.0, step=50.0):
    candles = []
    p = start
    for i in range(n):
        o = p
        c = p + step
        h = c + 10
        l = o - 5
        candles.append(Candle(i, o, h, l, c, 100.0, i + 1))
        p = c
    return candles


class TestIndicators(unittest.TestCase):
    def test_ema_constant(self):
        out = ema([10.0] * 50, 14)
        self.assertAlmostEqual(out[-1], 10.0, places=6)

    def test_rsi_uptrend_high(self):
        out = rsi(list(range(1, 100)), 14)
        self.assertGreater(out[-1], 70.0)

    def test_rsi_bounds(self):
        out = rsi([100 + (i % 5) for i in range(100)], 14)
        for v in out:
            if not math.isnan(v):
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 100.0)

    def test_macd_shapes(self):
        m = macd([100 + i * 0.1 for i in range(100)])
        self.assertEqual(len(m.hist), 100)

    def test_bollinger_pctb(self):
        bb = bollinger([100.0 + (i % 3) for i in range(50)], 20, 2.0)
        for v in bb.pct_b[20:]:
            self.assertFalse(math.isnan(v))

    def test_volume_zscore_constant(self):
        self.assertEqual(volume_zscore([5.0] * 30, 20)[-1], 0.0)

    def test_slope_positive(self):
        self.assertGreater(slope(list(range(1, 50)), 5), 0)


class TestModelAndTrade(unittest.TestCase):
    def test_uptrend_yields_long_bias(self):
        candles = _synthetic_uptrend()
        fng = FearGreed(50, "Neutral", 0)
        v = evaluate(candles, fng, horizon=4)
        # On a strong synthetic uptrend, we should never lean short.
        # (A perfect ramp pushes RSI to 100 and BB above upper, which
        # legitimately counter-balance trend signals — landing on
        # "long" or "neutral" is acceptable.)
        self.assertIn(v.bias, ("long", "neutral"))
        self.assertGreater(v.probability_up, 0.5)

    def test_trade_idea_long_setup(self):
        candles = _synthetic_uptrend()
        fng = FearGreed(50, "Neutral", 0)
        v = evaluate(candles, fng, horizon=4)
        idea = make_idea(v, candles, "1h")
        # On strong synthetic uptrend, we should get a LONG idea or at worst STAND ASIDE,
        # but never SHORT.
        self.assertIn(idea.action, ("LONG", "STAND ASIDE"))
        self.assertGreater(idea.entry, 0)
        self.assertGreaterEqual(idea.suggested_size_pct, 0.0)
        self.assertLessEqual(idea.suggested_size_pct, 2.0)  # cap

    def test_trade_idea_caps_size(self):
        candles = _synthetic_uptrend()
        fng = FearGreed(50, "Neutral", 0)
        v = evaluate(candles, fng, horizon=4)
        idea = make_idea(v, candles, "1h", kelly_cap_pct=0.5)
        self.assertLessEqual(idea.suggested_size_pct, 0.5)


if __name__ == "__main__":
    unittest.main()

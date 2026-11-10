"""Keep prices factual, missing markets neutral and model inputs consistent."""
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from nuke_pga_data import attach_market, expected_points, load_market_snapshot
from test_pga_portfolio import page_functions

ROOT = Path(__file__).resolve().parents[1]


class PGAMarketTests(unittest.TestCase):
    def test_aliases_and_snapshot_coverage(self):
        h = page_functions()
        raw = pd.read_csv(ROOT / "data/pga_current.csv")
        if not raw["Game Info"].str.contains("Austin Championship").all():
            self.skipTest("Default slate has moved on")
        d = h["load_csv"](ROOT / "data/pga_current.csv")
        enriched = attach_market(d, load_market_snapshot(d["Game Info"].iloc[0]))
        self.assertEqual(len(enriched), 120)
        self.assertEqual(enriched["Win Odds"].notna().sum(), 114)
        by_name = enriched.set_index("Name")
        for name, price in [("Jordan L. Smith", 30), ("Zachary Bauchou", 40),
                            ("Kris Ventura", 50), ("Thomas Morrison", 60)]:
            self.assertEqual(by_name.loc[name, "Win Odds"], price)
        self.assertAlmostEqual(by_name.loc["Jackson Koivun", "Implied Win %"], 100/15)
        self.assertEqual(set(enriched.loc[enriched["Win Odds"].isna(), "Name"]),
                         {"William Sides", "Thomas Rosenmueller", "Frankie Harris",
                          "Nick Hardy", "Tyler Duncan", "Ben Martin"})
        self.assertTrue(enriched.loc[enriched["Win Odds"].isna(), "Market Adjustment"].eq(0).all())
        self.assertTrue(enriched["Market Adjustment"].between(-4, 4).all())

    def test_better_market_price_increases_model_strength_at_equal_salary(self):
        d = pd.DataFrame({"Name": ["A", "B", "Missing"], "Salary": [8000]*3})
        snapshot = {"players": [{"name": "A", "american_odds": 2000},
                                  {"name": "B", "american_odds": 20000}]}
        result = attach_market(d, snapshot)
        h = page_functions()
        self.assertGreater(h["salary_baseline"](result)[0], h["salary_baseline"](result)[1])
        self.assertTrue(np.isfinite(h["ownership_estimate"](result)).all())
        self.assertAlmostEqual(h["ownership_estimate"](result).sum(), 600)

    def test_expected_points_include_cut_and_weather(self):
        pool = pd.DataFrame({"Weather Edge": [2., -2.]})
        np.testing.assert_allclose(expected_points(pool, [70., 70.], [1., 0.]), [72., 68*.43])

    def test_other_events_keep_baseline_and_do_not_reuse_austin_odds(self):
        self.assertEqual(load_market_snapshot("World Wide Technology Championship"), {})
        h = page_functions()
        d = pd.DataFrame({"Name": ["A", "B"], "Salary": [7000, 9000]})
        np.testing.assert_array_equal(h["salary_baseline"](attach_market(d, {})),
                                      h["salary_baseline"](d))


if __name__ == "__main__":
    unittest.main()

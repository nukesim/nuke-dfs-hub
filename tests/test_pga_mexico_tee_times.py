"""Regression coverage for the official 2026 Mexico Open DK field and tee waves."""
import ast
import re
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "15_PGA_SIM.py"


def helpers():
    tree = ast.parse(PAGE.read_text(encoding="utf-8"))
    wanted = {"_norm_name", "load_csv", "_mexico_2026_context",
              "attach_tee_weather", "weather_severity", "weather_dot"}
    funcs = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name in wanted]
    names = {node.name for node in funcs}
    assert names == wanted, f"Missing page functions: {wanted - names}"
    env = {"__file__": str(PAGE), "np": np, "pd": pd, "re": re}
    exec(compile(ast.Module(body=funcs, type_ignores=[]),
                 str(PAGE), "exec"), env)
    return env


class MexicoTeeTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = helpers()
        cls.ctx = cls.h["_mexico_2026_context"]()
        cls.dk = cls.h["load_csv"](ROOT / "data" / "pga_current.csv")

    def test_all_active_dk_golfers_have_both_published_rounds(self):
        self.assertEqual(len(self.dk), 119)
        norm = self.h["_norm_name"]
        missing = [name for name in self.dk["Name"]
                   if set(self.ctx["tee_times"].get(norm(name), {})) != {1, 2}]
        self.assertEqual(missing, [])

    def test_local_tee_times_and_draftkings_aliases(self):
        t = self.ctx["tee_times"]
        norm = self.h["_norm_name"]
        clark = t[norm("Wyndham Clark")]
        self.assertEqual(pd.Timestamp(clark[1]).strftime("%Y-%m-%d %H:%M"),
                         "2026-10-29 12:18")
        self.assertEqual(pd.Timestamp(clark[2]).strftime("%Y-%m-%d %H:%M"),
                         "2026-10-30 07:38")
        self.assertEqual(pd.Timestamp(t[norm("Benjamin James")][1]).strftime("%H:%M"), "08:44")
        self.assertEqual(pd.Timestamp(t[norm("Kris Ventura")][1]).strftime("%H:%M"), "13:24")

    def test_both_waves_and_weather_are_assigned(self):
        hours = pd.date_range("2026-10-29", periods=48, freq="h")
        wx = pd.DataFrame({"time": hours,
                           "temperature_2m": np.full(48, 82.0),
                           "wind_speed_10m": np.where(hours.hour < 10, 4.0, 12.0),
                           "wind_gusts_10m": np.full(48, 16.0),
                           "precipitation_probability": np.full(48, 10.0),
                           "precipitation": np.zeros(48)})
        enriched = self.h["attach_tee_weather"](self.dk, self.ctx, wx)
        self.assertEqual(enriched["Wave"].value_counts().to_dict(),
                         {"AM": 60, "PM": 59})
        self.assertTrue(enriched["R1 Tee"].ne("—").all())
        self.assertTrue(enriched["R2 Tee"].ne("—").all())
        self.assertTrue(enriched["Weather"].ne("⚪ TBD").all())
        self.assertTrue(np.isfinite(enriched["Weather Edge"]).all())


if __name__ == "__main__":
    unittest.main()

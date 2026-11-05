"""Keep WWT tee waves, withdrawals, local weather and slate routing aligned."""
import ast
from datetime import datetime
from pathlib import Path
import re
import unittest
from unittest.mock import Mock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "15_PGA_SIM.py"


def helpers():
    wanted = {"_norm_name", "load_csv", "_wwt_2026_context", "fetch_pga_context",
              "attach_tee_weather", "weather_severity", "weather_dot"}
    tree = ast.parse(PAGE.read_text())
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in funcs} == wanted
    for node in funcs:
        node.decorator_list = []
    env = {"__file__": str(PAGE), "Path": Path, "pd": pd, "np": np,
           "re": re, "datetime": datetime, "requests": Mock()}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(PAGE), "exec"), env)
    return env


class WWTTeeTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = helpers()
        cls.ctx = cls.h["_wwt_2026_context"]()

    def test_official_rounds_and_local_timezone(self):
        groups = pd.read_csv(ROOT / "data/pga_wwt_2026_pairings.psv", sep="|")
        names = [p for row in groups["Players"] for p in row.split(";")]
        self.assertEqual(len(groups), 40)
        self.assertEqual(len(set(names)), 120)
        self.assertTrue(self.ctx["has_cut"])
        self.assertEqual(self.ctx["round_dates"],
                         ["2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"])
        for record in self.ctx["tee_times"].values():
            for rnd, day in [(1, "2026-11-05"), (2, "2026-11-06")]:
                stamp = pd.Timestamp(record[rnd])
                self.assertEqual(str(stamp.date()), day)
                self.assertEqual(stamp.utcoffset().total_seconds(), -7 * 3600)

    def test_published_slots_and_aliases(self):
        norm = self.h["_norm_name"]
        tee = self.ctx["tee_times"]
        for name, r1, r2 in [("Peter Malnati", "06:30", "11:05"),
                             ("Jackson Koivun", "11:38", "07:03"),
                             ("Benjamin James", "11:49", "07:14"),
                             ("Jordan L. Smith", "11:27", "06:52"),
                             ("Harry Higgs", "11:16", "06:41"),
                             ("Jay Leng", "12:44", "08:09")]:
            self.assertEqual(pd.Timestamp(tee[norm(name)][1]).strftime("%H:%M"), r1)
            self.assertEqual(pd.Timestamp(tee[norm(name)][2]).strftime("%H:%M"), r2)

    def test_event_routing_does_not_discover_unrelated_espn_event(self):
        self.h["datetime"] = Mock()
        self.h["datetime"].now.return_value = datetime(2026, 11, 4)
        ctx = self.h["fetch_pga_context"]("World Wide Technology Championship")
        self.assertEqual(ctx["event_id"], "2026457")
        self.assertEqual(ctx["course"], "El Cardonal at Diamante")
        self.h["requests"].get.assert_not_called()

    def test_current_dk_pool_waves_and_weather(self):
        raw = pd.read_csv(ROOT / "data/pga_current.csv")
        if not raw["Game Info"].eq("World Wide Technology Championship").all():
            self.skipTest("Default slate has moved on from 2026 WWT")
        dk = self.h["load_csv"](ROOT / "data/pga_current.csv")
        self.assertEqual(len(raw), 122)
        self.assertEqual(len(dk), 120)
        self.assertEqual(dk["ID"].nunique(), 120)
        self.assertEqual(set(raw.loc[raw["Status"] == "OUT", "Name"]),
                         {"Adam Schenk", "Aldrich Potgieter"})
        self.assertTrue({"Will Gordon", "Harry Higgs"}.issubset(set(dk["Name"])))
        hours = pd.date_range("2026-11-05", periods=48, freq="h")
        weather = pd.DataFrame({"time": hours, "temperature_2m": 80.0,
                                "wind_speed_10m": np.where(hours.hour < 11, 7.0, 15.0),
                                "wind_gusts_10m": 20.0, "precipitation_probability": 10.0,
                                "precipitation": 0.0})
        pool = self.h["attach_tee_weather"](dk, self.ctx, weather)
        self.assertEqual(pool["Wave"].value_counts().to_dict(), {"AM": 60, "PM": 60})
        self.assertTrue(pool[["R1 Tee", "R2 Tee"]].ne("—").all().all())
        self.assertTrue(pool["Weather"].ne("⚪ TBD").all())
        self.assertTrue(np.isfinite(pool["Weather Edge"]).all())
        self.assertAlmostEqual(pool["Weather Edge"].mean(), 0.0)
        self.assertEqual(pool.set_index("Name").loc["Jackson Koivun", "Wave"], "PM")
        neutral = self.h["attach_tee_weather"](dk, self.ctx, pd.DataFrame())
        self.assertTrue(neutral["Weather Edge"].eq(0).all())


if __name__ == "__main__":
    unittest.main()

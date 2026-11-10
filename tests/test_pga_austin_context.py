"""Austin must retain its course and reject unrelated or stale tee sheets."""
import ast
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import re
import unittest
from unittest.mock import Mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def helpers():
    page = ROOT / "pages/15_PGA_SIM.py"
    names = {"_norm_name", "fetch_pga_context", "load_csv"}
    nodes = [n for n in ast.parse(page.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    clock = Mock()
    clock.now.return_value = datetime(2026, 11, 10)
    env = {"pd": pd, "re": re, "datetime": clock,
           "SequenceMatcher": SequenceMatcher, "requests": Mock()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(page), "exec"), env)
    return env


class AustinContextTests(unittest.TestCase):
    def test_unrelated_scoreboard_keeps_austin_metadata_and_no_tee_times(self):
        env = helpers()
        env["requests"].get.return_value.json.return_value = {
            "events": [{"id": "wwt", "name": "World Wide Technology Championship",
                        "date": "2026-11-05"}]}
        ctx = env["fetch_pga_context"]("Austin Championship presented by Compliance Solutions")
        self.assertIsNone(ctx["event_id"])
        self.assertEqual(ctx["timezone"], "America/Chicago")
        self.assertIn("Fazio Canyons", ctx["course"])
        self.assertEqual(ctx["round_dates"], ["2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"])
        self.assertTrue(ctx["has_cut"])
        self.assertEqual(ctx["tee_times"], {})
        self.assertEqual(env["requests"].get.call_count, 1)

    def test_only_current_event_round_dates_are_accepted(self):
        env = helpers()
        payload = {"players": [
            {"displayName": "Doug Ghim", "teeTime": "2026-11-12T13:00:00Z", "round": 1},
            {"displayName": "Doug Ghim", "teeTime": "2026-11-13T17:40:00Z", "round": 2},
            {"displayName": "Stale Golfer", "teeTime": "2026-11-05T13:00:00Z", "round": 1},
            {"displayName": "Wrong Round", "teeTime": "2026-11-13T13:00:00Z", "round": 1},
            {"displayName": "No Timezone", "teeTime": "2026-11-12T07:00:00", "round": 1}]}
        env["requests"].get.return_value.json.side_effect = [
            {"events": [{"id": "austin", "name": "Austin Championship",
                          "date": "2026-11-12T12:00:00Z"}]},
            {"venue": {"name": "Wrong venue", "geo": {"latitude": 0, "longitude": 0}}},
            payload, {}]
        ctx = env["fetch_pga_context"]("Austin Championship")
        self.assertEqual(ctx["event_id"], "austin")
        self.assertIn("Fazio Canyons", ctx["course"])
        self.assertEqual(set(ctx["tee_times"]), {"dougghim"})
        self.assertEqual(set(ctx["tee_times"]["dougghim"]), {1, 2})

    def test_default_salary_pool_excludes_out_players(self):
        raw = pd.read_csv(ROOT / "data/pga_current.csv")
        if not raw["Game Info"].str.contains("Austin Championship").all():
            self.skipTest("Default slate has moved on from Austin")
        pool = helpers()["load_csv"](ROOT / "data/pga_current.csv")
        self.assertEqual(len(raw), 124)
        self.assertEqual(len(pool), 120)
        self.assertEqual(pool["ID"].nunique(), 120)
        self.assertEqual(set(raw.loc[raw["Status"] == "OUT", "Name"]),
                         {"Benjamin James", "Michael Kim", "Beau Hossler", "Tom Hoge"})
        self.assertTrue({"David Skinns", "Jimmy Stanger", "Paul Peterson", "Ben Martin", "Tyler Duncan"}
                        .issubset(set(pool["Name"])))


if __name__ == "__main__":
    unittest.main()

"""Austin must retain its course and reject unrelated or stale tee sheets."""
import ast
import json
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import re
import unittest
from unittest.mock import Mock

import numpy as np
import pandas as pd
from nuke_pga_data import parse_austin_pairings

ROOT = Path(__file__).resolve().parents[1]


def helpers():
    page = ROOT / "pages/15_PGA_SIM.py"
    names = {"_norm_name", "fetch_pga_context", "load_csv", "_austin_2026_context",
             "attach_tee_weather", "weather_severity", "weather_dot"}
    nodes = [n for n in ast.parse(page.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    clock = Mock()
    clock.now.return_value = datetime(2026, 11, 10)
    env = {"pd": pd, "np": np, "re": re, "datetime": clock,"Path":Path,"__file__":str(page),
           "parse_austin_pairings":parse_austin_pairings,
           "SequenceMatcher": SequenceMatcher, "requests": Mock()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(page), "exec"), env)
    return env


class AustinContextTests(unittest.TestCase):
    def test_official_pairings_load_when_live_provider_is_unavailable(self):
        env = helpers()
        env["requests"].get.side_effect = OSError("Offline")
        ctx = env["fetch_pga_context"]("Austin Championship presented by Compliance Solutions")
        self.assertEqual(ctx["event_id"], "2026558")
        self.assertEqual(ctx["timezone"], "America/Chicago")
        self.assertIn("Fazio Canyons", ctx["course"])
        self.assertEqual(ctx["round_dates"], ["2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"])
        self.assertTrue(ctx["has_cut"])
        self.assertGreaterEqual(len(ctx["tee_times"]),120)
        self.assertEqual(env["requests"].get.call_count, 1)

    def test_published_slots_and_draftkings_aliases(self):
        env = helpers()
        ctx=env["_austin_2026_context"]()
        for name,r1,r2 in [("Jackson Koivun","12:13","07:33"),("Doug Ghim","07:44","12:24"),
                           ("Thomas Morrison","12:13","07:33"),("Jordan L. Smith","12:35","07:55"),
                           ("Kris Ventura","12:46","08:06"),("Matthew McCarty","12:13","07:33"),
                           ("Cameron Davis","07:55","12:35"),("Nick Hardy","07:00","11:40")]:
            record=ctx["tee_times"][env["_norm_name"](name)]
            self.assertEqual(pd.Timestamp(record[1]).strftime("%H:%M"),r1)
            self.assertEqual(pd.Timestamp(record[2]).strftime("%H:%M"),r2)
            self.assertEqual(pd.Timestamp(record[1]).utcoffset().total_seconds(),-21600)

    def test_full_pool_has_both_rounds_and_balanced_waves(self):
        env=helpers();ctx=env["_austin_2026_context"]()
        pool=env["load_csv"](ROOT/"data/pga_current.csv")
        if not pool["Game Info"].str.contains("Austin Championship").all():
            self.skipTest("Default slate has moved on")
        enriched=env["attach_tee_weather"](pool,ctx,pd.DataFrame())
        self.assertTrue(enriched[["R1 Tee","R2 Tee"]].ne("—").all().all())
        self.assertEqual(enriched["Wave"].value_counts().to_dict(),{"AM":60,"PM":60})
        self.assertEqual(enriched.set_index("Name").loc["David Lipsky","Wave"],"PM")
        self.assertEqual(enriched.set_index("Name").loc["David Lipsky","R1 Tee"],"11:40 AM")
        self.assertTrue(enriched["Weather Edge"].eq(0).all())

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

    def test_live_pairings_validate_event_and_round_dates(self):
        payload={"pga":{"event_id":558,"event_name":"Austin Championship",
                         "data":[{"player_name":"Smith, Jordan","teetimes":{
                             "1":{"date":"2026-11-12","time":"12:35 PM"},
                             "2":{"date":"2026-11-13","time":"7:55 AM"}}}]}}
        def html():
            return "var data = JSON.parse('"+json.dumps(payload)+"');"
        parsed=parse_austin_pairings(html())
        self.assertEqual(pd.Timestamp(parsed["jordansmith"][1]).hour,12)
        self.assertEqual(pd.Timestamp(parsed["jordansmith"][2]).hour,7)
        payload["pga"]["data"][0]["teetimes"]["1"]["date"]="2026-11-05"
        self.assertEqual(parse_austin_pairings(html()),{})
        payload["pga"]["event_id"]=457
        self.assertEqual(parse_austin_pairings(html()),{})

    def test_live_refresh_updates_dk_aliases_without_losing_official_fallback(self):
        payload={"pga":{"event_id":558,"event_name":"Austin Championship",
                         "data":[{"player_name":"Smith, Jordan","teetimes":{
                             "1":{"date":"2026-11-12","time":"12:46 PM"},
                             "2":{"date":"2026-11-13","time":"8:06 AM"}}}]}}
        env=helpers()
        env["requests"].get.return_value.text="var data = JSON.parse('"+json.dumps(payload)+"');"
        ctx=env["fetch_pga_context"]("Austin Championship")
        self.assertEqual(pd.Timestamp(ctx["tee_times"]["jordanlsmith"][1]).strftime("%H:%M"),"12:46")
        self.assertEqual(pd.Timestamp(ctx["tee_times"]["dougghim"][1]).strftime("%H:%M"),"07:44")


if __name__ == "__main__":
    unittest.main()

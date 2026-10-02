import unittest
from types import SimpleNamespace
from unittest.mock import patch
from check_mma_live import scope


class FighterStatsTests(unittest.TestCase):
    def test_moneylines_bind_to_names_when_page_reverses_order(self):
        text = "Sportsbook Deiveson Figueiredo Payton Talbott Trend BetMGM +525 -750 DraftKings +525 -750 FanDuel +490 -750"
        result = scope["_parse_fight_market"](text, "Payton Talbott", "Deiveson Figueiredo")
        self.assertEqual(result["paytontalbott"]["Moneyline"], -750)
        self.assertEqual(result["deivesonfigueiredo"]["Moneyline"], 525)
        self.assertAlmostEqual(sum(r["Market Win %"] for r in result.values()), 100)

    def test_consensus_ignores_opening_and_best_lines(self):
        text = "Betting Odds Deiveson Figueiredo +517 16% Open: +408 Best: +596 Payton Talbott -764 88% Open: -597 Best: -567 Line Movement"
        result = scope["_parse_fight_market"](text, "Payton Talbott", "Deiveson Figueiredo")
        self.assertEqual(result["paytontalbott"]["Moneyline"], -764)
        self.assertEqual(result["deivesonfigueiredo"]["Moneyline"], 517)

    def test_published_career_rates_and_decimals(self):
        text = ("Payton Talbott stats Career totals Strikes landed / min 6.62 "
                "Strikes absorbed / min 3.41 Takedowns / 15 min 0.78 "
                "UFC career Record: 5-1-0 Source: UFCStats.com "
                "Significant strikes 5.87 per min SApM 3.00 per min "
                "Takedowns 0.97 per 15 min Takedown accuracy 50% "
                "TD Def. 72% Submission attempts 0.2 per 15 min "
                "Tracked fights Source: UFCalendar Significant strikes 6.62 per min "
                "SApM 3.41 per min Takedowns 0.78 per 15 min")
        result = scope["_parse_ufcalendar_stats"](text)
        self.assertEqual(result, {"SLpM": 5.87, "SApM": 3.0, "TD Avg": 0.97,
                                 "TD Acc %": 50.0, "TD Def %": 72.0,
                                 "Sub Avg": 0.2, "Stats Source": "UFCStats via UFCalendar"})

    def test_tracked_only_source_is_explicit(self):
        result = scope["_parse_ufcalendar_stats"](
            "Tracked fights Source: UFCalendar Significant strikes 2.34 per min "
            "SApM 1.56 per min Takedowns 0.0 per 15 min Submission attempts 0.0 per 15 min")
        self.assertEqual(result["TD Avg"], 0)
        self.assertEqual(result["Sub Avg"], 0)
        self.assertEqual(result["Stats Source"], "UFCalendar tracked bouts")
        self.assertNotIn("TD Def %", result)

    def test_official_ufc_number_before_label(self):
        value = scope["_grab_before"]("5.87 Sig. Str. Landed Per Min", [r"Sig\.?\s*Str\.?\s*Landed\s*Per\s*Min"])
        self.assertEqual(value, 5.87)

    def test_empty_page_does_not_invent_stats(self):
        self.assertEqual(scope["_parse_ufcalendar_stats"]("No tracked fights"), {})
        with patch.object(scope["requests"], "get", return_value=SimpleNamespace(ok=False)):
            self.assertEqual(scope["fetch_ufcstats"]("Unknown Fighter"), {})

    def test_wrong_fighter_page_is_rejected(self):
        wrong = "Other Fighter stats UFC career Significant strikes 7.0 SApM 1.0 Tracked fights Payton Talbott"
        with patch.object(scope["requests"], "get", return_value=SimpleNamespace(ok=True, text=wrong)):
            self.assertEqual(scope["fetch_ufcstats"]("Payton Talbott"), {})

    def test_ufcstats_matches_exact_row(self):
        listing = ('<tr><td><a href="http://ufcstats.com/fighter-details/aaa">Other</a>'
                   '<a href="http://ufcstats.com/fighter-details/aaa">Fighter</a></td></tr>'
                   '<tr><td><a href="http://ufcstats.com/fighter-details/bbb">Payton</a>'
                   '<a href="http://ufcstats.com/fighter-details/bbb">Talbott</a></td></tr>')
        called = []
        def get(url, **kwargs):
            called.append(url)
            if "statistics/fighters" in url:
                return SimpleNamespace(ok=True, text=listing)
            if url.endswith("/bbb"):
                return SimpleNamespace(ok=True, text="SLpM: 5.87 SApM: 3.00 TD Avg.: 0.97 TD Acc.: 50% TD Def.: 72% Sub. Avg.: 0.2")
            return SimpleNamespace(ok=False)
        with patch.object(scope["requests"], "get", side_effect=get):
            result = scope["fetch_ufcstats"]("Payton Talbott")
        self.assertEqual(result["SLpM"], 5.87)
        self.assertEqual(result["Sub Avg"], 0.2)
        self.assertNotIn("https://ufcstats.com/fighter-details/aaa", called)

    def test_snapshot_survives_total_network_failure(self):
        pd = scope["pd"]
        original = pd.DataFrame([{"Name": "Payton Talbott", "Fight": "test"},
                                 {"Name": "Unknown Fighter", "Fight": "other"}])
        with patch.object(scope["requests"], "get", return_value=SimpleNamespace(ok=False)):
            result = scope["enrich_live_context"](original)
        self.assertGreater(result.loc[0, "SLpM"], 0)
        self.assertTrue(pd.isna(result.loc[1, "SLpM"]))
        self.assertTrue(result.loc[0, "Stats Updated"])

    def test_existing_values_survive_total_network_failure(self):
        pd = scope["pd"]
        original = pd.DataFrame([{"Name": "Unknown Fighter", "Fight": "test", "SLpM": 2.34, "Sub Avg": 0.0}])
        with patch.object(scope["requests"], "get", return_value=SimpleNamespace(ok=False)):
            result = scope["enrich_live_context"](original)
        self.assertEqual(result.loc[0, "SLpM"], 2.34)
        self.assertEqual(result.loc[0, "Sub Avg"], 0.0)


if __name__ == "__main__":
    unittest.main()

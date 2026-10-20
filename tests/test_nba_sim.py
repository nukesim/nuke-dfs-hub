import csv
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from nuke_nba_data import (
    apply_live_data, fetch_rotowire_lineups, norm_name, parse_slate, standardized_status,
)
from nuke_nba_engine import (
    build_portfolio, estimate_ownership, export_dk_csv, optimize_once,
    project_players, simulate_slate, validate_lineup,
)


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "nba_current.csv"


class NbaSimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slate, cls.warnings = parse_slate(FIXTURE.read_text(encoding="utf-8-sig"))

    def model(self, include_q=False):
        historic = {norm_name(p["name"]): {"minutes":max(11.0,min(37.0,18+(p["salary"]-3000)/290)),
                                             "fppm":0.98, "games":60} for p in self.slate}
        live = apply_live_data(self.slate, prior_stats=historic)
        return estimate_ownership(project_players(live, included_questionable=include_q))

    def test_real_dk_slate_has_valid_slots_and_unique_ids(self):
        self.assertEqual(len(self.slate), 125)
        self.assertFalse(self.warnings)
        self.assertEqual(len({p["id"] for p in self.slate}), 125)
        self.assertEqual(len({p["game"] for p in self.slate}), 3)
        for player in self.slate:
            self.assertTrue(player["eligible"])
            self.assertIn(player["team"], {player["game"].split("@")[0], player["game"].split("@")[1]})

    def test_rejects_team_game_mismatch(self):
        sample = FIXTURE.read_text(encoding="utf-8-sig").replace(",SAS,51.7", ",LAL,51.7", 1)
        players, warnings = parse_slate(sample)
        self.assertEqual(len(players), 124)
        self.assertTrue(any("mismatch" in w for w in warnings))

    def test_status_and_confirmed_vs_expected_are_separate(self):
        self.assertEqual(standardized_status("Out"), "OUT")
        p = self.slate[0]
        expected = {p["team"]: {"state":"expected", "starters":{norm_name(p["name"])}}}
        out = apply_live_data([p], lineups=expected)[0]
        self.assertEqual(out["starter"], "EXPECTED")
        confirmed = {p["team"]: {"state":"confirmed", "starters":{norm_name(p["name"])}}}
        self.assertEqual(apply_live_data([p], lineups=confirmed)[0]["starter"], "CONFIRMED")

    def test_questionable_is_excluded_unless_enabled(self):
        base = self.model()
        self.assertTrue(all(p["excluded"] for p in base if p["status"] == "Q"))
        with_q = self.model(include_q=True)
        self.assertTrue(any(not p["excluded"] for p in with_q if p["status"] == "Q"))

    def test_team_minutes_and_injury_reallocation(self):
        players = self.model()
        by_team = sorted({p["team"] for p in players})
        for team in by_team:
            total = sum(p["minutes"] for p in players if p["team"] == team)
            self.assertAlmostEqual(total, 240, delta=0.7)
        star = next(p for p in players if p["team"] == "SAS" and p["minutes"] >= 25)
        injured = self.model()
        changed = project_players(injured, status_overrides={star["id"]: "OUT"})
        self.assertEqual(next(p for p in changed if p["id"] == star["id"])["minutes"], 0)
        self.assertAlmostEqual(sum(p["minutes"] for p in changed if p["team"] == "SAS"), 240, delta=0.7)

    def test_ownership_is_full_slate_prior_not_observed(self):
        players = self.model()
        self.assertAlmostEqual(sum(p["ownership"] for p in players), 800, delta=4.0)
        self.assertTrue(all(0 <= p["ownership"] <= 62 for p in players))

    def test_lineup_scrape_does_not_invent_confirmations(self):
        from datetime import date
        names = ["A One", "B Two", "C Three", "D Four", "E Five"]
        body = "".join(f'<li class="lineup__player"><a title="{n}">{n}</a></li>' for n in names)
        markup = ('<div class="lineup is-nba" data-lnum="1">'
                  '<a class="lineup__team is-visit"><div class="lineup__abbr">SAS</div></a>'
                  '<ul class="lineup__list is-visit"><li class="lineup__status is-expected">Expected</li>'
                  +body+'</ul></div>')
        with patch("nuke_nba_data._text", return_value=markup):
            data = fetch_rotowire_lineups(date(2026,10,20))
        self.assertEqual(data["SAS"]["state"], "expected")
        self.assertEqual(len(data["SAS"]["starters"]), 5)

    def test_optimizer_and_export(self):
        import numpy as np
        players = self.model()
        scores = simulate_slate(players, simulations=350, seed=12)
        self.assertEqual(scores.shape, (125, 350))
        estimate_ownership(players)
        lineup = optimize_once(players, [p["projection"] for p in players], min_salary=45000, max_team=4)
        self.assertIsNotNone(lineup)
        self.assertTrue(validate_lineup(lineup, players, 45000, 4))
        result, exposure, meta = build_portfolio(players, scores, entries=3, simulations=350,
                                                 min_salary=45000, max_team=4, field_size=1000,
                                                 max_exposure=67, seed=40)
        self.assertEqual(len(result), 3, meta)
        self.assertEqual(len({frozenset(x["lineup"]) for x in result}), 3)
        self.assertTrue(all(validate_lineup(x["lineup"], players, 45000, 4) for x in result))
        exported = list(csv.reader(io.StringIO(export_dk_csv(result, players))))
        self.assertEqual(exported[0], ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"])
        self.assertEqual(len(exported), 4)
        self.assertTrue(all(len(set(row)) == 8 for row in exported[1:]))
        for result_row, csv_row in zip(result, exported[1:]):
            expected = [f'{players[i]["name"]} ({players[i]["id"]})' for i in result_row["lineup"]]
            self.assertEqual(csv_row, expected)


if __name__ == "__main__":
    unittest.main()

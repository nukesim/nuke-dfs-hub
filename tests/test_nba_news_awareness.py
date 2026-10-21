"""NBA late-news projection regression checks.

A green confirmed badge MUST produce a new minute/projection estimate,
rather than merely changing the user interface label.
"""

import unittest

from nuke_nba_data import apply_live_data, norm_name
from nuke_nba_engine import estimate_ownership, project_players


def sample_roster(confirmed=False):
    roster = []
    # Include 11 rotation players on each side; the away team's 5 are provided
    # by a verified lineup source while the other team's lineup stays unknown.
    for team in ("ATL", "ORL"):
        for j in range(11):
            name = f"{team} Player {j}"
            roster.append({
                "id": f"{team}{j}", "name": name, "team": team,
                "salary": 4000 + j * 400,
                "minutes_base": 26.0 if j < 5 else 19.0,
                "fppm_base": 1.05 + j / 100,
                "status": "ACTIVE", "dk_status": "",
                "game_total": None, "eligible": ("PG", "G", "UTIL"),
                "starter": ("CONFIRMED" if confirmed else "EXPECTED")
                           if team == "ATL" and j < 5 else "UNKNOWN",
                "confirmed_team": bool(confirmed and team == "ATL"),
            })
    return roster


class TestNewsAwareNBA(unittest.TestCase):
    def test_confirmed_five_reallocates_team_minutes_and_points(self):
        expected = project_players(sample_roster(False), rotation_depth=11)
        confirmed = project_players(sample_roster(True), rotation_depth=11)
        for players in (expected, confirmed):
            self.assertAlmostEqual(
                sum(p["minutes"] for p in players if p["team"] == "ATL"),
                240, delta=0.7,
            )
        old_starter_minutes = sum(p["minutes"] for p in expected
                                  if p["team"] == "ATL" and p["starter"] == "EXPECTED")
        new_starter_minutes = sum(p["minutes"] for p in confirmed
                                  if p["team"] == "ATL" and p["starter"] == "CONFIRMED")
        self.assertGreater(new_starter_minutes, old_starter_minutes)
        old_starter_points = sum(p["projection"] for p in expected
                                 if p["team"] == "ATL" and p["starter"] == "EXPECTED")
        new_starter_points = sum(p["projection"] for p in confirmed
                                 if p["team"] == "ATL" and p["starter"] == "CONFIRMED")
        self.assertGreater(new_starter_points, old_starter_points)
        estimate_ownership(expected)
        estimate_ownership(confirmed)
        self.assertTrue(any(
            a["ownership"] != b["ownership"] for a, b in zip(expected, confirmed)
        ))

    def test_confirmed_questionable_starter_is_not_silently_excluded(self):
        name = "Confirmed Player"
        player = {
            "name": name, "id": "9", "team": "ATL", "opp": "ORL",
            "salary": 7000, "dk_avg": 32, "dk_status": "Q",
        }
        expected = {"ATL": {"state": "expected", "starters": {norm_name(name)}}}
        confirmed = {"ATL": {"state": "confirmed", "starters": {norm_name(name)}}}
        before = apply_live_data([player], lineups=expected)[0]
        after = apply_live_data([player], lineups=confirmed)[0]
        self.assertEqual(before["status"], "Q")
        self.assertTrue(project_players([before])[0]["excluded"])
        self.assertEqual(after["status"], "ACTIVE")
        self.assertTrue(after["confirmed_cleared_questionable"])
        self.assertFalse(project_players([after])[0]["excluded"])

    def test_explicit_out_wins_even_when_starter_is_confirmed(self):
        p = {
            "name": "Conflicting Player", "id": "10", "team": "ATL",
            "opp": "ORL", "salary": 7000, "dk_avg": 32, "dk_status": "OUT",
        }
        lineups = {"ATL": {"state": "confirmed",
                           "starters": {norm_name(p["name"])}}}
        player = apply_live_data([p], lineups=lineups)[0]
        self.assertEqual(player["status"], "OUT")
        self.assertTrue(player["confirmed_injury_conflict"])
        self.assertTrue(project_players([player])[0]["excluded"])


if __name__ == "__main__":
    unittest.main()

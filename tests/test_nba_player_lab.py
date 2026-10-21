"""Regression checks for the NBA Player Lab sortable, filterable player grid."""

import unittest

from nuke_nba_player_lab import GRID_COLUMNS, POSITION_ORDER, player_lab_rows


def player(name, eligible, *, team="ATL", salary=5000, proj=20, minutes=25,
           ownership=10, status="ACTIVE", starter="UNKNOWN", excluded=False):
    return {
        "id": name, "name": name, "eligible": eligible, "team": team,
        "salary": salary, "projection": proj, "minutes": minutes,
        "ownership": ownership, "status": status, "starter": starter,
        "excluded": excluded, "p90": proj * 1.3, "p99": proj * 1.6,
        "value": proj * 1000 / salary, "hit_20": 65,
        "hit_6x": 18, "source": "ESPN",
    }


class TestNBAPlayerLab(unittest.TestCase):
    def setUp(self):
        self.players = [
            player("High Guard", ("PG", "G", "UTIL"), proj=45, ownership=38, salary=9000,
                   starter="CONFIRMED"),
            player("Combo Star", ("PG", "SF", "F", "G", "UTIL"),
                   team="BOS", proj=42, ownership=22, salary=8200, minutes=33,
                   starter="EXPECTED"),
            player("Questionable Forward", ("PF", "F", "UTIL"), status="Q",
                   excluded=True, minutes=0, proj=0),
            player("Center Out", ("C", "UTIL"), status="OUT", excluded=True,
                   minutes=0, proj=0),
            player("Cheap Wing", ("SG", "SF", "G", "F", "UTIL"), team="BOS",
                   salary=3500, proj=19, ownership=3, minutes=20),
        ]

    def test_default_grid_is_sorted_with_only_available_players(self):
        rows = player_lab_rows(self.players)
        self.assertEqual([x["Player"] for x in rows],
                         ["High Guard", "Combo Star", "Cheap Wing"])
        self.assertEqual(tuple(rows[0].keys()), GRID_COLUMNS)
        self.assertEqual(rows[0]["Proj"], 45)
        self.assertEqual(rows[0]["Own %"], 38)
        self.assertEqual(rows[0]["Pos"], "PG")

    def test_core_position_filter_respects_multi_position_dk_eligibility(self):
        self.assertEqual(POSITION_ORDER, ("PG", "SG", "SF", "PF", "C"))
        self.assertEqual({r["Player"] for r in player_lab_rows(self.players, position="SF")},
                         {"Combo Star", "Cheap Wing"})
        self.assertEqual({r["Player"] for r in player_lab_rows(self.players, position="PG")},
                         {"High Guard", "Combo Star"})
        self.assertEqual(player_lab_rows(self.players, position="C"), [])
        self.assertEqual({r["Player"] for r in player_lab_rows(self.players, position="C", pool="All players")},
                         {"Center Out"})

    def test_salary_minutes_name_team_filter_and_ownership_sort(self):
        rows = player_lab_rows(
            self.players, team="BOS", search="a", position="SF",
            salary_range=(3000, 8500), minimum_minutes=20, sort_by="Ownership",
        )
        self.assertEqual([r["Player"] for r in rows], ["Combo Star", "Cheap Wing"])
        self.assertEqual(rows[0]["Own %"], 22)
        self.assertEqual(rows[0]["Min"], 33)
        self.assertEqual(rows[1]["Salary"], 3500)

    def test_injury_and_starting_five_views_include_excluded_players(self):
        injuries = player_lab_rows(self.players, pool="Injury watch")
        self.assertEqual({r["Player"] for r in injuries},
                         {"Questionable Forward", "Center Out"})
        self.assertTrue(all(r["Pool"] == "EXCLUDED" for r in injuries))
        starters = player_lab_rows(self.players, pool="Starting fives")
        self.assertEqual({r["Player"] for r in starters}, {"High Guard", "Combo Star"})
        self.assertEqual([r["Starter"] for r in starters], ["CONFIRMED", "EXPECTED"])

    def test_empty_and_invalid_filters(self):
        self.assertEqual(player_lab_rows(self.players, search="not-there"), [])
        with self.assertRaises(ValueError):
            player_lab_rows(self.players, position="G")
        with self.assertRaises(ValueError):
            player_lab_rows(self.players, sort_by="Not a sort")


if __name__ == "__main__":
    unittest.main()

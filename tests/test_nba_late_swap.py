"""Safety tests for DraftKings NBA pre-lock placement and in-contest late swap."""
import csv
import io
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from nuke_nba_data import DK_SLOTS
from nuke_nba_late_swap import (
    export_dk_swaps, is_locked, late_swap_slots, optimize_late_entry,
    parse_dk_entries, reorder_for_late_swap,
)

ET = ZoneInfo("America/New_York")
DATE = "2026-10-21"


def player(pid, pos, hour, *, team="ATL", salary=6000, proj=24, out=False):
    return {
        "id": str(pid), "name": f"Player {pid}",
        "salary": salary, "eligible": tuple(pos),
        "start": datetime(2026, 10, 21, hour, 0, tzinfo=ET),
        "team": team, "game": team+"@ORL",
        "excluded": out, "minutes": 30 if not out else 0,
        "projection": proj if not out else 0,
        "p90": proj * 1.35 if not out else 0,
        "p99": proj * 1.7 if not out else 0,
        "ownership": 12 if not out else 0,
    }


def pool():
    return [
        player("101", ("PG", "G", "UTIL"), 19, team="ATL"),
        player("102", ("SG", "G", "UTIL"), 19, team="BOS"),
        player("103", ("SF", "F", "UTIL"), 21, team="DEN"),
        player("104", ("PF", "F", "UTIL"), 20, team="DAL"),
        player("105", ("C", "UTIL"), 22, team="PHX"),
        player("106", ("PG", "G", "UTIL"), 22, team="LAL"),
        player("107", ("SF", "F", "UTIL"), 22, team="GSW"),
        player("108", ("C", "UTIL"), 19, team="MIA"),
        player("109", ("PG", "G", "UTIL"), 22, team="POR", proj=45),
        player("110", ("C", "UTIL"), 22, team="SAC", proj=49),
        player("111", ("SG", "G", "UTIL"), 22, team="LAC", proj=38, out=True),
    ]


class TestNBASmartLateSwap(unittest.TestCase):
    def setUp(self):
        self.players = pool()
        self.lineup = (0, 1, 2, 3, 4, 5, 6, 7)

    def test_prelock_placement_moves_later_player_into_util_when_eligible(self):
        # Center starting 19 ET is currently UTIL; swap with C starting 22 ET.
        changed = reorder_for_late_swap(self.lineup, self.players)
        self.assertEqual(changed[7], 4)  # latest-starting center in UTIL
        self.assertEqual(changed[4], 7)  # early center moves into C
        self.assertEqual(set(changed), set(self.lineup))
        self.assertTrue(all(DK_SLOTS[k] in self.players[i]["eligible"]
                            for k, i in enumerate(changed)))

    def test_started_players_are_frozen_in_exact_original_slot(self):
        after_first_lock = datetime(2026, 10, 21, 20, 15, tzinfo=ET)
        locked = late_swap_slots(self.lineup, self.players, after_first_lock, 0)
        self.assertIn(0, locked)
        self.assertIn(1, locked)
        self.assertIn(3, locked)
        self.assertIn(7, locked)
        # Source player was OUT in a future game: can't be inserted.
        reordered = reorder_for_late_swap(self.lineup, self.players, locked)
        self.assertTrue(all(reordered[k] == self.lineup[k] for k in locked))
        change = optimize_late_entry(self.players, self.lineup, after_first_lock,
                                     buffer_minutes=0, time_limit=3.0, min_gain=0)
        self.assertTrue(all(change["lineup"][k] == self.lineup[k] for k in locked))
        self.assertTrue(all(
            self.players[change["lineup"][k]]["start"] > after_first_lock
            for k in range(8) if k not in locked
        ))
        self.assertTrue(all(DK_SLOTS[k] in self.players[x]["eligible"]
                            for k, x in enumerate(change["lineup"])))
        self.assertLessEqual(sum(self.players[i]["salary"] for i in change["lineup"]), 50000)
        self.assertNotIn(10, change["lineup"])  # OUT player prohibited.

    def test_known_upgrade_and_salary_limit(self):
        now = datetime(2026, 10, 21, 20, 15, tzinfo=ET)
        improved = optimize_late_entry(self.players, self.lineup, now, buffer_minutes=0,
                                       mode="Ceiling chase", min_gain=0, time_limit=3.0)
        self.assertIn(8, improved["lineup"])  # late 45-projection guard replaces lower
        self.assertGreater(improved["gain"], 0)
        self.assertEqual(improved["lineup"][0], self.lineup[0])
        self.assertLessEqual(sum(self.players[x]["salary"] for x in improved["lineup"]), 50000)

    def test_buffer_prevents_last_second_swap(self):
        before = datetime(2026, 10, 21, 21, 59, tzinfo=ET)
        self.assertFalse(is_locked(self.players[4], before, 0))
        self.assertTrue(is_locked(self.players[4], before, 2))

    def test_csv_keeps_entry_identifiers_and_frozen_cells_exact(self):
        headers = ["Entry ID", "Contest Name", *DK_SLOTS]
        line = ["9001", "NBA $100K GPP",
                *(f'{self.players[i]["name"]} ({self.players[i]["id"]})'
                  for i in self.lineup)]
        file = io.StringIO()
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerow(line)
        columns, entries, errors = parse_dk_entries(file.getvalue(), self.players)
        self.assertFalse(errors)
        self.assertEqual(entries[0]["lineup"], self.lineup)
        now = datetime(2026, 10, 21, 20, 15, tzinfo=ET)
        swap = optimize_late_entry(self.players, entries[0]["lineup"], now,
                                   min_gain=0, buffer_minutes=0, time_limit=3)
        exported, exported_count = export_dk_swaps(columns, entries, [swap],
                                                   self.players, changed_only=False)
        record = list(csv.DictReader(io.StringIO(exported)))[0]
        self.assertEqual(record["Entry ID"], "9001")
        self.assertEqual(record["Contest Name"], "NBA $100K GPP")
        self.assertEqual(exported_count, 1)
        for k in swap["locked"]:
            self.assertEqual(record[DK_SLOTS[k]], entries[0]["row"][DK_SLOTS[k]])

    def test_bad_unknown_ids_and_duplicate_lineup_rejected(self):
        row = io.StringIO()
        writer = csv.writer(row)
        writer.writerow(DK_SLOTS)
        writer.writerow(["999"] + [self.players[i]["id"] for i in self.lineup[1:]])
        with self.assertRaisesRegex(ValueError, "No valid entries"):
            parse_dk_entries(row.getvalue(), self.players)
        row = io.StringIO()
        writer = csv.writer(row)
        writer.writerow(DK_SLOTS)
        writer.writerow([self.players[0]["id"]] * 8)
        with self.assertRaisesRegex(ValueError, "No valid entries"):
            parse_dk_entries(row.getvalue(), self.players)

    def test_all_locked_means_no_changes(self):
        now = datetime(2026, 10, 21, 23, 15, tzinfo=ET)
        output = optimize_late_entry(self.players, self.lineup, now)
        self.assertEqual(output["lineup"], self.lineup)
        self.assertEqual(output["changes"], 0)


if __name__ == "__main__":
    unittest.main()

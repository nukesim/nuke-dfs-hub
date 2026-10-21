"""Guard published 2026 Bermuda PGA groupings against slate/name regressions."""
import csv
import unittest
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data"
ALIASES = {"Seung-Yul Noh": "S.Y. Noh",
           "Cameron Davis": "Cam Davis",
           "Willie Mack": "Willie Mack III"}


def normalized(name):
    return "".join(c for c in name.lower() if c.isalnum())


class BermudaTeeTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (DATA / "pga_bermuda_2026_pairings.psv").open(encoding="utf-8", newline="") as file:
            cls.groups = list(csv.DictReader(file, delimiter="|"))

    def test_full_2026_first_two_rounds(self):
        self.assertEqual(len(self.groups), 40)
        players = [n.strip() for group in self.groups for n in group["Players"].split(";")]
        self.assertEqual(len(players), 120)
        self.assertEqual(len(set(map(normalized, players))), 120)
        self.assertEqual(sum(" AM" in x["R1_ET"] and x["R1_ET"].split(":")[0] in ("6", "7", "8") for x in self.groups), 20)
        self.assertEqual(sum(x["R1_ET"].startswith(("11:", "12:")) for x in self.groups), 20)
        for group in self.groups:
            self.assertIn(group["R1_Hole"], ("1", "10"))
            self.assertTrue(group["R1_ET"])
            self.assertTrue(group["R2_ET"])

    def test_both_rounds_match_draftkings_roster(self):
        with (DATA / "pga_current.csv").open(encoding="utf-8-sig", newline="") as file:
            dk_rows = list(csv.DictReader(file))
        if not dk_rows or "Butterfield Bermuda" not in dk_rows[0].get("Game Info", ""):
            self.skipTest("Current default PGA slate is no longer 2026 Bermuda")
        group_names = {normalized(n.strip()) for group in self.groups for n in group["Players"].split(";")}
        missing = [r["Name"] for r in dk_rows if normalized(ALIASES.get(r["Name"], r["Name"])) not in group_names]
        self.assertEqual(missing, [])
        self.assertEqual(len(dk_rows), 120)

    def test_key_player_round_switches(self):
        sheet = {normalized(n.strip()): (g["R1_ET"], g["R2_ET"])
                 for g in self.groups for n in g["Players"].split(";")}
        self.assertEqual(sheet[normalized("Benjamin James")], ("12:11 PM", "7:41 AM"))
        self.assertEqual(sheet[normalized("Eric Cole")], ("6:46 AM", "11:16 AM"))
        self.assertEqual(sheet[normalized("Corey Conners")], ("11:27 AM", "6:57 AM"))


if __name__ == "__main__":
    unittest.main()

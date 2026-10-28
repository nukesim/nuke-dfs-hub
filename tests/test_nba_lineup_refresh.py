"""Regression tests for NBA confirmed-starter feed updates and cache safety."""

import unittest
from datetime import date
from unittest.mock import patch

from nuke_nba_data import (
    _parse_rotowire_lineups, apply_live_data, fetch_rotowire_lineups,
    merge_lineup_updates, norm_name,
)


SLOTS = ("PG", "SG", "SF", "PF", "C")


def lineup_page(team="ATL", names=None, state="expected", *, loose=False, page_date=None):
    names = names or ("Guard One", "Guard Two", "Wing Three", "Forward Four", "Center Five")
    if loose:
        team_tag = f'<a data-x="1" class="extra is-visit lineup__team">'
        abbr = f'<span class="extra lineup__abbr">{team}</span>'
        ul = '<ul data-y="1" class="is-visit other lineup__list">'
        player = lambda slot, name: (
            "<li class='other lineup__player'><span class='extra lineup__pos'>"
            f"{slot}</span><a href='/player' title='{name}'>{name}</a></li>"
        )
        status = f'<li class="is-{state} other lineup__status">Status</li>'
        wrapper = "<div class='is-nba other lineup' data-lnum='1'>"
    else:
        team_tag = '<a class="lineup__team is-visit">'
        abbr = f'<div class="lineup__abbr">{team}</div>'
        ul = '<ul class="lineup__list is-visit">'
        player = lambda slot, name: (
            f'<li class="lineup__player"><div class="lineup__pos">{slot}</div>'
            f'<a title="{name}">{name}</a></li>'
        )
        status = f'<li class="lineup__status is-{state}">Status</li>'
        wrapper = '<div class="lineup is-nba" data-lnum="1">'
    header = f"<h1>Starting lineups for {page_date}</h1>" if page_date else ""
    return (
        header + wrapper + team_tag + abbr + "</a>" + ul + status
        + "".join(player(s, name) for s, name in zip(SLOTS, names))
        + '<li class="lineup__title">Bench</li>'
        + '<li class="lineup__player"><a title="Bench Player">Bench</a></li>'
        + "</ul></div>"
    )


class ConfirmedStarterRefreshTests(unittest.TestCase):
    def test_live_confirmed_mirror_overrides_first_mirror_expected(self):
        original = ("Guard One", "Guard Two", "Wing Three", "Forward Four", "Center Five")
        actual = ("New Starter", *original[1:])
        def response(url, timeout):
            if "web7" in url:
                return lineup_page(names=actual, state="confirmed")
            return lineup_page(names=original, state="expected")
        with patch("nuke_nba_data._text", side_effect=response) as getter:
            feed = fetch_rotowire_lineups(date(2026, 10, 28))
        self.assertEqual(getter.call_count, 3)
        self.assertEqual(feed["ATL"]["state"], "confirmed")
        self.assertIn(norm_name("New Starter"), feed["ATL"]["starters"])
        self.assertNotIn(norm_name("Guard One"), feed["ATL"]["starters"])
        self.assertEqual(feed["ATL"]["display_positions"]["PG"], "New Starter")

        old, new = (
            {"name": n, "team": "ATL", "opp": "ORL", "dk_status": "",
             "salary": 5000, "dk_avg": 20, "id": str(i)}
            for i, n in enumerate(("Guard One", "New Starter"), 1)
        )
        projected = apply_live_data([old, new], lineups=feed)
        self.assertEqual(projected[0]["starter"], "UNKNOWN")
        self.assertEqual(projected[1]["starter"], "CONFIRMED")

    def test_confirmed_five_survives_expected_regression_and_partial_feed(self):
        names = [norm_name(n) for n in
                 ("A One", "B Two", "C Three", "D Four", "E Five")]
        confirmed = {"state": "confirmed", "starters": set(names)}
        previous = {"ATL": confirmed,
                    "BOS": {"state": "expected", "starters": set(names)}}
        refresh = {"ATL": {"state": "expected", "starters": set(names[1:])}}
        merged, stale = merge_lineup_updates(previous, refresh)
        self.assertEqual(stale, ["ATL", "BOS"])
        self.assertEqual(merged["ATL"]["state"], "confirmed")
        self.assertTrue(merged["ATL"]["_stale"])
        self.assertTrue(merged["BOS"]["_stale"])
        updated = {"state": "confirmed", "starters": set(names[1:]) | {"newstarter"}}
        merged2, stale2 = merge_lineup_updates(merged, {"ATL": updated})
        self.assertEqual(merged2["ATL"]["starters"], updated["starters"])
        self.assertNotIn("_stale", merged2["ATL"])
        self.assertEqual(stale2, ["BOS"])

    def test_extra_classes_and_single_quotes_parse_correctly(self):
        markup = lineup_page(loose=True, state="confirmed")
        result = _parse_rotowire_lineups(markup)
        self.assertEqual(result["ATL"]["state"], "confirmed")
        self.assertEqual(len(result["ATL"]["starters"]), 5)
        self.assertEqual(result["ATL"]["display_positions"]["C"], "Center Five")
        self.assertNotIn(norm_name("Bench Player"), result["ATL"]["starters"])

    def test_unmarked_status_is_not_automatically_confirmed(self):
        markup = lineup_page(state="unknown")
        self.assertEqual(_parse_rotowire_lineups(markup), {})

    def test_mirror_explicitly_marked_wrong_date_is_rejected(self):
        markup = lineup_page(state="confirmed", page_date="October 27, 2026")
        with patch("nuke_nba_data._text", return_value=markup):
            with self.assertRaisesRegex(ConnectionError, "All starting-lineup sources unavailable"):
                fetch_rotowire_lineups(date(2026, 10, 28))


if __name__ == "__main__":
    unittest.main()

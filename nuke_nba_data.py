"""NBA DraftKings slate ingestion and independently refreshable public data feeds.

No website is assumed to be authoritative when it cannot be reached.  Source
failures remain visible to the caller; expected lineups never become confirmed.
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import unicodedata
from datetime import datetime
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


DK_SLOTS = ("PG", "SG", "SF", "PF", "C", "G", "F", "UTIL")
TEAM_NAMES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}
TEAM_ALIASES = {"SA": "SAS", "NY": "NYK", "GS": "GSW", "NO": "NOP", "UTAH": "UTA"}


def norm_name(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = value.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", value)


def norm_team(value):
    value = str(value or "").strip().upper()
    return TEAM_ALIASES.get(value, value)


def parse_game(value):
    match = re.search(
        r"\b([A-Z]{2,4})@([A-Z]{2,4})\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}[AP]M)\s+ET",
        str(value or "").upper(),
    )
    if not match:
        raise ValueError(f"Unrecognized DK game/time: {value}")
    away, home = norm_team(match.group(1)), norm_team(match.group(2))
    start = datetime.strptime(f"{match.group(3)} {match.group(4)}", "%m/%d/%Y %I:%M%p")
    start = start.replace(tzinfo=ZoneInfo("America/New_York"))
    return away, home, start


def parse_slate(text):
    """Return (players, warnings) while enforcing DK's eight-slot eligibility."""
    reader = csv.DictReader(io.StringIO(str(text).lstrip("\ufeff")))
    required = {"Name", "ID", "Salary", "Roster Position", "TeamAbbrev", "Game Info"}
    if not required.issubset(reader.fieldnames or ()):
        raise ValueError("Upload an NBA DraftKings Classic salaries CSV with Name, ID, Salary, Roster Position, TeamAbbrev and Game Info.")
    players, warnings, seen = [], [], set()
    for row in reader:
        try:
            identifier = str(int(row["ID"]))
            salary = int(row["Salary"])
            team = norm_team(row["TeamAbbrev"])
            away, home, start = parse_game(row["Game Info"])
            eligible = tuple(pos for pos in DK_SLOTS if pos in set(row["Roster Position"].upper().split("/")))
            if not eligible or salary < 1000 or salary > 20000 or team not in {away, home}:
                raise ValueError("invalid salary, positions or team/game mismatch")
            if identifier in seen:
                raise ValueError("duplicate player ID")
            seen.add(identifier)
            players.append({
                "id": identifier, "name": row["Name"].strip(), "team": team,
                "opp": home if team == away else away,
                "game": f"{away}@{home}", "start": start,
                "salary": salary, "eligible": eligible,
                "position": str(row.get("Position", "")).strip().upper(),
                "dk_avg": float(row.get("AvgPointsPerGame") or 0),
                "dk_status": str(row.get("Status") or "").strip().upper(),
                "dk_starting": str(row.get("Starting") or "").strip(),
            })
        except (TypeError, ValueError) as exc:
            warnings.append(f"Skipped {row.get('Name') or 'row'}: {exc}")
    if not players:
        raise ValueError("No valid players were found in the NBA slate.")
    dates = {p["start"].date() for p in players}
    if len(dates) != 1:
        warnings.append("Slate contains more than one game date; confirm the selected DK contest.")
    return players, warnings


def _json(url, timeout=12):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NUKE-DFS/1.0)", "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def _text(url, timeout=12):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NUKE-DFS/1.0)"})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def fetch_espn_stats(season_end_year):
    """League-wide prior/current regular-season box-score rates from ESPN."""
    url = (
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete"
        f"?season={int(season_end_year)}&seasontype=2&limit=1000"
    )
    data = _json(url, timeout=20)
    definitions = {cat["name"]: list(cat.get("names") or []) for cat in data.get("categories", [])}
    out = {}
    for item in data.get("athletes", []):
        athlete = item.get("athlete") or {}
        label = athlete.get("displayName", "")
        if not label:
            continue
        vals = {}
        for cat in item.get("categories", []):
            fields = definitions.get(cat.get("name"), [])
            for name, raw in zip(fields, cat.get("totals", [])):
                try:
                    vals[name] = float(str(raw).replace(",", ""))
                except (TypeError, ValueError):
                    pass
        gp = vals.get("gamesPlayed", 0.0)
        minutes = vals.get("avgMinutes", 0.0)
        if gp <= 0 or minutes <= 0:
            continue
        dk_fpg = (
            vals.get("avgPoints", 0) + 0.5 * vals.get("avgThreePointFieldGoalsMade", 0)
            + 1.25 * vals.get("avgRebounds", 0) + 1.5 * vals.get("avgAssists", 0)
            + 2.0 * (vals.get("avgSteals", 0) + vals.get("avgBlocks", 0))
            - 0.5 * vals.get("avgTurnovers", 0)
            + 1.5 * vals.get("doubleDouble", 0) / gp
            + 3.0 * vals.get("tripleDouble", 0) / gp
        )
        out[norm_name(label)] = {
            "games": gp, "minutes": minutes, "dk_fpg": max(0, dk_fpg),
            "fppm": max(0, dk_fpg) / minutes, "season": str(season_end_year),
            "espn_id": str(athlete.get("id", "")), "name": label,
        }
    return out


def fetch_espn_injuries():
    data = _json("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries")
    teams = {norm_name(name): code for code, name in TEAM_NAMES.items()}
    out = {}
    for group in data.get("injuries", []):
        team = teams.get(norm_name(group.get("displayName")))
        if not team:
            continue
        for injury in group.get("injuries", []):
            name = (injury.get("athlete") or {}).get("displayName") or ""
            if name:
                out[(team, norm_name(name))] = {
                    "status": str(injury.get("status") or ""),
                    "note": str(injury.get("shortComment") or "")[:260],
                    "updated": str(injury.get("date") or ""),
                }
    return out


def fetch_espn_games(slate_date):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={slate_date:%Y%m%d}"
    data = _json(url)
    out = {}
    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        teams = [norm_team(t.get("team", {}).get("abbreviation", "")) for t in comp.get("competitors", [])]
        if len(teams) != 2:
            continue
        key = frozenset(teams)
        market = (comp.get("odds") or [{}])[0]
        try:
            total = float(market.get("overUnder") or 0)
        except (ValueError, TypeError):
            total = 0.0
        out[key] = {"total": total if 170 <= total <= 280 else None,
                    "event": str(event.get("id", ""))}
    return out


def _html_classes(tag):
    """Read CSS classes regardless of attribute order, quoting or extra classes."""
    match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', tag, re.I | re.S)
    return set(match.group(2).split()) if match else set()


def _html_attribute(tag, attribute):
    match = re.search(r'\b' + re.escape(attribute) + r'\s*=\s*(["\'])(.*?)\1',
                      tag, re.I | re.S)
    return html.unescape(match.group(2)) if match else ""


def _parse_rotowire_lineups(raw):
    """Only an explicit provider confirmation can mark a starting five confirmed.

    Parse individual list elements so a bench player, class order or unrelated
    'is-confirmed' marker cannot turn an expected lineup into confirmed.
    """
    result = {}
    div_tags = re.finditer(r'<div\b[^>]*>', raw, re.I | re.S)
    starts = [m for m in div_tags
              if {"lineup", "is-nba"} <= _html_classes(m.group(0))]
    for number, match in enumerate(starts):
        section = raw[match.start():starts[number+1].start()
                      if number+1 < len(starts) else len(raw)]
        for side in ("visit", "home"):
            team = ""
            for tag in re.finditer(r'<(?:a|div)\b[^>]*>', section, re.I | re.S):
                if {"lineup__team", "is-" + side} <= _html_classes(tag.group(0)):
                    snippet = section[tag.end():tag.end()+1800]
                    for abbr in re.finditer(r'<(?:div|span)\b[^>]*>(.*?)</(?:div|span)>',
                                            snippet, re.S | re.I):
                        opening = abbr.group(0).split(">", 1)[0] + ">"
                        if "lineup__abbr" in _html_classes(opening):
                            team = norm_team(re.sub(r'<[^>]+>', '', abbr.group(1)).strip())
                            break
                    break
            if team not in TEAM_NAMES:
                continue

            block = ""
            for ul in re.finditer(r'<ul\b[^>]*>', section, re.I | re.S):
                if {"lineup__list", "is-" + side} <= _html_classes(ul.group(0)):
                    closing = re.search(r'</ul\s*>', section[ul.end():], re.I)
                    if closing:
                        block = section[ul.end():ul.end()+closing.start()]
                    break
            if not block:
                continue

            # Ignore the non-starter bench list, even if it contains player tags.
            tags = []
            for li in re.finditer(r'<li\b[^>]*>.*?</li\s*>', block, re.I | re.S):
                opening = li.group(0).split(">", 1)[0] + ">"
                if "lineup__title" in _html_classes(opening):
                    break
                tags.append(li.group(0))
            starter_block = "".join(tags)
            state = "unknown"
            for tag in re.finditer(r'<[a-z][^>]*>', starter_block, re.I | re.S):
                classes = _html_classes(tag.group(0))
                if "lineup__status" in classes:
                    if "is-confirmed" in classes:
                        state = "confirmed"
                    elif "is-expected" in classes:
                        state = "expected"
                    break

            names, positions, display_positions = [], {}, {}
            for li in tags:
                opening = li.split(">", 1)[0] + ">"
                if "lineup__player" not in _html_classes(opening):
                    continue
                anchor = re.search(r'<a\b[^>]*>(.*?)</a\s*>', li, re.I | re.S)
                if anchor is None:
                    continue
                anchor_tag = anchor.group(0).split(">", 1)[0] + ">"
                name = _html_attribute(anchor_tag, "title")
                if not name:
                    name = html.unescape(re.sub(r'<[^>]+>', '', anchor.group(1)).strip())
                if not name:
                    continue
                names.append(name)
                for pos in re.finditer(
                    r'<(?:div|span)\b[^>]*>\s*(PG|SG|SF|PF|C)\s*</(?:div|span)\s*>',
                    li, re.I | re.S,
                ):
                    pos_opening = pos.group(0).split(">", 1)[0] + ">"
                    if "lineup__pos" in _html_classes(pos_opening):
                        slot = pos.group(1).upper()
                        positions[slot] = norm_name(name)
                        display_positions[slot] = name
                        break

            if state in {"expected", "confirmed"} and len(names) == 5 and len(
                {norm_name(name) for name in names}
            ) == 5:
                result[team] = {
                    "state": state,
                    "starters": {norm_name(name) for name in names},
                    "positions": positions,
                    "display_positions": display_positions,
                }
    return result


def fetch_rotowire_lineups(slate_date):
    """Reconcile RotoWire mirrors instead of accepting the first *expected* five.

    Main site takes precedence if equally confirmed. A confirmed five from any
    date-matched mirror outranks an expected five, without inventing confirmations.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    hosts = (
        "https://www.rotowire.com",
        "https://web7.rotowire.com",
        "https://aws-prod-web9.rotowire.com",
    )

    def read_host(rank, host):
        response = _text(
            f"{host}/basketball/nba-lineups.php?date={slate_date:%Y-%m-%d}",
            timeout=6,
        )
        # A mirror can ignore ?date and serve an older page; reject it if the
        # published header explicitly identifies a different date.
        plain = re.sub(r'<[^>]+>', ' ', response)
        plain = html.unescape(re.sub(r'\s+', ' ', plain))
        date_match = re.search(r'Starting lineups for\s+([A-Za-z]+ \d{1,2}, \d{4})',
                               plain, re.I)
        if date_match:
            try:
                posted = datetime.strptime(date_match.group(1), "%B %d, %Y").date()
            except ValueError:
                posted = None
            if posted and posted != slate_date:
                raise ValueError(f"wrong slate date ({posted})")
        parsed = _parse_rotowire_lineups(response)
        if not parsed:
            raise ValueError("no parsable lineups")
        return rank, parsed

    results, errors = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(read_host, n, host): host
                   for n, host in enumerate(hosts)}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append(f"{futures[future]}: {type(exc).__name__}: {exc}")

    if not results:
        raise ConnectionError(
            "All starting-lineup sources unavailable (" + "; ".join(errors) + ")"
        )

    merged = {}
    for _, lineups in sorted(results, key=lambda item: item[0]):
        for team, new in lineups.items():
            old = merged.get(team)
            if old is None or (old["state"] != "confirmed"
                               and new["state"] == "confirmed"):
                merged[team] = dict(new)
    return merged


def fetch_rotoballer_lineups(slate_date):
    """Fetch explicitly labeled live starting fives from RotoBaller's JSON feed.

    The endpoint also supplies projected prior-game lineups; they MUST NEVER be
    treated as confirmations. Confirmed cards have postedAt and source metadata.
    """
    url = "https://www.rotoballer.com/wp-json/rb/v1/nba-lineups"
    req = Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "application/json",
    })
    with urlopen(req, timeout=7) as response:
        data = json.load(response)
    if data.get("date") != slate_date.isoformat():
        raise ValueError(f"RotoBaller returned the wrong slate date: {data.get('date')}")
    result = {}
    for game in data.get("games", []):
        for side in ("away", "home"):
            item = game.get(side) or {}
            team = norm_team(item.get("team"))
            if team not in TEAM_NAMES:
                continue
            card = item.get("card") or {}
            raw_state = str(card.get("status") or "").lower()
            if raw_state not in {"confirmed", "projected"}:
                continue
            starters = card.get("starters") or []
            if len(starters) != 5:
                continue
            names = [str(p.get("name") or "").strip() for p in starters]
            keys = [norm_name(name) for name in names]
            if not all(keys) or len(set(keys)) != 5:
                continue

            confirmed = (raw_state == "confirmed"
                         and bool(card.get("postedAt"))
                         and bool((card.get("source") or {}).get("url")))
            if raw_state == "confirmed" and not confirmed:
                continue  # Do not upgrade a source-less card to confirmed.

            slots = ("PG", "SG", "SF", "PF", "C")
            declared = [str(p.get("pos") or "").upper() for p in starters]
            authentic = set(declared) == set(slots) and len(set(declared)) == 5
            positions = {slot: key for slot, key in
                         zip(declared if authentic else slots, keys)}
            display = {slot: name for slot, name in
                       zip(declared if authentic else slots, names)}
            result[team] = {
                "state": "confirmed" if confirmed else "expected",
                "starters": set(keys),
                "positions": positions,
                "display_positions": display,
                "source": "RotoBaller",
                "positions_estimated": not authentic,
                "projected_from": card.get("projectedFrom", ""),
                "posted_at": card.get("postedAt") if confirmed else None,
                "source_url": ((card.get("source") or {}).get("url")
                               if confirmed else None),
            }
    if not result:
        raise ValueError("RotoBaller provided no valid lineup cards for the slate")
    return result


def reconcile_lineup_sources(rotowire=None, rotoballer=None):
    """Prefer explicit confirmations; RotoBaller fills gaps when RW is blocked.

    A projected RotoBaller five never overwrites an expected RotoWire five.
    Both sources' confirmed states count only when their parser verifies them.
    """
    merged = {team: dict(data) for team, data in (rotowire or {}).items()}
    for team, data in (rotoballer or {}).items():
        previous = merged.get(team)
        if previous is None or data.get("state") == "confirmed":
            merged[team] = dict(data)
    return merged


def merge_lineup_updates(previous, fresh):
    """Keep last verified team data when a mirror regresses or omits that team.

    Returns (combined, stale_teams). Retained lineups are visibly stale; they
    must never be presented as if the current fetch just confirmed them.
    """
    merged = {}
    stale = []
    for team, update in (fresh or {}).items():
        earlier = (previous or {}).get(team)
        if earlier and earlier.get("state") == "confirmed" and update.get("state") != "confirmed":
            entry = dict(earlier)
            entry["_stale"] = True
            merged[team] = entry
            stale.append(team)
        else:
            entry = dict(update)
            entry.pop("_stale", None)
            merged[team] = entry
    for team, earlier in (previous or {}).items():
        if team not in merged:
            entry = dict(earlier)
            entry["_stale"] = True
            merged[team] = entry
            stale.append(team)
    return merged, sorted(set(stale))


def standardized_status(raw):
    s = str(raw or "").upper().strip()
    if s in {"OUT", "O", "IR", "INJURED RESERVE", "SUSPENDED"}:
        return "OUT"
    if s in {"DOUBTFUL", "D"}:
        return "DOUBTFUL"
    if s in {"QUESTIONABLE", "Q", "DAY-TO-DAY", "GAME-TIME DECISION", "GTD"}:
        return "Q"
    if s in {"PROBABLE", "P"}:
        return "P"
    return "ACTIVE"


def apply_live_data(players, prior_stats=None, current_stats=None, injuries=None, lineups=None, games=None):
    prior_stats, current_stats = prior_stats or {}, current_stats or {}
    injuries, lineups, games = injuries or {}, lineups or {}, games or {}
    out = []
    for base in players:
        p = dict(base)
        key = norm_name(p["name"])
        prior = prior_stats.get(key, {})
        curr = current_stats.get(key, {})
        # Current-season blend is deliberately conservative for small samples.
        if curr.get("games", 0) >= 2 and prior:
            mix = min(0.75, curr["games"] / (curr["games"] + 12))
            minutes = prior["minutes"] * (1-mix) + curr["minutes"] * mix
            fppm = prior["fppm"] * (1-mix) + curr["fppm"] * mix
            source = "ESPN blended"
        elif curr.get("games", 0) >= 2:
            minutes, fppm, source = curr["minutes"], curr["fppm"], "ESPN current"
        elif prior:
            minutes, fppm, source = prior["minutes"], prior["fppm"], "ESPN prior season"
        else:
            minutes = min(36.0, max(8.0, 12.0 + (p["salary"] - 3000) / 340))
            fppm = (p["dk_avg"] / minutes) if p["dk_avg"] > 0 else 0.70
            source = "DK average fallback"
        injury = injuries.get((p["team"], key), {})
        dk_status, feed_status = standardized_status(p["dk_status"]), standardized_status(injury.get("status"))
        # A stale/missing remote response must never resurrect a DK OUT player.
        severity = {"ACTIVE": 0, "P": 1, "Q": 2, "DOUBTFUL": 3, "OUT": 4}
        status = max((dk_status, feed_status), key=lambda x: severity[x])
        lineup = lineups.get(p["team"], {})
        is_starter = key in lineup.get("starters", set())
        confirmed = lineup.get("state") == "confirmed" and is_starter
        confirmed_team = (lineup.get("state") == "confirmed"
                          and len(lineup.get("starters", set())) == 5)
        # DK and ESPN questionable designations can lag a confirmed starting
        # five. A confirmed *individual* starter is eligible unless either
        # feed explicitly says OUT/DOUBTFUL. Preserve an audit flag.
        cleared_questionable = bool(confirmed and status in {"Q", "P"})
        conflicting_out = bool(confirmed and status in {"OUT", "DOUBTFUL"})
        if cleared_questionable:
            status = "ACTIVE"
        p.update({
            "minutes_base": max(0.0, min(float(minutes), 40.0)),
            "fppm_base": max(0.1, min(float(fppm), 2.5)),
            "source": source,
            "status": status, "injury_note": injury.get("note", ""),
            "injury_updated": injury.get("updated", ""),
            "confirmed_cleared_questionable": cleared_questionable,
            "confirmed_injury_conflict": conflicting_out,
            "confirmed_team": confirmed_team,
            "starter": "CONFIRMED" if confirmed else
                       "EXPECTED" if is_starter and lineup.get("state") == "expected" else "UNKNOWN",
            "game_total": games.get(frozenset((p["team"], p["opp"])), {}).get("total"),
        })
        out.append(p)
    return out

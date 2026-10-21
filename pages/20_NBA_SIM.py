"""NUKE NBA Classic Sim — injury-aware DraftKings large-field GPP research."""

from __future__ import annotations

import hashlib
import html
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from nuke_nav import render_nav
from nuke_nba_data import (
    DK_SLOTS, TEAM_NAMES, apply_live_data, fetch_espn_games, fetch_espn_injuries,
    fetch_espn_stats, fetch_rotowire_lineups, norm_name, parse_slate,
)
from nuke_nba_engine import (
    build_portfolio, estimate_ownership, export_dk_csv, project_players,
    simulate_slate,
)
from nuke_nba_player_lab import GRID_COLUMNS, POSITION_ORDER, SORT_OPTIONS, player_lab_rows

st.set_page_config(page_title="NUKE NBA Sim", page_icon="🏀", layout="wide")
render_nav()

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "nba_current.csv"
st.markdown("""
<style>
.block-container {max-width:1660px;padding-top:.85rem!important}
.stApp {background:radial-gradient(circle at 80% 0%,rgba(25,195,125,.065),transparent 26%),#0b0f14}
.nbanav {font-size:.72rem;color:#19c37d;font-weight:900;letter-spacing:.17em}
.nbahead {font-size:2.5rem;font-weight:1000;line-height:1.03;letter-spacing:-.035em}
.nbasub {color:#95a4b1;font-size:.89rem;margin:7px 0 14px}
.nbacard {border:1px solid rgba(255,255,255,.11);background:linear-gradient(155deg,rgba(255,255,255,.035),rgba(255,255,255,.012));border-radius:15px;padding:13px 15px;margin:7px 0}
.nbacard.green {border-color:rgba(25,195,125,.43);background:linear-gradient(155deg,rgba(25,195,125,.073),rgba(255,255,255,.009))}
.nbacard.yellow {border-color:rgba(244,193,57,.45)}
.nbarank {font-size:.67rem;font-weight:950;letter-spacing:.10em;color:#19c37d;text-transform:uppercase}
.nbaname {font-weight:900;font-size:1.08rem;margin:4px 0}
.nbameta {font-size:.76rem;color:#93a1af}
.nbabig {font-size:1.52rem;font-weight:950;color:#f3f5f7}
.nbachip {display:inline-block;border-radius:6px;background:rgba(25,195,125,.11);color:#9ceec9;font-size:.68rem;font-weight:850;padding:3px 7px;margin:2px 4px 2px 0}
.nbachip.warn {background:rgba(244,193,57,.13);color:#ffe69a}
.nbachip.red {background:rgba(255,85,85,.12);color:#ffb1b1}
.nbaplayers {color:#e8f2ea;font-weight:800;line-height:1.75}
.nbalabel {color:#8fa0ae;font-size:.69rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase}

.nba-start-game {border:1px solid rgba(255,255,255,.13);border-radius:17px;overflow:hidden;background:#101721;margin:13px 0 20px;box-shadow:0 10px 28px rgba(0,0,0,.16)}
.nba-start-gamehead {display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:7px;padding:12px 17px;background:#1b2633;border-bottom:1px solid rgba(255,255,255,.1);color:#d9e6f2;font-size:.78rem;font-weight:850;letter-spacing:.06em}
.nba-start-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0}
.nba-start-team {padding:14px 18px 15px;min-width:0}
.nba-start-team + .nba-start-team {border-left:1px solid rgba(255,255,255,.11)}
.nba-start-teamhead {display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:11px}
.nba-start-abbr {font-size:1.6rem;font-weight:950;color:#f5f8fc;letter-spacing:-.04em}
.nba-start-full {font-size:.7rem;font-weight:700;color:#899bab}
.nba-start-pill {font-size:.67rem;font-weight:900;border-radius:20px;padding:5px 8px;white-space:nowrap;background:rgba(244,193,57,.11);color:#fbd776}
.nba-start-pill.confirmed {background:rgba(25,195,125,.13);color:#78eab3}
.nba-start-pill.pending {background:rgba(143,160,174,.12);color:#aab7c3}
.nba-start-row {display:grid;grid-template-columns:34px minmax(0,1fr) 46px;align-items:center;gap:7px;min-height:39px;border-top:1px solid rgba(255,255,255,.055);font-size:.89rem}
.nba-start-pos {color:#72e0b0;font-size:.73rem;font-weight:950}
.nba-start-player {font-weight:760;color:#edf4fb;overflow-wrap:anywhere}
.nba-start-player.pending {color:#798997;font-weight:550}
.nba-start-min {color:#9cabb8;font-weight:750;font-size:.72rem;text-align:right;white-space:nowrap}
.nba-start-alert {font-size:.62rem;font-weight:950;background:rgba(245,75,82,.14);color:#ff929a;padding:2px 5px;border-radius:4px;margin-left:5px}
.nba-start-watch {border-top:1px solid rgba(255,255,255,.09);padding-top:10px;margin-top:5px;min-height:55px}
.nba-start-watchlabel {font-size:.66rem;font-weight:950;letter-spacing:.1em;color:#8296a5;margin-bottom:6px}
.nba-start-watchline {font-size:.73rem;color:#d2dde5;line-height:1.8}
.nba-start-watchline b {color:#ff929a}
.nba-start-foot {font-size:.68rem;color:#91a4b2;margin-top:6px}
@media(max-width:760px) {.nba-start-grid{grid-template-columns:1fr}.nba-start-team + .nba-start-team{border-left:none;border-top:1px solid rgba(255,255,255,.14)}}
div[data-testid="stMetric"]{border:1px solid rgba(255,255,255,.11);border-radius:14px;padding:9px 12px;background:rgba(255,255,255,.022)}
div[data-testid="stMetricValue"]{font-weight:950}

/* Strong mobile contrast independent of the user's Streamlit theme. */
div[data-testid="stMetricLabel"] *, div[data-testid="stMetricLabel"] {color:#c2d0df!important}
div[data-testid="stMetricValue"] *, div[data-testid="stMetricValue"] {color:#f3f7fc!important}
div[data-testid="stCaptionContainer"] *, div[data-testid="stCaptionContainer"] {color:#a8bbcb!important}
div[data-testid="stTabs"] button {color:#c7d4e1!important}
div[data-testid="stTabs"] button[aria-selected="true"] {color:#f47272!important}
.nba-statstrip {display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 16px}
.nba-stat {display:flex;align-items:center;gap:6px;border:1px solid rgba(255,255,255,.15);
 background:#17212c;border-radius:10px;padding:8px 11px;color:#b3c6d5;font-size:.75rem;font-weight:700}
.nba-stat strong {color:#f5f8ff;font-size:1.05rem}
.nba-stat.warn strong {color:#ffd57a}
.nba-stat.danger strong {color:#ff9a9a}
@media(max-width:760px){.nbahead{font-size:1.85rem}.nba-statstrip{gap:5px}.nba-stat{padding:6px 8px;font-size:.68rem}
.nba-stat strong{font-size:.91rem}.nba-start-gamehead{font-size:.72rem}.nba-start-team{padding:11px 12px}}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def history_stats(year):
    return fetch_espn_stats(year)


@st.cache_data(ttl=150, show_spinner=False)
def cached_injuries(refresh_token):
    return fetch_espn_injuries()


@st.cache_data(ttl=150, show_spinner=False)
def cached_games(slate_date, refresh_token):
    return fetch_espn_games(slate_date)


@st.cache_data(ttl=45, show_spinner=False)
def cached_starting_fives(slate_date, refresh_token):
    return fetch_rotowire_lineups(slate_date)


@st.cache_data(ttl=45, show_spinner=False)
def live_feeds(slate_date, refresh_token):
    sources = {
        "Injuries · ESPN": lambda: cached_injuries(refresh_token),
        "Starting fives · RotoWire": lambda: cached_starting_fives(slate_date, refresh_token),
        "Games · ESPN": lambda: cached_games(slate_date, refresh_token),
    }
    data, errors = {}, []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(action) for name, action in sources.items()}
        for name, future in futures.items():
            try:
                data[name] = future.result(timeout=20)
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:100]}")
                data[name] = {}
    return data, errors, datetime.now(timezone.utc).isoformat(timespec="seconds")


def player_name(p):
    return html.escape(p["name"])


def player_badges(p):
    if p["status"] in {"OUT", "DOUBTFUL", "Q"}:
        return f'<span class="nbachip red">{p["status"]}</span>'
    if p["starter"] == "CONFIRMED":
        return '<span class="nbachip">STARTER CONFIRMED</span>'
    if p["starter"] == "EXPECTED":
        return '<span class="nbachip warn">EXPECTED STARTER</span>'
    return '<span class="nbachip warn">START UNKNOWN</span>'


STARTING_POSITIONS = ("PG", "SG", "SF", "PF", "C")


def starting_team_html(team, roster, lineups):
    """Render sourced position assignments, never guessing a confirmed five."""
    lineup = (lineups or {}).get(team, {})
    state = lineup.get("state", "unknown")
    positions = lineup.get("positions") or {}
    display_positions = lineup.get("display_positions") or {}
    roster_lookup = {norm_name(p["name"]): p for p in roster}
    complete = all(positions.get(slot) for slot in STARTING_POSITIONS)
    if complete and state == "confirmed":
        status_label, status_class = "● CONFIRMED", "confirmed"
    elif complete and state == "expected":
        status_label, status_class = "● EXPECTED", ""
    elif lineup.get("starters"):
        status_label, status_class = "● POSITIONS PENDING", "pending"
    else:
        status_label, status_class = "● LINEUP PENDING", "pending"

    rows = []
    for slot in STARTING_POSITIONS:
        match = roster_lookup.get(positions.get(slot, ""))
        source_name = display_positions.get(slot, "")
        if match is not None:
            name = html.escape(match["name"])
            minutes = f'{match["minutes"]:.0f}m'
            status = match["status"]
            alert = (f'<span class="nba-start-alert">{html.escape(status)}</span>'
                     if status in {"OUT", "Q", "DOUBTFUL"} else "")
            name_class = ""
        else:
            name = html.escape(source_name or "Awaiting starter")
            minutes, alert = "—", ""
            name_class = " pending" if not source_name else ""
        rows.append(
            f'<div class="nba-start-row"><span class="nba-start-pos">{slot}</span>'
            f'<span class="nba-start-player{name_class}">{name}{alert}</span>'
            f'<span class="nba-start-min">{minutes}</span></div>'
        )

    severity = {"OUT": 0, "DOUBTFUL": 1, "Q": 2}
    watched = sorted((p for p in roster if p["status"] in severity),
                     key=lambda p: (severity[p["status"]], -p["salary"]))
    if watched:
        warning_list = " · ".join(
            f'{html.escape(p["name"])} <b>{html.escape(p["status"])}</b>'
            for p in watched[:5]
        )
        if len(watched) > 5:
            warning_list += f" · +{len(watched)-5} more"
    else:
        warning_list = "No OUT / doubtful / questionable flags in the current feed"
    source_note = ("Starting positions supplied by RotoWire"
                   if complete else "Source has not supplied a complete five by position")
    return (
        '<div class="nba-start-team">'
        '<div class="nba-start-teamhead">'
        f'<div><div class="nba-start-abbr">{html.escape(team)}</div>'
        f'<div class="nba-start-full">{html.escape(TEAM_NAMES.get(team, team))}</div></div>'
        f'<span class="nba-start-pill {status_class}">{status_label}</span></div>'
        + "".join(rows)
        + '<div class="nba-start-watch"><div class="nba-start-watchlabel">INJURY WATCH</div>'
        f'<div class="nba-start-watchline">{warning_list}</div></div>'
        f'<div class="nba-start-foot">{source_note} · Minutes = NUKE projection</div>'
        '</div>'
    )


def lineup_card(item, players, index):
    members = [players[i] for i in item["lineup"]]
    label = " · ".join(f"{slot} {player_name(p)}" for slot, p in zip(DK_SLOTS, members))
    st.markdown(f"""
    <div class="nbacard green">
      <div class="nbarank">GPP RANK #{index} · FIELD-BEAT PROXY {item['field_beat_proxy']:.2f}% · TOP-1% PROXY {item['top_one_proxy']:.1f}%</div>
      <div class="nbabig">{item['projection']:.1f} projected <span style="color:#96b5a7;font-size:.80rem"> / {item['p99']:.1f} P99</span></div>
      <div class="nbaplayers">{label}</div>
      <div class="nbameta">${item['salary']:,} used · P90 {item['p90']:.1f} · Total player ownership {item['chalk_sum']:.0f}% · Duplication-risk index {item['duplication_index']:.2f}</div>
    </div>""", unsafe_allow_html=True)


def player_card(p, rank, show_risk=False):
    tone = "yellow" if p["status"] in {"Q", "DOUBTFUL"} else "green" if rank < 4 else ""
    st.markdown(f"""
    <div class="nbacard {tone}">
     <div class="nbarank">#{rank} · {p['team']} vs {p['opp']} · ${p['salary']:,}</div>
     <div class="nbaname">{player_name(p)} {player_badges(p)}</div>
     <div class="nbabig">{p['projection']:.1f} <span style="color:#93a4b2;font-size:.74rem">PROJ DK PTS</span></div>
     <div class="nbameta">{p['minutes']:.1f} min · P90 {p['p90']:.1f} · 20+ {p['hit_20']:.0f}% · 6x {p['hit_6x']:.0f}% · Own {p['ownership']:.1f}%</div>
     {'<div class="nbameta">'+html.escape(p['injury_note'])+'</div>' if show_risk and p['injury_note'] else ''}
    </div>""", unsafe_allow_html=True)


st.markdown('<div class="nbanav">NUKE / NBA / DRAFTKINGS CLASSIC</div>', unsafe_allow_html=True)
st.markdown('<div class="nbahead">NBA Tournament Simulator <span style="color:#19c37d">☢</span></div>', unsafe_allow_html=True)
st.markdown('<div class="nbasub">Minutes engine · injury/starting-five refresh · 20+ and 6x paths · ownership prior · simulated GPP portfolios</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### NBA SLATE")
    upload = st.file_uploader("DraftKings NBA Classic salaries", type="csv", key="nba_file")
    if "nba_refresh" not in st.session_state:
        st.session_state.nba_refresh = 0
    if st.button("↻ REFRESH INJURIES + STARTERS", use_container_width=True, type="primary"):
        st.session_state.nba_refresh += 1
        st.rerun()
    st.caption("Lineups are checked about once a minute while this tab is open; ESPN injuries about every 2½ minutes. Use Refresh for an immediate recheck.")
    st.divider()
    st.markdown("### GPP ENGINE")
    entries = st.slider("Lineups", 1, 150, 20, 1)
    field_size = st.number_input("Contest entries", min_value=100, max_value=1000000, value=10000, step=1000)
    simulations = st.select_slider("Slate simulations", options=[1000, 2500, 5000, 10000], value=2500)
    min_salary = st.slider("Minimum salary", 42000, 49900, 47500, 100)
    max_team = st.slider("Max players per NBA team", 2, 6, 4)
    max_exposure = st.slider("Max player exposure %", 10, 100, 40, 5)
    rotation_depth = st.slider("Rotation players per team", 9, 13, 11)
    include_questionable = st.checkbox("Include Q / doubtful scenarios", value=False,
                                       help="Questionable players are excluded unless enabled. When included, model simulates zeroes when they sit.")
    seed = st.number_input("Simulation seed", value=20261020, step=1)
    st.caption("The GPP field comparison uses a synthetic field sample. It is not a measured 1st-place probability or a guarantee of profit.")

try:
    raw = upload.getvalue().decode("utf-8-sig") if upload else DEFAULT_CSV.read_text(encoding="utf-8-sig")
    slate, csv_warnings = parse_slate(raw)
except (OSError, UnicodeError, ValueError) as exc:
    st.error(f"The NBA slate could not load: {exc}")
    st.stop()

slate_fingerprint = hashlib.sha256(raw.encode()).hexdigest()
if st.session_state.get("nba_slate_fingerprint") != slate_fingerprint:
    st.session_state.nba_slate_fingerprint = slate_fingerprint
    st.session_state.nba_results = None
    st.session_state.nba_minutes_overrides = {}
    st.session_state.nba_status_overrides = {}
    st.session_state.nba_excluded_ids = set()

slate_date = slate[0]["start"].date()
today_et = datetime.now(ZoneInfo("America/New_York")).date()
stale_slate = slate_date < today_et
if stale_slate:
    st.error(
        f"STALE DRAFTKINGS SLATE: Loaded {slate_date:%b %d, %Y}, but today is "
        f"{today_et:%b %d, %Y} (ET). Do not submit yesterday's player IDs. "
        "Refresh the Streamlit deployment or upload today's salary CSV in the sidebar."
    )
season_end = slate_date.year + 1 if slate_date.month >= 7 else slate_date.year


@st.fragment(run_every="60s")
def nba_dashboard():
    feeds, feed_errors, last_refresh = live_feeds(slate_date, st.session_state.nba_refresh)
    history_errors = []
    try:
        prior = history_stats(season_end-1)
    except Exception as exc:
        prior = {}
        history_errors.append(f"Historical ESPN stats: {exc}")
    try:
        current = history_stats(season_end)
    except Exception as exc:
        current = {}
        history_errors.append(f"Current ESPN stats: {exc}")
    # A temporary source outage must not erase a previously verified lineup.
    # Cache is scoped to the exact DK slate date, never reused across days.
    lineup_key = f"nba_last_good_lineups_{slate_date:%Y%m%d}"
    fresh_lineups = feeds.get("Starting fives · RotoWire") or {}
    cached_lineups = False
    news_events = []
    if fresh_lineups:
        # Record real status transitions only when the provider returned data.
        # Never fabricate a "confirmed" event from a previous cached response.
        previous = st.session_state.get(f"nba_news_snapshot_{slate_date:%Y%m%d}", {})
        latest = {
            team: (data.get("state", "unknown"), tuple(sorted(data.get("starters", set()))))
            for team, data in fresh_lineups.items()
        }
        for team, (state, names) in latest.items():
            if team in previous and previous[team] != (state, names):
                if state == "confirmed" and previous[team][0] != "confirmed":
                    news_events.append(f"{team}: STARTING FIVE CONFIRMED")
                elif state == "confirmed" and previous[team][1] != names:
                    news_events.append(f"{team}: CONFIRMED STARTERS CHANGED")
                elif state == "expected" and previous[team][1] != names:
                    news_events.append(f"{team}: EXPECTED FIVE UPDATED")
        st.session_state[f"nba_news_snapshot_{slate_date:%Y%m%d}"] = latest
        st.session_state[lineup_key] = {"lineups": fresh_lineups, "checked": last_refresh}
    elif lineup_key in st.session_state:
        feeds = dict(feeds)
        feeds["Starting fives · RotoWire"] = st.session_state[lineup_key]["lineups"]
        cached_lineups = True
    lineup_asof = (st.session_state[lineup_key]["checked"]
                   if lineup_key in st.session_state else None)
    players = apply_live_data(slate, prior, current,
                              feeds.get("Injuries · ESPN"),
                              feeds.get("Starting fives · RotoWire"),
                              feeds.get("Games · ESPN"))
    overrides = st.session_state.nba_minutes_overrides
    statuses = st.session_state.nba_status_overrides
    excluded = st.session_state.nba_excluded_ids
    modeled = project_players(players, rotation_depth=rotation_depth,
                              minutes_overrides=overrides, status_overrides=statuses,
                              excluded_ids=excluded, included_questionable=include_questionable)
    # Player probabilities/ceilings must be available *before* the user creates
    # a portfolio; the GPP button reuses these identical scenario paths.
    scores = simulate_slate(modeled, simulations=simulations, seed=int(seed))
    estimate_ownership(modeled)

    signature = hashlib.sha256(repr((
        slate_fingerprint, [(p["id"], p["status"], p["starter"], p["minutes"], p["fppm_base"], p["game_total"]) for p in modeled],
        entries, field_size, simulations, min_salary, max_team, max_exposure,
        rotation_depth, include_questionable, int(seed), sorted(excluded),
    )).encode()).hexdigest()
    stale_results = bool(st.session_state.nba_results) and st.session_state.nba_results.get("signature") != signature

    totals = Counter(p["status"] for p in modeled)
    expected = sum(p["starter"] == "EXPECTED" for p in modeled)
    confirmed = sum(p["starter"] == "CONFIRMED" for p in modeled)
    st.markdown(
        '<div class="nba-statstrip">'
        f'<span class="nba-stat"><strong>{len(modeled)}</strong> Players</span>'
        f'<span class="nba-stat danger"><strong>{totals["OUT"]}</strong> OUT</span>'
        f'<span class="nba-stat warn"><strong>{totals["Q"] + totals["DOUBTFUL"]}</strong> Q/D</span>'
        f'<span class="nba-stat"><strong>{expected}</strong> Expected</span>'
        f'<span class="nba-stat"><strong>{confirmed}</strong> Confirmed</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Slate {slate_date:%b %d, %Y} · Feed refresh {last_refresh.replace('T', ' ')} UTC · Historical model base: ESPN {season_end-2}–{str(season_end-1)[-2:]} season. Starter confirmations update only when a source confirms them.")
    for warning in csv_warnings:
        st.warning(warning)
    for err in feed_errors + history_errors:
        if err.startswith("Starting fives"):
            if cached_lineups:
                st.warning(
                    f"Lineup feed is temporarily unavailable. Showing cached lineups "
                    f"from {lineup_asof.replace('T', ' ')} UTC, NOT live confirmations. "
                    "Verify starters before submitting lineups."
                )
            else:
                st.warning(
                    "Starting-five feed is currently unavailable and no lineup has "
                    "been verified for this slate. Check the external lineup link below "
                    "or refresh later. No starting players will be invented."
                )
        else:
            st.error(f"Feed unavailable — {err}. Check player status before entering.")
    for warning in {p.get("minutes_warning") for p in modeled if p.get("minutes_warning")}:
        st.warning(warning)
    conflicts = [p["name"] for p in modeled if p.get("confirmed_injury_conflict")]
    if conflicts:
        st.error(
            "CONFLICTING STARTER / INJURY NEWS — " + ", ".join(conflicts[:6]) +
            ". The OUT/DOUBTFUL designation takes precedence until verified. "
            "These players are excluded to avoid a risky lineup."
        )
    if news_events:
        st.success("🔔 LINEUP NEWS — " + " | ".join(news_events) +
                   ". Minutes, projections and ownership have been recalculated.")
    if stale_results:
        st.error("🚨 NEWS/PROJECTIONS CHANGED: Existing portfolio is now STALE. "
                 "Rebuild your GPP lineups before exporting or entering. "
                 "Downloaded CSV files and already-entered DK rosters will NOT update automatically.")

    starters_tab, slate_tab, player_tab, tournament_tab, portfolio_tab = st.tabs([
        "🏀 STARTING 5", "🏟 SLATE INTEL", "🧪 PLAYER LAB", "☢ GPP SIM", "📈 PORTFOLIO + EXPORT"
    ])
    with starters_tab:
        lineup_feed = feeds.get("Starting fives · RotoWire") or {}
        teams = sorted({p["team"] for p in modeled})
        confirmed_teams = sum(lineup_feed.get(t, {}).get("state") == "confirmed"
                              and len(lineup_feed.get(t, {}).get("positions", {})) == 5 for t in teams)
        expected_teams = sum(lineup_feed.get(t, {}).get("state") == "expected"
                             and len(lineup_feed.get(t, {}).get("positions", {})) == 5 for t in teams)
        ready = confirmed_teams + expected_teams
        st.markdown(
            '<div class="nba-statstrip">'
            f'<span class="nba-stat"><strong>{confirmed_teams}</strong> Confirmed fives</span>'
            f'<span class="nba-stat warn"><strong>{expected_teams}</strong> Expected fives</span>'
            f'<span class="nba-stat"><strong>{len(teams) - ready}</strong> Pending fives</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        freshness = (f"Cached as of {lineup_asof.replace('T', ' ')} UTC — NOT LIVE"
                     if cached_lineups and lineup_asof
                     else f"Last feed check {last_refresh.replace('T', ' ')} UTC")
        st.caption("Source: RotoWire reported/expected fives. Minutes are NUKE projections. "
                   f"{freshness} · Refresh in sidebar or wait about one minute.")
        st.link_button(
            "↗ Check starting lineups on RotoBaller",
            "https://www.rotoballer.com/todays-nba-starting-lineups-daily-basketball-starters",
        )
        games_order = sorted({p["game"] for p in modeled},
                             key=lambda game: min(p["start"] for p in modeled if p["game"] == game))
        selected_matchup = st.selectbox("Matchup", ["All games"] + games_order, key="nba_starting_matchup")
        for game in games_order:
            if selected_matchup != "All games" and selected_matchup != game:
                continue
            group = [p for p in modeled if p["game"] == game]
            away, home = game.split("@")
            away_roster = [p for p in group if p["team"] == away]
            home_roster = [p for p in group if p["team"] == home]
            tip = group[0]["start"].strftime("%I:%M %p ET").lstrip("0")
            total = group[0].get("game_total")
            header = f"{html.escape(game)} · {tip} · O/U {total:g}" if total else f"{html.escape(game)} · {tip} · O/U unavailable"
            st.markdown(
                '<div class="nba-start-game">'
                f'<div class="nba-start-gamehead"><span>🏀 {header}</span><span>PG · SG · SF · PF · C</span></div>'
                '<div class="nba-start-grid">'
                + starting_team_html(away, away_roster, lineup_feed)
                + starting_team_html(home, home_roster, lineup_feed)
                + '</div></div>',
                unsafe_allow_html=True,
            )
        if not ready:
            st.info("No complete starting fives have been received yet. This view populates as the lineup provider updates (roughly one-minute checks); "
                    "do not treat a pending lineup as confirmed.")
        st.caption("⚠ A source-confirmed lineup is not the same as a guaranteed player-minute allotment. "
                   "FPPM and injury-adjusted rotations remain modeled estimates; check updates before lock.")

    with slate_tab:
        for game in sorted({p["game"] for p in modeled}):
            group = [p for p in modeled if p["game"] == game]
            total = group[0].get("game_total")
            first_start = group[0]["start"].strftime("%I:%M %p ET").lstrip("0")
            starters = [p for p in group if p["starter"] != "UNKNOWN"]
            outs = [p for p in group if p["status"] in {"OUT", "Q", "DOUBTFUL"}]
            st.markdown(f"<div class='nbacard'><div class='nbarank'>{game} · {first_start} · O/U {total if total else 'unavailable'}</div><div class='nbaname'>{len(starters)} projected/confirmed starters · {len(outs)} injury flags</div><div class='nbameta'>{', '.join(html.escape(x['name'])+' ('+x['status']+')' for x in outs) or 'No listed injuries in the slate/feed'}</div></div>", unsafe_allow_html=True)
            for i, p in enumerate(sorted(starters, key=lambda x: x["projection"], reverse=True)[:4]):
                st.caption(f"{p['team']} · {p['name']} · {p['starter']} · {p['minutes']:.1f} projected min · {p['projection']:.1f} DK")
        with st.expander("Data source notes and fallback rules"):
            st.write("Prior/current player box-score rates: ESPN league player statistics. Injury statuses: ESPN league report plus stricter existing DraftKings OUT/Q tags. Expected/confirmed five-man lineups: public RotoWire listing. Game totals: ESPN when provided. Feeds are unofficial and can fail or lag.")
            st.write("Minutes are a modeled 240-minute rotation, not a feed's projected minutes. Player ownership is a salary/value/role prior calibrated to roughly 800 total percentage points, not observed DraftKings contest ownership. DK AvgPointsPerGame is only used for players missing ESPN statistical history.")

    with player_tab:
        st.markdown("### NBA PLAYER LAB")
        st.caption(
            "Full slate player grid · Tap a column heading to sort · "
            "Model ownership is an estimate, not observed DraftKings ownership."
        )
        position_filter = st.segmented_control(
            "POSITION", ["ALL", *POSITION_ORDER],
            default="ALL", selection_mode="single", key="nba_lab_position",
        ) or "ALL"
        search_col, team_col, pool_col = st.columns([2, 1, 1])
        name_query = search_col.text_input(
            "Search player", placeholder="Find a player...", key="nba_lab_search",
        )
        team_filter = team_col.selectbox(
            "Team", ["ALL", *sorted({p["team"] for p in modeled})], key="nba_lab_team",
        )
        pool_filter = pool_col.selectbox(
            "Show", ["Eligible", "All players", "Injury watch", "Starting fives"],
            key="nba_lab_pool",
        )
        full_min_salary = min(p["salary"] for p in modeled)
        full_max_salary = max(p["salary"] for p in modeled)
        with st.expander("⚙ Salary, minutes & ranking filters", expanded=False):
            salary_col, minute_col, sort_col = st.columns([2, 1, 1])
            if full_min_salary < full_max_salary:
                salary_range = salary_col.slider(
                    "Salary range", full_min_salary, full_max_salary,
                    (full_min_salary, full_max_salary), step=100,
                    key="nba_lab_salary_range",
                )
            else:
                salary_range = (full_min_salary, full_max_salary)
                salary_col.caption(f"All players cost {full_min_salary:,} USD.")
            minimum_minutes = minute_col.slider(
                "Min projected minutes", 0, 42, value=0, step=2,
                key="nba_lab_min_minutes",
            )
            sort_by = sort_col.selectbox(
                "Default ranking", list(SORT_OPTIONS), key="nba_lab_sort",
            )
        selected = player_lab_rows(
            modeled, position=position_filter, team=team_filter, pool=pool_filter,
            search=name_query, salary_range=salary_range,
            minimum_minutes=minimum_minutes, sort_by=sort_by,
        )
        count = len(selected)
        st.markdown(
            '<div class="nba-statstrip">'
            f'<span class="nba-stat"><strong>{count}</strong> Players shown</span>'
            f'<span class="nba-stat"><strong>{len(modeled)}</strong> Slate total</span>'
            f'<span class="nba-stat"><strong>{html.escape(position_filter)}</strong> Position</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        extra_columns = st.toggle(
            "Show additional GPP metrics (P99, hit rates, starters, pool)",
            value=False, key="nba_lab_extra_columns",
        )
        compact_columns = [
            "Player", "Pos", "Salary", "Own %", "Proj", "Min",
            "FPPM", "P90", "Status", "Team",
        ]
        visible_columns = list(GRID_COLUMNS) if extra_columns else compact_columns
        grid_data = pd.DataFrame(selected, columns=GRID_COLUMNS)
        if grid_data.empty:
            st.info("No players match your filters. Try ALL positions, a wider salary range, or All players.")
        else:
            def highlight_status(status):
                if status in {"OUT", "DOUBTFUL"}:
                    return "background-color:#4a252a;color:#ffd6d9;font-weight:bold"
                if status in {"Q", "P"}:
                    return "background-color:#433821;color:#ffe3a1;font-weight:bold"
                return ""

            def highlight_projection(value):
                if value >= 45:
                    return "color:#8ef0b9;font-weight:bold"
                if value >= 30:
                    return "color:#b8ead2;font-weight:bold"
                return ""

            grid_style = (
                grid_data[visible_columns].style
                .map(highlight_status, subset=["Status"])
                .map(highlight_projection, subset=["Proj"])
            )
            st.dataframe(
                grid_style,
                hide_index=True, use_container_width=True, height=640,
                column_config={
                    "Player": st.column_config.TextColumn("PLAYER", width="medium"),
                    "Pos": st.column_config.TextColumn("POS", width="small", help="DraftKings eligible PG/SG/SF/PF/C positions"),
                    "Team": st.column_config.TextColumn("TEAM", width="small"),
                    "Salary": st.column_config.NumberColumn("SALARY", format="$%d", width="small"),
                    "Own %": st.column_config.NumberColumn(
                        "OWN %", format="%.1f%%", width="small",
                        help="NUKE modeled projected ownership; not actual DK ownership",
                    ),
                    "Proj": st.column_config.NumberColumn("PROJ DK", format="%.1f", width="small"),
                    "Min": st.column_config.NumberColumn("PROJ MIN", format="%.1f", width="small"),
                    "FPPM": st.column_config.NumberColumn("DK FPPM", format="%.2f", width="small",
                           help="Historical/model blended DK fantasy points per minute"),
                    "P90": st.column_config.NumberColumn("P90", format="%.1f", width="small"),
                    "P99": st.column_config.NumberColumn("P99", format="%.1f", width="small"),
                    "Value": st.column_config.NumberColumn("PTS/$1K", format="%.2f", width="small"),
                    "20+ %": st.column_config.NumberColumn("20+ %", format="%.1f%%", width="small"),
                    "6x %": st.column_config.NumberColumn("6X %", format="%.1f%%", width="small"),
                    "Status": st.column_config.TextColumn("INJURY", width="small"),
                    "Starter": st.column_config.TextColumn("STARTER", width="small"),
                    "Pool": st.column_config.TextColumn("POOL", width="small"),
                    "Source": st.column_config.TextColumn("MODEL SOURCE", width="medium"),
                },
            )
        st.caption(
            "Projected points are modeled minutes × modeled DK FPPM × game context × availability. "
            "Minutes reallocate within each team's 240-minute rotation when starters or injuries change. "
            "Position filters include multi-position eligible players. "
            "OUT and doubtful players are highlighted red; questionable/probable amber. "
            "The table scrolls horizontally on mobile."
        )
        st.download_button(
            "⬇ DOWNLOAD FILTERED PLAYER GRID",
            grid_data.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"nuke_nba_player_lab_{slate_date:%Y%m%d}.csv",
            mime="text/csv", key="nba_lab_download",
        )
        with st.expander("⚙ Manual injury and minutes overrides", expanded=False):
            st.subheader("Manual injury and minutes overrides")
            st.caption("Change a player after credible news arrives. Overrides persist for this slate, and any existing portfolio becomes stale.")
            labels = {f"{p['name']} · {p['team']} · ${p['salary']:,}":p for p in modeled}
            chosen = st.selectbox("Player to adjust", list(labels))
            target = labels[chosen]
            status_options = ["LIVE", "ACTIVE", "P", "Q", "DOUBTFUL", "OUT"]
            current_status = statuses.get(target["id"], "LIVE")
            col_a, col_b, col_c = st.columns([1.0, 1.0, .8])
            status_override = col_a.selectbox("Availability", status_options, index=status_options.index(current_status), key=f"nba_status_input_{target['id']}")
            default_minutes = float(overrides.get(target["id"], target["minutes"]))
            minutes_input = col_b.number_input("Minutes (conditional)", min_value=0.0, max_value=42.0,
                                              value=default_minutes, step=0.5, key=f"nba_min_input_{target['id']}")
            excluded_input = col_c.checkbox("Exclude", value=target["id"] in excluded, key=f"nba_exclude_{target['id']}")
            if st.button("APPLY PLAYER TAKE", type="primary"):
                if status_override == "LIVE": statuses.pop(target["id"], None)
                else: statuses[target["id"]] = status_override
                overrides[target["id"]] = minutes_input
                if excluded_input: excluded.add(target["id"])
                else: excluded.discard(target["id"])
                st.rerun()
            if st.button("CLEAR THIS PLAYER'S OVERRIDES"):
                statuses.pop(target["id"], None); overrides.pop(target["id"], None); excluded.discard(target["id"])
                st.rerun()

    with tournament_tab:
        st.markdown("### Build a first-place-oriented portfolio")
        st.caption("Four complementary lineup paths: star ceiling, leverage, correlated slate outcomes, and stable minutes. Every lineup is validated against DK roster slots, $50K cap, team count, and portfolio exposure limits.")
        core = [p for p in modeled if p["minutes"] >= 8 and not p["excluded"]]
        options = {f"{p['name']} ({p['team']}) · ${p['salary']:,}":p["id"] for p in core}
        locked = st.multiselect("100% lock players (optional)", list(options), key="nba_forced")
        faded = st.multiselect("Remove players from portfolio (optional)", [x for x in options if x not in locked], key="nba_banned")
        if st.button("☢ RUN NBA SLATE SIM + BUILD PORTFOLIO", type="primary", use_container_width=True, disabled=stale_slate):
            with st.spinner(f"Simulating {simulations:,} slates and generating up to {entries} unique legal lineups..."):
                results, exposure, meta = build_portfolio(
                    modeled, scores, entries=entries, simulations=simulations,
                    seed=int(seed), min_salary=min_salary, max_team=max_team,
                    max_exposure=max_exposure, field_size=int(field_size),
                    forced_ids=[options[x] for x in locked], banned_ids=[options[x] for x in faded],
                )
                st.session_state.nba_results = {
                    "signature": signature, "results": results, "exposure": exposure,
                    "meta": meta, "players": modeled,
                    "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            if not results:
                st.error(meta.get("reason", "No valid roster available."))
            elif len(results) < entries:
                st.warning(f"Produced {len(results)} of {entries} requested. The salary/exposure/lock combination may be too restrictive; relax it before exporting.")
            else:
                st.success(f"Generated {len(results)} unique legal lineups. Review and export them in Portfolio + Export.")
        data = st.session_state.get("nba_results")
        if data and not stale_results and data["results"]:
            st.markdown("#### Top modeled GPP paths")
            for j, item in enumerate(data["results"][:5], 1):
                lineup_card(item, data["players"], j)

    with portfolio_tab:
        data = st.session_state.get("nba_results")
        if not data:
            st.info("Run the GPP engine to create a portfolio.")
        elif stale_results:
            st.error("The portfolio is stale after an injury, minutes, slate, or settings change. Rebuild before export.")
        elif not data["results"]:
            st.warning("There are no legal lineups to export yet.")
        else:
            results, exposure, meta = data["results"], data["exposure"], data["meta"]
            a,b,c,d = st.columns(4)
            a.metric("Valid unique lineups", len(results))
            b.metric("Avg projected", f"{sum(x['projection'] for x in results)/len(results):.1f}")
            c.metric("Best P99", f"{max(x['p99'] for x in results):.1f}")
            d.metric("Field proxy lineups", meta["field_samples"])
            st.download_button("⬇ EXPORT DRAFTKINGS CLASSIC LINEUPS CSV",
                               export_dk_csv(results, data["players"]),
                               file_name=f"nuke_nba_{slate_date:%Y%m%d}_{len(results)}_lineups.csv",
                               mime="text/csv", use_container_width=True, type="primary", disabled=stale_slate)
            st.caption("Eight columns in DK order: PG, SG, SF, PF, C, G, F, UTIL. Import to the matching contest/slate only. The tool does not overwrite or automatically late-swap already locked DK entries.")
            st.subheader("Portfolio exposure")
            if exposure:
                show = pd.DataFrame(exposure[:20]).set_index("name")
                st.bar_chart(show["exposure"], horizontal=True, color="#19c37d")
                with st.expander("All player exposures"):
                    st.dataframe(pd.DataFrame(exposure), hide_index=True, use_container_width=True)
            st.subheader("Ranked lineups")
            page_size = st.selectbox("Show lineup count", [10, 20, 50, 150], index=1)
            for j, item in enumerate(results[:page_size], 1):
                lineup_card(item, data["players"], j)
            st.caption(f"Field-beat and top-1% proxies compare against {meta['field_samples']} ownership-weighted synthetic lineups per simulation, scaled conservatively with contest size. This finite sample is not the full paid tournament field; do not read these figures as calibrated win probabilities.")


nba_dashboard()

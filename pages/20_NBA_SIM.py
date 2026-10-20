"""NUKE NBA Classic Sim — injury-aware DraftKings large-field GPP research."""

from __future__ import annotations

import hashlib
import html
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from nuke_nav import render_nav
from nuke_nba_data import (
    DK_SLOTS, apply_live_data, fetch_espn_games, fetch_espn_injuries,
    fetch_espn_stats, fetch_rotowire_lineups, parse_slate,
)
from nuke_nba_engine import (
    build_portfolio, estimate_ownership, export_dk_csv, project_players,
    simulate_slate,
)

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
div[data-testid="stMetric"]{border:1px solid rgba(255,255,255,.11);border-radius:14px;padding:9px 12px;background:rgba(255,255,255,.022)}
div[data-testid="stMetricValue"]{font-weight:950}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def history_stats(year):
    return fetch_espn_stats(year)


@st.cache_data(ttl=300, show_spinner=False)
def live_feeds(slate_date, refresh_token):
    sources = {
        "Injuries · ESPN": lambda: fetch_espn_injuries(),
        "Starting fives · RotoWire": lambda: fetch_rotowire_lineups(slate_date),
        "Games · ESPN": lambda: fetch_espn_games(slate_date),
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
    st.caption("Live information is fetched on refresh and rechecked about every five minutes while this page is open.")
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
season_end = slate_date.year + 1 if slate_date.month >= 7 else slate_date.year


@st.fragment(run_every="300s")
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
    first, second, third, fourth, fifth = st.columns(5)
    first.metric("Slate players", len(modeled))
    second.metric("OUT", totals["OUT"])
    third.metric("Questionable", totals["Q"] + totals["DOUBTFUL"])
    fourth.metric("Expected starters", expected)
    fifth.metric("Confirmed starters", confirmed)
    st.caption(f"Slate {slate_date:%b %d, %Y} · Feed refresh {last_refresh.replace('T', ' ')} UTC · Historical model base: ESPN {season_end-2}–{str(season_end-1)[-2:]} season. Starter confirmations update only when a source confirms them.")
    for warning in csv_warnings:
        st.warning(warning)
    for err in feed_errors + history_errors:
        st.error(f"Feed unavailable — {err}. The model uses existing DK information or a labeled fallback; confirm status before entering.")
    for warning in {p.get("minutes_warning") for p in modeled if p.get("minutes_warning")}:
        st.warning(warning)
    if stale_results:
        st.warning("Injury, minutes or contest settings changed since the last run. Rebuild the GPP portfolio before downloading.")

    slate_tab, player_tab, tournament_tab, portfolio_tab = st.tabs([
        "🏟 SLATE INTEL", "🧪 PLAYER LAB", "☢ GPP SIM", "📈 PORTFOLIO + EXPORT"
    ])
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
        a, b, c = st.columns([1, 1, 1])
        sort_name = a.selectbox("Rank players by", ["P90 ceiling", "Projected points", "20+ hit rate", "6x hit rate", "Value per $1k", "Leverage vs ownership"])
        team_filter = b.selectbox("Team", ["ALL"] + sorted({p["team"] for p in modeled}))
        role_filter = c.selectbox("Pool", ["Eligible", "All players", "Injury alerts", "Expected/confirmed starters"])
        metric = {"P90 ceiling":"p90", "Projected points":"projection", "20+ hit rate":"hit_20",
                  "6x hit rate":"hit_6x", "Value per $1k":"value", "Leverage vs ownership":"leverage"}[sort_name]
        selected = [p for p in modeled if (team_filter == "ALL" or p["team"] == team_filter)]
        if role_filter == "Eligible": selected = [p for p in selected if not p["excluded"] and p["minutes"] > 0]
        if role_filter == "Injury alerts": selected = [p for p in selected if p["status"] != "ACTIVE"]
        if role_filter == "Expected/confirmed starters": selected = [p for p in selected if p["starter"] != "UNKNOWN"]
        selected.sort(key=lambda p: p.get(metric, 0), reverse=True)
        st.caption("Probability-style rates shown below are outputs of the uncalibrated player model; they are not market-implied probabilities.")
        for start in range(0, min(18, len(selected)), 3):
            cols = st.columns(3)
            for col, rank, p in zip(cols, range(start+1, start+4), selected[start:start+3]):
                with col: player_card(p, rank, show_risk=True)
        with st.expander(f"Full NBA player pool ({len(selected)} players)"):
            df = pd.DataFrame([{
                "Player":p["name"], "Team":p["team"], "Salary":p["salary"], "Pos":"/".join(p["eligible"]),
                "Status":p["status"], "Starting":p["starter"], "Minutes":p["minutes"], "DK Projection":p["projection"],
                "P90":p["p90"], "20+ %":p["hit_20"], "6x %":p["hit_6x"], "Model Own %":p["ownership"], "Data":p["source"],
            } for p in selected])
            st.dataframe(df, hide_index=True, use_container_width=True, height=500)
        st.divider()
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
        if st.button("☢ RUN NBA SLATE SIM + BUILD PORTFOLIO", type="primary", use_container_width=True):
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
                               mime="text/csv", use_container_width=True, type="primary")
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

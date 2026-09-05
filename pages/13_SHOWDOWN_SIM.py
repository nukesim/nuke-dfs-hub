from pathlib import Path
import secrets

import pandas as pd
import streamlit as st

from nuke_nav import render_nav
from nuke_showdown import parse_showdown_salary_csv
from nuke_showdown_sim import (
    SCRIPT_NAMES, add_lineup_labels, build_portfolio, evaluate_candidates,
    exposure_table, generate_showdown_candidates, simulate_player_outcomes,
)

DEFAULT_SHOWDOWN_CSV = Path(__file__).resolve().parents[1] / "data" / "showdown_current.csv"
ODDS_CURRENT_CSV = Path(__file__).resolve().parents[1] / "data" / "nfl_odds_current.csv"
ODDS_HISTORY_CSV = Path(__file__).resolve().parents[1] / "data" / "nfl_odds_history.csv"

st.set_page_config(page_title="NUKE Showdown Sim", page_icon="⚡", layout="wide")
render_nav()
st.title("⚡ NUKE SHOWDOWN")
st.caption("Projection-free DraftKings NFL single-game simulation · game scripts · Captain outcomes · portfolio generation")

st.subheader("🏈 Current Game")
with st.expander("Optional: upload a different DraftKings Showdown salary CSV", expanded=False):
    upload = st.file_uploader(
        "Override current Showdown slate",
        type=["csv"],
        key="showdown_sim_upload",
        help="Normally you do not need this. NUKE automatically loads the current bundled Showdown slate.",
    )

try:
    if upload is not None:
        raw = pd.read_csv(upload)
        source_label = f"Uploaded override: {upload.name}"
    else:
        if not DEFAULT_SHOWDOWN_CSV.exists():
            st.error("The current Showdown slate is not available yet.")
            st.stop()
        raw = pd.read_csv(DEFAULT_SHOWDOWN_CSV)
        source_label = "Loaded automatically"
    players, meta = parse_showdown_salary_csv(raw)
except Exception as exc:
    st.error(f"Could not read this Showdown slate: {exc}")
    st.stop()

slate_sig = f"{meta['game_info']}|{len(players)}|{source_label}"
if st.session_state.get("showdown_sim_slate_sig") != slate_sig:
    st.session_state["showdown_sim_slate_sig"] = slate_sig
    for key in [
        "showdown_sim_results", "showdown_sim_portfolio", "showdown_sim_players",
        "showdown_sim_scripts", "showdown_sim_seed", "showdown_player_controls",
    ]:
        st.session_state.pop(key, None)

all_player_count = len(players)
players = players[players["Auto Include"]].reset_index(drop=True)
team_a, team_b = meta["teams"]

st.success(f"{source_label}: {team_a} @ {team_b} · {meta['game_info']}")
flagged = all_player_count - len(players)
if flagged:
    st.caption(f"{flagged} OUT/IR player{'s' if flagged != 1 else ''} automatically excluded from the simulation pool.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Game", f"{team_a} vs {team_b}")
m2.metric("Active Players", len(players))
m3.metric("Format", "1 CPT + 5 FLEX")
m4.metric("Cap", "$50,000")

st.subheader("📈 Sportsbook & Line Movement")
odds_now = pd.DataFrame()
odds_hist = pd.DataFrame()
try:
    if ODDS_CURRENT_CSV.exists():
        odds_now = pd.read_csv(ODDS_CURRENT_CSV)
        odds_now = odds_now[odds_now["Team"].astype(str).isin([team_a, team_b])].copy()
        if not odds_now.empty:
            event_ids = odds_now["Event ID"].dropna().astype(str).unique().tolist()
            if event_ids:
                odds_now = odds_now[odds_now["Event ID"].astype(str).eq(event_ids[0])].copy()
    if ODDS_HISTORY_CSV.exists() and not odds_now.empty:
        odds_hist = pd.read_csv(ODDS_HISTORY_CSV)
        eid = str(odds_now.iloc[0]["Event ID"])
        odds_hist = odds_hist[odds_hist["Event ID"].astype(str).eq(eid)].copy()
except Exception:
    odds_now = pd.DataFrame()
    odds_hist = pd.DataFrame()

if odds_now.empty:
    st.info("Sportsbook consensus is not available for this game yet.")
else:
    odds_now = odds_now.sort_values("Team")
    game_total = float(odds_now["Game Total"].dropna().iloc[0]) if odds_now["Game Total"].notna().any() else None
    book_count = int(odds_now["Book Count"].max()) if "Book Count" in odds_now.columns else 0
    snapshot = str(odds_now["Snapshot UTC"].max()) if "Snapshot UTC" in odds_now.columns else ""
    o1, o2, o3 = st.columns(3)
    o1.metric("Game Total", f"{game_total:.1f}" if game_total is not None else "—")
    for col, team in zip([o2, o3], [team_a, team_b]):
        r = odds_now[odds_now["Team"].astype(str).eq(team)]
        if not r.empty:
            rr = r.iloc[0]
            spread = float(rr.get("Spread", 0) or 0)
            tt = float(rr.get("Team Total", 0) or 0)
            col.metric(f"{team} · Team Total", f"{tt:.1f}", delta=f"Spread {spread:+.1f}")
    books = str(odds_now.iloc[0].get("Books", ""))
    st.caption(f"Consensus across {book_count} sportsbooks · Latest snapshot: {snapshot}" + (f" · {books}" if books else ""))

    if not odds_hist.empty:
        odds_hist["Snapshot UTC"] = pd.to_datetime(odds_hist["Snapshot UTC"], errors="coerce", utc=True)
        odds_hist = odds_hist.dropna(subset=["Snapshot UTC"]).sort_values("Snapshot UTC")
        first = odds_hist.groupby("Team", as_index=False).first()
        last = odds_hist.groupby("Team", as_index=False).last()
        with st.expander("Line movement history", expanded=False):
            mov_rows = []
            for team in [team_a, team_b]:
                a = first[first["Team"].astype(str).eq(team)]
                b = last[last["Team"].astype(str).eq(team)]
                if not a.empty and not b.empty:
                    mov_rows.append({
                        "Team": team,
                        "Open Spread": float(a.iloc[0]["Spread"]),
                        "Current Spread": float(b.iloc[0]["Spread"]),
                        "Spread Move": float(b.iloc[0]["Spread"] - a.iloc[0]["Spread"]),
                        "Open Team Total": float(a.iloc[0]["Team Total"]),
                        "Current Team Total": float(b.iloc[0]["Team Total"]),
                        "Team Total Move": float(b.iloc[0]["Team Total"] - a.iloc[0]["Team Total"]),
                    })
            if mov_rows:
                st.dataframe(pd.DataFrame(mov_rows), use_container_width=True, hide_index=True)
            chart = odds_hist.pivot_table(index="Snapshot UTC", columns="Team", values="Team Total", aggfunc="last")
            if not chart.empty:
                st.caption("Team total movement")
                st.line_chart(chart, use_container_width=True)
            gt = odds_hist.drop_duplicates("Snapshot UTC").set_index("Snapshot UTC")[["Game Total"]]
            if not gt.empty:
                st.caption("Game total movement")
                st.line_chart(gt, use_container_width=True)

st.subheader("🎛️ Player Controls")
st.caption("Boost changes the simulated baseline for that player. Min/Max exposure are enforced in the generated portfolio. Leave 0 / 100 for no player-specific exposure rule.")
control_state = dict(st.session_state.get("showdown_player_controls", {}) or {})
team_columns = st.columns(2)
for col, team in zip(team_columns, [team_a, team_b]):
    with col:
        st.markdown(f"#### {team}")
        tp = players[players["Team"].astype(str).eq(team)].copy().reset_index()
        rows = []
        for _, r in tp.iterrows():
            key = str(r["Player Key"])
            cfg = control_state.get(key, {})
            rows.append({
                "_idx": int(r["index"]),
                "Player": r["Name"],
                "Pos": r["Pos"],
                "Salary": int(r["FLEX Salary"]),
                "Boost %": float(cfg.get("boost", 0.0)),
                "Min %": int(cfg.get("min", 0)),
                "Max %": int(cfg.get("max", 100)),
            })
        edit = pd.DataFrame(rows).set_index("_idx")
        edited = st.data_editor(
            edit,
            use_container_width=True,
            hide_index=True,
            disabled=["Player", "Pos", "Salary"],
            column_config={
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Pos": st.column_config.TextColumn("Pos", width="small"),
                "Salary": st.column_config.NumberColumn("FLEX", format="$%d", width="small"),
                "Boost %": st.column_config.NumberColumn("Boost %", min_value=-50.0, max_value=50.0, step=5.0, format="%.0f%%", width="small", help="Changes this player's simulated baseline before each game outcome is drawn."),
                "Min %": st.column_config.NumberColumn("Min %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),
                "Max %": st.column_config.NumberColumn("Max %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),
            },
            key=f"showdown_controls_{team}_{slate_sig}",
        )
        for idx, er in edited.iterrows():
            key = str(players.iloc[int(idx)]["Player Key"])
            mn = int(er["Min %"]); mx = int(er["Max %"])
            if mn > mx:
                mn = mx
            control_state[key] = {"boost": float(er["Boost %"]), "min": mn, "max": mx}
st.session_state["showdown_player_controls"] = control_state

boosts = {i: float(control_state.get(str(r["Player Key"]), {}).get("boost", 0.0)) for i, r in players.iterrows()}
player_mins = {i: float(control_state.get(str(r["Player Key"]), {}).get("min", 0)) / 100.0 for i, r in players.iterrows()}
player_maxes = {i: float(control_state.get(str(r["Player Key"]), {}).get("max", 100)) / 100.0 for i, r in players.iterrows()}

with st.expander("Simulation Settings", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    n_sims = c1.selectbox("Game simulations", [2000, 5000, 10000], index=1)
    candidates = c2.selectbox("Candidate lineups", [3000, 6000, 12000], index=1)
    min_salary = c3.slider("Minimum salary", 30000, 50000, 42000, 500)
    portfolio_n = c4.selectbox("Portfolio lineups", [5, 10, 20, 50, 100, 150], index=2)
    c5, c6 = st.columns(2)
    max_player = c5.slider("Max player exposure", 25, 100, 75, 5) / 100
    max_cpt = c6.slider("Max Captain exposure", 10, 100, 35, 5) / 100

    st.markdown("##### Randomness")
    r1, r2 = st.columns([1, 2])
    fixed_seed = r1.checkbox(
        "Use fixed seed",
        value=False,
        help="Off = every run gets a fresh random seed. Turn on only when you want to reproduce the exact same simulation.",
    )
    manual_seed = r2.number_input(
        "Seed",
        min_value=1,
        max_value=2147483646,
        value=260905,
        step=1,
        disabled=not fixed_seed,
    )
    if not fixed_seed:
        st.caption("Fresh random seed will be generated each time you click RUN SHOWDOWN SIM.")

st.markdown("#### What NUKE is simulating")
st.caption(
    "Balanced · Shootout · Low Scoring · each team controlling the game · Passing Spike · "
    "Rushing Control · Chaos. Player outcomes use DraftKings salary/FPPG as baseline signals "
    "plus correlated game, team and role volatility — no paid projections required."
)

if st.button("☢️ RUN SHOWDOWN SIM", type="primary", use_container_width=True):
    seed = int(manual_seed) if fixed_seed else secrets.randbelow(2147483645) + 1
    with st.spinner("Simulating single-game outcomes and evaluating Showdown constructions..."):
        sims, scripts, base = simulate_player_outcomes(
            players, meta["teams"], n_sims=n_sims, seed=seed, boosts=boosts
        )
        cand = generate_showdown_candidates(
            players,
            max_candidates=candidates,
            min_salary=min_salary,
            seed=seed,
        )
        results = evaluate_candidates(players, cand, sims, scripts)
        portfolio = build_portfolio(
            results, players, count=portfolio_n,
            max_player_pct=max_player, max_cpt_pct=max_cpt,
            player_mins=player_mins, player_maxes=player_maxes,
        )
        st.session_state["showdown_sim_results"] = results
        st.session_state["showdown_sim_portfolio"] = portfolio
        st.session_state["showdown_sim_players"] = players
        st.session_state["showdown_sim_scripts"] = pd.Series(scripts).value_counts().to_dict()
        st.session_state["showdown_sim_seed"] = seed
    st.success(
        f"Showdown SIM complete · seed {seed:,} · {n_sims:,} game outcomes · "
        f"{len(cand):,} legal candidate lineups"
    )

results = st.session_state.get("showdown_sim_results")
portfolio = st.session_state.get("showdown_sim_portfolio")
sim_players = st.session_state.get("showdown_sim_players")
run_seed = st.session_state.get("showdown_sim_seed")
if results is None or sim_players is None or results.empty:
    st.stop()

if run_seed:
    st.caption(f"Current run seed: {int(run_seed):,}")

st.subheader("Top Simulated Lineups")
labeled = add_lineup_labels(results.head(250), sim_players)
show_cols = [
    "CPT", "FLEX1", "FLEX2", "FLEX3", "FLEX4", "FLEX5", "Split", "Salary",
    "NUKE Score", "Mean", "Ceiling", "P95", "Top 1% Score",
]
st.dataframe(
    labeled[show_cols].round(2),
    use_container_width=True,
    hide_index=True,
    column_config={"Salary": st.column_config.NumberColumn("Salary", format="$%d")},
)

st.subheader("Game-Script Leaders")
script_tabs = st.tabs(SCRIPT_NAMES)
for tab, script in zip(script_tabs, SCRIPT_NAMES):
    with tab:
        x = results.nlargest(20, script)
        x = add_lineup_labels(x, sim_players)
        st.dataframe(
            x[["CPT", "FLEX1", "FLEX2", "FLEX3", "FLEX4", "FLEX5", "Split", "Salary", script]].round(2),
            use_container_width=True,
            hide_index=True,
        )

st.subheader("NUKE Showdown Portfolio")
if portfolio is None or portfolio.empty:
    st.info("No portfolio could be built with the current exposure limits.")
else:
    if len(portfolio) < int(portfolio_n):
        st.warning(
            f"Exposure limits allowed {len(portfolio)} of the requested {int(portfolio_n)} lineups. "
            "Increase candidate lineups or loosen exposure caps if you want the full portfolio size."
        )
    else:
        st.success(f"Built full {len(portfolio)}-lineup portfolio with exposure caps enforced.")

    p = add_lineup_labels(portfolio, sim_players)
    st.dataframe(
        p[show_cols].round(2),
        use_container_width=True,
        hide_index=True,
        column_config={"Salary": st.column_config.NumberColumn("Salary", format="$%d")},
    )
    overall, captains = exposure_table(portfolio, sim_players)
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("#### Player Exposure")
        st.dataframe(overall, use_container_width=True, hide_index=True)
    with e2:
        st.markdown("#### Captain Exposure")
        st.dataframe(captains, use_container_width=True, hide_index=True)

    split_counts = p["Split"].value_counts().rename_axis("Construction").reset_index(name="Lineups")
    st.markdown("#### Construction Mix")
    st.dataframe(split_counts, use_container_width=True, hide_index=True)

st.info(
    "Showdown SIM V1 intentionally ranks lineups by simulated outcome quality rather than contest payout simulation. "
    "The next layer is ownership/duplication leverage once we have a reliable public ownership signal."
)

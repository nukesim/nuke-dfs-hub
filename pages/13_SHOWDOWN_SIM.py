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
        "showdown_sim_scripts", "showdown_sim_seed",
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
            players, meta["teams"], n_sims=n_sims, seed=seed
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

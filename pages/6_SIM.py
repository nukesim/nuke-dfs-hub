import streamlit as st
import pandas as pd
from nuke_sim import prepare_slate, simulate_player_matrix, generate_lineups, evaluate_lineups, exposure_table

st.set_page_config(page_title="NUKE SIM", page_icon="☢️", layout="wide")
st.title("☢️ NUKE SIM")
st.caption("Projection-free NFL DFS outcome simulation — built directly into the NUKE DFS Hub.")

with st.sidebar:
    st.header("SIM CONTROL ROOM")
    preset = st.selectbox("Preset", ["QUICK", "STANDARD", "DEEP"], index=1)
    presets = {
        "QUICK": (300, 500, 400),
        "STANDARD": (700, 1500, 800),
        "DEEP": (1400, 3000, 1500),
    }
    candidates, sims, portfolio_n = presets[preset]
    min_salary = st.number_input("Minimum salary", 45000, 50000, 49400, 100)
    candidates = st.number_input("Candidate lineups", 100, 5000, candidates, 100)
    sims = st.number_input("Football universes", 250, 10000, sims, 250)
    portfolio_n = st.number_input("Exposure portfolio", 10, 150, min(portfolio_n, 150), 10)
    seed = st.number_input("Random seed", 1, 999999, 26, 1)

uploaded = st.file_uploader("Upload DraftKings NFL salary CSV", type=["csv"], help="Use the normal DraftKings salary export. No coding or local files beyond the CSV are required.")

if uploaded is None:
    st.info("Upload a DraftKings NFL salary CSV to start the simulator.")
    st.stop()

try:
    raw = pd.read_csv(uploaded)
    players = prepare_slate(raw)
except Exception as e:
    st.error(f"Could not read this slate: {e}")
    st.stop()

c1,c2,c3,c4 = st.columns(4)
c1.metric("Players", len(players))
c2.metric("Teams", players.Team.nunique())
c3.metric("Games", players.Game.nunique())
c4.metric("Salary Floor", f"${int(min_salary):,}")

st.subheader("Player / Injury Overrides")
st.caption("Exclude inactive players before running. Role-based overrides are coming next; this first Hub version focuses on the simulation workflow.")
editor = players[["Name","Position","Team","Salary","Game"]].copy()
editor.insert(0, "Active", True)
edited = st.data_editor(editor, use_container_width=True, hide_index=True, disabled=["Name","Position","Team","Salary","Game"])
active_names = set(edited.loc[edited.Active, "Name"])
players = players[players.Name.isin(active_names)].reset_index(drop=True)

if st.button("☢️ RUN NUKE SIM", type="primary", use_container_width=True):
    if len(players) < 9:
        st.error("Not enough active players to build DraftKings lineups.")
        st.stop()
    with st.status("NUKE SIM is running...", expanded=True) as status:
        st.write("Generating legal DraftKings candidate lineups...")
        lineups = generate_lineups(players, int(candidates), int(min_salary), int(seed))
        if not lineups:
            status.update(label="No legal lineups found", state="error")
            st.error("No lineups met the salary constraints. Lower the minimum salary or check the uploaded slate.")
            st.stop()
        st.write(f"Generated {len(lineups):,} unique candidates.")
        st.write(f"Simulating {int(sims):,} football universes...")
        matrix = simulate_player_matrix(players, int(sims), int(seed), "NUKEM")
        st.write("Scoring lineup outcome distributions...")
        results = evaluate_lineups(players, lineups, matrix)
        exposure = exposure_table(players, results, int(portfolio_n))
        st.session_state["nuke_sim_results"] = results
        st.session_state["nuke_sim_exposure"] = exposure
        status.update(label="NUKE SIM complete", state="complete")

results = st.session_state.get("nuke_sim_results")
exposure = st.session_state.get("nuke_sim_exposure")
if results is not None and not results.empty:
    tab1,tab2,tab3 = st.tabs(["🏆 LINEUPS", "👤 EXPOSURE", "🧠 HOW TO READ IT"])
    with tab1:
        show = results.drop(columns=["_indices"], errors="ignore")
        st.dataframe(show.head(150), use_container_width=True, hide_index=True)
        st.download_button("Download SIM results CSV", show.to_csv(index=False).encode(), "nuke_sim_results.csv", "text/csv")
    with tab2:
        st.caption(f"Exposure across the top {min(int(portfolio_n), len(results))} simulated lineups.")
        st.dataframe(exposure, use_container_width=True, hide_index=True)
    with tab3:
        st.markdown("""
**NUKE Score** rewards lineups that combine strong simulated average outcomes with volatility and ceiling. It is a ranking signal, not a guaranteed fantasy-point projection.

**Median** is the middle simulated lineup score. **Ceiling 95** is the lineup's 95th-percentile simulated score. **Stack** shows QB teammates and bring-backs in `QB + X / Y` format.

This page is the first integrated SIM layer. The next layer is **contest simulation**: generate an opponent field, apply a payout structure, and calculate 1st-place probability, Top 0.1%, cash rate, duplication and simulated ROI.
        """)

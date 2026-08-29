import streamlit as st
import pandas as pd
from nuke_sim import prepare_slate, simulate_player_matrix, generate_lineups, evaluate_lineups, exposure_table
from nuke_contest import simulate_contest
from nuke_paths import attach_path_labels, path_exposure

st.set_page_config(page_title="NUKE SIM", page_icon="☢️", layout="wide")
st.title("☢️ NUKE SIM")
st.caption("Projection-free NFL DFS outcome + contest simulation inside the NUKE DFS Hub.")

with st.sidebar:
    st.header("SIM CONTROL ROOM")
    preset = st.selectbox("Preset", ["QUICK", "STANDARD", "DEEP"], index=1)
    presets = {
        "QUICK": (300, 500, 50, 300),
        "STANDARD": (700, 1500, 75, 750),
        "DEEP": (1400, 3000, 100, 1500),
    }
    candidates, sims, portfolio_n, contest_iters = presets[preset]
    min_salary = st.number_input("Minimum salary", 45000, 50000, 49400, 100)
    candidates = st.number_input("Candidate lineups", 100, 5000, candidates, 100)
    sims = st.number_input("Football universes", 250, 10000, sims, 250)
    portfolio_n = st.number_input("Exposure portfolio", 10, 150, portfolio_n, 10)
    seed = st.number_input("Random seed", 1, 999999, 26, 1)

    st.divider()
    st.subheader("Contest")
    field_size = st.number_input("Field size", 2, 100000, 470, 1)
    entry_fee = st.number_input("Entry fee ($)", 0.25, 10000.0, 25.0, 1.0)
    first_prize = st.number_input("1st prize ($)", 1.0, 10000000.0, 2500.0, 100.0)
    user_lineups = st.number_input("Lineups to contest-sim", 1, 150, 50, 1)
    contest_iters = st.number_input("Contest iterations", 50, 5000, contest_iters, 50)

uploaded = st.file_uploader(
    "Upload DraftKings NFL salary CSV",
    type=["csv"],
    help="Use the normal DraftKings salary export. Your friend only needs the website and this CSV — no Python or VS Code.",
)

if uploaded is None:
    st.info("Upload a DraftKings NFL salary CSV to start NUKE SIM.")
    st.stop()

try:
    raw = pd.read_csv(uploaded)
    players = prepare_slate(raw)
except Exception as e:
    st.error(f"Could not read this slate: {e}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Players", len(players))
c2.metric("Teams", players.Team.nunique())
c3.metric("Games", players.Game.nunique())
c4.metric("Salary Floor", f"${int(min_salary):,}")

st.subheader("Player / Injury Overrides")
st.caption("Uncheck inactive players before running. Role and usage overrides are the next model upgrade.")
editor = players[["Name", "Position", "Team", "Salary", "Game"]].copy()
editor.insert(0, "Active", True)
edited = st.data_editor(
    editor,
    use_container_width=True,
    hide_index=True,
    disabled=["Name", "Position", "Team", "Salary", "Game"],
)
active_names = set(edited.loc[edited.Active, "Name"])
players = players[players.Name.isin(active_names)].reset_index(drop=True)

if st.button("☢️ RUN NUKE SIM", type="primary", use_container_width=True):
    if len(players) < 9:
        st.error("Not enough active players to build DraftKings lineups.")
        st.stop()

    with st.status("NUKE SIM is running...", expanded=True) as status:
        st.write("1/4 · Generating legal DraftKings candidate lineups...")
        lineups = generate_lineups(players, int(candidates), int(min_salary), int(seed))
        if not lineups:
            status.update(label="No legal lineups found", state="error")
            st.error("No lineups met the salary constraints. Lower the minimum salary or check the uploaded slate.")
            st.stop()
        st.write(f"Generated {len(lineups):,} unique candidates.")

        st.write(f"2/4 · Simulating {int(sims):,} correlated football universes...")
        matrix = simulate_player_matrix(players, int(sims), int(seed), "NUKEM")

        st.write("3/4 · Ranking lineup outcomes and assigning NUKEM paths...")
        results = evaluate_lineups(players, lineups, matrix)
        results = attach_path_labels(players, results)
        exposure = exposure_table(players, results, int(portfolio_n))
        pexposure = path_exposure(results, int(portfolio_n))

        st.write(f"4/4 · Simulating a {int(field_size):,}-entry tournament...")
        contest_results, contest_summary = simulate_contest(
            results=results,
            player_matrix=matrix,
            field_size=int(field_size),
            entry_fee=float(entry_fee),
            first_prize=float(first_prize),
            user_lineups=int(user_lineups),
            iterations=int(contest_iters),
            seed=int(seed) + 97,
        )

        st.session_state["nuke_sim_results"] = results
        st.session_state["nuke_sim_exposure"] = exposure
        st.session_state["nuke_path_exposure"] = pexposure
        st.session_state["nuke_contest_results"] = contest_results
        st.session_state["nuke_contest_summary"] = contest_summary
        status.update(label="NUKE SIM complete", state="complete")

results = st.session_state.get("nuke_sim_results")
exposure = st.session_state.get("nuke_sim_exposure")
pexposure = st.session_state.get("nuke_path_exposure")
contest_results = st.session_state.get("nuke_contest_results")
contest_summary = st.session_state.get("nuke_contest_summary", {})

if results is not None and not results.empty:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏆 CONTEST SIM",
        "☢️ NUKEM LINEUPS",
        "🧭 PATHS",
        "👤 EXPOSURE",
        "🧠 MODEL NOTES",
    ])

    with tab1:
        if contest_results is None or contest_results.empty:
            st.info("Run NUKE SIM to generate contest metrics.")
        else:
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Field", f"{int(contest_summary.get('field_size', 0)):,}")
            m2.metric("Entry", f"${float(contest_summary.get('entry_fee', 0)):,.2f}")
            m3.metric("Paid Places", f"{int(contest_summary.get('paid_places', 0)):,}")
            m4.metric("Contest Sims", f"{int(contest_summary.get('iterations', 0)):,}")
            m5.metric("Candidates", f"{int(contest_summary.get('candidate_pool', 0)):,}")

            st.caption(
                "ROI and finish rates are simulated estimates. The current field is generated by NUKE using salary/market behavior; "
                "the payout curve is synthetic until direct DraftKings contest/payout import is added."
            )

            preferred = [
                "Contest Rank", "Sim ROI %", "1st %", "Top 0.1%", "Top 1%", "Cash %",
                "Avg Finish", "Expected Duplicates", "Avg Payout", "Strongest Path", "Path Score",
                "Lineup Thesis", "NUKE Score", "Ceiling 95", "Salary", "Stack", "QB", "RB", "WR", "TE", "DST",
            ]
            cols = [c for c in preferred if c in contest_results.columns]
            contest_show = contest_results[cols].copy()
            st.dataframe(contest_show, use_container_width=True, hide_index=True)
            st.download_button(
                "Download Contest SIM CSV",
                contest_show.to_csv(index=False).encode(),
                "nuke_contest_sim.csv",
                "text/csv",
            )

    with tab2:
        show = results.drop(columns=["_indices"], errors="ignore").copy()
        if "Top 1% Rate" in show.columns:
            show = show.drop(columns=["Top 1% Rate"])
        first = ["Rank", "NUKE Score", "Strongest Path", "Path Score", "Lineup Thesis", "Median", "Ceiling 95", "Salary", "Stack"]
        remaining = [c for c in show.columns if c not in first]
        show = show[[c for c in first if c in show.columns] + remaining]
        st.caption("Football-outcome ranking before opponent-field and payout effects are applied.")
        st.dataframe(show.head(150), use_container_width=True, hide_index=True)
        st.download_button(
            "Download NUKEM lineup results CSV",
            show.to_csv(index=False).encode(),
            "nuke_sim_results.csv",
            "text/csv",
        )

    with tab3:
        st.subheader("Portfolio Path Coverage")
        st.caption("Shows how the top NUKEM portfolio is distributed across different ways the slate can break.")
        if pexposure is not None and not pexposure.empty:
            st.dataframe(pexposure, use_container_width=True, hide_index=True)
        cols = [c for c in ["Rank", "Strongest Path", "Secondary Path", "Path Score", "Lineup Thesis", "Stack", "Salary", "QB"] if c in results.columns]
        st.dataframe(results[cols].head(int(portfolio_n)), use_container_width=True, hide_index=True)

    with tab4:
        st.caption(f"Player exposure across the top {min(int(portfolio_n), len(results))} NUKEM-ranked lineups.")
        st.dataframe(exposure, use_container_width=True, hide_index=True)

    with tab5:
        st.markdown("""
### What the layers mean

**NUKEM Lineups** simulates football outcomes first. Salary is used as a market/depth-chart signal rather than as a traditional fantasy projection. Player outcomes are volatile and correlated through shared team/game shocks.

**NUKEM Paths** classify each lineup by the slate story it is structurally positioned to win: `PASSING_EXPLOSION`, `RB_DOMINANCE`, `VALUE_ERUPTION`, `STARS_FAIL`, `SHOOTOUT`, `LOW_SCORING`, or `BALANCED`. Path Score is a relative lineup-path affinity, not a win probability.

**Contest SIM** places candidate lineups into a generated tournament field and reruns football universes. This produces `1st %`, `Top 0.1%`, `Top 1%`, `Cash %`, `Expected Duplicates`, `Avg Payout`, and `Sim ROI %`.

### Important current limitations

The opponent field is still an **estimated field**, not an imported real DraftKings contest. Field popularity is inferred from construction behavior rather than paid ownership projections. The payout curve is estimated from the contest settings. These numbers should be used to compare lineups, not treated as guaranteed returns.

### Next upgrades

1. Import an actual DraftKings contest/payout structure.
2. Add optional ownership/projection CSVs for Projection Mode.
3. Add role/usage overrides for injuries and promoted cheap starters.
4. Build portfolio selection that deliberately covers different paths instead of simply taking ranks 1–20.
5. Add Projection vs NUKEM vs Hybrid comparison mode.
        """)

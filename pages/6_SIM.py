import streamlit as st
import pandas as pd
from nuke_sim import prepare_slate, simulate_player_matrix, generate_lineups, evaluate_lineups, exposure_table
from nuke_contest import simulate_contest
from nuke_paths import attach_path_labels, path_exposure
from nuke_portfolio import build_portfolio, portfolio_summary

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
    candidates, sims, exposure_n, contest_iters = presets[preset]
    min_salary = st.number_input("Minimum salary", 45000, 50000, 49400, 100)
    candidates = st.number_input("Candidate lineups", 100, 5000, candidates, 100)
    sims = st.number_input("Football universes", 250, 10000, sims, 250)
    exposure_n = st.number_input("Exposure sample", 10, 150, exposure_n, 10)
    seed = st.number_input("Random seed", 1, 999999, 26, 1)

    st.divider()
    st.subheader("Contest")
    field_size = st.number_input("Field size", 2, 100000, 470, 1)
    entry_fee = st.number_input("Entry fee ($)", 0.25, 10000.0, 25.0, 1.0)
    first_prize = st.number_input("1st prize ($)", 1.0, 10000000.0, 2500.0, 100.0)
    user_lineups = st.number_input("Lineups to contest-sim", 1, 150, 50, 1)
    contest_iters = st.number_input("Contest iterations", 50, 5000, contest_iters, 50)

    st.divider()
    st.subheader("Portfolio")
    portfolio_size = st.number_input("Portfolio size", 1, 150, 20, 1)
    max_overlap = st.slider("Max player overlap", 4, 8, 7, 1)
    path_balance = st.slider("Path diversification", 0.0, 3.0, 1.25, 0.25)

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

st.subheader("Player / Injury / Role Overrides")
st.caption("Uncheck inactive players. Promote cheap backups with a role override and/or usage multiplier before running the sim.")
editor = players[["Name", "Position", "Team", "Salary", "Game"]].copy()
editor.insert(0, "Active", True)
editor["Role"] = "AUTO"
editor["Usage x"] = 1.0
edited = st.data_editor(
    editor,
    use_container_width=True,
    hide_index=True,
    disabled=["Name", "Position", "Team", "Salary", "Game"],
    column_config={
        "Role": st.column_config.SelectboxColumn(
            "Role",
            options=["AUTO", "QB1", "RB1", "RB2", "RB3", "WR1", "WR2", "WR3", "TE1", "BACKUP"],
        ),
        "Usage x": st.column_config.NumberColumn("Usage x", min_value=0.25, max_value=2.25, step=0.05, format="%.2f"),
    },
)
active_mask = edited["Active"].fillna(False).astype(bool).to_numpy()
players = players.loc[active_mask].copy().reset_index(drop=True)
active_edits = edited.loc[active_mask].reset_index(drop=True)
players["role_override"] = active_edits["Role"].fillna("AUTO").astype(str).str.upper().values
players["usage_multiplier"] = pd.to_numeric(active_edits["Usage x"], errors="coerce").fillna(1.0).clip(0.25, 2.25).values

if st.button("☢️ RUN NUKE SIM", type="primary", use_container_width=True):
    if len(players) < 9:
        st.error("Not enough active players to build DraftKings lineups.")
        st.stop()

    with st.status("NUKE SIM is running...", expanded=True) as status:
        st.write("1/5 · Generating legal DraftKings candidate lineups...")
        lineups = generate_lineups(players, int(candidates), int(min_salary), int(seed))
        if not lineups:
            status.update(label="No legal lineups found", state="error")
            st.error("No lineups met the salary constraints. Lower the minimum salary or check the uploaded slate.")
            st.stop()
        st.write(f"Generated {len(lineups):,} unique candidates.")

        st.write(f"2/5 · Simulating {int(sims):,} correlated football universes...")
        matrix = simulate_player_matrix(players, int(sims), int(seed), "NUKEM")

        st.write("3/5 · Ranking lineup outcomes and assigning NUKEM paths...")
        results = attach_path_labels(players, evaluate_lineups(players, lineups, matrix))
        exposure = exposure_table(players, results, int(exposure_n))
        pexposure = path_exposure(results, int(exposure_n))

        st.write(f"4/5 · Simulating a {int(field_size):,}-entry tournament...")
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

        st.write("5/5 · Building a path-diversified portfolio...")
        portfolio = build_portfolio(
            contest_results,
            size=int(portfolio_size),
            max_overlap=int(max_overlap),
            path_balance=float(path_balance),
        )
        portfolio_paths, portfolio_stats = portfolio_summary(portfolio)

        st.session_state["nuke_sim_results"] = results
        st.session_state["nuke_sim_exposure"] = exposure
        st.session_state["nuke_path_exposure"] = pexposure
        st.session_state["nuke_contest_results"] = contest_results
        st.session_state["nuke_contest_summary"] = contest_summary
        st.session_state["nuke_portfolio"] = portfolio
        st.session_state["nuke_portfolio_paths"] = portfolio_paths
        st.session_state["nuke_portfolio_stats"] = portfolio_stats
        status.update(label="NUKE SIM complete", state="complete")

results = st.session_state.get("nuke_sim_results")
exposure = st.session_state.get("nuke_sim_exposure")
pexposure = st.session_state.get("nuke_path_exposure")
contest_results = st.session_state.get("nuke_contest_results")
contest_summary = st.session_state.get("nuke_contest_summary", {})
portfolio = st.session_state.get("nuke_portfolio")
portfolio_paths = st.session_state.get("nuke_portfolio_paths")
portfolio_stats = st.session_state.get("nuke_portfolio_stats", {})

if results is not None and not results.empty:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏆 CONTEST SIM", "🧬 PORTFOLIO", "☢️ NUKEM LINEUPS", "🧭 PATHS", "👤 EXPOSURE", "🧠 MODEL NOTES"
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
            st.caption("ROI and finish rates are simulated estimates. Field and payout modeling are still estimated until direct DraftKings contest import is added.")
            preferred = [
                "Contest Rank", "Sim ROI %", "1st %", "Top 0.1%", "Top 1%", "Cash %", "Avg Finish",
                "Expected Duplicates", "Avg Payout", "Strongest Path", "Path Score", "Lineup Thesis",
                "NUKE Score", "Ceiling 95", "Salary", "Stack", "QB", "RB", "WR", "TE", "DST",
            ]
            contest_show = contest_results[[c for c in preferred if c in contest_results.columns]].copy()
            st.dataframe(contest_show, use_container_width=True, hide_index=True)
            st.download_button("Download Contest SIM CSV", contest_show.to_csv(index=False).encode(), "nuke_contest_sim.csv", "text/csv")

    with tab2:
        if portfolio is None or portfolio.empty:
            st.info("Run NUKE SIM to build a portfolio.")
        else:
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Lineups", int(portfolio_stats.get("lineups", 0)))
            p2.metric("Paths Covered", int(portfolio_stats.get("paths", 0)))
            p3.metric("Avg Sim ROI", f"{float(portfolio_stats.get('avg_roi', 0)):.1f}%")
            p4.metric("Avg Duplicates", f"{float(portfolio_stats.get('avg_dup', 0)):.2f}")
            st.caption("NUKE balances contest quality, path coverage, and lineup uniqueness instead of blindly taking ranks 1 through N.")
            if portfolio_paths is not None and not portfolio_paths.empty:
                st.dataframe(portfolio_paths, use_container_width=True, hide_index=True)
            preferred = [
                "Portfolio Slot", "Portfolio Reason", "Sim ROI %", "1st %", "Top 1%", "Expected Duplicates",
                "Strongest Path", "Path Score", "Lineup Thesis", "Salary", "Stack", "QB", "RB", "WR", "TE", "DST",
            ]
            pshow = portfolio[[c for c in preferred if c in portfolio.columns]].copy()
            st.dataframe(pshow, use_container_width=True, hide_index=True)
            st.download_button("Download NUKE Portfolio CSV", pshow.to_csv(index=False).encode(), "nuke_portfolio.csv", "text/csv")

    with tab3:
        show = results.drop(columns=["_indices"], errors="ignore").copy()
        first = ["Rank", "NUKE Score", "Strongest Path", "Path Score", "Lineup Thesis", "Median", "Ceiling 95", "Salary", "Stack"]
        show = show[[c for c in first if c in show.columns] + [c for c in show.columns if c not in first]]
        st.caption("Football-outcome ranking before opponent-field and payout effects are applied.")
        st.dataframe(show.head(150), use_container_width=True, hide_index=True)
        st.download_button("Download NUKEM lineup results CSV", show.to_csv(index=False).encode(), "nuke_sim_results.csv", "text/csv")

    with tab4:
        st.subheader("Path Coverage")
        if pexposure is not None and not pexposure.empty:
            st.dataframe(pexposure, use_container_width=True, hide_index=True)
        cols = [c for c in ["Rank", "Strongest Path", "Secondary Path", "Path Score", "Lineup Thesis", "Stack", "Salary", "QB"] if c in results.columns]
        st.dataframe(results[cols].head(int(exposure_n)), use_container_width=True, hide_index=True)

    with tab5:
        st.caption(f"Player exposure across the top {min(int(exposure_n), len(results))} NUKEM-ranked lineups.")
        st.dataframe(exposure, use_container_width=True, hide_index=True)

    with tab6:
        st.markdown("""
**NUKEM Lineups** simulate volatile, correlated football outcomes without requiring a traditional fantasy-point projection feed.

**Role / Usage Overrides** let you react to news. Example: if a $4,200 backup becomes the starter, set `Role = RB1` and raise `Usage x` (for example `1.25–1.45`) instead of pretending his old salary still represents his opportunity.

**NUKEM Paths** classify the slate story each lineup is built to win: `PASSING_EXPLOSION`, `RB_DOMINANCE`, `VALUE_ERUPTION`, `STARS_FAIL`, `SHOOTOUT`, `LOW_SCORING`, or `BALANCED`.

**Contest SIM** generates a tournament field and estimates `1st %`, `Top 0.1%`, `Top 1%`, `Cash %`, duplication, payout and ROI.

**Portfolio** selects lineups as a group, balancing contest quality against overlap and path concentration.

Current limitation: the opponent field and payout curve are modeled estimates. Next major additions are direct DraftKings contest/payout import and optional Projection / Hybrid modes.
        """)

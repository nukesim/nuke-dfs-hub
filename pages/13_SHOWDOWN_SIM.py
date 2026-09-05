from pathlib import Path
import secrets

import pandas as pd
import streamlit as st

from nuke_nav import render_nav
from nuke_showdown import export_lineup_only_csv, parse_showdown_salary_csv
from nuke_showdown_fanduel import (
    FANDUEL_SHOWDOWN_SALARY_CAP, export_fanduel_lineup_only_csv, parse_fanduel_showdown_csv,
)
from nuke_showdown_sim import (
    SCRIPT_NAMES, add_lineup_labels, build_portfolio, evaluate_candidates,
    exposure_table, generate_showdown_candidates, simulate_player_outcomes,
)
from nuke_showdown_workspace import (
    apply_workspace as apply_showdown_workspace,
    load_workspace_bytes as load_showdown_workspace_bytes,
    workspace_bytes as showdown_workspace_bytes,
)

DEFAULT_SHOWDOWN_CSV = Path(__file__).resolve().parents[1] / "data" / "showdown_current.csv"
DEFAULT_FANDUEL_SHOWDOWN_CSV = Path(__file__).resolve().parents[1] / "data" / "showdown_fanduel_current.csv"
ODDS_CURRENT_CSV = Path(__file__).resolve().parents[1] / "data" / "nfl_odds_current.csv"
ODDS_HISTORY_CSV = Path(__file__).resolve().parents[1] / "data" / "nfl_odds_history.csv"

st.set_page_config(page_title="NUKE Showdown Sim", page_icon="⚡", layout="wide")
render_nav()
st.title("⚡ NUKE SHOWDOWN")
site = st.radio("Platform", ["DraftKings", "FanDuel"], horizontal=True, key="showdown_site")
site_key = "dk" if site == "DraftKings" else "fd"
salary_cap = 50000 if site == "DraftKings" else FANDUEL_SHOWDOWN_SALARY_CAP
multiplier_label = "CPT" if site == "DraftKings" else "MVP"
flex_label = "FLEX" if site == "DraftKings" else "AnyFLEX"
st.caption(f"Projection-free {site} NFL single-game simulation · game scripts · {multiplier_label} outcomes · portfolio generation")

if st.session_state.get("showdown_last_site") != site:
    st.session_state["showdown_last_site"] = site
    st.session_state["showdown_min_salary"] = 42000 if site == "DraftKings" else 50000
    st.session_state["showdown_max_salary"] = salary_cap
    for _key in [
        "showdown_sim_results", "showdown_sim_portfolio", "showdown_sim_players",
        "showdown_sim_scripts", "showdown_sim_seed", "showdown_player_controls",
        "showdown_construction_controls",
    ]:
        st.session_state.pop(_key, None)

st.subheader("🏈 Current Game")
with st.expander(f"Optional: upload a different {site} Showdown salary CSV", expanded=False):
    upload = st.file_uploader(
        f"Override current {site} Showdown slate",
        type=["csv"],
        key=f"showdown_sim_upload_{site_key}",
        help=f"Normally you do not need this. NUKE automatically loads the current bundled {site} single-game slate.",
    )

try:
    if upload is not None:
        raw = pd.read_csv(upload)
        source_label = f"Uploaded override: {upload.name}"
    else:
        default_csv = DEFAULT_SHOWDOWN_CSV if site == "DraftKings" else DEFAULT_FANDUEL_SHOWDOWN_CSV
        if not default_csv.exists():
            st.error(f"The current {site} Showdown slate is not available yet.")
            st.stop()
        raw = pd.read_csv(default_csv)
        source_label = "Loaded automatically"
    if site == "DraftKings":
        players, meta = parse_showdown_salary_csv(raw)
    else:
        players, meta = parse_fanduel_showdown_csv(raw)
except Exception as exc:
    st.error(f"Could not read this {site} Showdown slate: {exc}")
    st.stop()

slate_sig = f"{site}|{meta['game_info']}|{len(players)}|{source_label}"

with st.sidebar:
    st.divider()
    st.markdown("### 💾 Showdown Workspace")
    st.caption("Save a true snapshot of this game, player controls, SIM settings, and completed results.")
    workspace_payload = showdown_workspace_bytes(st.session_state, meta["game_info"], site)
    st.download_button(
        "SAVE WORKSPACE",
        data=workspace_payload,
        file_name=f"nuke_showdown_{site_key}_workspace.json",
        mime="application/json",
        use_container_width=True,
        key="showdown_workspace_download",
    )
    workspace_upload = st.file_uploader(
        "Load workspace",
        type=["json"],
        key="showdown_workspace_upload",
        help="Loads player controls, simulation settings, and saved SIM results for this same Showdown game.",
    )
    if st.button(
        "LOAD WORKSPACE",
        use_container_width=True,
        disabled=workspace_upload is None,
        key="showdown_workspace_load_button",
    ):
        try:
            loaded_workspace = load_showdown_workspace_bytes(workspace_upload.getvalue())
            saved_slate = str(loaded_workspace.get("slate_label", "") or "")
            saved_platform = str(loaded_workspace.get("platform", "") or "")
            current_slate = str(meta.get("game_info", "") or "")
            if saved_platform and saved_platform != site:
                raise ValueError(f"This workspace is for {saved_platform}, but the current platform is {site}.")
            if saved_slate and saved_slate != current_slate:
                raise ValueError(
                    f"This workspace is for {saved_slate}, but the current Showdown slate is {current_slate}."
                )
            apply_showdown_workspace(st.session_state, loaded_workspace)
            st.session_state["showdown_workspace_loaded_notice"] = True
            st.rerun()
        except Exception as exc:
            st.error(f"Could not load Showdown workspace: {exc}")

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
if st.session_state.pop("showdown_workspace_loaded_notice", False):
    if st.session_state.get("showdown_sim_results") is not None:
        st.success("Showdown workspace loaded — saved SIM results and portfolio restored.")
    else:
        st.success("Showdown workspace loaded.")
if st.session_state.pop("showdown_workspace_run_ready_notice", False):
    st.success("Showdown SIM complete. Workspace save is ready with these results.")
flagged = all_player_count - len(players)
if flagged:
    st.caption(f"{flagged} OUT/IR player{'s' if flagged != 1 else ''} automatically excluded from the simulation pool.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Game", f"{team_a} vs {team_b}")
m2.metric("Active Players", len(players))
m3.metric("Format", f"1 {multiplier_label} + 5 {flex_label}")
m4.metric("Cap", f"${salary_cap:,}")

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
                "Salary": st.column_config.NumberColumn(flex_label, format="$%d", width="small"),
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

st.subheader("🧱 Construction Limits")
st.caption("Control the team build mix in the final portfolio. 3-3 is even; team-specific 4-2 and 5-1 builds show which team supplies the majority of the lineup.")
construction_styles = [f"{team_a} 5-1", f"{team_b} 5-1", f"{team_a} 4-2", f"{team_b} 4-2", "3-3 Even"]
construction_state = dict(st.session_state.get("showdown_construction_controls", {}) or {})
construction_rows = []
for style in construction_styles:
    cfg = construction_state.get(style, {})
    construction_rows.append({
        "Construction": style,
        "Min %": int(cfg.get("min", 0)),
        "Max %": int(cfg.get("max", 100)),
    })
construction_editor_version = int(st.session_state.get("showdown_construction_editor_version", 0))
construction_editor = st.data_editor(
    pd.DataFrame(construction_rows),
    use_container_width=True,
    hide_index=True,
    disabled=["Construction"],
    column_config={
        "Construction": st.column_config.TextColumn("Construction", width="medium"),
        "Min %": st.column_config.NumberColumn("Min %", min_value=0, max_value=100, step=1, format="%d%%", width="small"),
        "Max %": st.column_config.NumberColumn("Max %", min_value=0, max_value=100, step=1, format="%d%%", width="small"),
    },
    key=f"showdown_construction_editor_{construction_editor_version}",
)
construction_state = {}
for _, row in construction_editor.iterrows():
    mn = int(row["Min %"]); mx = int(row["Max %"])
    if mn > mx:
        mn = mx
    construction_state[str(row["Construction"])] = {"min": mn, "max": mx}
st.session_state["showdown_construction_controls"] = construction_state
construction_mins = {k: float(v["min"]) / 100.0 for k, v in construction_state.items()}
construction_maxes = {k: float(v["max"]) / 100.0 for k, v in construction_state.items()}
if sum(v["min"] for v in construction_state.values()) > 100:
    st.warning("Construction minimums add up to more than 100%. Lower the Min % values before running the SIM.")

with st.expander("Simulation Settings", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    n_sims = c1.selectbox("Game simulations", [2000, 5000, 10000], index=1, key="showdown_game_sims")
    candidates = c2.selectbox("Candidate lineups", [3000, 6000, 12000], index=1, key="showdown_candidates")
    portfolio_n = c3.selectbox("Portfolio lineups", [5, 10, 20, 50, 100, 150], index=2, key="showdown_portfolio_n")
    c4.caption("Salary range applies to every generated candidate lineup.")
    s1, s2 = st.columns(2)
    salary_floor_min = 30000
    min_salary = s1.slider("Minimum salary", salary_floor_min, salary_cap, 42000 if site == "DraftKings" else 50000, 100, key="showdown_min_salary")
    max_salary = s2.slider(
        "Maximum salary", salary_floor_min, salary_cap, salary_cap, 100, key="showdown_max_salary",
        help=f"Set below ${salary_cap:,} to intentionally leave salary unused and reduce duplicated Showdown constructions.",
    )
    if max_salary < min_salary:
        st.warning("Maximum salary is below Minimum salary. Raise Max or lower Min before running the SIM.")
    c5, c6 = st.columns(2)
    max_player = c5.slider("Max player exposure", 25, 100, 75, 5, key="showdown_max_player") / 100
    max_cpt = c6.slider(f"Max {multiplier_label} exposure", 10, 100, 35, 5, key="showdown_max_cpt") / 100

    st.markdown("##### Randomness")
    r1, r2 = st.columns([1, 2])
    fixed_seed = r1.checkbox(
        "Use fixed seed",
        value=False,
        help="Off = every run gets a fresh random seed. Turn on only when you want to reproduce the exact same simulation.",
        key="showdown_fixed_seed",
    )
    manual_seed = r2.number_input(
        "Seed",
        min_value=1,
        max_value=2147483646,
        value=260905,
        step=1,
        disabled=not fixed_seed,
        key="showdown_manual_seed",
    )
    if not fixed_seed:
        st.caption("Fresh random seed will be generated each time you click RUN SHOWDOWN SIM.")

st.markdown("#### What NUKE is simulating")
st.caption(
    "Balanced · Shootout · Low Scoring · each team controlling the game · Passing Spike · "
    f"Rushing Control · Chaos. Player outcomes use {site} salary/FPPG as baseline signals "
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
            max_salary=max_salary,
            salary_cap=salary_cap,
            seed=seed,
        )
        results = evaluate_candidates(players, cand, sims, scripts)
        portfolio = build_portfolio(
            results, players, count=portfolio_n,
            max_player_pct=max_player, max_cpt_pct=max_cpt,
            player_mins=player_mins, player_maxes=player_maxes,
            construction_mins=construction_mins, construction_maxes=construction_maxes,
        )
        st.session_state["showdown_sim_results"] = results
        st.session_state["showdown_sim_portfolio"] = portfolio
        st.session_state["showdown_sim_players"] = players
        st.session_state["showdown_sim_scripts"] = pd.Series(scripts).value_counts().to_dict()
        st.session_state["showdown_sim_seed"] = seed
        st.session_state["showdown_workspace_run_ready_notice"] = True
    st.rerun()

results = st.session_state.get("showdown_sim_results")
portfolio = st.session_state.get("showdown_sim_portfolio")
sim_players = st.session_state.get("showdown_sim_players")
run_seed = st.session_state.get("showdown_sim_seed")
if results is None or sim_players is None or results.empty:
    st.stop()

if run_seed:
    st.caption(f"Current run seed: {int(run_seed):,}")
if st.session_state.pop("showdown_construction_rebuild_notice", False):
    st.success("Construction mix applied — portfolio rebuilt from the existing SIM results. No new football simulation was required.")

st.subheader("Top Simulated Lineups")
labeled = add_lineup_labels(results.head(250), sim_players)
if site == "FanDuel":
    labeled = labeled.rename(columns={"CPT": "MVP"})
show_cols = [
    multiplier_label, "FLEX1", "FLEX2", "FLEX3", "FLEX4", "FLEX5", "Construction", "Salary",
    "NUKE Score", "Mean", "Ceiling", "P95", "Top 1% Score",
]
st.dataframe(
    labeled[show_cols].round(2),
    use_container_width=True,
    hide_index=True,
    column_config={"Salary": st.column_config.NumberColumn("Salary", format="$%d")},
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
    if site == "FanDuel":
        p = p.rename(columns={"CPT": "MVP"})
    st.dataframe(
        p[show_cols].round(2),
        use_container_width=True,
        hide_index=True,
        column_config={"Salary": st.column_config.NumberColumn("Salary", format="$%d")},
    )

    st.markdown("""
    <style id="showdown-dk-export-green">
    div[data-testid="stDownloadButton"] button[kind="primary"] {
        background: #16a34a !important;
        border-color: #16a34a !important;
        color: white !important;
    }
    div[data-testid="stDownloadButton"] button[kind="primary"]:hover {
        background: #15803d !important;
        border-color: #15803d !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f"#### 📤 {site} Export")
    st.caption(f"Download this exact NUKE portfolio using the {site} {multiplier_label}/{flex_label} player IDs from the current single-game salary file.")
    export_rows = []
    export_error = None
    sim_rows = sim_players.reset_index(drop=True)
    try:
        for _, lineup in portfolio.iterrows():
            cpt_idx = int(lineup["_cpt"])
            flex_idxs = list(map(int, lineup["_flex"]))
            all_idxs = [cpt_idx] + flex_idxs
            if len(all_idxs) != 6 or len(set(all_idxs)) != 6:
                raise ValueError("A portfolio lineup does not contain 6 unique players.")
            salary = int(lineup["Salary"])
            if salary > salary_cap:
                raise ValueError(f"A portfolio lineup exceeds the {site} salary cap: ${salary:,}.")
            cpt_key = str(sim_rows.iloc[cpt_idx]["Player Key"])
            flex_keys = [str(sim_rows.iloc[i]["Player Key"]) for i in flex_idxs]
            export_rows.append({
                "captain_key": cpt_key,
                "flex_keys": flex_keys,
                "salary": salary,
            })

        players_by_key = {
            str(r["Player Key"]): r.to_dict()
            for _, r in sim_rows.iterrows()
        }
        for rec in export_rows:
            cpt = players_by_key.get(rec["captain_key"])
            flex = [players_by_key.get(k) for k in rec["flex_keys"]]
            if cpt is None or any(x is None for x in flex):
                raise ValueError(f"A portfolio player could not be matched back to the current {site} salary file.")
            if not str(cpt.get("CPT ID", "")).strip() or any(not str(x.get("FLEX ID", "")).strip() for x in flex):
                raise ValueError(f"A {site} {multiplier_label}/{flex_label} player ID is missing from the current salary file.")

        export_csv = export_lineup_only_csv(export_rows, players_by_key) if site == "DraftKings" else export_fanduel_lineup_only_csv(export_rows, players_by_key)
    except Exception as exc:
        export_error = str(exc)
        export_csv = None

    if export_error:
        st.error(f"{site} export is not ready: {export_error}")
    else:
        st.download_button(
            f"DOWNLOAD {'DK' if site == 'DraftKings' else 'FANDUEL'} SHOWDOWN CSV",
            data=export_csv,
            file_name=f"nuke_showdown_{site_key}_portfolio.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
            key=f"showdown_{site_key}_export_download",
        )
        st.caption(f"{len(export_rows)} lineup{'s' if len(export_rows) != 1 else ''} ready for {site}.")

    overall, captains = exposure_table(portfolio, sim_players)
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("#### Player Exposure")
        st.dataframe(overall, use_container_width=True, hide_index=True)
    with e2:
        st.markdown(f"#### {multiplier_label} Exposure")
        st.dataframe(captains, use_container_width=True, hide_index=True)

    construction_counts = p["Construction"].value_counts().reindex(construction_styles, fill_value=0)
    construction_mix = construction_counts.rename_axis("Construction").reset_index(name="Lineups")
    construction_mix["Construction %"] = (100.0 * construction_mix["Lineups"] / max(1, len(p))).round(1)
    construction_mix["Min %"] = construction_mix["Construction"].map(lambda x: construction_state.get(x, {}).get("min", 0))
    construction_mix["Max %"] = construction_mix["Construction"].map(lambda x: construction_state.get(x, {}).get("max", 100))
    st.markdown("#### Construction Mix")
    st.caption("Type new Min/Max percentages below, then rebuild the portfolio instantly from this completed SIM. Values are limited to 0–100%.")
    with st.form("showdown_construction_results_form", clear_on_submit=False):
        mix_editor = st.data_editor(
            construction_mix,
            use_container_width=True,
            hide_index=True,
            disabled=["Construction", "Lineups", "Construction %"],
            column_config={
                "Construction": st.column_config.TextColumn("Construction", width="medium"),
                "Lineups": st.column_config.NumberColumn("Lineups", width="small"),
                "Construction %": st.column_config.NumberColumn("Construction %", min_value=0.0, max_value=100.0, format="%.1f%%", width="small"),
                "Min %": st.column_config.NumberColumn("Min %", min_value=0, max_value=100, step=1, format="%d%%", width="small"),
                "Max %": st.column_config.NumberColumn("Max %", min_value=0, max_value=100, step=1, format="%d%%", width="small"),
            },
            key="showdown_construction_results_editor",
        )
        apply_mix = st.form_submit_button("APPLY MIX & REBUILD PORTFOLIO", type="primary", use_container_width=True)

    if apply_mix:
        new_state = {}
        errors = []
        for _, er in mix_editor.iterrows():
            style = str(er["Construction"])
            mn = int(er["Min %"]); mx = int(er["Max %"])
            if mn < 0 or mn > 100 or mx < 0 or mx > 100:
                errors.append(f"{style}: percentages must be between 0 and 100.")
            if mn > mx:
                errors.append(f"{style}: Min % cannot be greater than Max %.")
            new_state[style] = {"min": mn, "max": mx}

        if sum(v["min"] for v in new_state.values()) > 100:
            errors.append("Construction minimums cannot add up to more than 100%.")
        if sum(v["max"] for v in new_state.values()) < 100:
            errors.append("Construction maximums must add up to at least 100% so a full portfolio is possible.")

        if errors:
            for msg in errors:
                st.error(msg)
        else:
            new_mins = {k: v["min"] / 100.0 for k, v in new_state.items()}
            new_maxes = {k: v["max"] / 100.0 for k, v in new_state.items()}
            rebuilt = build_portfolio(
                results, sim_players, count=portfolio_n,
                max_player_pct=max_player, max_cpt_pct=max_cpt,
                player_mins=player_mins, player_maxes=player_maxes,
                construction_mins=new_mins, construction_maxes=new_maxes,
            )
            st.session_state["showdown_construction_controls"] = new_state
            st.session_state["showdown_sim_portfolio"] = rebuilt
            st.session_state["showdown_construction_editor_version"] = construction_editor_version + 1
            st.session_state["showdown_construction_rebuild_notice"] = True
            st.rerun()

st.info(
    "Showdown SIM V1 intentionally ranks lineups by simulated outcome quality rather than contest payout simulation. "
    "The next layer is ownership/duplication leverage once we have a reliable public ownership signal."
)

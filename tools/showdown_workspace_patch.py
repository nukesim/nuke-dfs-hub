from pathlib import Path

p = Path("pages/13_SHOWDOWN_SIM.py")
s = p.read_text(encoding="utf-8")

# Imports.
anchor = '''from nuke_showdown_sim import (
    SCRIPT_NAMES, add_lineup_labels, build_portfolio, evaluate_candidates,
    exposure_table, generate_showdown_candidates, simulate_player_outcomes,
)
'''
replacement = anchor + '''from nuke_showdown_workspace import (
    apply_workspace as apply_showdown_workspace,
    load_workspace_bytes as load_showdown_workspace_bytes,
    workspace_bytes as showdown_workspace_bytes,
)
'''
if anchor not in s:
    raise SystemExit("showdown sim import anchor not found")
s = s.replace(anchor, replacement, 1)

# Workspace UI after current slate has been parsed, but before slate-change cleanup.
anchor = '''slate_sig = f"{meta['game_info']}|{len(players)}|{source_label}"
if st.session_state.get("showdown_sim_slate_sig") != slate_sig:
'''
replacement = '''slate_sig = f"{meta['game_info']}|{len(players)}|{source_label}"

with st.sidebar:
    st.divider()
    st.markdown("### 💾 Showdown Workspace")
    st.caption("Save a true snapshot of this game, player controls, SIM settings, and completed results.")
    workspace_payload = showdown_workspace_bytes(st.session_state, meta["game_info"])
    st.download_button(
        "SAVE WORKSPACE",
        data=workspace_payload,
        file_name="nuke_showdown_workspace.json",
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
            current_slate = str(meta.get("game_info", "") or "")
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
'''
if anchor not in s:
    raise SystemExit("slate sig anchor not found")
s = s.replace(anchor, replacement, 1)

# Show a restore confirmation after rerun.
anchor = '''st.success(f"{source_label}: {team_a} @ {team_b} · {meta['game_info']}")
flagged = all_player_count - len(players)
'''
replacement = '''st.success(f"{source_label}: {team_a} @ {team_b} · {meta['game_info']}")
if st.session_state.pop("showdown_workspace_loaded_notice", False):
    if st.session_state.get("showdown_sim_results") is not None:
        st.success("Showdown workspace loaded — saved SIM results and portfolio restored.")
    else:
        st.success("Showdown workspace loaded.")
if st.session_state.pop("showdown_workspace_run_ready_notice", False):
    st.success("Showdown SIM complete. Workspace save is ready with these results.")
flagged = all_player_count - len(players)
'''
if anchor not in s:
    raise SystemExit("success anchor not found")
s = s.replace(anchor, replacement, 1)

# Give all simulation controls stable keys so they survive workspace load.
repls = {
    'n_sims = c1.selectbox("Game simulations", [2000, 5000, 10000], index=1)':
        'n_sims = c1.selectbox("Game simulations", [2000, 5000, 10000], index=1, key="showdown_game_sims")',
    'candidates = c2.selectbox("Candidate lineups", [3000, 6000, 12000], index=1)':
        'candidates = c2.selectbox("Candidate lineups", [3000, 6000, 12000], index=1, key="showdown_candidates")',
    'min_salary = c3.slider("Minimum salary", 30000, 50000, 42000, 500)':
        'min_salary = c3.slider("Minimum salary", 30000, 50000, 42000, 500, key="showdown_min_salary")',
    'portfolio_n = c4.selectbox("Portfolio lineups", [5, 10, 20, 50, 100, 150], index=2)':
        'portfolio_n = c4.selectbox("Portfolio lineups", [5, 10, 20, 50, 100, 150], index=2, key="showdown_portfolio_n")',
    'max_player = c5.slider("Max player exposure", 25, 100, 75, 5) / 100':
        'max_player = c5.slider("Max player exposure", 25, 100, 75, 5, key="showdown_max_player") / 100',
    'max_cpt = c6.slider("Max Captain exposure", 10, 100, 35, 5) / 100':
        'max_cpt = c6.slider("Max Captain exposure", 10, 100, 35, 5, key="showdown_max_cpt") / 100',
    '        help="Off = every run gets a fresh random seed. Turn on only when you want to reproduce the exact same simulation.",\n    )':
        '        help="Off = every run gets a fresh random seed. Turn on only when you want to reproduce the exact same simulation.",\n        key="showdown_fixed_seed",\n    )',
    '        disabled=not fixed_seed,\n    )':
        '        disabled=not fixed_seed,\n        key="showdown_manual_seed",\n    )',
}
for old, new in repls.items():
    if old not in s:
        raise SystemExit(f"settings anchor not found: {old[:60]}")
    s = s.replace(old, new, 1)

# After a fresh run, rerun once so the sidebar download payload contains the just-created results.
anchor = '''        st.session_state["showdown_sim_scripts"] = pd.Series(scripts).value_counts().to_dict()
        st.session_state["showdown_sim_seed"] = seed
    st.success(
        f"Showdown SIM complete · seed {seed:,} · {n_sims:,} game outcomes · "
        f"{len(cand):,} legal candidate lineups"
    )
'''
replacement = '''        st.session_state["showdown_sim_scripts"] = pd.Series(scripts).value_counts().to_dict()
        st.session_state["showdown_sim_seed"] = seed
        st.session_state["showdown_workspace_run_ready_notice"] = True
    st.rerun()
'''
if anchor not in s:
    raise SystemExit("post-run rerun anchor not found")
s = s.replace(anchor, replacement, 1)

p.write_text(s, encoding="utf-8")
print("patched Showdown true-snapshot workspace support")
# retrigger after verification marker fix

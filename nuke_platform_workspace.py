WORKSPACE_KEYS = [
    "nuke_sim_results",
    "nuke_sim_players",
    "nuke_sim_exposure",
    "nuke_path_exposure",
    "nuke_contest_results",
    "nuke_contest_summary",
    "nuke_portfolio",
    "nuke_portfolio_paths",
    "nuke_portfolio_stats",
    "nuke_sim_runtime",
    "nuke_stage_times",
    "nuke_candidate_diagnostics",
    "nuke_player_takes",
    "nuke_shared_portfolio_rows",
    "nuke_shared_portfolio_version",
    "nuke_pregame_pool",
    "nuke_pool_editor_version",
    "nuke_sim_hub_signature",
    "nuke_active_pool_game",
]


def switch_workspace(session_state, target_site):
    """Save the current site's SIM workspace and restore the target site's workspace.

    Workspaces live only for the current Streamlit session. Nothing is deleted when
    switching DK <-> FD; a platform starts clean only if it has not been used yet.
    """
    target_site = str(target_site or "DK").upper()
    previous_site = session_state.get("nuke_sim_active_site")
    workspaces = session_state.setdefault("nuke_platform_workspaces", {})

    restored = False
    if previous_site is not None and previous_site != target_site:
        # Save references to the current immutable/result objects and state dicts.
        # Streamlit keeps these objects alive for the session, so no serialization is needed.
        workspaces[previous_site] = {
            key: session_state[key]
            for key in WORKSPACE_KEYS
            if key in session_state
        }

        # Clear only the live workspace slots before restoring the other platform.
        for key in WORKSPACE_KEYS:
            session_state.pop(key, None)

        saved = workspaces.get(target_site, {})
        for key, value in saved.items():
            session_state[key] = value
        restored = bool(saved)

    session_state["nuke_sim_active_site"] = target_site
    session_state["nuke_platform_workspaces"] = workspaces
    return previous_site, restored


def workspace_status(session_state, site):
    site = str(site or "DK").upper()
    current = session_state.get("nuke_sim_active_site")
    if current == site:
        has_results = any(
            key in session_state
            for key in ("nuke_sim_results", "nuke_contest_results", "nuke_portfolio", "nuke_pregame_pool")
        )
        return has_results
    saved = session_state.get("nuke_platform_workspaces", {}).get(site, {})
    return bool(saved)

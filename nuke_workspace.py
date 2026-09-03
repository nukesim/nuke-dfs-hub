import json
from datetime import datetime, timezone

WORKSPACE_VERSION = 1

CONTROL_KEYS = [
    "dfs_site", "sim_preset", "candidate_lineups", "football_universes", "exposure_sample",
    "use_reproducible_seed", "nuke_manual_seed", "field_size", "entry_fee", "first_prize",
    "contest_iterations", "portfolio_size", "max_player_overlap", "path_diversification",
    "max_player_exposure", "max_qb_exposure", "max_team_exposure", "max_game_exposure",
    "min_salary_DK", "min_salary_FD",
]

STATE_KEYS = [
    "nuke_pregame_pool", "nuke_player_takes", "nuke_pool_editor_version",
    "nuke_sim_hub_signature",
]


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    try:
        return value.item()
    except Exception:
        return str(value)


def build_workspace(session_state, slate_label=""):
    controls = {k: _json_safe(session_state[k]) for k in CONTROL_KEYS if k in session_state}
    state = {k: _json_safe(session_state[k]) for k in STATE_KEYS if k in session_state}
    return {
        "product": "NUKE SIM",
        "workspace_version": WORKSPACE_VERSION,
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "slate_label": str(slate_label or ""),
        "controls": controls,
        "state": state,
    }


def workspace_bytes(session_state, slate_label=""):
    return json.dumps(build_workspace(session_state, slate_label), indent=2, sort_keys=True).encode("utf-8")


def load_workspace_bytes(data):
    if not data:
        raise ValueError("Workspace file is empty")
    obj = json.loads(data.decode("utf-8-sig"))
    if obj.get("product") != "NUKE SIM":
        raise ValueError("This is not a NUKE SIM workspace file")
    if int(obj.get("workspace_version", 0)) > WORKSPACE_VERSION:
        raise ValueError("This workspace was created by a newer NUKE SIM version")
    return obj


def apply_workspace(session_state, workspace):
    controls = workspace.get("controls", {}) or {}
    for key, value in controls.items():
        if key in CONTROL_KEYS:
            session_state[key] = value

    state = workspace.get("state", {}) or {}
    for key, value in state.items():
        if key not in STATE_KEYS:
            continue
        if key == "nuke_player_takes" and isinstance(value, dict):
            converted = {}
            for pid, pref in value.items():
                try:
                    converted[int(pid)] = pref
                except Exception:
                    converted[pid] = pref
            value = converted
        session_state[key] = value

    # Results are intentionally not restored. Loading a workspace returns the user to the
    # saved inputs/pool and lets them run against the latest odds/injury data.
    for key in [
        "nuke_sim_results", "nuke_sim_players", "nuke_sim_exposure", "nuke_path_exposure",
        "nuke_contest_results", "nuke_contest_summary", "nuke_portfolio", "nuke_portfolio_paths",
        "nuke_portfolio_stats", "nuke_sim_runtime", "nuke_stage_times", "nuke_candidate_diagnostics",
        "nuke_shared_portfolio_rows", "nuke_shared_portfolio_version",
    ]:
        session_state.pop(key, None)

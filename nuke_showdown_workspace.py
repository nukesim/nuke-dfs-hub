import json
from datetime import datetime, timezone

import pandas as pd

WORKSPACE_VERSION = 1

CONTROL_KEYS = [
    "showdown_player_controls",
    "showdown_game_sims",
    "showdown_candidates",
    "showdown_min_salary",
    "showdown_max_salary",
    "showdown_portfolio_n",
    "showdown_max_player",
    "showdown_max_cpt",
    "showdown_fixed_seed",
    "showdown_manual_seed",
    "showdown_construction_controls",
]

STATE_KEYS = [
    "showdown_sim_slate_sig",
]

RESULT_KEYS = [
    "showdown_sim_results",
    "showdown_sim_portfolio",
    "showdown_sim_players",
    "showdown_sim_scripts",
    "showdown_sim_seed",
]


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, pd.DataFrame):
        return {
            "__nuke_type__": "dataframe",
            "columns": [str(c) for c in value.columns],
            "records": [
                {str(k): _json_safe(v) for k, v in row.items()}
                for row in value.to_dict(orient="records")
            ],
        }
    if isinstance(value, pd.Series):
        return {
            "__nuke_type__": "series",
            "name": str(value.name) if value.name is not None else None,
            "values": [_json_safe(v) for v in value.tolist()],
        }
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    try:
        return value.item()
    except Exception:
        return str(value)


def _restore_json(value):
    if isinstance(value, list):
        return [_restore_json(v) for v in value]
    if not isinstance(value, dict):
        return value
    marker = value.get("__nuke_type__")
    if marker == "dataframe":
        cols = list(value.get("columns", []) or [])
        records = [
            {k: _restore_json(v) for k, v in row.items()}
            for row in (value.get("records", []) or [])
        ]
        return pd.DataFrame(records, columns=cols)
    if marker == "series":
        return pd.Series(
            [_restore_json(v) for v in (value.get("values", []) or [])],
            name=value.get("name"),
        )
    return {k: _restore_json(v) for k, v in value.items()}


def build_workspace(session_state, slate_label="", platform=""):
    return {
        "product": "NUKE SHOWDOWN",
        "workspace_version": WORKSPACE_VERSION,
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "slate_label": str(slate_label or ""),
        "platform": str(platform or ""),
        "controls": {
            k: _json_safe(session_state[k]) for k in CONTROL_KEYS if k in session_state
        },
        "state": {
            k: _json_safe(session_state[k]) for k in STATE_KEYS if k in session_state
        },
        "results": {
            k: _json_safe(session_state[k]) for k in RESULT_KEYS if k in session_state
        },
    }


def workspace_bytes(session_state, slate_label="", platform=""):
    return json.dumps(
        build_workspace(session_state, slate_label, platform), indent=2, sort_keys=True
    ).encode("utf-8")


def load_workspace_bytes(data):
    if not data:
        raise ValueError("Workspace file is empty")
    obj = json.loads(data.decode("utf-8-sig"))
    if obj.get("product") != "NUKE SHOWDOWN":
        raise ValueError("This is not a NUKE Showdown workspace file")
    if int(obj.get("workspace_version", 0)) > WORKSPACE_VERSION:
        raise ValueError("This workspace was created by a newer NUKE Showdown version")
    return obj


def apply_workspace(session_state, workspace):
    for key, value in (workspace.get("controls", {}) or {}).items():
        if key in CONTROL_KEYS:
            session_state[key] = _restore_json(value)
    for key, value in (workspace.get("state", {}) or {}).items():
        if key in STATE_KEYS:
            session_state[key] = _restore_json(value)
    for key in RESULT_KEYS:
        session_state.pop(key, None)
    for key, value in (workspace.get("results", {}) or {}).items():
        if key in RESULT_KEYS:
            session_state[key] = _restore_json(value)

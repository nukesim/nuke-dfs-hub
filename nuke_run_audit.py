from __future__ import annotations

from datetime import datetime, timezone


AUDIT_VERSION = "Run Audit V1"


def make_run_audit(*, slate, preset, seed, fixed_seed, candidates, football_universes,
                   field_size, entry_fee, first_prize, contest_iterations, portfolio_size,
                   min_salary, runtime, football_engine, portfolio_engine, candidate_health=None):
    health = candidate_health or {}
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "slate": str(slate),
        "preset": str(preset),
        "seed": int(seed),
        "seed_mode": "Fixed" if fixed_seed else "Random",
        "candidates": int(candidates),
        "football_universes": int(football_universes),
        "field_size": int(field_size),
        "entry_fee": float(entry_fee),
        "first_prize": float(first_prize),
        "contest_iterations": int(contest_iterations),
        "portfolio_size": int(portfolio_size),
        "min_salary": int(min_salary),
        "runtime_seconds": float(runtime),
        "football_engine": str(football_engine),
        "portfolio_engine": str(portfolio_engine),
        "candidate_grade": str(health.get("grade", "—")),
        "candidate_score": float(health.get("score", 0.0)),
    }


def audit_rows(audit):
    if not audit:
        return []
    return [
        ("Slate", audit.get("slate", "—")),
        ("Run", audit.get("timestamp", "—")),
        ("Preset", audit.get("preset", "—")),
        ("Seed", f"{audit.get('seed', '—')} · {audit.get('seed_mode', '—')}"),
        ("Candidates", f"{int(audit.get('candidates', 0)):,}"),
        ("Football Universes", f"{int(audit.get('football_universes', 0)):,}"),
        ("Contest", f"{int(audit.get('field_size', 0)):,} field · ${float(audit.get('entry_fee', 0)):,.2f} entry"),
        ("Portfolio", f"{int(audit.get('portfolio_size', 0)):,} lineups"),
        ("Engines", f"{audit.get('football_engine', '—')} · {audit.get('portfolio_engine', '—')}"),
        ("Candidate Health", f"{audit.get('candidate_grade', '—')} · {float(audit.get('candidate_score', 0)):.0f}/100"),
        ("Runtime", f"{float(audit.get('runtime_seconds', 0)):.1f}s"),
    ]


# Only weekly/work-product state is cleared. UI preferences and sidebar settings remain intact.
WEEKLY_STATE_KEYS = {
    "nuke_pregame_pool", "nuke_pool_editor_version", "nuke_sim_hub_signature",
    "nuke_sim_results", "nuke_sim_players", "nuke_sim_exposure", "nuke_path_exposure",
    "nuke_contest_results", "nuke_contest_summary", "nuke_portfolio", "nuke_portfolio_paths",
    "nuke_portfolio_stats", "nuke_sim_runtime", "nuke_stage_times", "nuke_candidate_diagnostics",
    "nuke_player_takes", "nuke_shared_portfolio_rows", "nuke_shared_portfolio_version",
    "nuke_hub_imported_portfolio_version", "nuke_last_run_audit", "nuke_run_history",
    "pool_ids", "pending_pool_ids", "projection_overrides", "saved_lineups", "lineups",
    "active_lineup", "qb_plan", "game_totals", "game_totals_source", "model_df", "model_errors",
    "depth_df", "nuke_hub_bridge_ready", "nuke_hub_bridge_version", "nuke_hub_pool_ids",
    "nuke_hub_role_adjustments",
}


def reset_week_state(session_state):
    removed = []
    for key in list(WEEKLY_STATE_KEYS):
        if key in session_state:
            del session_state[key]
            removed.append(key)
    # Dynamic data-editor/form keys can otherwise preserve prior-week selections.
    for key in list(session_state.keys()):
        sk = str(key)
        if sk.startswith(("game_pool_", "game_bulk_", "team_bulk_", "pool_form_", "nuke_active_pool_game")):
            del session_state[key]
            removed.append(sk)
    session_state["nuke_week_reset_notice"] = True
    return removed

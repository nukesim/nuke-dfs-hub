"""Validated Football Engine V2.1 + live game-environment layer.

V2.1 preserves the original generative Football Engine V2 and applies the
position-level mean/spread calibration learned only from 2017 Weeks 1-8.
Those frozen calibration parameters subsequently passed the untouched 2017
Weeks 9-17 holdout and independent 2018-2021 validation.

On live slates NUKE can additionally apply current sportsbook consensus as a
bounded game-context layer (team total, game total, spread). That live context
is intentionally separate from the frozen V2.1 calibration and should not be
described as historically validated by the V2.1 tests.
"""
import numpy as np

from nuke_football_v2 import simulate_player_matrix_v2

ENGINE_VERSION = "Football Engine V2.1 + Live Game Environment"
CALIBRATION_TRAINING = "2017 Weeks 1-8"
CALIBRATION_VALIDATION = "2017 Weeks 9-17 holdout + independent 2018-2021"

# Frozen, predeclared values. Live slates never refit these parameters.
V21_POSITION_CALIBRATION = {
    "QB": {"bias": 3.4650, "spread": 1.2697},
    "RB": {"bias": 1.3784, "spread": 1.2483},
    "WR": {"bias": 2.1108, "spread": 1.0861},
    "TE": {"bias": 0.7608, "spread": 1.0599},
    "DST": {"bias": 0.5466, "spread": 1.5753},
}


def apply_v21_calibration(players, matrix):
    """Apply the frozen V2.1 position calibration to a V2 outcome matrix."""
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != len(players):
        raise ValueError("Player table and simulation matrix do not align.")

    out = arr.copy()
    positions = players.Position.astype(str).to_numpy()
    for j, pos in enumerate(positions):
        cfg = V21_POSITION_CALIBRATION.get(pos, {"bias": 0.0, "spread": 1.0})
        col = arr[:, j]
        mean = float(np.mean(col))
        corrected_mean = mean - float(cfg["bias"])
        out[:, j] = corrected_mean + (col - mean) * float(cfg["spread"])
        floor = -6.0 if pos == "DST" else 0.0
        out[:, j] = np.maximum(floor, out[:, j])
    return out.astype(np.float32)


def _live_environment(players):
    """Build the current sportsbook environment without making a network call.

    nuke_odds reads the locally cached snapshot maintained by the scheduled
    GitHub workflow. Any failure simply returns None and V2.1 falls back to its
    original projection-free behavior.
    """
    try:
        from nuke_odds import load_current_odds
        from nuke_game_pool import game_environment
        odds = load_current_odds()
        if odds is None or odds.empty:
            return None
        env = game_environment(players, odds)
        if env is None or env.empty:
            return None
        if "Source" in env.columns and not env["Source"].astype(str).eq("Sportsbook Consensus").any():
            return None
        return env
    except Exception:
        return None


def simulate_player_matrix_v21(players, n_sims=1500, seed=26, game_environment=None):
    """Run V2 with bounded live market context, then frozen V2.1 calibration.

    Pass game_environment explicitly for testing/reproducibility. When omitted,
    the engine automatically uses NUKE's latest cached sportsbook snapshot.
    """
    env = game_environment if game_environment is not None else _live_environment(players)
    original = simulate_player_matrix_v2(
        players,
        n_sims=n_sims,
        seed=seed,
        game_environment=env,
    )
    return apply_v21_calibration(players, original)

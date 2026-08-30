"""Validated Football Engine V2.1.

V2.1 preserves the original generative Football Engine V2 and applies the
position-level mean/spread calibration learned only from 2017 Weeks 1-8.
Those parameters subsequently passed the untouched 2017 Weeks 9-17 holdout
and independent 2018-2021 validation.

Keeping V2 in a separate module gives NUKE a clean rollback/baseline path.
"""
import numpy as np

from nuke_football_v2 import simulate_player_matrix_v2

ENGINE_VERSION = "Football Engine V2.1"
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


def simulate_player_matrix_v21(players, n_sims=1500, seed=26):
    """Run generative V2, then apply the frozen validated V2.1 calibration."""
    original = simulate_player_matrix_v2(players, n_sims=n_sims, seed=seed)
    return apply_v21_calibration(players, original)

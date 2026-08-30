import numpy as np
import pandas as pd

from nuke_football_v21 import (
    V21_POSITION_CALIBRATION,
    apply_v21_calibration,
)


def test_v21_shifts_and_widens_qb_distribution():
    players = pd.DataFrame({"Position": ["QB"]})
    matrix = np.array([[10.0], [20.0], [30.0]], dtype=np.float32)
    out = apply_v21_calibration(players, matrix)
    cfg = V21_POSITION_CALIBRATION["QB"]
    assert out.shape == matrix.shape
    assert np.isclose(out[:, 0].mean(), matrix[:, 0].mean() - cfg["bias"], atol=1e-5)
    assert out[:, 0].std() > matrix[:, 0].std()


def test_v21_respects_non_dst_floor():
    players = pd.DataFrame({"Position": ["RB"]})
    matrix = np.array([[0.0], [0.1], [0.2]], dtype=np.float32)
    out = apply_v21_calibration(players, matrix)
    assert float(out.min()) >= 0.0


def test_v21_respects_dst_floor():
    players = pd.DataFrame({"Position": ["DST"]})
    matrix = np.array([[-6.0], [-2.0], [2.0]], dtype=np.float32)
    out = apply_v21_calibration(players, matrix)
    assert float(out.min()) >= -6.0

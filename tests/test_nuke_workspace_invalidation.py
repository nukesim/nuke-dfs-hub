import pandas as pd

from nuke_workspace import RESULT_KEYS, invalidate_sim_results


def test_flex_change_invalidates_every_stale_sim_output():
    state = {key: pd.DataFrame({"stale": [1]}) for key in RESULT_KEYS}
    state["nuke_flex_position_FD"] = "RB"
    state["_nuke_workspace_export_cache"] = {"data": b"stale"}

    removed = invalidate_sim_results(state)

    assert set(removed) == set(RESULT_KEYS)
    assert not any(key in state for key in RESULT_KEYS)
    assert "_nuke_workspace_export_cache" not in state
    assert state["nuke_flex_position_FD"] == "RB"

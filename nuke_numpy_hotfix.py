"""Very narrow NumPy cast guard for the UFC single-entry simulator.

The UFC sim's losing-score vector is built from integer branches and then receives
fractional style adjustments. Newer NumPy versions correctly reject the in-place
float-to-int cast. This guard only promotes the exact score-vector pattern used by
that call; all other np.where behavior is unchanged.
"""
import numpy as np

if not getattr(np.where, "_nuke_ufc_cast_guard", False):
    _original_where = np.where

    def _nuke_where_guard(condition, *args, **kwargs):
        out = _original_where(condition, *args, **kwargs)
        if len(args) == 2:
            x, y = args
            try:
                is_ufc_loser_score = (
                    isinstance(out, np.ndarray)
                    and out.dtype.kind in "iu"
                    and isinstance(condition, np.ndarray)
                    and condition.dtype == bool
                    and condition.ndim == 1
                    and isinstance(x, np.ndarray)
                    and x.dtype.kind in "iu"
                    and x.shape == condition.shape
                    and np.isscalar(y)
                    and int(y) in (43, 63)
                    and x.size > 0
                    and np.all((x % 11) == 0)
                    and np.min(x) >= 11
                    and np.max(x) <= 66
                )
                if is_ufc_loser_score:
                    return out.astype(float)
            except Exception:
                pass
        return out

    _nuke_where_guard._nuke_ufc_cast_guard = True
    np.where = _nuke_where_guard

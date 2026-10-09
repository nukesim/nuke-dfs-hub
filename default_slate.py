import base64
import io
import lzma
from pathlib import Path
import pandas as pd

SLATE_LABEL = "2026 Week 5 Sunday Main · 2026-10-11 · Updated 2026-10-09"

_PARTS = [
    Path(__file__).parent / "data" / f"dk_nfl_current.csv.xz.b64.part{i}"
    for i in range(1, 5)
]

def load_default_slate():
    csv_path = Path(__file__).parent / "data" / "dk_nfl_current.csv"
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return pd.read_csv(csv_path)
    payload = "".join(p.read_text(encoding="utf-8").strip() for p in _PARTS)
    raw = lzma.decompress(base64.b64decode(payload))
    return pd.read_csv(io.BytesIO(raw))

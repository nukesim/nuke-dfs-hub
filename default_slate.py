import base64
import io
import lzma
from pathlib import Path
import pandas as pd

SLATE_LABEL = "2026 Week 3 Sunday Main · Updated 2026-09-16"

_PARTS = [
    Path(__file__).parent / "data" / f"dk_nfl_current.csv.xz.b64.part{i}"
    for i in range(1, 5)
]

def load_default_slate():
    payload = "".join(p.read_text(encoding="utf-8").strip() for p in _PARTS)
    raw = lzma.decompress(base64.b64decode(payload))
    return pd.read_csv(io.BytesIO(raw))

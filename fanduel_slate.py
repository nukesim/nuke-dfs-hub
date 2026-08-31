from pathlib import Path
import base64
import gzip
import io
import pandas as pd

ROOT = Path(__file__).resolve().parent
FD_SLATE_PATH = ROOT / "data" / "fanduel_nfl_current.csv"
FD_B64_PREFIX = ROOT / "data" / "fanduel_nfl_current.csv.gz.b64.part"
FD_SLATE_LABEL = "2026 FanDuel Week 1"


def _payload_parts():
    parts=[]
    i=1
    while True:
        p=Path(str(FD_B64_PREFIX)+str(i))
        if not p.exists():
            break
        parts.append(p)
        i+=1
    return parts


def has_fanduel_slate():
    if FD_SLATE_PATH.exists() and FD_SLATE_PATH.stat().st_size > 0:
        return True
    return len(_payload_parts()) > 0


def load_fanduel_slate():
    if FD_SLATE_PATH.exists() and FD_SLATE_PATH.stat().st_size > 0:
        return pd.read_csv(FD_SLATE_PATH)
    parts=_payload_parts()
    if not parts:
        raise FileNotFoundError("No repository FanDuel slate has been loaded yet.")
    encoded="".join(p.read_text().strip() for p in parts)
    raw=gzip.decompress(base64.b64decode(encoded))
    return pd.read_csv(io.BytesIO(raw))


def fanduel_slate_status():
    if not has_fanduel_slate():
        return {"available": False, "path": str(FD_SLATE_PATH), "players": 0}
    try:
        df = load_fanduel_slate()
        return {"available": True, "path": str(FD_SLATE_PATH), "players": int(len(df))}
    except Exception:
        return {"available": False, "path": str(FD_SLATE_PATH), "players": 0}

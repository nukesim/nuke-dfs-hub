from pathlib import Path
import pandas as pd

FD_SLATE_PATH = Path(__file__).resolve().parent / "data" / "fanduel_nfl_current.csv"
FD_SLATE_LABEL = "FanDuel NFL Current Slate"


def has_fanduel_slate():
    return FD_SLATE_PATH.exists() and FD_SLATE_PATH.stat().st_size > 0


def load_fanduel_slate():
    if not has_fanduel_slate():
        raise FileNotFoundError("No repository FanDuel slate has been loaded yet.")
    return pd.read_csv(FD_SLATE_PATH)


def fanduel_slate_status():
    if not has_fanduel_slate():
        return {"available": False, "path": str(FD_SLATE_PATH), "players": 0}
    try:
        df = load_fanduel_slate()
        return {"available": True, "path": str(FD_SLATE_PATH), "players": int(len(df))}
    except Exception:
        return {"available": False, "path": str(FD_SLATE_PATH), "players": 0}

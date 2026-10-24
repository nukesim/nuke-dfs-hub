from pathlib import Path
import pandas as pd

SLATE_LABEL = "2026 Week 7 Sunday Main · 2026-10-25 · Updated 2026-10-24"

def load_default_slate():
    """Load the current DraftKings NFL salary CSV."""
    path = Path(__file__).parent / "data" / "dk_nfl_current.csv"
    if not path.is_file():
        raise FileNotFoundError(f"No DraftKings NFL slate found: {path}")
    slate = pd.read_csv(path)
    required = {"Position", "Name", "ID", "Salary", "Game Info", "TeamAbbrev"}
    missing = required.difference(slate.columns)
    if missing or slate.empty:
        raise ValueError(f"Invalid NFL slate: missing={sorted(missing)}")
    return slate

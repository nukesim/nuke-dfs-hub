"""Event-specific PGA market snapshots and deterministic model inputs."""
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent / "data"


def name_key(name):
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def load_market_snapshot(event):
    if "austinchampionship" not in name_key(event) and "goodgoodchampionship" not in name_key(event):
        return {}
    return json.loads((DATA / "pga_austin_2026_market.json").read_text())


def attach_market(pool, snapshot):
    result = pool.copy()
    result["Win Odds"] = np.nan
    result["Implied Win %"] = np.nan
    result["Market Adjustment"] = 0.0
    aliases = {"jordanlsmith": "jordansmith", "zacharybauchou": "zachbauchou",
               "krisventura": "kristofferventura", "matthewmccarty": "mattmccarty",
               "camerondavis": "camdavis", "thomasmorrison": "tommymorrison"}
    prices = {name_key(p["name"]): float(p["american_odds"])
              for p in snapshot.get("players", [])}
    for ix, name in result["Name"].items():
        key = name_key(name)
        odds = prices.get(aliases.get(key, key))
        if odds is not None and np.isfinite(odds) and odds >= 100:
            result.at[ix, "Win Odds"] = odds / 100
            result.at[ix, "Implied Win %"] = 10000 / (odds + 100)
    covered = result["Win Odds"].notna()
    if covered.sum() > 1:
        # Small rank-disagreement adjustment, not a calibrated projection service.
        # Unpriced players keep their salary baseline. Never invent their odds.
        market_rank = (-result.loc[covered, "Win Odds"]).rank(pct=True)
        salary_rank = result.loc[covered, "Salary"].rank(pct=True)
        result.loc[covered, "Market Adjustment"] = ((market_rank - salary_rank) * 8).clip(-4, 4)
    result.attrs["market_snapshot"] = snapshot
    return result


def expected_points(pool, made_cut_mean, cut_probability):
    weather = pd.to_numeric(pool.get("Weather Edge", pd.Series(0., index=pool.index)),
                            errors="coerce").fillna(0).to_numpy(float)
    made = np.asarray(made_cut_mean, dtype=float) + weather
    missed = np.maximum(8, made * .43)
    probability = np.asarray(cut_probability, dtype=float)
    return probability * made + (1 - probability) * missed

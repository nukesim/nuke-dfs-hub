import numpy as np
import pandas as pd

PATHS = [
    "PASSING_EXPLOSION",
    "RB_DOMINANCE",
    "VALUE_ERUPTION",
    "STARS_FAIL",
    "SHOOTOUT",
    "LOW_SCORING",
    "BALANCED",
]


def _lineup_features(players, lu):
    r = players.iloc[list(lu)].copy()
    qb = r[r.Position.eq("QB")]
    qb_team = qb.iloc[0].Team if not qb.empty else ""
    qb_game = qb.iloc[0].Game if not qb.empty else ""
    pass_mates = r[(r.Team.eq(qb_team)) & (r.Position.isin(["WR", "TE"]))]
    bringbacks = r[(r.Game.eq(qb_game)) & (~r.Team.eq(qb_team)) & (r.Position.ne("DST"))]
    skill = r[r.Position.ne("DST")]
    star_count = int((skill.Salary >= 7000).sum())
    value_count = int((skill.Salary <= 5000).sum())
    rb_spend = float(r.loc[r.Position.eq("RB"), "Salary"].sum())
    pass_spend = float(r.loc[r.Position.isin(["QB", "WR", "TE"]), "Salary"].sum())
    same_game = int((r.Game.eq(qb_game)).sum()) if qb_game else 0
    return {
        "pass_mates": len(pass_mates), "bringbacks": len(bringbacks),
        "star_count": star_count, "value_count": value_count,
        "rb_spend": rb_spend, "pass_spend": pass_spend,
        "same_game": same_game, "salary": float(r.Salary.sum()),
    }


def _scores(f):
    return {
        "PASSING_EXPLOSION": 1.8*f["pass_mates"] + .8*f["bringbacks"] + .00008*f["pass_spend"],
        "RB_DOMINANCE": .00019*f["rb_spend"] + .7*max(0, 2-f["pass_mates"]),
        "VALUE_ERUPTION": 1.15*f["value_count"] + .35*f["star_count"],
        "STARS_FAIL": 1.0*f["value_count"] - .55*f["star_count"] + .4*max(0, 2-f["pass_mates"]),
        "SHOOTOUT": 1.2*f["pass_mates"] + 1.0*f["bringbacks"] + .45*max(0, f["same_game"]-3),
        "LOW_SCORING": .9*max(0, 2-f["pass_mates"]) + .5*max(0, 1-f["bringbacks"]) + .00005*f["rb_spend"],
        "BALANCED": 3.5 - .45*abs(f["star_count"]-2) - .35*abs(f["value_count"]-3) - .35*abs(f["pass_mates"]-1),
    }


def attach_path_labels(players, results):
    if results is None or results.empty or "_indices" not in results.columns:
        return results
    out = results.copy()
    strongest, second, affinities, theses = [], [], [], []
    for lu in out["_indices"]:
        f = _lineup_features(players, lu)
        s = _scores(f)
        ordered = sorted(s.items(), key=lambda kv: kv[1], reverse=True)
        top, runner = ordered[0][0], ordered[1][0]
        vals = np.array([v for _, v in ordered], dtype=float)
        spread = max(.25, float(vals.max() - vals.min()))
        path_score = 50.0 + 45.0 * float((ordered[0][1] - np.median(vals)) / spread)
        path_score = float(np.clip(path_score, 5, 99))
        strongest.append(top); second.append(runner); affinities.append(round(path_score, 1))
        parts = []
        parts.append("DOUBLE STACK" if f["pass_mates"] >= 2 else "QB STACK" if f["pass_mates"] == 1 else "NAKED / NONSTANDARD QB")
        parts.append(top.replace("_", " "))
        if f["bringbacks"]:
            parts.append(f"{f['bringbacks']} BRING-BACK" + ("S" if f["bringbacks"] > 1 else ""))
        # ASCII delimiter prevents the UTF-8 middle-dot mojibake Excel can display as 'Â'.
        theses.append(" | ".join(parts))
    out["Strongest Path"] = strongest
    out["Secondary Path"] = second
    out["Path Score"] = affinities
    out["Lineup Thesis"] = theses
    return out


def path_exposure(results, top_n=50):
    if results is None or results.empty or "Strongest Path" not in results.columns:
        return pd.DataFrame()
    x = results.head(min(int(top_n), len(results)))
    counts = x["Strongest Path"].value_counts()
    return pd.DataFrame({"Path": counts.index, "Lineups": counts.values, "Exposure %": np.round(100 * counts.values / len(x), 1)}).reset_index(drop=True)

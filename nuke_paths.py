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
    rb_rows = r[r.Position.eq("RB")]
    rb_spend = float(rb_rows["Salary"].sum())
    expensive_rbs = int((rb_rows.Salary >= 7000).sum())
    pass_spend = float(r.loc[r.Position.isin(["QB", "WR", "TE"]), "Salary"].sum())
    same_game = int((r.Game.eq(qb_game)).sum()) if qb_game else 0
    return {
        "pass_mates": len(pass_mates), "bringbacks": len(bringbacks),
        "star_count": star_count, "value_count": value_count,
        "rb_spend": rb_spend, "expensive_rbs": expensive_rbs,
        "pass_spend": pass_spend, "same_game": same_game,
        "salary": float(r.Salary.sum()),
    }


def _scores(f):
    """Structural path affinities.

    The scores are deliberately balanced so a normal QB stack does not automatically become a
    PASSING_EXPLOSION lineup. Passing Explosion now requires real pass concentration, while
    Shootout rewards game concentration/bring-backs, RB Dominance rewards actual RB spend, and
    the remaining paths are driven by roster construction rather than being buried by one large
    coefficient.
    """
    pass_mates = f["pass_mates"]
    bring = f["bringbacks"]
    same_game = f["same_game"]
    stars = f["star_count"]
    values = f["value_count"]
    rb_spend = f["rb_spend"]

    return {
        "PASSING_EXPLOSION": (
            1.55*max(0, pass_mates-1)
            + .45*bring
            + .000035*max(0, f["pass_spend"]-22000)
        ),
        "RB_DOMINANCE": (
            .00022*rb_spend
            + .70*f["expensive_rbs"]
            + .45*max(0, 2-pass_mates)
        ),
        "VALUE_ERUPTION": (
            .85*values
            + .28*stars
            + .35*max(0, values-3)
        ),
        "STARS_FAIL": (
            .75*values
            + .80*max(0, 2-stars)
            + .30*max(0, 2-pass_mates)
        ),
        "SHOOTOUT": (
            .70*pass_mates
            + 1.15*bring
            + .75*max(0, same_game-3)
        ),
        "LOW_SCORING": (
            .65*max(0, 2-pass_mates)
            + .50*max(0, 1-bring)
            + .00008*rb_spend
            + .35*max(0, 2-stars)
        ),
        "BALANCED": (
            4.35
            - .42*abs(stars-2)
            - .30*abs(values-3)
            - .38*abs(pass_mates-1)
            - .25*max(0, same_game-4)
        ),
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
        strongest.append(top)
        second.append(runner)
        affinities.append(round(path_score, 1))
        parts = []
        parts.append("DOUBLE STACK" if f["pass_mates"] >= 2 else "QB STACK" if f["pass_mates"] == 1 else "NAKED / NONSTANDARD QB")
        parts.append(top.replace("_", " "))
        if f["bringbacks"]:
            parts.append(f"{f['bringbacks']} BRING-BACK" + ("S" if f["bringbacks"] > 1 else ""))
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
    return pd.DataFrame({
        "Path": counts.index,
        "Lineups": counts.values,
        "Exposure %": np.round(100 * counts.values / len(x), 1),
    }).reset_index(drop=True)

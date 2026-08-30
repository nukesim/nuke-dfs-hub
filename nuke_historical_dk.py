import json
from urllib.request import Request, urlopen

import pandas as pd


def _get_json(url, timeout=12):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 NUKE-DFS-Hub"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _first_value(obj, keys):
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] not in (None, ""):
                return obj[k]
        for v in obj.values():
            found = _first_value(v, keys)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _first_value(v, keys)
            if found not in (None, ""):
                return found
    return None


def recover_contest_draftables(contest_id):
    """Try to reconstruct a historical DraftKings salary slate from DK's public API.

    Returns (draftables_df, metadata). Historical contests may no longer be retained
    by DraftKings; callers should treat an empty dataframe as unavailable rather
    than fabricate salary data.
    """
    cid = str(contest_id)
    contest_url = f"https://api.draftkings.com/contests/v1/contests/{cid}?format=json"
    meta = {"contest_id": cid, "contest_url": contest_url, "recovered": False}
    try:
        contest = _get_json(contest_url)
    except Exception as exc:
        meta["error"] = f"Contest API unavailable: {exc}"
        return pd.DataFrame(), meta

    draft_group_id = _first_value(contest, ["draftGroupId", "DraftGroupId", "draft_group_id"])
    if draft_group_id is None:
        meta["error"] = "DraftKings contest response did not include a draftGroupId."
        return pd.DataFrame(), meta

    meta["draft_group_id"] = str(draft_group_id)
    draftables_url = f"https://api.draftkings.com/draftgroups/v1/draftgroups/{draft_group_id}/draftables"
    meta["draftables_url"] = draftables_url
    try:
        data = _get_json(draftables_url)
    except Exception as exc:
        meta["error"] = f"Draftables API unavailable: {exc}"
        return pd.DataFrame(), meta

    rows = None
    if isinstance(data, dict):
        for key in ["draftables", "Draftables", "players", "Players"]:
            if isinstance(data.get(key), list):
                rows = data[key]
                break
    if rows is None and isinstance(data, list):
        rows = data
    if not rows:
        meta["error"] = "DraftKings returned no draftables for this historical slate."
        return pd.DataFrame(), meta

    out = pd.DataFrame(rows)
    rename = {}
    candidates = {
        "name": ["displayName", "name", "playerName"],
        "position": ["position", "rosterSlot"],
        "salary": ["salary"],
        "team": ["teamAbbreviation", "teamAbbrev", "team"],
        "id": ["draftableId", "playerId", "id"],
    }
    for target, options in candidates.items():
        for src in options:
            if src in out.columns:
                rename[src] = target
                break
    out = out.rename(columns=rename)
    keep = [c for c in ["name", "id", "position", "team", "salary"] if c in out.columns]
    out = out[keep].copy()
    if "salary" in out.columns:
        out["salary"] = pd.to_numeric(out["salary"], errors="coerce")
    if "position" in out.columns:
        out["position"] = out["position"].astype(str).str.upper().replace({"DEF": "DST", "D/ST": "DST"})
    meta["recovered"] = not out.empty
    meta["players"] = int(len(out))
    return out.reset_index(drop=True), meta

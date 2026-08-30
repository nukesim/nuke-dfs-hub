import re
import numpy as np
import pandas as pd

ROSTER_ORDER=["QB","RB","RB","WR","WR","WR","TE","FLEX","DST"]
SLOT_TOKENS={"QB","RB","WR","TE","FLEX","DST","DEF"}


def _clean_name(x):
    return re.sub(r"\s+"," ",str(x or "").strip())


def parse_dk_lineup(lineup):
    """Parse DraftKings lineup text such as 'QB Josh Allen RB ... DST Bills'."""
    text=_clean_name(lineup)
    if not text:
        return []
    pattern=r"\b(QB|RB|WR|TE|FLEX|DST|DEF)\b"
    matches=list(re.finditer(pattern,text,flags=re.I))
    out=[]
    for i,m in enumerate(matches):
        slot=m.group(1).upper().replace("DEF","DST")
        start=m.end(); end=matches[i+1].start() if i+1<len(matches) else len(text)
        name=_clean_name(text[start:end])
        if name:
            out.append((slot,name))
    return out


def normalize_contests(df):
    d=df.copy()
    rename={c:str(c).strip().lower() for c in d.columns}
    d=d.rename(columns=rename)
    needed={"contest_id","entries","entry_fee"}
    if not needed.issubset(d.columns):
        raise ValueError(f"contests.csv missing required columns: {sorted(needed-set(d.columns))}")
    for c in ["entries","entry_fee","total_prizes","week","year"]:
        if c in d.columns: d[c]=pd.to_numeric(d[c],errors="coerce")
    d["contest_id"]=d["contest_id"].astype(str)
    return d


def normalize_results(df):
    d=df.copy(); d.columns=[str(c).strip().lower() for c in d.columns]
    needed={"contest_id","place","points","lineup","payout"}
    if not needed.issubset(d.columns):
        raise ValueError(f"contestResults.csv missing required columns: {sorted(needed-set(d.columns))}")
    d["contest_id"]=d["contest_id"].astype(str)
    for c in ["place","points","payout"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d[d["points"].notna()].copy()
    d["parsed_lineup"]=d["lineup"].map(parse_dk_lineup)
    d["players"]=d["parsed_lineup"].map(lambda x:[n for _,n in x])
    d["roster_size"]=d["players"].map(len)
    return d


def normalize_ownership(df):
    d=df.copy(); d.columns=[str(c).strip().lower() for c in d.columns]
    needed={"contest_id","player","pos","drafted","points"}
    if not needed.issubset(d.columns):
        raise ValueError(f"contestOwnership.csv missing required columns: {sorted(needed-set(d.columns))}")
    d["contest_id"]=d["contest_id"].astype(str)
    d["player"]=d["player"].map(_clean_name)
    d["pos"]=d["pos"].astype(str).str.upper().replace({"DEF":"DST"})
    d["drafted"]=pd.to_numeric(d["drafted"],errors="coerce")
    d["points"]=pd.to_numeric(d["points"],errors="coerce")
    # Scrapers may store ownership either 0-1 or 0-100.
    med=float(d["drafted"].dropna().median()) if d["drafted"].notna().any() else 0.0
    if med<=1.0: d["drafted"]=100*d["drafted"]
    return d


def contest_structure(results):
    if results is None or results.empty:
        return {}
    d=results.copy()
    valid=d[d.roster_size.eq(9)] if "roster_size" in d.columns else d
    if valid.empty: valid=d
    top=max(1,int(np.ceil(len(valid)*.01)))
    cash_cut=max(1,int(np.ceil(len(valid)*.20)))
    return {
        "entries":int(len(valid)),
        "winning_score":float(valid["points"].max()),
        "median_score":float(valid["points"].median()),
        "top1_score":float(valid.nlargest(top,"points")["points"].min()),
        "cash20_score":float(valid.nlargest(cash_cut,"points")["points"].min()),
        "duplicate_lineups":int(valid["lineup"].astype(str).duplicated(keep=False).sum()),
        "unique_lineups":int(valid["lineup"].astype(str).nunique()),
        "total_payout":float(pd.to_numeric(valid["payout"],errors="coerce").fillna(0).sum()),
    }


def lineup_stack_label(parsed_lineup, player_team_map=None):
    """Return simple QB pass-catcher / bring-back structure if team map is supplied."""
    if not parsed_lineup or not player_team_map:
        return "UNKNOWN"
    qb=[n for s,n in parsed_lineup if s=="QB"]
    if not qb: return "NO_QB"
    q=qb[0]; qt=player_team_map.get(q)
    if not qt: return "UNKNOWN"
    teammates=0
    for s,n in parsed_lineup:
        if n==q or s=="DST": continue
        if player_team_map.get(n)==qt: teammates+=1
    return f"QB+{teammates}"


def ownership_summary(ownership):
    if ownership is None or ownership.empty:
        return pd.DataFrame()
    rows=[]
    for pos,g in ownership.groupby("pos"):
        own=pd.to_numeric(g["drafted"],errors="coerce").dropna()
        if own.empty: continue
        rows.append({
            "Position":pos,"Players":len(g),"Avg Ownership %":round(float(own.mean()),2),
            "Median Ownership %":round(float(own.median()),2),"Max Ownership %":round(float(own.max()),2)
        })
    return pd.DataFrame(rows).sort_values("Position").reset_index(drop=True)


def compare_modeled_ownership(actual_ownership, modeled):
    """Compare actual DK ownership to a modeled player ownership table.

    `modeled` should contain Name and a modeled ownership percentage column named
    one of Ownership %, Ownership, Projected Ownership, or Field Ownership.
    """
    if actual_ownership is None or actual_ownership.empty or modeled is None or modeled.empty:
        return pd.DataFrame(),{}
    m=modeled.copy(); m.columns=[str(c).strip() for c in m.columns]
    own_col=next((c for c in ["Ownership %","Ownership","Projected Ownership","Field Ownership"] if c in m.columns),None)
    name_col=next((c for c in ["Name","Player","player"] if c in m.columns),None)
    if not own_col or not name_col:
        raise ValueError("Modeled ownership file needs Name and an ownership percentage column.")
    m=m[[name_col,own_col]].rename(columns={name_col:"player",own_col:"modeled"})
    m["player"]=m["player"].map(_clean_name); m["modeled"]=pd.to_numeric(m["modeled"],errors="coerce")
    med=float(m.modeled.dropna().median()) if m.modeled.notna().any() else 0
    if med<=1.0: m["modeled"]=100*m["modeled"]
    a=actual_ownership[["player","drafted","pos"]].copy()
    x=a.merge(m,on="player",how="inner")
    if x.empty: return x,{}
    x["Error"]=x.modeled-x.drafted; x["Abs Error"]=x.Error.abs()
    corr=float(x[["drafted","modeled"]].corr().iloc[0,1]) if len(x)>1 else np.nan
    summary={"matched_players":len(x),"mae":float(x["Abs Error"].mean()),"bias":float(x["Error"].mean()),"corr":corr}
    return x.sort_values("Abs Error",ascending=False).reset_index(drop=True),summary

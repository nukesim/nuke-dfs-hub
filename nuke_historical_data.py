import io
import urllib.request
import pandas as pd

NFLDFS_2017_URL = "https://raw.githubusercontent.com/Brian-Doucet/nfldfs/master/data/draftkings_sample_output.csv"
SOURCE_NAME = "Brian-Doucet/nfldfs (DraftKings historical salary + points data)"


def _display_name(name):
    s=str(name or "").strip()
    if "," in s:
        last, first = [x.strip() for x in s.split(",", 1)]
        return f"{first} {last}".strip()
    return s


def _position(pos):
    p=str(pos or "").upper().strip()
    return "DST" if p in {"DEF", "D", "DST"} else p


def _team(team):
    return str(team or "").upper().strip()


def _depth_label(pos, rank):
    rank=int(rank)
    if pos=="QB": return "QB1" if rank==1 else "QB2+"
    if pos=="RB": return "RB1" if rank==1 else "RB2" if rank==2 else "RB3" if rank==3 else "RB4+"
    if pos=="WR": return "WR1" if rank==1 else "WR2" if rank==2 else "WR3" if rank==3 else "WR4" if rank==4 else "WR5+"
    if pos=="TE": return "TE1" if rank==1 else "TE2" if rank==2 else "TE3+"
    return "DST"


def add_salary_depth_roles(df):
    """Infer pre-game depth from DK salary within team/position.

    This deliberately uses salary only and never actual fantasy points, so the
    validation filter does not leak post-game information into the test.
    """
    out=df.copy().reset_index(drop=True)
    out["Depth Rank"]=1
    mask=out.Position.isin(["QB","RB","WR","TE"])
    if mask.any():
        ranked=out.loc[mask].copy()
        ranked["Depth Rank"]=ranked.groupby(["Year","Week","Team","Position"])["Salary"].rank(method="first",ascending=False).astype(int)
        out.loc[ranked.index,"Depth Rank"]=ranked["Depth Rank"]
    out["Historical Role"]=[_depth_label(p,r) for p,r in zip(out.Position,out["Depth Rank"])]
    return out


def starter_aware_pool(df):
    """Return players that resemble the active DFS roles NUKE models most directly.

    QB is limited to the highest-salaried QB on each team/week. Skill positions
    retain normal rotation depth (RB1-3, WR1-4, TE1-2). DST is always retained.
    No actual-score information is used to make this decision.
    """
    x=add_salary_depth_roles(df)
    keep=(
        x.Position.eq("DST") |
        (x.Position.eq("QB") & x["Depth Rank"].eq(1)) |
        (x.Position.eq("RB") & x["Depth Rank"].le(3)) |
        (x.Position.eq("WR") & x["Depth Rank"].le(4)) |
        (x.Position.eq("TE") & x["Depth Rank"].le(2))
    )
    return x[keep].reset_index(drop=True)


def load_nfldfs_2017(timeout=20):
    """Download the public nfldfs 2017 DraftKings dataset and normalize it for NUKE."""
    req=urllib.request.Request(NFLDFS_2017_URL, headers={"User-Agent":"nuke-dfs-validation/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw=resp.read()
    df=pd.read_csv(io.BytesIO(raw))
    return normalize_nfldfs(df)


def normalize_nfldfs(df):
    required={"week","year","player_name","position","team_name","opponent_name","points","salary"}
    missing=required-set(df.columns)
    if missing:
        raise ValueError(f"Historical source missing columns: {sorted(missing)}")
    out=pd.DataFrame()
    out["Year"]=pd.to_numeric(df["year"],errors="coerce").astype("Int64")
    out["Week"]=pd.to_numeric(df["week"],errors="coerce").astype("Int64")
    out["Name"]=df["player_name"].map(_display_name)
    out["Position"]=df["position"].map(_position)
    out["Team"]=df["team_name"].map(_team)
    out["Opponent"]=df["opponent_name"].map(_team)
    out["Salary"]=pd.to_numeric(df["salary"],errors="coerce").fillna(0).astype(int)
    out["Actual DK Points"]=pd.to_numeric(df["points"],errors="coerce")
    out["Game"]=["@".join(sorted([t,o])) if t and o else f"{t}@{o}" for t,o in zip(out.Team,out.Opponent)]
    out=out[out.Position.isin(["QB","RB","WR","TE","DST"])].copy()
    out=out[(out.Salary>0)&out["Actual DK Points"].notna()].reset_index(drop=True)
    return add_salary_depth_roles(out)


def available_seasons():
    return [2017]


def available_weeks(data, season):
    x=data[pd.to_numeric(data.Year,errors="coerce").eq(int(season))]
    return sorted(pd.to_numeric(x.Week,errors="coerce").dropna().astype(int).unique().tolist())


def historical_week(data, season, week):
    x=data[
        pd.to_numeric(data.Year,errors="coerce").eq(int(season)) &
        pd.to_numeric(data.Week,errors="coerce").eq(int(week))
    ].copy()
    return x.reset_index(drop=True)


def historical_season(data, season):
    x=data[pd.to_numeric(data.Year,errors="coerce").eq(int(season))].copy()
    return x.reset_index(drop=True)

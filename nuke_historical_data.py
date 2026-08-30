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


def load_nfldfs_2017(timeout=20):
    """Download the public nfldfs 2017 DraftKings dataset and normalize it for NUKE.

    The upstream sample contains DraftKings salary and actual DK fantasy points for
    all regular-season weeks.  This is used only for model validation/backtesting.
    """
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
    return out


def available_seasons():
    # The currently bundled public source is the repository's complete 2017 DK sample.
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

import html
import io
import re
import urllib.request
import pandas as pd

ROTOGURU_URL = "https://rotoguru1.com/cgi-bin/fyday.pl?week={week}&year={year}&game=dk&scsv=1"
ROTOGURU_HTTP_URL = "http://rotoguru1.com/cgi-bin/fyday.pl?week={week}&year={year}&game=dk&scsv=1"
SOURCE_NAME = "RotoGuru historical DraftKings NFL salary + fantasy points"


def _display_name(name):
    s=str(name or "").strip()
    if "," in s:
        last,first=[x.strip() for x in s.split(",",1)]
        return f"{first} {last}".strip()
    return s


def _position(v):
    p=str(v or "").upper().strip()
    return "DST" if p in {"DEF","D","DST"} else p


def _extract_pre_text(page_text):
    m=re.search(r"<pre[^>]*>(.*?)</pre>",page_text,flags=re.I|re.S)
    if not m:
        raise ValueError("Historical source did not contain the expected PRE data block.")
    text=html.unescape(m.group(1))
    text=re.sub(r"<[^>]+>","",text)
    return text.strip()


def parse_rotoguru_page(page_text):
    """Parse one RotoGuru scsv page without BeautifulSoup."""
    text=_extract_pre_text(page_text)
    rows=pd.read_csv(
        io.StringIO(text),sep=";",header=None,skiprows=1,
        names=["week","year","gid","player_name","position","team_name","home_or_away","opponent_name","points","salary"]
    )
    return normalize_rotoguru(rows)


def normalize_rotoguru(df):
    req={"week","year","player_name","position","team_name","opponent_name","points","salary"}
    missing=req-set(df.columns)
    if missing:
        raise ValueError(f"RotoGuru data missing columns: {sorted(missing)}")
    out=pd.DataFrame()
    out["Year"]=pd.to_numeric(df.year,errors="coerce").astype("Int64")
    out["Week"]=pd.to_numeric(df.week,errors="coerce").astype("Int64")
    out["Name"]=df.player_name.map(_display_name)
    out["Position"]=df.position.map(_position)
    out["Team"]=df.team_name.fillna("").astype(str).str.upper().str.strip()
    out["Opponent"]=df.opponent_name.fillna("").astype(str).str.upper().str.strip()
    out["Salary"]=pd.to_numeric(df.salary,errors="coerce").fillna(0).astype(int)
    out["Actual DK Points"]=pd.to_numeric(df.points,errors="coerce")
    out["Game"]=["@".join(sorted([t,o])) if t and o else f"{t}@{o}" for t,o in zip(out.Team,out.Opponent)]
    out=out[out.Position.isin(["QB","RB","WR","TE","DST"])].copy()
    return out[(out.Salary>0)&out["Actual DK Points"].notna()].reset_index(drop=True)


def load_rotoguru_week(year,week,timeout=20):
    last_error=None
    for template in (ROTOGURU_URL,ROTOGURU_HTTP_URL):
        url=template.format(year=int(year),week=int(week))
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"nuke-dfs-validation/1.0"})
            with urllib.request.urlopen(req,timeout=timeout) as resp:
                page=resp.read().decode("latin-1",errors="replace")
            data=parse_rotoguru_page(page)
            if not data.empty:
                return data
        except Exception as e:
            last_error=e
    raise RuntimeError(f"Could not load {year} Week {week} from RotoGuru: {last_error}")


def load_rotoguru_season(year,weeks=None,timeout=20):
    weeks=list(weeks or range(1,18 if int(year)<=2020 else 19))
    parts=[]; failures=[]
    for w in weeks:
        try:
            x=load_rotoguru_week(year,w,timeout=timeout)
            if not x.empty: parts.append(x)
        except Exception as e:
            failures.append((int(w),str(e)))
    if not parts:
        raise RuntimeError(f"No usable historical DraftKings data loaded for {year}.")
    return pd.concat(parts,ignore_index=True),failures

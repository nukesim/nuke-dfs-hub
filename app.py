
import streamlit as st
import pandas as pd
import json
import re
import math
import unicodedata
import numpy as np
from itertools import combinations
from pathlib import Path
from default_slate import load_default_slate, SLATE_LABEL
from nuke_bridge import portable_to_hub_lineup

st.set_page_config(page_title="NUKE NFL DFS Hub", page_icon="🏈", layout="wide")

SLOTS = ["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DST"]
SLOT_POS = {
    "QB":["QB"],"RB1":["RB"],"RB2":["RB"],
    "WR1":["WR"],"WR2":["WR"],"WR3":["WR"],
    "TE":["TE"],"FLEX":["RB","WR","TE"],"DST":["DST"]
}
CAP = 50000
MAX_LU = 50

st.markdown("""
<style>
.block-container{padding-top:1rem;padding-bottom:2rem;max-width:1600px}
h1,h2,h3{letter-spacing:-.02em}
.dkrow{border:1px solid rgba(128,128,128,.22);border-radius:12px;padding:8px 10px;margin:4px 0}
.team{display:inline-block;min-width:38px;text-align:center;border-radius:7px;padding:3px 6px;margin-right:7px;background:rgba(128,128,128,.18);font-weight:900;font-size:.72rem}
.pname{font-weight:850}
.meta{opacity:.6;font-size:.75rem}
div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.2);padding:9px 11px;border-radius:11px}

.team-BUF{background:#00338D!important;color:#fff!important}.team-MIA{background:#008E97!important;color:#fff!important}
.team-NE{background:#002244!important;color:#fff!important}.team-NYJ{background:#125740!important;color:#fff!important}
.team-BAL{background:#241773!important;color:#fff!important}.team-CIN{background:#FB4F14!important;color:#111!important}
.team-CLE{background:#311D00!important;color:#fff!important}.team-PIT{background:#FFB612!important;color:#111!important}
.team-HOU{background:#03202F!important;color:#fff!important}.team-IND{background:#002C5F!important;color:#fff!important}
.team-JAX{background:#006778!important;color:#fff!important}.team-TEN{background:#0C2340!important;color:#fff!important}
.team-DEN{background:#FB4F14!important;color:#111!important}.team-KC{background:#E31837!important;color:#fff!important}
.team-LV{background:#000!important;color:#fff!important}.team-LAC{background:#0080C6!important;color:#fff!important}
.team-DAL{background:#041E42!important;color:#fff!important}.team-NYG{background:#0B2265!important;color:#fff!important}
.team-PHI{background:#004C54!important;color:#fff!important}.team-WAS{background:#5A1414!important;color:#fff!important}
.team-CHI{background:#0B162A!important;color:#fff!important}.team-DET{background:#0076B6!important;color:#fff!important}
.team-GB{background:#203731!important;color:#fff!important}.team-MIN{background:#4F2683!important;color:#fff!important}
.team-ATL{background:#A71930!important;color:#fff!important}.team-CAR{background:#0085CA!important;color:#fff!important}
.team-NO{background:#D3BC8D!important;color:#111!important}.team-TB{background:#D50A0A!important;color:#fff!important}
.team-ARI{background:#97233F!important;color:#fff!important}.team-LAR{background:#003594!important;color:#fff!important}
.team-SF{background:#AA0000!important;color:#fff!important}.team-SEA{background:#002244!important;color:#fff!important}
.build-panel{border:2px solid rgba(25,195,125,.34);border-radius:18px;padding:16px 18px;background:rgba(25,195,125,.035);margin-top:4px}
.build-heading{font-size:.72rem;font-weight:950;letter-spacing:.11em;color:#19c37d;margin-bottom:8px}
.metricbox{border:1px solid rgba(128,128,128,.22);border-radius:12px;padding:10px 12px;min-height:76px}
.metriclabel{font-size:.72rem;opacity:.58;font-weight:800}
.metricvalue{font-size:1.55rem;font-weight:950;margin-top:4px}
.metricred{border-color:rgba(255,70,70,.7)!important;background:rgba(255,70,70,.07)!important}
.redtext{color:#ff4b4b!important}
.stack-card{border:1px solid rgba(25,195,125,.32);border-radius:14px;padding:11px 13px;margin:7px 0;background:rgba(25,195,125,.05)}
.stack-rank{display:inline-block;border-radius:999px;padding:3px 7px;background:rgba(25,195,125,.14);color:#19c37d;font-size:.72rem;font-weight:900;margin-right:5px}
.rank-badge{display:inline-block;border-radius:999px;padding:3px 7px;background:rgba(128,128,128,.16);font-size:.72rem;font-weight:900;margin-left:5px}

.roster-player-line{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:2px}
.remove-x button{padding:0!important;min-height:26px!important;height:26px!important;width:28px!important;border-radius:7px!important;font-size:1rem!important;line-height:1!important}
.active-select button{font-weight:900!important}

:root{
  --nuke-bg:#0b0f14;
  --nuke-panel:#111820;
  --nuke-panel2:#0f151c;
  --nuke-border:rgba(255,255,255,.08);
  --nuke-green:#19c37d;
  --nuke-yellow:#f2c94c;
  --nuke-red:#ff5d5d;
  --nuke-text:#f5f7fa;
  --nuke-muted:#8d99a8;
}
.stApp{
  background:
    radial-gradient(circle at 20% 0%, rgba(25,195,125,.08), transparent 28%),
    linear-gradient(180deg,#0b0f14 0%,#0a0d12 100%);
}
.block-container{
  padding-top:.85rem!important;
  max-width:1680px!important;
}
h1,h2,h3{
  letter-spacing:-.025em;
}
h1{
  font-weight:1000!important;
}
[data-testid="stMetric"]{
  background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.015));
  border:1px solid var(--nuke-border)!important;
  border-radius:14px!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}
[data-testid="stTabs"] button{
  font-weight:900!important;
  letter-spacing:.02em!important;
}
[data-testid="stTabs"] button[aria-selected="true"]{
  color:var(--nuke-green)!important;
}
.nuke-section-kicker{
  font-size:.68rem;
  font-weight:1000;
  letter-spacing:.13em;
  color:var(--nuke-green);
  text-transform:uppercase;
  margin-bottom:4px;
}
.nuke-card{
  background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,.012));
  border:1px solid var(--nuke-border);
  border-radius:16px;
  padding:12px 14px;
}
.nuke-game-board{
  border:1px solid rgba(255,255,255,.11);
  border-radius:18px;
  padding:14px 16px;
  margin:4px 0 12px 0;
  background:
    linear-gradient(90deg,rgba(25,195,125,.045),transparent 35%,transparent 65%,rgba(25,195,125,.025)),
    rgba(255,255,255,.018);
}
.nuke-game-team{
  font-size:1.6rem;
  font-weight:1000;
  line-height:1;
}
.nuke-odds-label{
  font-size:.68rem;
  font-weight:950;
  letter-spacing:.08em;
  color:var(--nuke-muted);
  text-transform:uppercase;
}
.nuke-odds-value{
  font-size:1.04rem;
  font-weight:950;
}
.nuke-rank-pill{
  display:inline-block;
  border:1px solid currentColor;
  border-radius:999px;
  padding:3px 8px;
  font-size:.69rem;
  font-weight:950;
  margin-top:5px;
}
.nuke-roster-panel{
  border:1px solid var(--nuke-border);
  border-radius:16px;
  padding:12px 13px 8px 13px;
  background:rgba(255,255,255,.018);
}
.nuke-roster-panel.active{
  border-color:rgba(25,195,125,.55);
  background:rgba(25,195,125,.045);
}
.nuke-player-pool-banner{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  align-items:center;
  margin:6px 0 10px 0;
}
.nuke-pill{
  border:1px solid rgba(255,255,255,.10);
  background:rgba(255,255,255,.025);
  border-radius:999px;
  padding:5px 9px;
  font-size:.72rem;
  font-weight:900;
}
.nuke-lineup-shell{
  border:1px solid rgba(255,255,255,.09);
  border-radius:17px;
  padding:11px;
  background:linear-gradient(180deg,rgba(255,255,255,.025),rgba(255,255,255,.012));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.02);
}
.nuke-lineup-shell.active{
  border:2px solid rgba(25,195,125,.62);
  background:linear-gradient(180deg,rgba(25,195,125,.055),rgba(255,255,255,.012));
}
.nuke-lineup-top{
  display:flex;
  justify-content:space-between;
  gap:8px;
  align-items:center;
  margin-bottom:7px;
}
.nuke-lineup-name{
  font-size:.82rem;
  font-weight:1000;
  letter-spacing:.08em;
}
.nuke-status-complete{
  display:inline-block;
  border-radius:999px;
  padding:3px 7px;
  font-size:.66rem;
  font-weight:1000;
  color:#74e6b4;
  background:rgba(25,195,125,.13);
  border:1px solid rgba(25,195,125,.35);
}
.nuke-status-draft{
  display:inline-block;
  border-radius:999px;
  padding:3px 7px;
  font-size:.66rem;
  font-weight:1000;
  color:#b9c2cc;
  background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.08);
}
.salary-track{
  width:100%;
  height:8px;
  background:rgba(255,255,255,.07);
  border-radius:999px;
  overflow:hidden;
  margin:8px 0 4px 0;
}
.salary-fill{
  height:100%;
  border-radius:999px;
}
.salary-good{background:linear-gradient(90deg,#19c37d,#45d69a)}
.salary-warn{background:linear-gradient(90deg,#f2c94c,#ffad3d)}
.salary-over{background:linear-gradient(90deg,#ff5d5d,#ff8080)}
.lineup-summary-grid{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:6px;
  margin:7px 0 8px 0;
}
.lineup-summary-cell{
  border:1px solid rgba(255,255,255,.07);
  border-radius:10px;
  padding:6px 7px;
  background:rgba(255,255,255,.018);
}
.lineup-summary-cell .lbl{
  display:block;
  font-size:.61rem;
  color:var(--nuke-muted);
  font-weight:900;
  letter-spacing:.06em;
}
.lineup-summary-cell .val{
  display:block;
  font-size:.88rem;
  font-weight:1000;
  margin-top:2px;
}
.saved-card{
  border:1px solid rgba(255,255,255,.09);
  border-radius:15px;
  padding:10px 11px;
  background:rgba(255,255,255,.017);
}
.saved-card h4{
  margin:0 0 5px 0;
  font-size:.82rem;
}
.exposure-row{
  display:flex;
  align-items:center;
  gap:8px;
  margin:5px 0;
}
.exposure-name{
  min-width:145px;
  font-size:.79rem;
  font-weight:850;
}
.exposure-track{
  flex:1;
  height:8px;
  background:rgba(255,255,255,.07);
  border-radius:999px;
  overflow:hidden;
}
.exposure-fill{
  height:100%;
  border-radius:999px;
}
@media(max-width:1000px){
  .lineup-summary-grid{grid-template-columns:1fr 1fr}
}

.corr-wrap{display:flex;flex-wrap:wrap;gap:5px;margin:7px 0 9px 0}
.corr-badge{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:4px 8px;font-size:.66rem;font-weight:950;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.025)}
.corr-qb{color:#64d8ff;border-color:rgba(100,216,255,.35);background:rgba(100,216,255,.08)}
.corr-game{color:#f2c94c;border-color:rgba(242,201,76,.35);background:rgba(242,201,76,.08)}
.corr-team{color:#9be28f;border-color:rgba(155,226,143,.35);background:rgba(155,226,143,.08)}
.corr-bring{color:#d4a7ff;border-color:rgba(212,167,255,.35);background:rgba(212,167,255,.08)}
.corr-none{color:#8d99a8}
.stack-big{font-size:.76rem;font-weight:1000;letter-spacing:.025em;padding:5px 7px;border-radius:8px;background:rgba(242,201,76,.07);border:1px solid rgba(242,201,76,.22);margin-top:5px}
.portfolio-rank-pill{display:inline-block;border-radius:999px;padding:3px 7px;font-size:.65rem;font-weight:1000;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08)}
</style>
""", unsafe_allow_html=True)

def empty_lu():
    return {s:None for s in SLOTS}

def init():
    st.session_state.setdefault("slate",None)
    st.session_state.setdefault("slate_name","No slate loaded")
    st.session_state.setdefault("pool_ids",set())
    st.session_state.setdefault("pending_pool_ids",set())
    st.session_state.setdefault("pool_editor_map",[])
    st.session_state.setdefault("game_editor_map",[])
    st.session_state.setdefault("game_totals",{})
    st.session_state.setdefault("game_totals_source","None")
    st.session_state.setdefault("lineups",[empty_lu() for _ in range(MAX_LU)])
    st.session_state.setdefault("current_lu",0)
    st.session_state.setdefault("slot","QB")
    st.session_state.setdefault("combo_threshold",35)
    st.session_state.setdefault("saved_lineups",{})
    st.session_state.setdefault("draft_saved_link",{})
    st.session_state.setdefault("qb_plan",{})
    st.session_state.setdefault("qb_slot_map",{})
    st.session_state.setdefault("multi_view",1)
    st.session_state.setdefault("active_build_slot",0)
    st.session_state.setdefault("model_df",None)
    st.session_state.setdefault("model_errors",[])
    st.session_state.setdefault("projection_overrides",{})
    st.session_state.setdefault("depth_df",None)
    st.session_state.setdefault("nuke_shared_portfolio_version",0)
    st.session_state.setdefault("nuke_shared_portfolio_rows",[])
    st.session_state.setdefault("nuke_hub_imported_portfolio_version",0)
init()


TEAM_NAME_MAP = {
    "ARI Cardinals":"ARI","ATL Falcons":"ATL","BAL Ravens":"BAL","BUF Bills":"BUF",
    "CAR Panthers":"CAR","CHI Bears":"CHI","CIN Bengals":"CIN","CLE Browns":"CLE",
    "DAL Cowboys":"DAL","DEN Broncos":"DEN","DET Lions":"DET","GB Packers":"GB",
    "HOU Texans":"HOU","IND Colts":"IND","JAX Jaguars":"JAX","KC Chiefs":"KC",
    "LA Chargers":"LAC","LA Rams":"LAR","LV Raiders":"LV","MIA Dolphins":"MIA",
    "MIN Vikings":"MIN","NE Patriots":"NE","NO Saints":"NO","NY Giants":"NYG",
    "NY Jets":"NYJ","PHI Eagles":"PHI","PIT Steelers":"PIT","SEA Seahawks":"SEA",
    "SF 49ers":"SF","TB Buccaneers":"TB","TEN Titans":"TEN","WAS Commanders":"WAS"
}

def odds_num(v):
    if v is None:return None
    if isinstance(v,(int,float)):return float(v)
    s=str(v).strip().replace("−","-").replace("+","")
    try:return float(s)
    except:return None

def parse_total(v):
    if v is None:return None
    m=re.search(r'([0-9]+(?:\.[0-9]+)?)',str(v))
    return float(m.group(1)) if m else None

def parse_gametotals_xlsx(source):
    """Parse the user's pasted one-column gametotals workbook."""
    try:
        raw=pd.read_excel(source,header=None,usecols=[0])
    except Exception:
        return {}
    vals=raw.iloc[:,0].tolist()
    games={}
    for i,v in enumerate(vals):
        if str(v).strip().lower()!="at":continue

        # Previous nonblank = away team.
        ai=i-1
        while ai>=0 and (pd.isna(vals[ai]) or str(vals[ai]).strip()==""):ai-=1

        # Next nonblank = home team.
        hi=i+1
        while hi<len(vals) and (pd.isna(vals[hi]) or str(vals[hi]).strip()==""):hi+=1
        if ai<0 or hi>=len(vals):continue

        away_name=str(vals[ai]).strip()
        home_name=str(vals[hi]).strip()
        away=TEAM_NAME_MAP.get(away_name)
        home=TEAM_NAME_MAP.get(home_name)
        if not away or not home:continue

        # Expected sequence after the home team:
        # away spread, spread price, O total, over price, away ML,
        # home spread, spread price, U total, under price, home ML, date/time.
        seq=[]
        k=hi+1
        while k<len(vals) and len(seq)<11:
            if not (pd.isna(vals[k]) or str(vals[k]).strip()==""):
                seq.append(vals[k])
            k+=1
        if len(seq)<10:continue

        away_spread=odds_num(seq[0])
        total=parse_total(seq[2])
        away_ml=odds_num(seq[4])
        home_spread=odds_num(seq[5])
        home_ml=odds_num(seq[9])
        game_time=str(seq[10]).strip() if len(seq)>10 and seq[10] is not None else ""

        key="|".join(sorted([away,home]))
        away_implied=(total/2-away_spread/2) if total is not None and away_spread is not None else None
        home_implied=(total/2-home_spread/2) if total is not None and home_spread is not None else None
        games[key]={
            "away":away,"home":home,
            "away_name":away_name,"home_name":home_name,
            "away_spread":away_spread,"home_spread":home_spread,
            "total":total,"away_ml":away_ml,"home_ml":home_ml,
            "away_implied":away_implied,"home_implied":home_implied,
            "game_time":game_time
        }
    return games


@st.cache_data(show_spinner=False)
def cached_parse_gametotals_file(path_str, mtime):
    return parse_gametotals_xlsx(path_str)

def fmt_spread(v):
    if v is None:return "—"
    return f"{v:+g}"

def fmt_ml(v):
    if v is None:return "—"
    return f"{v:+.0f}"

def sync_game_editor():
    """Persist game-view checkbox edits to staged player pool."""
    state=st.session_state.get("game_pool_editor",{})
    edited=state.get("edited_rows",{}) if isinstance(state,dict) else {}
    mapping=st.session_state.get("game_editor_map",[])
    for row_idx,changes in edited.items():
        try:nid=mapping[int(row_idx)]
        except (ValueError,IndexError,TypeError):continue
        if "Use" in changes:
            if changes["Use"]:st.session_state.pending_pool_ids.add(nid)
            else:st.session_state.pending_pool_ids.discard(nid)


def team_badge(team):
    team=str(team).strip().upper()
    return f'<span class="team team-{team}">{team}</span>'


def slate_scope():
    if st.session_state.slate is None:
        return set(), set()
    teams=set(st.session_state.slate["Team"].dropna().astype(str).str.strip())
    games=set()
    for _,r in st.session_state.slate.iterrows():
        t=str(r["Team"]).strip()
        o=str(r["Opp"]).strip()
        if t and o and t!="nan" and o!="nan":
            games.add("|".join(sorted([t,o])))
    return teams,games

def slate_total_ranks():
    games=st.session_state.get("game_totals",{}) or {}
    slate_teams,slate_games=slate_scope()

    game_vals=[]
    team_vals={}
    for key,g in games.items():
        if key in slate_games and g.get("total") is not None:
            game_vals.append((key,float(g["total"])))
        for side in ("away","home"):
            team=g.get(side)
            imp=g.get(f"{side}_implied")
            if team in slate_teams and imp is not None:
                team_vals[team]=float(imp)

    game_vals.sort(key=lambda x:x[1],reverse=True)
    team_vals=sorted(team_vals.items(),key=lambda x:x[1],reverse=True)

    return (
        {k:i+1 for i,(k,_) in enumerate(game_vals)},
        {t:i+1 for i,(t,_) in enumerate(team_vals)},
        len(game_vals),
        len(team_vals)
    )

def heat_color(rank,total):
    if not rank or not total or total<=1:
        return "#f0ad4e"
    pct=(total-rank)/(total-1)
    if pct>=.75:return "#19c37d"
    if pct>=.50:return "#8bc34a"
    if pct>=.25:return "#f0ad4e"
    return "#ef5350"

def concentration_rank_and_color(team_counts,team):
    values=sorted(team_counts.values(),reverse=True)
    val=team_counts.get(team,0)
    rank=1+values.index(val) if values else None
    total=len(values)
    return rank,total,heat_color(rank,total)


def next_saved_id():
    used=[]
    for k in st.session_state.saved_lineups.keys():
        try:used.append(int(k))
        except:pass
    return (max(used)+1) if used else 0

def save_as_new_snapshot(draft_idx,lu):
    sid=next_saved_id()
    st.session_state.saved_lineups[str(sid)]=dict(lu)
    st.session_state.draft_saved_link[str(draft_idx)]=sid
    return sid

def update_linked_snapshot(draft_idx,lu):
    sid=st.session_state.draft_saved_link.get(str(draft_idx))
    if sid is None:
        return None
    if str(sid) not in st.session_state.saved_lineups:
        return None
    st.session_state.saved_lineups[str(sid)]=dict(lu)
    return sid

def apply_qb_plan(plan_rows):
    """
    Assign QB-anchored draft slots sequentially, up to 50.
    Existing saved portfolio entries are untouched.
    Empty/nonpositive targets are ignored.
    """
    slot_map={}
    draft_idx=0
    for _,r in plan_rows.iterrows():
        try:target=int(r.get("Target Lineups",0) or 0)
        except:target=0
        if target<=0:
            continue
        qb_id=r.get("Name + ID")
        qb_name=r.get("QB")
        if not qb_id:
            continue
        slots=[]
        for _ in range(target):
            if draft_idx>=MAX_LU:
                break
            st.session_state.lineups[draft_idx]=empty_lu()
            st.session_state.lineups[draft_idx]["QB"]=qb_id
            st.session_state.draft_saved_link.pop(str(draft_idx),None)
            slots.append(draft_idx)
            draft_idx+=1
        slot_map[str(qb_id)]={"qb":qb_name,"slots":slots}
        if draft_idx>=MAX_LU:
            break

    # clear remaining unused draft slots
    for i in range(draft_idx,MAX_LU):
        st.session_state.lineups[i]=empty_lu()
        st.session_state.draft_saved_link.pop(str(i),None)

    st.session_state.qb_slot_map=slot_map
    st.session_state.current_lu=0
    st.session_state.active_build_slot=0
    st.session_state.slot="RB1"
    return draft_idx

def qb_group_options():
    opts=[]
    for qb_id,data in st.session_state.qb_slot_map.items():
        if data.get("slots"):
            opts.append((data.get("qb",qb_id),qb_id,data["slots"]))
    return opts



def lineup_correlation(lu):
    ps=players(lu)
    out={"qb_stack":None,"bringback":None,"team_clusters":[],"game_clusters":[]}

    qb=next((p for p in ps if p["Position"]=="QB"),None)
    if qb:
        mates=[p for p in ps if p["Name + ID"]!=qb["Name + ID"] and p["Team"]==qb["Team"] and p["Position"] in ["RB","WR","TE"]]
        bring=[p for p in ps if p["Team"]==qb["Opp"] and p["Position"] in ["RB","WR","TE"]]
        if mates:
            out["qb_stack"]={"team":qb["Team"],"count":len(mates),"names":[p["Name"] for p in mates]}
        if bring:
            out["bringback"]={"team":qb["Opp"],"count":len(bring),"names":[p["Name"] for p in bring]}

    teams={}
    for p in ps:
        if p["Position"]=="DST":continue
        teams.setdefault(p["Team"],[]).append(p)
    for team,tps in teams.items():
        if len(tps)>=2:
            out["team_clusters"].append({"team":team,"count":len(tps),"names":[p["Name"] for p in tps]})

    games={}
    for p in ps:
        if p["Position"]=="DST":continue
        t=str(p["Team"]).strip(); o=str(p["Opp"]).strip()
        if not t or not o:continue
        key="|".join(sorted([t,o]))
        games.setdefault(key,[]).append(p)

    for key,gps in games.items():
        if len(gps)>=2:
            a,b=key.split("|")
            ca=sum(p["Team"]==a for p in gps); cb=sum(p["Team"]==b for p in gps)
            hi=max(ca,cb); lo=min(ca,cb)
            out["game_clusters"].append({
                "key":key,"label":f"{a}-{b} {hi}-{lo}","count":len(gps),
                "names":[p["Name"] for p in gps]
            })

    out["team_clusters"].sort(key=lambda x:(-x["count"],x["team"]))
    out["game_clusters"].sort(key=lambda x:(-x["count"],x["label"]))
    return out

def correlation_html(lu):
    c=lineup_correlation(lu)
    badges=[]
    if c["qb_stack"]:
        q=c["qb_stack"]
        badges.append(f'<span class="corr-badge corr-qb">QB+{q["count"]} {q["team"]}</span>')
    if c["bringback"]:
        b=c["bringback"]
        badges.append(f'<span class="corr-badge corr-bring">BRING-BACK {b["team"]} x{b["count"]}</span>')
    for g in c["game_clusters"][:3]:
        badges.append(f'<span class="corr-badge corr-game">GAME {g["label"]}</span>')
    qb_team=c["qb_stack"]["team"] if c["qb_stack"] else None
    for t in c["team_clusters"][:3]:
        if t["team"]==qb_team:continue
        badges.append(f'<span class="corr-badge corr-team">{t["team"]} x{t["count"]}</span>')
    if not badges:
        badges=['<span class="corr-badge corr-none">No meaningful correlation yet</span>']
    return '<div class="corr-wrap">'+"".join(badges)+'</div>'

def open_slots_for_position(lu,pos,preferred=None):
    orders={"QB":["QB"],"RB":["RB1","RB2","FLEX"],"WR":["WR1","WR2","WR3","FLEX"],"TE":["TE","FLEX"],"DST":["DST"]}
    slots=orders.get(pos,[])
    if preferred in slots:
        slots=[preferred]+[s for s in slots if s!=preferred]
    return [s for s in slots if not lu.get(s)]

def add_multiple_players(lu,player_ids,preferred_slot=None):
    added=[]; skipped=[]
    used=set(v for v in lu.values() if v)
    for nid in player_ids:
        p=pbyid(nid)
        if not p:continue
        if nid in used:
            skipped.append(p["Name"]); continue
        slots=open_slots_for_position(lu,p["Position"],preferred_slot)
        if not slots:
            skipped.append(p["Name"]); continue
        lu[slots[0]]=nid
        used.add(nid); added.append(p["Name"])
        preferred_slot=None
    return added,skipped

def saved_team_portfolio_summary():
    ds=saved_valid_lineups()
    if st.session_state.slate is None:return pd.DataFrame()
    rows=[]
    for team in sorted(st.session_state.slate["Team"].unique()):
        pool_df=st.session_state.slate[st.session_state.slate["Team"]==team]
        pool_count=sum(n in st.session_state.pending_pool_ids for n in pool_df["Name + ID"])
        lu_count=total_players=two_plus=three_plus=qb_stack_lu=0
        for _,lu in ds:
            ps=players(lu)
            n=sum(p["Team"]==team and p["Position"]!="DST" for p in ps)
            if n:
                lu_count+=1; total_players+=n; two_plus+=n>=2; three_plus+=n>=3
            c=lineup_correlation(lu)
            if c["qb_stack"] and c["qb_stack"]["team"]==team:
                qb_stack_lu+=1
        rows.append({
            "Team":team,"Pool":pool_count,"Saved LU":lu_count,"Players Used":total_players,
            "2+ Team LU":two_plus,"3+ Team LU":three_plus,"QB Stack LU":qb_stack_lu,
            "Portfolio %":round(lu_count/max(1,len(ds))*100,1) if ds else 0.0
        })
    return pd.DataFrame(rows)

def saved_game_portfolio_summary():
    """
    Summarize saved-lineup game concentration and game-stack structures.
    Returns a dict keyed by sorted team-pair game key.
    """
    summary={}
    ds=saved_valid_lineups()
    for _,lu in ds:
        ps=players(lu)
        # Group rostered skill players by actual game.
        game_players={}
        for p in ps:
            if p["Position"]=="DST":
                continue
            t=str(p["Team"]).strip()
            o=str(p["Opp"]).strip()
            if not t or not o:
                continue
            key="|".join(sorted([t,o]))
            game_players.setdefault(key,[]).append(p)

        for key,gps in game_players.items():
            teams=key.split("|")
            a,b=teams[0],teams[1]
            ca=sum(p["Team"]==a for p in gps)
            cb=sum(p["Team"]==b for p in gps)
            total=len(gps)

            if total<=1:
                stack_type="1-off"
            elif ca>0 and cb>0:
                hi=max(ca,cb); lo=min(ca,cb)
                stack_type=f"{hi}-{lo}"
            else:
                stack_type=f"{total}-0"

            rec=summary.setdefault(
                key,
                {
                    "lineups":0,
                    "2plus":0,
                    "3plus":0,
                    "4plus":0,
                    "types":{},
                    "max_players":0
                }
            )
            rec["lineups"]+=1
            rec["2plus"]+=total>=2
            rec["3plus"]+=total>=3
            rec["4plus"]+=total>=4
            rec["max_players"]=max(rec["max_players"],total)
            rec["types"][stack_type]=rec["types"].get(stack_type,0)+1
    return summary

def game_pool_summary():
    """One row per DK slate game with staged pool counts by team."""
    slate=st.session_state.slate
    if slate is None or slate.empty:
        return pd.DataFrame()

    rows=[]
    seen=set()
    saved_summary=saved_game_portfolio_summary()
    saved_n=max(1,len(saved_valid_lineups()))

    for _,r in slate.iterrows():
        t=str(r["Team"]).strip()
        o=str(r["Opp"]).strip()
        if not t or not o:
            continue
        key="|".join(sorted([t,o]))
        if key in seen:
            continue
        seen.add(key)

        odds=st.session_state.game_totals.get(key,{}) if st.session_state.get("game_totals") else {}
        if odds:
            away=odds.get("away") or key.split("|")[0]
            home=odds.get("home") or key.split("|")[1]
        else:
            away,home=key.split("|")[0],key.split("|")[1]

        away_all=slate[slate["Team"]==away]
        home_all=slate[slate["Team"]==home]

        away_pool=sum(n in st.session_state.pending_pool_ids for n in away_all["Name + ID"])
        home_pool=sum(n in st.session_state.pending_pool_ids for n in home_all["Name + ID"])
        game_pool=away_pool+home_pool

        port=saved_summary.get(key,{})
        types=port.get("types",{})
        type_txt=" • ".join(
            f"{k} x{v}"
            for k,v in sorted(
                types.items(),
                key=lambda kv:(-sum(int(x) for x in kv[0].split("-") if x.isdigit()),-kv[1],kv[0])
            )[:4]
        ) if types else "—"

        rows.append({
            "GameKey":key,
            "Game":f"{away} @ {home}",
            "Away":away,
            "Home":home,
            "Away Pool":away_pool,
            "Home Pool":home_pool,
            "Game Pool":game_pool,
            "Total":odds.get("total"),
            "Saved LU":port.get("lineups",0),
            "2+ Stack LU":port.get("2plus",0),
            "3+ Stack LU":port.get("3plus",0),
            "4+ Stack LU":port.get("4plus",0),
            "Portfolio %":round(port.get("lineups",0)/saved_n*100,1) if saved_valid_lineups() else 0.0,
            "Stack Types":type_txt,
            "Max Players":port.get("max_players",0)
        })

    out=pd.DataFrame(rows)
    if not out.empty:
        out=out.sort_values(
            ["Game Pool","Saved LU","Total"],
            ascending=[False,False,False],
            na_position="last"
        ).reset_index(drop=True)
    return out

def saved_items():
    items=[]
    for k,v in st.session_state.saved_lineups.items():
        try:i=int(k)
        except:continue
        items.append((i,v))
    return sorted(items,key=lambda x:x[0])

def saved_valid_lineups():
    return [(i,l) for i,l in saved_items() if complete(l) and valid(l)]

def saved_duplicate_groups():
    groups={}
    for i,l in saved_valid_lineups():
        sig=tuple(sorted(l.values()))
        groups.setdefault(sig,[]).append(i+1)
    return [v for v in groups.values() if len(v)>1]

def saved_exposure():
    ds=saved_valid_lineups()
    if not ds:
        return pd.DataFrame(columns=["Player","Pos","Team","Lineups","Exposure %"])
    m={}
    for _,lu in ds:
        for p in players(lu):
            m[p["Name + ID"]]=m.get(p["Name + ID"],0)+1
    rows=[]
    for nid,c in m.items():
        p=pbyid(nid)
        rows.append({
            "Player":p["Name"],"Pos":p["Position"],"Team":p["Team"],
            "Lineups":c,"Exposure %":round(c/len(ds)*100,1)
        })
    return pd.DataFrame(rows).sort_values(["Exposure %","Player"],ascending=[False,True])

def saved_combo_df(size):
    ds=saved_valid_lineups()
    if not ds:
        return pd.DataFrame(columns=["Combo","Lineups","Exposure %","Type"])
    m={}; memo={}
    for _,lu in ds:
        u={p["Name + ID"]:p for p in players(lu)}
        for ids in combinations(sorted(u),size):
            m[ids]=m.get(ids,0)+1
            memo[ids]=[u[x] for x in ids]
    rows=[]
    for ids,c in m.items():
        ps=memo[ids]
        if size==2:
            a,b=ps
            if a["Team"]==b["Team"] and "QB" in [a["Position"],b["Position"]]:
                typ="QB + teammate"
            elif a["Team"]==b["Team"]:
                typ="Same team"
            elif a["Opp"]==b["Team"] or b["Opp"]==a["Team"]:
                typ="Same game"
            else:
                typ="Other pair"
        else:
            qb=next((p for p in ps if p["Position"]=="QB"),None)
            typ="QB + 2" if qb and sum(p["Team"]==qb["Team"] for p in ps)>=3 else "Trio"
        rows.append({
            "Combo":" + ".join(p["Name"] for p in ps),
            "Lineups":c,
            "Exposure %":round(c/len(ds)*100,1),
            "Type":typ
        })
    return pd.DataFrame(rows).sort_values(["Exposure %","Combo"],ascending=[False,True])

def saved_dna():
    ds=saved_valid_lineups()
    if not ds:
        return {}
    d={"QB + 1":0,"QB + 2+":0,"Bring-back":0,"Double TE":0,"RB + DST":0,"4+ game stack":0}
    for _,lu in ds:
        s=stack(lu); ps=players(lu)
        d["QB + 1"]+=s["mates"]==1
        d["QB + 2+"]+=s["mates"]>=2
        d["Bring-back"]+=s["bring"]>=1
        d["Double TE"]+=sum(p["Position"]=="TE" for p in ps)>=2
        d["RB + DST"]+=bool(
            {p["Team"] for p in ps if p["Position"]=="RB"} &
            {p["Team"] for p in ps if p["Position"]=="DST"}
        )
        d["4+ game stack"]+=s["game"]>=4
    return {k:round(v/len(ds)*100) for k,v in d.items()}

def saved_dk_export():
    rows=[]
    for _,l in saved_valid_lineups():
        rows.append({
            "QB":l["QB"],"RB":l["RB1"],"RB.1":l["RB2"],
            "WR":l["WR1"],"WR.1":l["WR2"],"WR.2":l["WR3"],
            "TE":l["TE"],"FLEX":l["FLEX"],"DST":l["DST"]
        })
    return pd.DataFrame(rows).to_csv(index=False).encode()

def slate_overview():
    teams,games=slate_scope()
    odds=st.session_state.get("game_totals",{}) or {}
    gt=[]
    implied={}
    for key in games:
        g=odds.get(key,{})
        if g.get("total") is not None:
            gt.append((key,float(g["total"])))
        for side in ("away","home"):
            t=g.get(side)
            imp=g.get(f"{side}_implied")
            if t in teams and imp is not None:
                implied[t]=float(imp)
    gt.sort(key=lambda x:x[1],reverse=True)
    implied=sorted(implied.items(),key=lambda x:x[1],reverse=True)
    return {
        "teams":len(teams),
        "games":len(games),
        "games_with_lines":len(gt),
        "avg_total":round(sum(v for _,v in gt)/len(gt),1) if gt else None,
        "top_games":gt,
        "top_teams":implied
    }

def clean_pos(x):
    x=str(x).upper().strip()
    return "DST" if x in {"D","DEF","D/ST","DST"} else x

def opp_from_game(team,game):
    s="" if pd.isna(game) else str(game)
    m=re.search(r'([A-Z]{2,4})@([A-Z]{2,4})',s)
    if not m:return ""
    a,b=m.group(1),m.group(2)
    return b if team==a else a if team==b else ""


def parse_start_time(game_info):
    """Parse DraftKings Game Info like TEN@SF 12/14/2025 04:25PM ET."""
    if game_info is None or pd.isna(game_info):
        return pd.NaT
    s=str(game_info).strip()
    m=re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}\s*[AP]M)',s,re.I)
    if not m:
        return pd.NaT
    try:
        return pd.to_datetime(m.group(1)+" "+m.group(2),format="%m/%d/%Y %I:%M%p")
    except:
        return pd.to_datetime(m.group(1)+" "+m.group(2),errors="coerce")

def fmt_start(v):
    if v is None or pd.isna(v):
        return "—"
    try:
        ts=pd.Timestamp(v)
        return ts.strftime("%-I:%M %p")
    except:
        try:
            return pd.Timestamp(v).strftime("%I:%M %p").lstrip("0")
        except:
            return "—"

def flex_candidates(lu):
    """
    Return players who can legally occupy FLEX without breaking positional requirements.
    In DK classic, the FLEX position is the 'extra' RB/WR/TE beyond:
    2 RB, 3 WR, 1 TE.
    """
    ps=players(lu)
    skill=[p for p in ps if p["Position"] in ["RB","WR","TE"]]
    counts={
        "RB":sum(p["Position"]=="RB" for p in skill),
        "WR":sum(p["Position"]=="WR" for p in skill),
        "TE":sum(p["Position"]=="TE" for p in skill)
    }
    mins={"RB":2,"WR":3,"TE":1}
    flex_positions=[pos for pos in ["RB","WR","TE"] if counts[pos]>mins[pos]]
    return [p for p in skill if p["Position"] in flex_positions]

def flex_status(lu):
    flex=pbyid(lu.get("FLEX"))
    if not flex:
        return {
            "ok":False,"message":"No FLEX selected yet.",
            "flex":None,"latest":None,"candidates":[]
        }

    cands=flex_candidates(lu)
    if not cands:
        return {
            "ok":True,
            "message":"No alternative FLEX assignment available from current roster construction.",
            "flex":flex,"latest":flex,"candidates":[flex]
        }

    # Only candidates with known times can be ranked.
    known=[p for p in cands if p.get("Start") is not None and not pd.isna(p.get("Start"))]
    if not known:
        return {
            "ok":True,
            "message":"Kickoff times unavailable for FLEX candidates.",
            "flex":flex,"latest":flex,"candidates":cands
        }

    latest=max(known,key=lambda p:pd.Timestamp(p["Start"]))
    ok=latest["Name + ID"]==flex["Name + ID"]

    if ok:
        msg=f'{flex["Name"]} is already the latest-starting legal FLEX option ({fmt_start(flex["Start"])}).'
    else:
        msg=(
            f'{latest["Name"]} starts at {fmt_start(latest["Start"])} and can legally be moved to FLEX. '
            f'Current FLEX {flex["Name"]} starts at {fmt_start(flex.get("Start"))}.'
        )

    return {"ok":ok,"message":msg,"flex":flex,"latest":latest,"candidates":cands}

def optimize_flex(lu):
    """
    Reassign the latest-starting legal skill player to FLEX.
    Because the legal FLEX position is determined by the extra roster position,
    this only swaps players within that same position.
    """
    stat=flex_status(lu)
    latest=stat.get("latest")
    current=stat.get("flex")
    if not latest or not current or latest["Name + ID"]==current["Name + ID"]:
        return False

    latest_slot=None
    for s in SLOTS:
        if lu.get(s)==latest["Name + ID"]:
            latest_slot=s
            break
    if not latest_slot or latest_slot=="FLEX":
        return False

    # This should be a same-position swap because of flex_candidates logic.
    if latest["Position"]!=current["Position"]:
        return False

    lu["FLEX"],lu[latest_slot]=lu[latest_slot],lu["FLEX"]
    return True

def normalize(df):
    cm={str(c).strip().lower():c for c in df.columns}
    def f(*names):
        for n in names:
            if n.lower() in cm:return cm[n.lower()]
        return None
    cp=f("Position","Roster Position"); cnid=f("Name + ID","Name+ID","Name + Id")
    cn=f("Name"); cid=f("ID","Id"); cs=f("Salary"); cg=f("Game Info","GameInfo","game_id","Game","game")
    co=f("Opponent","Opp","opponent","opp")
    ct=f("TeamAbbrev","Team Abbrev","Team")
    miss=[]
    if not cp:miss.append("Position")
    if not cs:miss.append("Salary")
    if not ct:miss.append("TeamAbbrev")
    if not cnid and not(cn and cid):miss.append("Name + ID or Name/ID")
    if miss:raise ValueError("Missing DK columns: "+", ".join(miss))
    o=pd.DataFrame()
    o["Position"]=df[cp].map(clean_pos)
    if cnid:
        o["Name + ID"]=df[cnid].astype(str)
        o["Name"]=o["Name + ID"].str.replace(r"\s*\(\d+\)\s*$","",regex=True).str.strip()
    else:
        o["Name"]=df[cn].astype(str).str.strip()
        ids=df[cid].astype(str).str.replace(r"\.0$","",regex=True)
        o["Name + ID"]=o["Name"]+" ("+ids+")"
    o["Salary"]=pd.to_numeric(df[cs],errors="coerce").fillna(0).astype(int)
    o["Game Info"]=df[cg].fillna("").astype(str) if cg else ""
    o["Start"]=o["Game Info"].map(parse_start_time)
    o["Team"]=df[ct].fillna("").astype(str).str.upper().str.strip()
    o["Opp"]=df[co].fillna("").astype(str).str.upper().str.strip().values if co else [opp_from_game(t,g) for t,g in zip(o["Team"],o["Game Info"])]
    o=o[o["Position"].isin(["QB","RB","WR","TE","DST"])]
    return o[o["Salary"]>0].drop_duplicates("Name + ID").reset_index(drop=True)

def pbyid(nid):
    if st.session_state.slate is None or not nid:return None
    r=st.session_state.slate[st.session_state.slate["Name + ID"]==nid]
    return None if r.empty else r.iloc[0].to_dict()

def players(lu):
    return [p for p in (pbyid(lu.get(s)) for s in SLOTS) if p]

def salary(lu): return sum(p["Salary"] for p in players(lu))
def complete(lu): return all(lu.get(s) for s in SLOTS)

def valid(lu):
    vals=[lu.get(s) for s in SLOTS if lu.get(s)]
    if len(vals)!=len(set(vals)) or salary(lu)>CAP:return False
    for s in SLOTS:
        if lu.get(s):
            p=pbyid(lu[s])
            if not p or p["Position"] not in SLOT_POS[s]:return False
    return True

def done():
    return [(i,l) for i,l in enumerate(st.session_state.lineups) if complete(l) and valid(l)]

def stack(lu):
    qb=pbyid(lu.get("QB"))
    if not qb:return {"label":"—","mates":0,"bring":0,"game":0}
    ps=players(lu)
    mates=sum(1 for p in ps if p["Name + ID"]!=qb["Name + ID"] and p["Team"]==qb["Team"] and p["Position"] in ["RB","WR","TE"])
    bring=sum(1 for p in ps if p["Team"]==qb["Opp"] and p["Position"] in ["RB","WR","TE"])
    game=sum(1 for p in ps if p["Team"] in {qb["Team"],qb["Opp"]})
    return {"label":f"QB+{mates}"+(f"/{bring}" if bring else ""),"mates":mates,"bring":bring,"game":game}

def exposure():
    ds=done()
    if not ds:return pd.DataFrame(columns=["Player","Pos","Team","Lineups","Exposure %"])
    m={}
    for _,lu in ds:
        for p in players(lu):m[p["Name + ID"]]=m.get(p["Name + ID"],0)+1
    rows=[]
    for nid,c in m.items():
        p=pbyid(nid); rows.append({"Player":p["Name"],"Pos":p["Position"],"Team":p["Team"],"Lineups":c,"Exposure %":round(c/len(ds)*100,1)})
    return pd.DataFrame(rows).sort_values(["Exposure %","Player"],ascending=[False,True])

def combo_df(size):
    ds=done()
    if not ds:return pd.DataFrame(columns=["Combo","Lineups","Exposure %","Type"])
    m={}; memo={}
    for _,lu in ds:
        u={p["Name + ID"]:p for p in players(lu)}
        for ids in combinations(sorted(u),size):
            m[ids]=m.get(ids,0)+1; memo[ids]=[u[x] for x in ids]
    rows=[]
    for ids,c in m.items():
        ps=memo[ids]
        if size==2:
            a,b=ps
            if a["Team"]==b["Team"] and "QB" in [a["Position"],b["Position"]]:typ="QB + teammate"
            elif a["Team"]==b["Team"]:typ="Same team"
            elif a["Opp"]==b["Team"] or b["Opp"]==a["Team"]:typ="Same game"
            else:typ="Other pair"
        else:
            qb=next((p for p in ps if p["Position"]=="QB"),None)
            typ="QB + 2" if qb and sum(p["Team"]==qb["Team"] for p in ps)>=3 else "Trio"
        rows.append({"Combo":" + ".join(p["Name"] for p in ps),"Lineups":c,"Exposure %":round(c/len(ds)*100,1),"Type":typ})
    return pd.DataFrame(rows).sort_values(["Exposure %","Combo"],ascending=[False,True])

def dna():
    ds=done()
    if not ds:return {}
    d={"QB + 1":0,"QB + 2+":0,"Bring-back":0,"Double TE":0,"RB + DST":0,"4+ game stack":0}
    for _,lu in ds:
        s=stack(lu); ps=players(lu)
        d["QB + 1"]+=s["mates"]==1; d["QB + 2+"]+=s["mates"]>=2; d["Bring-back"]+=s["bring"]>=1
        d["Double TE"]+=sum(p["Position"]=="TE" for p in ps)>=2
        d["RB + DST"]+=bool({p["Team"] for p in ps if p["Position"]=="RB"} & {p["Team"] for p in ps if p["Position"]=="DST"})
        d["4+ game stack"]+=s["game"]>=4
    return {k:round(v/len(ds)*100) for k,v in d.items()}

def dupes():
    m={}
    for i,lu in done():
        sig=tuple(sorted(lu.values()));m.setdefault(sig,[]).append(i+1)
    return [x for x in m.values() if len(x)>1]

def workspace():
    return json.dumps({"slate_name":st.session_state.slate_name,"pool_ids":list(st.session_state.pool_ids),"lineups":st.session_state.lineups,"saved_lineups":st.session_state.saved_lineups,"draft_saved_link":st.session_state.draft_saved_link,"qb_plan":st.session_state.qb_plan,"qb_slot_map":st.session_state.qb_slot_map,"projection_overrides":st.session_state.projection_overrides},indent=2)

def restore(o):
    arr=o.get("lineups",[])[:MAX_LU]
    while len(arr)<MAX_LU:arr.append(empty_lu())
    st.session_state.lineups=arr
    st.session_state.pool_ids=set(o.get("pool_ids",[]))
    st.session_state.saved_lineups=o.get("saved_lineups",{})
    st.session_state.draft_saved_link=o.get("draft_saved_link",{})
    st.session_state.qb_plan=o.get("qb_plan",{})
    st.session_state.qb_slot_map=o.get("qb_slot_map",{})
    st.session_state.projection_overrides=o.get("projection_overrides",{})
    st.session_state.model_df=None
    st.session_state.pending_pool_ids=set(st.session_state.pool_ids)

def dk_export():
    rs=[]
    for _,l in done():
        rs.append({"QB":l["QB"],"RB":l["RB1"],"RB.1":l["RB2"],"WR":l["WR1"],"WR.1":l["WR2"],"WR.2":l["WR3"],"TE":l["TE"],"FLEX":l["FLEX"],"DST":l["DST"]})
    return pd.DataFrame(rs).to_csv(index=False).encode()




@st.cache_data(ttl=21600,show_spinner=False)
def load_depth_chart_2026():
    """
    nflverse weekly depth chart release.
    2025+ schema includes team, player_name, pos_abb, pos_rank.
    """
    urls=[
        "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2026.csv",
        "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2026.parquet"
    ]
    for url in urls:
        try:
            d=pd.read_csv(url) if url.endswith(".csv") else pd.read_parquet(url)
            return d
        except:
            pass
    return pd.DataFrame()

def latest_depth_roles(slate):
    d=load_depth_chart_2026()
    if d.empty:
        return pd.DataFrame(columns=["ModelName","DepthRole","DepthRank","DepthTeam"])

    name_col=next((c for c in ["player_name","full_name","football_name"] if c in d.columns),None)
    team_col=next((c for c in ["team","club_code"] if c in d.columns),None)
    pos_col=next((c for c in ["pos_abb","position","depth_position"] if c in d.columns),None)
    rank_col=next((c for c in ["pos_rank","depth_team"] if c in d.columns),None)
    if not name_col:
        return pd.DataFrame(columns=["ModelName","DepthRole","DepthRank","DepthTeam"])

    d=d.copy()
    # Restrict to latest date/week if columns exist.
    if "dt" in d.columns:
        mx=pd.to_datetime(d["dt"],errors="coerce").max()
        if not pd.isna(mx):
            d=d[pd.to_datetime(d["dt"],errors="coerce").eq(mx)]
    elif "week" in d.columns:
        wk=pd.to_numeric(d["week"],errors="coerce").max()
        if not pd.isna(wk):
            d=d[pd.to_numeric(d["week"],errors="coerce").eq(wk)]

    d["ModelName"]=d[name_col].map(norm_player_name)
    d["DepthTeam"]=d[team_col].astype(str).str.upper() if team_col else ""
    d["DepthPos"]=d[pos_col].astype(str).str.upper() if pos_col else ""
    if rank_col:
        ranks=pd.to_numeric(d[rank_col],errors="coerce")
    else:
        ranks=pd.Series(np.nan,index=d.index)

    d["DepthRank"]=ranks
    def role(row):
        pos=str(row["DepthPos"])
        r=row["DepthRank"]
        if pos=="QB":
            if pd.notna(r) and r<=1:return "STARTER"
            if pd.notna(r) and r>=2:return "BACKUP"
            return "UNKNOWN"
        if pd.notna(r):
            if r<=1:return "STARTER"
            if r<=3:return "ROTATION"
            return "BACKUP"
        return "UNKNOWN"
    d["DepthRole"]=d.apply(role,axis=1)

    # Prefer exact team match where possible; name is still primary.
    return d[["ModelName","DepthRole","DepthRank","DepthTeam"]].drop_duplicates(["ModelName","DepthTeam"])

def norm_player_name(name):
    s="" if name is None else str(name)
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode("ascii")
    s=s.lower()
    s=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b"," ",s)
    s=re.sub(r"[^a-z0-9 ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def ncol(df,name,default=0.0):
    if name in df.columns:
        return pd.to_numeric(df[name],errors="coerce").fillna(default)
    return pd.Series(default,index=df.index,dtype=float)

@st.cache_data(ttl=21600,show_spinner=False)
def load_free_nfl_history():
    """
    Free weekly player stats from nflverse.
    Tries 2024-2026 so the model automatically incorporates 2026 games once released.
    """
    frames=[]
    errors=[]
    for season in [2024,2025,2026]:
        url=f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv"
        try:
            d=pd.read_csv(url)
            if "season_type" in d.columns:
                d=d[d["season_type"].astype(str).str.upper().eq("REG")].copy()
            d["season_model"]=season
            frames.append(d)
        except Exception as e:
            errors.append(f"{season}: {type(e).__name__}")
    if not frames:
        return pd.DataFrame(),errors

    h=pd.concat(frames,ignore_index=True,sort=False)

    name_col=next((c for c in ["player_display_name","player_name","name"] if c in h.columns),None)
    if not name_col:
        return pd.DataFrame(),errors+["No player-name column found"]

    h["ModelName"]=h[name_col].map(norm_player_name)
    if "position" in h.columns:
        h["ModelPos"]=h["position"].astype(str).str.upper().replace({"HB":"RB","FB":"RB"})
    else:
        h["ModelPos"]=""

    # DraftKings classic scoring from box-score stats.
    py=ncol(h,"passing_yards")
    ptd=ncol(h,"passing_tds")
    ints=ncol(h,"interceptions")
    ry=ncol(h,"rushing_yards")
    rtd=ncol(h,"rushing_tds")
    rec=ncol(h,"receptions")
    rey=ncol(h,"receiving_yards")
    retd=ncol(h,"receiving_tds")
    fum=ncol(h,"fumbles_lost")
    twopt=ncol(h,"passing_2pt_conversions")+ncol(h,"rushing_2pt_conversions")+ncol(h,"receiving_2pt_conversions")

    h["DKFP"]=(
        py*.04 + ptd*4 - ints
        + ry*.10 + rtd*6
        + rec + rey*.10 + retd*6
        - fum + twopt*2
        + (py>=300).astype(float)*3
        + (ry>=100).astype(float)*3
        + (rey>=100).astype(float)*3
    )

    attempts=ncol(h,"attempts")
    carries=ncol(h,"carries")
    targets=ncol(h,"targets")
    h["RoleOpp"]=np.where(
        h["ModelPos"].eq("QB"),
        attempts + carries*.70,
        np.where(
            h["ModelPos"].eq("RB"),
            carries + targets*1.50,
            np.where(
                h["ModelPos"].isin(["WR","TE"]),
                targets*1.70 + carries,
                0
            )
        )
    )

    if "week" not in h.columns:
        h["week"]=0
    if "season" not in h.columns:
        h["season"]=h["season_model"]

    h["week"]=pd.to_numeric(h["week"],errors="coerce").fillna(0)
    h["season"]=pd.to_numeric(h["season"],errors="coerce").fillna(h["season_model"])
    h=h.sort_values(["ModelName","season","week"]).reset_index(drop=True)
    return h,errors

def salary_baseline(position,salary):
    s=float(salary)
    if position=="QB":
        return float(np.clip(12.0+(s-4000)*.0030,11,25))
    if position=="RB":
        return float(np.clip(4.5+(s-3000)*.0030,4,23))
    if position=="WR":
        return float(np.clip(4.0+(s-3000)*.0028,3.8,22))
    if position=="TE":
        return float(np.clip(3.5+(s-2500)*.0027,3.2,19))
    if position=="DST":
        return float(np.clip(5.0+(s-2000)*.0015,4,10))
    return 8.0

def betting_context(team,opp):
    key="|".join(sorted([str(team),str(opp)]))
    g=st.session_state.game_totals.get(key,{}) if st.session_state.get("game_totals") else {}
    implied=None
    spread=None
    if g:
        if g.get("away")==team:
            implied=g.get("away_implied"); spread=g.get("away_spread")
        elif g.get("home")==team:
            implied=g.get("home_implied"); spread=g.get("home_spread")
    game_rank,team_rank,ng,nt=slate_total_ranks()
    return {
        "key":key,
        "total":g.get("total") if g else None,
        "implied":implied,
        "spread":spread,
        "game_rank":game_rank.get(key),
        "team_rank":team_rank.get(team),
        "games":ng,
        "teams":nt
    }

def environment_multiplier(position,ctx):
    mult=1.0
    implied=ctx.get("implied")
    total=ctx.get("total")
    spread=ctx.get("spread")

    # Relative to ordinary NFL scoring environments; intentionally modest.
    if implied is not None:
        mult*=1+float(np.clip((float(implied)-23.0)*.012,-.08,.09))
    if total is not None:
        mult*=1+float(np.clip((float(total)-44.0)*.004,-.04,.05))

    if spread is not None:
        sp=float(spread)
        if position=="RB":
            if sp<=-6: mult*=1.04
            elif sp>=6: mult*=.96
        elif position in ["WR","TE"]:
            if sp>=6: mult*=1.025
        elif position=="QB" and abs(sp)<=3.5:
            mult*=1.015
    return float(np.clip(mult,.86,1.14))

def env_score_from_context(ctx):
    vals=[]
    if ctx.get("game_rank") and ctx.get("games"):
        vals.append(100*(ctx["games"]-ctx["game_rank"]+1)/ctx["games"])
    if ctx.get("team_rank") and ctx.get("teams"):
        vals.append(100*(ctx["teams"]-ctx["team_rank"]+1)/ctx["teams"])
    return float(np.mean(vals)) if vals else 50.0

def role_multiplier(hist_rows):
    if hist_rows is None or len(hist_rows)<5:
        return 1.0,"Unknown"
    recent=hist_rows.tail(3)["RoleOpp"].mean()
    baseline=hist_rows.tail(10)["RoleOpp"].mean()
    if not baseline or pd.isna(baseline):
        return 1.0,"Stable"
    ratio=float(np.clip(recent/baseline,.88,1.15))
    label="Up" if ratio>=1.06 else "Down" if ratio<=.94 else "Stable"
    return ratio,label

def normal_tail(threshold,mean,sd):
    sd=max(float(sd),1.5)
    z=(float(threshold)-float(mean))/(sd*math.sqrt(2))
    return .5*(1-math.erf(z))

def build_projection_model(slate,overrides):
    hist,errors=load_free_nfl_history()
    rows=[]

    # Index history by normalized player name for fast lookup.
    hist_groups={}
    if not hist.empty:
        for nm,g in hist.groupby("ModelName",sort=False):
            hist_groups[nm]=g

    depth=latest_depth_roles(slate)
    depth_map={}
    if not depth.empty:
        for _,dr in depth.iterrows():
            depth_map.setdefault(dr["ModelName"],[]).append(dr.to_dict())

    for _,p in slate.iterrows():
        pos=str(p["Position"])
        sal=int(p["Salary"])
        base_salary=salary_baseline(pos,sal)
        nm=norm_player_name(p["Name"])
        hg=hist_groups.get(nm,pd.DataFrame())

        depth_role="UNKNOWN"
        depth_rank=np.nan
        drows=depth_map.get(nm,[])
        if drows:
            exact=[x for x in drows if str(x.get("DepthTeam","")).upper()==str(p["Team"]).upper()]
            dr=(exact or drows)[0]
            depth_role=dr.get("DepthRole","UNKNOWN")
            depth_rank=dr.get("DepthRank",np.nan)

        if not hg.empty and pos!="DST":
            # Prefer same listed position where possible.
            samepos=hg[hg["ModelPos"].eq(pos)]
            if len(samepos)>=2:
                hg=samepos
            hg=hg.sort_values(["season","week"])
            # Exclude extreme zero-opportunity rows when enough real games exist.
            real=hg[(hg["RoleOpp"]>0)|(hg["DKFP"]>1)]
            if len(real)>=3:
                hg=real

        games=len(hg)
        ctx=betting_context(str(p["Team"]),str(p["Opp"]))
        env_mult=environment_multiplier(pos,ctx)
        env_score=env_score_from_context(ctx)

        rmult,rtrend=role_multiplier(hg) if games else (1.0,"Unknown")

        if games:
            last8=hg.tail(8)
            weights=np.linspace(.70,1.30,len(last8))
            recent=float(np.average(last8["DKFP"],weights=weights))
            med_hist=float(hg.tail(17)["DKFP"].median())
            if games>=6:
                median=.55*recent+.25*med_hist+.20*base_salary
            elif games>=3:
                median=.45*recent+.20*med_hist+.35*base_salary
            else:
                median=.25*recent+.75*base_salary
            median*=rmult*env_mult

            hist_floor=float(hg.tail(17)["DKFP"].quantile(.20))
            hist_ceil=float(hg.tail(17)["DKFP"].quantile(.85))
            floor=max(0,min(median*.72,hist_floor*env_mult*rmult))
            ceiling=max(median*1.34,hist_ceil*env_mult*rmult)
            ceiling=min(ceiling,median*2.25)
            hsd=float(hg.tail(12)["DKFP"].std(ddof=0)) if len(hg.tail(12))>1 else median*.28
            confidence=float(np.clip(34+games*5.5,38,94))
        else:
            median=base_salary*env_mult
            floor=max(0,median*.54)
            ceiling=median*1.60
            hsd=median*.32
            confidence=28 if pos!="DST" else 38
            rtrend="No history"

        # Structural backup-QB guardrail.
        if pos=="QB" and depth_role=="BACKUP":
            median=min(median,2.0)
            floor=0.0
            ceiling=min(ceiling,9.0)
            confidence=max(confidence,90)

        override=float(overrides.get(str(p["Name + ID"]),0) or 0)
        override=np.clip(override,-50,150)
        if override:
            om=1+override/100
            median*=om
            floor*=max(.5,min(om,1.5))
            ceiling*=om
            confidence=max(20,confidence-5)

        # Plausibility clamps.
        caps={"QB":38,"RB":36,"WR":37,"TE":30,"DST":18}
        median=float(np.clip(median,0,caps.get(pos,35)))
        floor=float(np.clip(floor,0,median))
        ceiling=float(np.clip(ceiling,max(median,floor),caps.get(pos,40)*1.35))

        sd=max(hsd,(ceiling-floor)/2.56,2.0)
        boom_mult=3.2 if pos=="QB" else 3.0 if pos=="DST" else 4.0
        boom_threshold=(sal/1000)*boom_mult
        boom=100*normal_tail(boom_threshold,median,sd)
        value=median/(sal/1000)

        rows.append({
            "Name + ID":p["Name + ID"],
            "Player":p["Name"],
            "Pos":pos,
            "Team":p["Team"],
            "Opp":p["Opp"],
            "Salary":sal,
            "Median":round(median,2),
            "Floor":round(floor,2),
            "Ceiling":round(ceiling,2),
            "Value":round(value,2),
            "Boom %":round(float(np.clip(boom,0,100)),1),
            "Hist Games":games,
            "Confidence":round(confidence),
            "Role Trend":rtrend,
            "Depth Role":depth_role,
            "Depth Rank":depth_rank,
            "Role Adj %":round(override,1),
            "Env Score":round(env_score,1),
            "Game Rank":ctx.get("game_rank"),
            "Team Total Rank":ctx.get("team_rank"),
            "Implied Total":ctx.get("implied"),
        })

    out=pd.DataFrame(rows)
    if out.empty:
        return out,errors

    # Percentile features by position.
    feature_cols=["Median","Ceiling","Value","Boom %","Env Score"]
    for col in feature_cols:
        out[f"_{col}P"]=out.groupby("Pos")[col].rank(pct=True,method="average")

    # Heuristic popularity estimate: useful as a field-popularity signal, not paid ownership.
    own_budgets={"QB":100.0,"RB":260.0,"WR":360.0,"TE":120.0,"DST":100.0}
    out["Est Own %"]=0.0
    for pos,gidx in out.groupby("Pos").groups.items():
        idx=list(gidx)
        g=out.loc[idx]
        sal_p=g["Salary"].rank(pct=True)
        appeal=(
            .38*g["_MedianP"]+
            .30*g["_ValueP"]+
            .17*g["_Env ScoreP"]+
            .15*sal_p
        )
        weights=np.exp(3.4*appeal.to_numpy())-1
        weights=np.maximum(weights,.001)

        playable=np.ones(len(g),dtype=bool)
        if pos=="QB":
            # QB backups should not absorb DFS ownership.
            playable=~g["Depth Role"].eq("BACKUP").to_numpy()
            # Also filter obvious non-starting QBs with near-zero projection.
            playable &= (g["Median"]>=8).to_numpy()

        weights=np.where(playable,weights,0.0)
        budget=own_budgets.get(pos,100.0)
        if weights.sum()>0:
            own=budget*weights/weights.sum()
        else:
            own=np.zeros(len(weights))
        out.loc[idx,"Est Own %"]=own

    # Hard guardrail: non-starting QBs cannot carry field ownership.
    qb_backup=(out["Pos"].eq("QB")) & (
        out["Depth Role"].eq("BACKUP")
        | (out["Median"]<8)
    )
    out.loc[qb_backup,"Est Own %"]=0.0
    out["Est Own %"]=out["Est Own %"].clip(0,48).round(1)
    out["_LeverageP"]=1-out.groupby("Pos")["Est Own %"].rank(pct=True,method="average")
    out["_ConfP"]=out["Confidence"]/100

    out["Small Field"]=(
        100*(
            .45*out["_MedianP"]+
            .20*out["_CeilingP"]+
            .15*out["_ValueP"]+
            .10*out["_ConfP"]+
            .05*out["_Env ScoreP"]+
            .05*out["_LeverageP"]
        )
    ).round(1)

    out["Large Field"]=(
        100*(
            .18*out["_MedianP"]+
            .34*out["_CeilingP"]+
            .20*out["_Boom %P"]+
            .15*out["_LeverageP"]+
            .08*out["_Env ScoreP"]+
            .05*out["_ValueP"]
        )
    ).round(1)

    drop=[c for c in out.columns if c.startswith("_")]
    return out.drop(columns=drop),errors

def sync_pool_editor():
    """Capture checkbox edits immediately into a staged pool that survives filters."""
    state=st.session_state.get("pool_editor",{})
    edited=state.get("edited_rows",{}) if isinstance(state,dict) else {}
    mapping=st.session_state.get("pool_editor_map",[])
    for row_idx,changes in edited.items():
        try:
            nid=mapping[int(row_idx)]
        except (ValueError,IndexError,TypeError):
            continue
        if "Use" in changes:
            if changes["Use"]:
                st.session_state.pending_pool_ids.add(nid)
            else:
                st.session_state.pending_pool_ids.discard(nid)

st.title("NUKE NFL DFS HUB")
st.markdown("<div class=\"nuke-section-kicker\">NFL DFS COMMAND CENTER</div>",unsafe_allow_html=True)
st.caption("Slate Intel • Player Pool • QB Planning • Multi-Lineup Hand Building • Late Swap • Portfolio Control")

with st.sidebar:
    st.markdown('<div class="nuke-section-kicker">NUKE CONTROL PANEL</div>',unsafe_allow_html=True)
    st.subheader("Slate")
    up=st.file_uploader("Optional: override current weekly DK slate",type="csv",help="Leave empty to use the same built-in weekly slate as NUKE SIM.")
    try:
        source_name=up.name if up is not None else SLATE_LABEL
        should_load=(st.session_state.slate is None or st.session_state.slate_name!=source_name)
        if should_load:
            raw=pd.read_csv(up) if up is not None else load_default_slate()
            sl=normalize(raw)
            st.session_state.slate=sl
            st.session_state.slate_name=source_name
            valid_ids=set(sl["Name + ID"])
            st.session_state.pool_ids={x for x in st.session_state.pool_ids if x in valid_ids}
            st.session_state.pending_pool_ids={x for x in st.session_state.pending_pool_ids if x in valid_ids}
            for lu in st.session_state.lineups:
                for slot_name in SLOTS:
                    if lu.get(slot_name) not in valid_ids:
                        lu[slot_name]=None
            if not st.session_state.pending_pool_ids and st.session_state.pool_ids:
                st.session_state.pending_pool_ids=set(st.session_state.pool_ids)
        if up is None:
            st.success(f"Auto-loaded {SLATE_LABEL} · {len(st.session_state.slate):,} players")
        else:
            st.info(f"Using uploaded override: {up.name} · {len(st.session_state.slate):,} players")
    except Exception as e:
        st.error(f"Could not load slate: {e}")
    st.caption(st.session_state.slate_name)

    st.divider()
    st.subheader("Game Totals / Spreads")
    local_totals=Path("gametotals.xlsx")
    odds_up=st.file_uploader("Optional gametotals.xlsx",type=["xlsx"],key="odds_upload")
    try:
        if odds_up is not None:
            parsed=parse_gametotals_xlsx(odds_up)
            if parsed:
                st.session_state.game_totals=parsed
                st.session_state.game_totals_source=odds_up.name
        elif local_totals.exists():
            parsed=cached_parse_gametotals_file(str(local_totals),local_totals.stat().st_mtime)
            if parsed:
                st.session_state.game_totals=parsed
                st.session_state.game_totals_source="gametotals.xlsx (local)"
    except Exception as e:
        st.warning(f"Could not read game totals: {e}")

    if st.session_state.game_totals:
        st.success(f"{len(st.session_state.game_totals)} games loaded")
        st.caption(st.session_state.game_totals_source)
    else:
        st.caption("Place gametotals.xlsx beside app.py or upload it here.")

    st.divider()
    wup=st.file_uploader("Load workspace",type="json")
    if wup is not None and st.button("Restore workspace"):
        try:restore(json.load(wup));st.success("Restored");st.rerun()
        except Exception as e:st.error(str(e))
    st.download_button("Save workspace",workspace(),"nuke_workspace.json","application/json",use_container_width=True)

if st.session_state.slate is None:
    st.info("The built-in weekly slate could not be loaded. Use the optional sidebar override.")
    st.stop()

# Shared Hub ↔ SIM session bridge. Import is explicit so existing Hub lineups are never overwritten silently.
shared_rows=st.session_state.get("nuke_shared_portfolio_rows",[])
shared_ver=int(st.session_state.get("nuke_shared_portfolio_version",0))
imported_ver=int(st.session_state.get("nuke_hub_imported_portfolio_version",0))
if shared_rows and shared_ver>0:
    with st.container(border=True):
        b1,b2=st.columns([3,1])
        b1.markdown("#### ☢️ NUKE SIM Portfolio Ready")
        b1.caption(f"{len(shared_rows)} Portfolio Intelligence lineups are available from NUKE SIM. Import adds them to Saved Lineups and never overwrites your existing saved lineups.")
        label="Imported" if imported_ver==shared_ver else "IMPORT SIM PORTFOLIO"
        if b2.button(label,type="primary",use_container_width=True,disabled=(imported_ver==shared_ver),key=f"import_sim_portfolio_{shared_ver}"):
            valid_ids=set(st.session_state.slate["Name + ID"].astype(str))
            imported=0
            skipped=0
            next_id=next_saved_id()
            for item in shared_rows:
                lu=portable_to_hub_lineup(item)
                if not lu or any(str(v) not in valid_ids for v in lu.values()):
                    skipped+=1
                    continue
                st.session_state.saved_lineups[str(next_id)]=dict(lu)
                next_id+=1
                imported+=1
            st.session_state["nuke_hub_imported_portfolio_version"]=shared_ver
            if imported:
                st.success(f"Imported {imported} NUKE SIM lineups into Saved Lineups" + (f" · skipped {skipped} slate mismatches" if skipped else ""))
            else:
                st.warning("No SIM lineups matched the Hub slate. Make sure both pages are using the same DraftKings slate.")
            st.rerun()

hub,modeltab,pooltab,qbplantab,buildtab,savedtab,exptab=st.tabs(["HUB","PLAYER MODEL","PLAYER POOL","QB PLAN","BUILD","SAVED LINEUPS","EXPOSURE & COMBOS"])

with hub:
    ov=slate_overview()
    st.subheader("Slate Overview")

    a,b,c,d=st.columns(4)
    a.metric("Games on DK slate",ov["games"])
    b.metric("Teams on DK slate",ov["teams"])
    c.metric("Games with betting lines",ov["games_with_lines"])
    d.metric("Average game total","—" if ov["avg_total"] is None else f'{ov["avg_total"]:.1f}')

    game_rank,team_rank,ng,nt=slate_total_ranks()

    if ov["top_games"]:
        left,right=st.columns([1.05,.95],gap="large")

        with left:
            st.markdown("#### Game Total Rankings")
            rows=[]
            for key,total in ov["top_games"]:
                g=st.session_state.game_totals.get(key,{})
                rows.append({
                    "Rank":game_rank.get(key),
                    "Game":f'{g.get("away","?")} @ {g.get("home","?")}',
                    "Total":total
                })
            gdf=pd.DataFrame(rows)
            st.dataframe(gdf,hide_index=True,use_container_width=True)

        with right:
            st.markdown("#### Implied Team Total Rankings")
            rows=[]
            for team,imp in ov["top_teams"]:
                rows.append({
                    "Rank":team_rank.get(team),
                    "Team":team,
                    "Implied Total":imp
                })
            tdf=pd.DataFrame(rows)
            st.dataframe(tdf,hide_index=True,use_container_width=True)

        st.caption("All ranks use only games and teams actually present in the uploaded DraftKings slate.")

    st.divider()
    st.subheader("Saved Portfolio")
    ds=saved_valid_lineups()
    ex=saved_exposure()
    cm=saved_combo_df(2)

    p1,p2,p3,p4=st.columns(4)
    p1.metric("Saved lineups",len(st.session_state.saved_lineups))
    p2.metric("Valid saved lineups",len(ds))
    p3.metric("Highest player exposure","—" if ex.empty else f"{ex.iloc[0]['Exposure %']:.0f}%")
    p4.metric("Highest combo exposure","—" if cm.empty else f"{cm.iloc[0]['Exposure %']:.0f}%")

    dups=saved_duplicate_groups()
    if dups:
        st.error("Duplicate saved lineups: "+"; ".join(", ".join(map(str,g)) for g in dups))


with modeltab:
    st.subheader("NUKE Player Model")
    st.caption("Free projection model using nflverse history/usage/depth charts + DraftKings salary + your slate's betting environment. Small/Large Field are contest scores, not separate fantasy-point projections.")

    st.markdown("#### Free Projection Engine")
    st.caption(
        "No subscriptions or API keys required. The model uses free nflverse history/depth charts, "
        "DraftKings salary, and your slate's game totals/spreads/implied totals."
    )

    c1,c2,c3=st.columns([.9,.9,1.8])
    if c1.button("LOAD / REFRESH MODEL",type="primary",use_container_width=True):
        with st.spinner("Loading free NFL history and building slate model..."):
            model,errs=build_projection_model(
                st.session_state.slate,
                st.session_state.projection_overrides
            )
            st.session_state.model_df=model
            st.session_state.model_errors=errs
        st.rerun()

    if c2.button("CLEAR MODEL",use_container_width=True):
        st.session_state.model_df=None
        st.session_state.model_errors=[]
        st.rerun()

    c3.caption("Historical data is cached for 6 hours, so normal lineup-building clicks do not repeatedly download or rebuild the model.")

    model=st.session_state.model_df
    if model is None or model.empty:
        st.info("Click **LOAD / REFRESH MODEL** once after the weekly slate loads. The app will not fetch historical data until you ask it to.")
    else:
        matched=int((model["Hist Games"]>0).sum())
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Players modeled",len(model))
        m2.metric("Historical matches",f"{matched} / {len(model)}")
        m3.metric("High confidence",int((model["Confidence"]>=75).sum()))
        m4.metric("Manual role overrides",len(st.session_state.projection_overrides))

        if st.session_state.model_errors:
            st.caption("Data-source notes: "+", ".join(st.session_state.model_errors))

        f1,f2,f3,f4=st.columns([1.2,.7,.7,.8])
        mq=f1.text_input("Search model",placeholder="Player, team…",key="model_search")
        mpos=f2.selectbox("Position",["ALL","QB","RB","WR","TE","DST"],key="model_pos")
        mteam=f3.selectbox("Team",["ALL"]+sorted(model["Team"].unique()),key="model_team")
        contest=f4.selectbox("Rank by",["Large Field","Small Field","Median","Ceiling","Value"],key="model_rank")

        view=model.copy()
        if mq:
            q=mq.lower()
            view=view[view.apply(lambda r:q in f'{r["Player"]} {r["Team"]} {r["Opp"]}'.lower(),axis=1)]
        if mpos!="ALL":
            view=view[view["Pos"]==mpos]
        if mteam!="ALL":
            view=view[view["Team"]==mteam]

        view=view.sort_values([contest,"Median"],ascending=[False,False])

        display_cols=[
            "Player","Pos","Team","Salary","Median","Floor","Ceiling",
            "Value","Boom %","Est Own %","Small Field","Large Field",
            "Confidence","Depth Role","Role Trend","Hist Games"
        ]
        st.dataframe(
            view[display_cols],
            hide_index=True,
            use_container_width=True,
            height=570,
            column_config={
                "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
                "Median":st.column_config.NumberColumn("Median",format="%.1f"),
                "Floor":st.column_config.NumberColumn("Floor",format="%.1f"),
                "Ceiling":st.column_config.NumberColumn("Ceiling",format="%.1f"),
                "Value":st.column_config.NumberColumn("Value",format="%.2fx"),
                "Boom %":st.column_config.NumberColumn("Boom %",format="%.1f%%"),
                "Est Own %":st.column_config.NumberColumn("Est Own*",format="%.1f%%"),
                "Small Field":st.column_config.NumberColumn("Small",format="%.1f"),
                "Large Field":st.column_config.NumberColumn("Large",format="%.1f"),
                "Confidence":st.column_config.ProgressColumn("Confidence",min_value=0,max_value=100,format="%d")
            }
        )
        st.caption("*Est Own is a heuristic field-popularity estimate. Backup QBs identified by the depth chart are structurally forced to 0.0%.")

        st.divider()
        st.markdown("#### Player Role Adjustment")
        st.caption("Use this for injury/role news the historical model cannot know — e.g. a backup RB becomes the starter. The adjustment changes that player's projection after you refresh the model.")

        selectable=view["Name + ID"].tolist()
        if selectable:
            labels={nid:model.loc[model["Name + ID"]==nid,"Player"].iloc[0] for nid in selectable}
            chosen_id=st.selectbox(
                "Player",
                selectable,
                format_func=lambda x:labels.get(x,x),
                key="override_player"
            )
            current=float(st.session_state.projection_overrides.get(chosen_id,0))
            o1,o2,o3=st.columns([.8,.8,1.4])
            new_adj=o1.number_input(
                "Role adjustment %",
                min_value=-50.0,max_value=150.0,value=current,step=5.0,
                key="override_amount"
            )
            if o2.button("SAVE ADJUSTMENT",use_container_width=True):
                if abs(new_adj)<.01:
                    st.session_state.projection_overrides.pop(chosen_id,None)
                else:
                    st.session_state.projection_overrides[chosen_id]=float(new_adj)
                with st.spinner("Rebuilding model..."):
                    model,errs=build_projection_model(
                        st.session_state.slate,
                        st.session_state.projection_overrides
                    )
                    st.session_state.model_df=model
                    st.session_state.model_errors=errs
                st.rerun()
            if o3.button("REMOVE ALL ROLE ADJUSTMENTS",use_container_width=True):
                st.session_state.projection_overrides={}
                with st.spinner("Rebuilding model..."):
                    model,errs=build_projection_model(st.session_state.slate,{})
                    st.session_state.model_df=model
                    st.session_state.model_errors=errs
                st.rerun()


with pooltab:
    st.markdown('<div class="nuke-section-kicker">YOUR DRAFT BOARD</div>',unsafe_allow_html=True)
    st.subheader("Choose the players you actually want to use")

    pool_counts=st.session_state.slate[
        st.session_state.slate["Name + ID"].isin(st.session_state.pending_pool_ids)
    ]["Position"].value_counts().to_dict()
    st.markdown(
        '<div class="nuke-player-pool-banner">'
        + f'<span class="nuke-pill">POOL {len(st.session_state.pending_pool_ids)} / {len(st.session_state.slate)}</span>'
        + ''.join(
            f'<span class="nuke-pill">{p} {int(pool_counts.get(p,0))}</span>'
            for p in ["QB","RB","WR","TE","DST"]
        )
        + '</div>',
        unsafe_allow_html=True
    )
    st.caption("Selections are staged as you filter. Nothing is committed until you click **Apply Player Pool Changes**.")

    player_view,game_view=st.tabs(["PLAYERS","GAME BY GAME"])

    with player_view:
        f1,f2,f3=st.columns([1.4,.7,.7])
        q=f1.text_input("Search",placeholder="Player, team, opponent…",key="poolq")
        teams=["ALL"]+sorted(st.session_state.slate["Team"].unique())
        tm=f2.selectbox("Team",teams,key="pooltm")
        po=f3.selectbox("Position",["ALL","QB","RB","WR","TE","DST"],key="poolpo")

        df=st.session_state.slate.copy()
        if q:
            qq=q.lower()
            df=df[df.apply(lambda r:qq in f"{r['Name']} {r['Team']} {r['Opp']} {r['Position']}".lower(),axis=1)]
        if tm!="ALL":df=df[df["Team"]==tm]
        if po!="ALL":df=df[df["Position"]==po]
        df=df.sort_values(["Team","Salary"],ascending=[True,False]).copy()

        if st.session_state.model_df is not None and not st.session_state.model_df.empty:
            model_cols=st.session_state.model_df[
                ["Name + ID","Median","Ceiling","Small Field","Large Field","Est Own %"]
            ].copy()
            df=df.merge(model_cols,on="Name + ID",how="left")

        df.insert(0,"Use",df["Name + ID"].isin(st.session_state.pending_pool_ids))

        st.session_state.pool_editor_map=df["Name + ID"].tolist()

        staged_add=len(st.session_state.pending_pool_ids-st.session_state.pool_ids)
        staged_remove=len(st.session_state.pool_ids-st.session_state.pending_pool_ids)
        a,b,c=st.columns(3)
        a.metric("Committed pool",len(st.session_state.pool_ids))
        b.metric("Staged additions",staged_add)
        c.metric("Staged removals",staged_remove)

        st.caption(f"{len(df)} players shown • {len(st.session_state.pending_pool_ids)} players staged for the next pool")

        pool_cols=["Use","Name","Position","Team","Opp","Salary"]
        if "Median" in df.columns:
            pool_cols+=["Median","Ceiling","Small Field","Large Field","Est Own %"]
        pool_cols+=["Name + ID"]

        st.data_editor(
            df[pool_cols],
            hide_index=True,
            use_container_width=True,
            height=590,
            disabled=[c for c in pool_cols if c!="Use"],
            column_config={
                "Use":st.column_config.CheckboxColumn("Use",width="small"),
                "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
                "Median":st.column_config.NumberColumn("Med",format="%.1f"),
                "Ceiling":st.column_config.NumberColumn("Ceil",format="%.1f"),
                "Small Field":st.column_config.NumberColumn("Small",format="%.0f"),
                "Large Field":st.column_config.NumberColumn("Large",format="%.0f"),
                "Est Own %":st.column_config.NumberColumn("Est Own*",format="%.1f%%"),
                "Name + ID":None,
            },
            key="pool_editor",
            on_change=sync_pool_editor
        )

    with game_view:
        st.caption("Matchup dashboard using the Team + Opponent fields from DraftKings and your gametotals.xlsx betting lines.")

        st.markdown('<div class="nuke-section-kicker">SLATE GAME MAP</div>',unsafe_allow_html=True)
        st.markdown("### Player Pool + Portfolio by Game")

        game_summary=game_pool_summary()
        if not game_summary.empty:
            sort1,sort2=st.columns([.45,1.55])
            game_sort=sort1.selectbox(
                "Sort game map by",
                ["Most stacked","Most saved lineup appearances","Most pool players","Highest game total","Most 4+ stacks"],
                key="game_map_sort"
            )
            if game_sort=="Most stacked":
                game_summary=game_summary.sort_values(["3+ Stack LU","4+ Stack LU","Saved LU","Game Pool"],ascending=[False,False,False,False],na_position="last")
            elif game_sort=="Most saved lineup appearances":
                game_summary=game_summary.sort_values(["Saved LU","3+ Stack LU","Game Pool"],ascending=[False,False,False],na_position="last")
            elif game_sort=="Most pool players":
                game_summary=game_summary.sort_values(["Game Pool","Saved LU"],ascending=[False,False],na_position="last")
            elif game_sort=="Highest game total":
                game_summary=game_summary.sort_values(["Total","Game Pool"],ascending=[False,False],na_position="last")
            else:
                game_summary=game_summary.sort_values(["4+ Stack LU","3+ Stack LU","Saved LU"],ascending=[False,False,False],na_position="last")
            game_summary=game_summary.reset_index(drop=True)
            sort2.caption("Most stacked prioritizes games appearing with 3+ correlated players across your saved portfolio.")
            total_saved=len(saved_valid_lineups())
            o1,o2,o3,o4=st.columns(4)
            o1.metric("Slate games",len(game_summary))
            o2.metric("Pool players",len(st.session_state.pending_pool_ids))
            o3.metric("Saved lineups",total_saved)
            o4.metric(
                "Most-used game",
                "—" if game_summary.empty or game_summary.iloc[0]["Saved LU"]==0
                else game_summary.sort_values("Saved LU",ascending=False).iloc[0]["Game"]
            )

            # Compact one-view cards: 3 games across.
            card_cols=st.columns(3,gap="small")
            for gi,row in game_summary.iterrows():
                with card_cols[gi%3]:
                    total=row["Total"]
                    total_txt="—" if pd.isna(total) else f'{float(total):g}'
                    port_pct=float(row["Portfolio %"])
                    port_color="#19c37d" if port_pct<35 else "#f2c94c" if port_pct<65 else "#ff5d5d"

                    st.markdown(
                        '<div class="nuke-card" style="margin-bottom:8px">'
                        '<div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">'
                        '<div>'
                        '<div style="font-size:.74rem;font-weight:1000;letter-spacing:.07em">'+str(row["Game"])+'</div>'
                        '<div style="font-size:.69rem;opacity:.58;margin-top:2px">O/U '+total_txt+'</div>'
                        '</div>'
                        '<div style="font-size:.68rem;font-weight:950;color:'+port_color+'">'
                        +f'{row["Saved LU"]} SAVED LU'
                        +'</div></div>'
                        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;margin-top:8px">'
                        '<div class="lineup-summary-cell"><span class="lbl">'+str(row["Away"])+' POOL</span><span class="val">'+str(int(row["Away Pool"]))+'</span></div>'
                        '<div class="lineup-summary-cell"><span class="lbl">'+str(row["Home"])+' POOL</span><span class="val">'+str(int(row["Home Pool"]))+'</span></div>'
                        '<div class="lineup-summary-cell"><span class="lbl">GAME POOL</span><span class="val">'+str(int(row["Game Pool"]))+'</span></div>'
                        '</div>'
                        '<div style="font-size:.68rem;opacity:.68;margin-top:7px">'
                        '<b>Game stacks:</b> '+str(row["Stack Types"])
                        +'</div>'
                        '<div style="font-size:.66rem;opacity:.54;margin-top:3px">'
                        +f'2+ players: {int(row["2+ Stack LU"])} LU • 3+: {int(row["3+ Stack LU"])} • 4+: {int(row["4+ Stack LU"])}'
                        +'</div>'
                        '</div>',
                        unsafe_allow_html=True
                    )

            with st.expander("Detailed game portfolio table"):
                detail=game_summary[
                    [
                        "Game","Total","Away Pool","Home Pool","Game Pool",
                        "Saved LU","Portfolio %","2+ Stack LU","3+ Stack LU",
                        "4+ Stack LU","Stack Types","Max Players"
                    ]
                ].copy()
                st.dataframe(
                    detail,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Total":st.column_config.NumberColumn("O/U",format="%.1f"),
                        "Portfolio %":st.column_config.NumberColumn("Saved LU %",format="%.1f%%")
                    }
                )

            with st.expander("Team stacking / exposure ranking"):
                team_summary=saved_team_portfolio_summary()
                if not team_summary.empty:
                    team_sort=st.selectbox(
                        "Sort teams by",
                        ["QB Stack LU","3+ Team LU","2+ Team LU","Saved LU","Pool","Players Used"],
                        key="team_port_sort"
                    )
                    team_summary=team_summary.sort_values([team_sort,"Saved LU","Pool"],ascending=[False,False,False])
                    st.dataframe(
                        team_summary,
                        hide_index=True,
                        use_container_width=True,
                        column_config={"Portfolio %":st.column_config.NumberColumn("Portfolio %",format="%.1f%%")}
                    )

            st.divider()
            st.markdown('<div class="nuke-section-kicker">MATCHUP WORKBENCH</div>',unsafe_allow_html=True)

        # Build unique matchups directly from the DK slate.
        game_lookup={}
        for _,p in st.session_state.slate.iterrows():
            t=str(p["Team"]).strip()
            o=str(p["Opp"]).strip()
            if not t or not o:continue
            key="|".join(sorted([t,o]))
            game_lookup.setdefault(key,set()).update([t,o])

        game_options=[]
        for key,tset in sorted(game_lookup.items()):
            odds=st.session_state.game_totals.get(key,{})
            if odds:
                label=f"{odds.get('away',sorted(tset)[0])} @ {odds.get('home',sorted(tset)[-1])}"
                total_txt=f"  •  O/U {odds['total']:g}" if odds.get("total") is not None else ""
            else:
                tt=sorted(tset)
                label=f"{tt[0]} vs {tt[1]}"
                total_txt=""
            game_options.append((label+total_txt,key))

        if not game_options:
            st.info("No Team/Opponent matchups found in the DraftKings slate.")
        else:
            labels=[x[0] for x in game_options]
            selected_label=st.selectbox("Game",labels,key="game_selector")
            game_key=dict(game_options)[selected_label]
            teams_in_game=sorted(game_lookup[game_key])
            odds=st.session_state.game_totals.get(game_key,{})
            game_rank,team_rank,game_count,team_count=slate_total_ranks()
            current_game_rank=game_rank.get(game_key)

            # Prefer away/home ordering from the odds workbook when available.
            if odds:
                away=odds["away"]; home=odds["home"]
            else:
                away,home=teams_in_game[0],teams_in_game[1]

            gdf=st.session_state.slate[
                st.session_state.slate["Team"].isin([away,home])
                & st.session_state.slate["Opp"].isin([away,home])
            ].drop_duplicates("Name + ID").copy()

            away_df=gdf[gdf["Team"]==away]
            home_df=gdf[gdf["Team"]==home]
            away_selected=sum(n in st.session_state.pending_pool_ids for n in away_df["Name + ID"])
            home_selected=sum(n in st.session_state.pending_pool_ids for n in home_df["Name + ID"])

            slate_team_counts={}
            for tname in sorted(st.session_state.slate["Team"].unique()):
                tdf_all=st.session_state.slate[st.session_state.slate["Team"]==tname]
                slate_team_counts[tname]=sum(n in st.session_state.pending_pool_ids for n in tdf_all["Name + ID"])
            away_conc_rank,conc_total,away_conc_color=concentration_rank_and_color(slate_team_counts,away)
            home_conc_rank,_,home_conc_color=concentration_rank_and_color(slate_team_counts,home)

            # Betting header.
            if odds:
                st.markdown(
                    f"""
                    <div class="nuke-game-board">
                      <div style="display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap">
                        <div style="min-width:190px">
                          <div style="font-size:.72rem;opacity:.58;font-weight:800">AWAY</div>
                          <div class="nuke-game-team">{away}</div>
                          <div style="font-size:.88rem;opacity:.75">Spread <b>{fmt_spread(odds.get("away_spread"))}</b> &nbsp; ML <b>{fmt_ml(odds.get("away_ml"))}</b></div>
                          <div style="font-size:.82rem;opacity:.62">Implied {odds.get("away_implied",0):.1f} pts <span class="rank-badge" style="color:{heat_color(team_rank.get(away),team_count)}">#{team_rank.get(away,"—")} of {team_count}</span></div>
                        </div>
                        <div style="text-align:center;min-width:180px">
                          <div style="font-size:.7rem;letter-spacing:.08em;opacity:.55;font-weight:900">GAME TOTAL</div>
                          <div style="font-size:2.1rem;font-weight:1000">{odds.get("total","—"):g}</div><div style="font-size:.78rem;font-weight:900;color:{heat_color(current_game_rank,game_count)}">GAME TOTAL RANK #{current_game_rank or "—"} of {game_count}</div>
                          <div style="font-size:.78rem;opacity:.58">{odds.get("game_time","")}</div>
                        </div>
                        <div style="min-width:190px;text-align:right">
                          <div style="font-size:.72rem;opacity:.58;font-weight:800">HOME</div>
                          <div class="nuke-game-team">{home}</div>
                          <div style="font-size:.88rem;opacity:.75">Spread <b>{fmt_spread(odds.get("home_spread"))}</b> &nbsp; ML <b>{fmt_ml(odds.get("home_ml"))}</b></div>
                          <div style="font-size:.82rem;opacity:.62">Implied {odds.get("home_implied",0):.1f} pts <span class="rank-badge" style="color:{heat_color(team_rank.get(home),team_count)}">#{team_rank.get(home,"—")} of {team_count}</span></div>
                        </div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(f"### {away} @ {home}")
                st.info("No betting line found for this matchup in gametotals.xlsx.")

            st.markdown('<div class="nuke-section-kicker">MATCHUP PLAYER POOL</div>',unsafe_allow_html=True)
            st.markdown("#### Game Rosters")
            st.caption("Build your staged player pool directly from each side of the matchup.")

            filter_left,filter_right=st.columns([.35,1.65])
            game_pos_filter=filter_left.selectbox(
                "Position",
                ["ALL","QB","RB","WR","TE","DST"],
                key=f"game_pos_filter_{game_key}"
            )
            filter_right.caption(
                "Position filtering applies to **both teams at the same time** so you can compare the matchup side-by-side."
            )

            # Keep team-player lists completely separated for easier game evaluation.
            roster_left,roster_right=st.columns(2,gap="large")

            for col,team_name,team_df,team_color in [
                (roster_left,away,away_df,away_conc_color),
                (roster_right,home,home_df,home_conc_color)
            ]:
                with col:
                    # Apply the shared position filter to both sides of the game.
                    visible_team_df=team_df.copy()
                    if game_pos_filter!="ALL":
                        visible_team_df=visible_team_df[
                            visible_team_df["Position"]==game_pos_filter
                        ].copy()

                    staged_count=sum(
                        nid in st.session_state.pending_pool_ids
                        for nid in team_df["Name + ID"]
                    )

                    st.markdown(
                        "<div class='nuke-roster-panel' style='border-left:4px solid "+team_color+";margin-bottom:8px'>"
                        "<div style='display:flex;justify-content:space-between;align-items:center;gap:10px'>"
                        "<div style='font-size:1.25rem;font-weight:1000'>"+team_name+"</div>"
                        "<div style='font-size:.72rem;font-weight:900;color:"+team_color+"'>"
                        +str(staged_count)+" IN POOL"
                        +"</div>"
                        "</div></div>",
                        unsafe_allow_html=True
                    )

                    team_roster=visible_team_df.drop_duplicates("Name + ID").copy()
                    pos_sort={"QB":1,"RB":2,"WR":3,"TE":4,"DST":5}
                    team_roster["_possort"]=team_roster["Position"].map(pos_sort).fillna(9)
                    team_roster=team_roster.sort_values(
                        ["_possort","Salary","Name"],
                        ascending=[True,False,True]
                    ).drop(columns="_possort")

                    # Position counts at a glance.
                    pos_counts=team_roster.groupby("Position").size().to_dict()
                    pos_summary=" • ".join(
                        f"{p} {int(pos_counts[p])}"
                        for p in ["QB","RB","WR","TE","DST"]
                        if p in pos_counts
                    )
                    if pos_summary:
                        st.caption(pos_summary)

                    if team_roster.empty:
                        st.info(
                            f"No {game_pos_filter} players for {team_name} in this DraftKings slate."
                        )
                        continue

                    # Use a compact checkbox table for each team.
                    team_editor=team_roster[
                        ["Name","Position","Salary","Name + ID"]
                    ].copy()
                    team_editor.insert(
                        0,
                        "Use",
                        team_editor["Name + ID"].isin(st.session_state.pending_pool_ids)
                    )

                    editor_key=f"game_team_editor_{game_key}_{team_name}"

                    edited=st.data_editor(
                        team_editor,
                        hide_index=True,
                        use_container_width=True,
                        height=min(620,75+34*len(team_editor)),
                        disabled=["Name","Position","Salary","Name + ID"],
                        column_config={
                            "Use":st.column_config.CheckboxColumn(
                                "Use",
                                width="small"
                            ),
                            "Name":st.column_config.TextColumn(
                                "Player",
                                width="large"
                            ),
                            "Position":st.column_config.TextColumn(
                                "Pos",
                                width="small"
                            ),
                            "Salary":st.column_config.NumberColumn(
                                "Salary",
                                format="$%d"
                            ),
                            "Name + ID":None
                        },
                        key=editor_key
                    )

                    # Capture changes for this team's visible roster immediately
                    # into the staged player-pool state.
                    shown_ids=set(team_editor["Name + ID"])
                    checked_ids=set(
                        edited.loc[edited["Use"],"Name + ID"]
                    )

                    current_for_team=(
                        st.session_state.pending_pool_ids & shown_ids
                    )
                    if checked_ids != current_for_team:
                        st.session_state.pending_pool_ids=(
                            st.session_state.pending_pool_ids-shown_ids
                        ) | checked_ids
                        st.rerun()

                    # Clean selected-player summary under each team only.
                    selected_team=team_roster[
                        team_roster["Name + ID"].isin(
                            st.session_state.pending_pool_ids
                        )
                    ].copy()

                    if selected_team.empty:
                        st.caption("No "+team_name+" players staged.")
                    else:
                        st.markdown(
                            "<div style='font-size:.70rem;letter-spacing:.08em;"
                            "font-weight:950;opacity:.58;margin-top:8px'>"
                            "STAGED "+team_name+" PLAYERS</div>",
                            unsafe_allow_html=True
                        )

                        for pos in ["QB","RB","WR","TE","DST"]:
                            pdf=selected_team[
                                selected_team["Position"]==pos
                            ].sort_values(
                                ["Salary","Name"],
                                ascending=[False,True]
                            )
                            if pdf.empty:
                                continue

                            names=", ".join(pdf["Name"].tolist())
                            st.markdown(
                                "<div style='margin:3px 0;font-size:.79rem'>"
                                "<b>"+pos+"</b> "
                                "<span style='opacity:.72'>"+names+"</span>"
                                "</div>",
                                unsafe_allow_html=True
                            )

    st.divider()
    st.caption("These buttons change the **staged** pool only. Nothing affects the lineup builder until you click Apply.")

    a1,a2,a3,a4=st.columns([.7,.7,.8,1.15])

    if a1.button("Add All",use_container_width=True):
        st.session_state.pending_pool_ids=set(st.session_state.slate["Name + ID"])
        st.rerun()

    if a2.button("Clear All",use_container_width=True):
        st.session_state.pending_pool_ids=set()
        st.rerun()

    if a3.button("Reset Staged",use_container_width=True):
        st.session_state.pending_pool_ids=set(st.session_state.pool_ids)
        st.rerun()

    if a4.button("Apply Player Pool Changes",type="primary",use_container_width=True):
        st.session_state.pool_ids=set(st.session_state.pending_pool_ids)
        st.success(f"Player pool updated: {len(st.session_state.pool_ids)} players · NUKE SIM will use this committed pool automatically.")
        st.rerun()



with qbplantab:
    st.subheader("QB Lineup Plan")
    st.caption("Choose how many lineups you want to hand-build around each quarterback. Applying the plan creates QB-anchored draft slots; it does not touch your Saved Lineups portfolio.")

    qbs=st.session_state.slate[st.session_state.slate["Position"]=="QB"].copy()
    qbs=qbs.sort_values(["Salary","Name"],ascending=[False,True]).reset_index(drop=True)

    existing=st.session_state.qb_plan or {}
    qbs.insert(0,"Target Lineups",[int(existing.get(nid,0)) for nid in qbs["Name + ID"]])
    qbs.rename(columns={"Name":"QB"},inplace=True)

    plan_edit=st.data_editor(
        qbs[["Target Lineups","QB","Team","Opp","Salary","Name + ID"]],
        hide_index=True,
        use_container_width=True,
        height=560,
        disabled=["QB","Team","Opp","Salary","Name + ID"],
        column_config={
            "Target Lineups":st.column_config.NumberColumn(
                "Target Lineups",min_value=0,max_value=50,step=1,width="small"
            ),
            "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
            "Name + ID":None
        },
        key="qb_plan_editor"
    )

    total_planned=int(pd.to_numeric(plan_edit["Target Lineups"],errors="coerce").fillna(0).sum())
    c1,c2,c3=st.columns(3)
    c1.metric("Planned lineups",total_planned)
    c2.metric("Remaining capacity",max(0,MAX_LU-total_planned))
    c3.metric("QB anchors",int((pd.to_numeric(plan_edit["Target Lineups"],errors="coerce").fillna(0)>0).sum()))

    if total_planned>MAX_LU:
        st.error(f"Your QB plan totals {total_planned} lineups. Maximum is {MAX_LU}.")
    else:
        if st.button("APPLY QB PLAN",type="primary",use_container_width=True):
            st.session_state.qb_plan={
                r["Name + ID"]:int(r["Target Lineups"])
                for _,r in plan_edit.iterrows()
                if int(r["Target Lineups"] or 0)>0
            }
            created=apply_qb_plan(plan_edit)
            st.success(f"Created {created} QB-anchored draft slots.")
            st.rerun()

    if st.session_state.qb_slot_map:
        st.divider()
        st.markdown("#### Current QB Build Groups")
        group_rows=[]
        for qb_id,data in st.session_state.qb_slot_map.items():
            slots=data.get("slots",[])
            if not slots:continue
            group_rows.append({
                "QB":data.get("qb",qb_id),
                "Draft Slots":f"{slots[0]+1}-{slots[-1]+1}" if len(slots)>1 else str(slots[0]+1),
                "Count":len(slots),
                "Saved from Group":sum(str(s) in st.session_state.draft_saved_link for s in slots)
            })
        st.dataframe(pd.DataFrame(group_rows),hide_index=True,use_container_width=True)


with buildtab:
    st.markdown('<div class="nuke-section-kicker">HAND BUILD MODE</div>',unsafe_allow_html=True)
    st.subheader("QB-Anchored Multi-Lineup Builder")

    groups=qb_group_options()
    if not groups:
        st.info("Set up at least one QB in the QB PLAN tab first. You can still use the old 1–50 draft slots, but the multi-lineup view is designed around QB groups.")
        group_slots=list(range(MAX_LU))
        group_name="All Draft Slots"
    else:
        labels=[f"{name} • {len(slots)} lineups" for name,_,slots in groups]
        selected_group_label=st.selectbox("QB Build Group",labels,key="build_qb_group")
        gi=labels.index(selected_group_label)
        group_name,qb_group_id,group_slots=groups[gi]

    top1,top2,top3=st.columns([.8,1.2,1.2])
    view_count=top1.selectbox("Lineups on screen",[1,2,3,4],index=[1,2,3,4].index(st.session_state.multi_view),key="multi_view_select")
    st.session_state.multi_view=view_count

    if group_slots:
        possible_starts=list(range(0,len(group_slots),view_count))
        start_labels=[]
        for sidx in possible_starts:
            subset=group_slots[sidx:sidx+view_count]
            if len(subset)==1:
                start_labels.append(f"Lineup {subset[0]+1}")
            else:
                start_labels.append(f"Lineups {subset[0]+1}-{subset[-1]+1}")
        page_label=top2.selectbox("Build Page",start_labels,key="multi_page")
        page_index=start_labels.index(page_label)
        visible_slots=group_slots[possible_starts[page_index]:possible_starts[page_index]+view_count]
    else:
        visible_slots=[]

    if not visible_slots:
        st.warning("This QB group has no draft slots.")
    else:
        # Active target lineup determines where selected player is added.
        active_choices={f"Lineup {i+1}":i for i in visible_slots}
        default_active=st.session_state.active_build_slot if st.session_state.active_build_slot in visible_slots else visible_slots[0]
        active_label=top3.radio(
            "Add players to",
            list(active_choices.keys()),
            index=list(active_choices.values()).index(default_active),
            horizontal=True,
            key="active_lineup_radio"
        )
        st.session_state.active_build_slot=active_choices[active_label]

        active_idx=st.session_state.active_build_slot
        active_lu=st.session_state.lineups[active_idx]

        st.divider()
        left,right=st.columns([.78,1.42],gap="large")

        # -------------------- SHARED PLAYER POOL --------------------
        with left:
            st.markdown('<div class="build-heading">SHARED PLAYER POOL</div>',unsafe_allow_html=True)
            p1,p2=st.columns([1.25,.75])
            search=p1.text_input("Search",placeholder="Player, team, opponent…",key="multi_build_search")
            chosen=st.session_state.slate[st.session_state.slate["Name + ID"].isin(st.session_state.pool_ids)].copy()
            teams=["ALL"]+sorted(chosen["Team"].unique())
            team_filter=p2.selectbox("Team",teams,key="multi_build_team")

            current_slot=st.session_state.slot
            cand=chosen[chosen["Position"].isin(SLOT_POS[current_slot])].copy()
            if team_filter!="ALL":
                cand=cand[cand["Team"]==team_filter]
            if search:
                q=search.lower()
                cand=cand[cand.apply(lambda r:q in f"{r['Name']} {r['Team']} {r['Opp']}".lower(),axis=1)]

            used=set(v for v in active_lu.values() if v)
            cand=cand[~cand["Name + ID"].isin(used)].copy()
            cand=cand.sort_values(["Salary","Name"],ascending=[False,True]).reset_index(drop=True)

            st.caption(
                f"Target: **Lineup {active_idx+1}** • Filling **{current_slot}** • "
                f"{len(cand)} available • players already used are hidden"
            )

            if cand.empty:
                st.info("No eligible players match the current filters.")
            else:
                event=st.dataframe(
                    cand.assign(Kickoff=cand["Start"].map(fmt_start))[["Name","Position","Team","Opp","Kickoff","Salary"]],
                    hide_index=True,
                    use_container_width=True,
                    height=560,
                    on_select="rerun",
                    selection_mode="multi-row",
                    column_config={
                        "Salary":st.column_config.NumberColumn("Salary",format="$%d")
                    },
                    key=f"multi_player_table_{active_idx}_{current_slot}"
                )

                selected_rows=event.selection.rows if event and hasattr(event,"selection") else []
                selected_players=[
                    cand.iloc[ridx].to_dict()
                    for ridx in selected_rows
                    if 0<=ridx<len(cand)
                ]

                if selected_players:
                    selected_ids=[p["Name + ID"] for p in selected_players]
                    selected_names=", ".join(p["Name"] for p in selected_players)

                    st.markdown(
                        '<div class="stack-card">'
                        '<div style="font-size:.69rem;font-weight:950;letter-spacing:.07em;color:#19c37d">SELECTED PLAYERS</div>'
                        '<div style="font-size:.83rem;font-weight:850;margin-top:4px">'+selected_names+'</div>'
                        '</div>',
                        unsafe_allow_html=True
                    )

                    add_label=(
                        f"ADD {len(selected_players)} PLAYERS TO LINEUP {active_idx+1}"
                        if len(selected_players)>1
                        else f"ADD {selected_players[0]['Name']} TO LINEUP {active_idx+1}"
                    )

                    if st.button(
                        add_label,
                        type="primary",
                        use_container_width=True,
                        key=f"multi_add_{active_idx}_{current_slot}"
                    ):
                        added,skipped=add_multiple_players(
                            active_lu,
                            selected_ids,
                            preferred_slot=current_slot
                        )
                        st.session_state.slot=next(
                            (s for s in SLOTS if not active_lu.get(s)),
                            current_slot
                        )
                        st.rerun()
                else:
                    st.caption("Select one or multiple rows. Example: select two WRs and add both at once.")

        # -------------------- 1-4 LINEUP SCREENS --------------------
        with right:
            st.markdown('<div class="build-heading">ACTIVE LINEUP CONSTRUCTION</div>',unsafe_allow_html=True)

            card_cols=st.columns(len(visible_slots),gap="small")
            for col,draft_idx in zip(card_cols,visible_slots):
                with col:
                    lu=st.session_state.lineups[draft_idx]
                    is_active=(draft_idx==active_idx)
                    border="#19c37d" if is_active else "rgba(128,128,128,.28)"
                    bg="rgba(25,195,125,.045)" if is_active else "rgba(128,128,128,.025)"

                    is_complete=complete(lu) and valid(lu)
                    status_html=(
                        '<span class="nuke-status-complete">COMPLETE ✓</span>'
                        if is_complete else
                        '<span class="nuke-status-draft">DRAFT</span>'
                    )
                    st.markdown(
                        '<div class="nuke-lineup-shell '+('active' if is_active else '')+'">'
                        '<div class="nuke-lineup-top">'
                        '<span class="nuke-lineup-name">'+('ACTIVE • ' if is_active else '')+'LINEUP '+str(draft_idx+1)+'</span>'
                        +status_html+
                        '</div></div>',
                        unsafe_allow_html=True
                    )

                    # Explicit lineup selection. No completion dependency.
                    if is_active:
                        st.button(
                            "✓ ACTIVE LINEUP",
                            key=f"active_card_{draft_idx}",
                            use_container_width=True,
                            disabled=True
                        )
                    else:
                        if st.button(
                            f"SELECT LINEUP {draft_idx+1}",
                            key=f"select_card_{draft_idx}",
                            use_container_width=True
                        ):
                            st.session_state.active_build_slot=draft_idx
                            # Keep current roster slot if eligible, otherwise find first open non-QB slot.
                            if st.session_state.slot=="QB" and lu.get("QB"):
                                st.session_state.slot=next((s for s in SLOTS if not lu.get(s)),"RB1")
                            st.rerun()

                    su=salary(lu)
                    rem=CAP-su
                    s=stack(lu)
                    count=sum(bool(lu.get(x)) for x in SLOTS)

                    m1,m2=st.columns(2)
                    m1.markdown(
                        f'<div class="metricbox {"metricred" if su>CAP else ""}">'
                        f'<div class="metriclabel">SALARY</div><div class="metricvalue {"redtext" if su>CAP else ""}">${su:,}</div></div>',
                        unsafe_allow_html=True
                    )
                    m2.markdown(
                        f'<div class="metricbox {"metricred" if rem<0 else ""}">'
                        f'<div class="metriclabel">LEFT</div><div class="metricvalue {"redtext" if rem<0 else ""}">${rem:,}</div></div>',
                        unsafe_allow_html=True
                    )
                    salary_pct=min(max(su/CAP,0),1.25)*100
                    salary_class="salary-over" if su>CAP else "salary-warn" if su>=48000 else "salary-good"
                    avg_left=(rem/max(1,9-count)) if count<9 else rem
                    st.markdown(
                        '<div class="salary-track"><div class="salary-fill '+salary_class+'" style="width:'+str(min(salary_pct,100))+'%"></div></div>'
                        '<div class="lineup-summary-grid">'
                        '<div class="lineup-summary-cell"><span class="lbl">STACK</span><span class="val">'+str(s["label"])+'</span></div>'
                        '<div class="lineup-summary-cell"><span class="lbl">PLAYERS</span><span class="val">'+str(count)+'/9</span></div>'
                        '<div class="lineup-summary-cell"><span class="lbl">AVG LEFT</span><span class="val">$'+f'{int(avg_left):,}'+'</span></div>'
                        '</div>',
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        '<div style="font-size:.64rem;font-weight:950;letter-spacing:.08em;opacity:.58;margin-top:5px">CORRELATION MAP</div>'
                        + correlation_html(lu),
                        unsafe_allow_html=True
                    )

                    # FLEX late-swap optimization.
                    fs=flex_status(lu)
                    if lu.get("FLEX"):
                        if fs["ok"]:
                            st.markdown(
                                '<div style="border:1px solid rgba(25,195,125,.42);'
                                'background:rgba(25,195,125,.07);border-radius:10px;padding:7px 9px;'
                                'font-size:.74rem;margin:5px 0 7px 0">'
                                '<b style="color:#19c37d">FLEX ✓</b><br>'+fs["message"]+'</div>',
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                '<div style="border:1px solid rgba(240,173,78,.62);'
                                'background:rgba(240,173,78,.08);border-radius:10px;padding:7px 9px;'
                                'font-size:.74rem;margin:5px 0 5px 0">'
                                '<b style="color:#f0ad4e">FLEX LATE-SWAP WARNING</b><br>'+fs["message"]+'</div>',
                                unsafe_allow_html=True
                            )
                            if st.button(
                                "OPTIMIZE FLEX",
                                key=f"opt_flex_{draft_idx}",
                                use_container_width=True
                            ):
                                if optimize_flex(lu):
                                    st.session_state.active_build_slot=draft_idx
                                    st.rerun()

                    # Roster rows: compact slot selector + player + inline X.
                    for sl in SLOTS:
                        p=pbyid(lu.get(sl))

                        if p:
                            slot_col,player_col,x_col=st.columns([.72,4.6,.52])
                        else:
                            slot_col,player_col=st.columns([.72,5.12])

                        slot_label=("▶ " if is_active and st.session_state.slot==sl else "")+sl
                        if slot_col.button(
                            slot_label,
                            key=f"mv_slot_{draft_idx}_{sl}",
                            use_container_width=True
                        ):
                            # Any lineup/slot can become active at any time.
                            st.session_state.active_build_slot=draft_idx
                            st.session_state.slot=sl
                            st.rerun()

                        if p:
                            player_col.markdown(
                                '<div class="roster-player-line">'
                                + team_badge(p["Team"])
                                + ' <b style="font-size:.83rem">' + str(p["Name"]) + '</b>'
                                + '</div>'
                                + '<div class="meta">$' + f'{int(p["Salary"]):,}'
                                + ' • ' + str(p["Team"]) + ' vs ' + str(p["Opp"]) + ' • ' + fmt_start(p.get("Start")) + '</div>',
                                unsafe_allow_html=True
                            )
                            if x_col.button(
                                "×",
                                key=f"mv_rm_{draft_idx}_{sl}",
                                help=f"Remove {p['Name']}",
                                use_container_width=True
                            ):
                                lu[sl]=None
                                st.session_state.active_build_slot=draft_idx
                                st.session_state.slot=sl
                                st.rerun()
                        else:
                            player_col.markdown(
                                '<div class="meta" style="padding-top:7px">Empty</div>',
                                unsafe_allow_html=True
                            )

                    st.divider()

                    complete_valid=complete(lu) and valid(lu)
                    linked_sid=st.session_state.draft_saved_link.get(str(draft_idx))

                    if st.button(
                        "SAVE AS NEW",
                        type="primary",
                        use_container_width=True,
                        disabled=not complete_valid,
                        key=f"save_new_{draft_idx}"
                    ):
                        sid=save_as_new_snapshot(draft_idx,lu)
                        st.success(f"Saved as portfolio Lineup {sid+1}.")
                        st.rerun()

                    if linked_sid is not None and str(linked_sid) in st.session_state.saved_lineups:
                        if st.button(
                            f"UPDATE SAVED #{linked_sid+1}",
                            use_container_width=True,
                            disabled=not complete_valid,
                            key=f"update_saved_{draft_idx}"
                        ):
                            update_linked_snapshot(draft_idx,lu)
                            st.success(f"Updated saved Lineup {linked_sid+1}.")
                            st.rerun()

                    if st.button(
                        "CLEAR DRAFT",
                        use_container_width=True,
                        key=f"clear_draft_{draft_idx}"
                    ):
                        qb_anchor=lu.get("QB")
                        st.session_state.lineups[draft_idx]=empty_lu()
                        if groups and draft_idx in group_slots:
                            st.session_state.lineups[draft_idx]["QB"]=qb_anchor
                        st.session_state.active_build_slot=draft_idx
                        st.session_state.slot="RB1" if qb_anchor else "QB"
                        st.rerun()

with savedtab:
    st.subheader("Saved Lineups")
    st.caption("This is your actual portfolio. BUILD drafts do not count until you intentionally save them.")

    saved=saved_items()
    if not saved:
        st.info("No saved lineups yet. Complete a lineup on BUILD and click SAVE LINEUP.")
    else:
        valid_saved=saved_valid_lineups()
        a,b,c=st.columns(3)
        a.metric("Saved",len(saved))
        b.metric("Valid",len(valid_saved))
        c.metric("Duplicate groups",len(saved_duplicate_groups()))

        st.markdown('<div class="nuke-section-kicker">PORTFOLIO BOARD</div>',unsafe_allow_html=True)
        preview_cols=st.columns(min(4,len(saved)))
        for pc,(pi,plu) in zip(preview_cols,saved[:4]):
            with pc:
                pstack=stack(plu)["label"]
                psal=salary(plu)
                pcorr=correlation_html(plu)
                player_lines=[]
                for ss in SLOTS:
                    pp=pbyid(plu.get(ss))
                    if pp:
                        player_lines.append(
                            '<div style="font-size:.72rem;margin:2px 0">'
                            '<b>'+ss+'</b> '+team_badge(pp["Team"])+' '+str(pp["Name"])+'</div>'
                        )
                st.markdown(
                    '<div class="saved-card"><h4>LINEUP '+str(pi+1)+'</h4>'
                    '<div style="font-size:.70rem;opacity:.62;margin-bottom:5px">$'+f'{psal:,}'+' • '+pstack+'</div>'
                    +pcorr+
                    ''.join(player_lines)+
                    '</div>',
                    unsafe_allow_html=True
                )

        rows=[]
        for i,lu in saved:
            row={"Lineup":i+1}
            for s in SLOTS:
                p=pbyid(lu.get(s))
                row[s]=p["Name"] if p else "—"
            row["Salary"]=salary(lu)
            row["Build"]=stack(lu)["label"]
            flex_p=pbyid(lu.get("FLEX"))
            row["FLEX Start"]=fmt_start(flex_p.get("Start")) if flex_p else "—"
            fs=flex_status(lu)
            row["FLEX Optimized"]="YES" if fs["ok"] else "NO"
            row["Valid"]="YES" if complete(lu) and valid(lu) else "NO"
            rows.append(row)

        view=pd.DataFrame(rows)
        st.dataframe(
            view,
            hide_index=True,
            use_container_width=True,
            height=min(720,80+35*len(view)),
            column_config={"Salary":st.column_config.NumberColumn("Salary",format="$%d")}
        )

        st.markdown("#### Manage Saved Lineups")
        ids=[i+1 for i,_ in saved]
        m1,m2,m3=st.columns([1,.9,1.1])
        selected=m1.selectbox("Saved lineup",ids,key="saved_manage")

        if m2.button("Load into BUILD",use_container_width=True):
            idx=selected-1
            snap=st.session_state.saved_lineups.get(str(idx))
            if snap:
                st.session_state.lineups[idx]=dict(snap)
                st.session_state.current_lu=idx
                st.session_state.active_build_slot=idx
                st.session_state.draft_saved_link[str(idx)]=idx
                st.session_state.slot="QB"
                st.success(f"Loaded Saved Lineup {selected} into BUILD. You can now UPDATE it or SAVE AS NEW.")

        if m3.button("Remove from Saved",use_container_width=True):
            st.session_state.saved_lineups.pop(str(selected-1),None)
            st.rerun()

        st.divider()
        if valid_saved:
            st.download_button(
                "EXPORT SAVED LINEUPS TO DRAFTKINGS CSV",
                data=saved_dk_export(),
                file_name="nuke_saved_dk_lineups.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True
            )
        else:
            st.warning("No valid saved lineups available to export.")

with exptab:
    ds=saved_valid_lineups()
    if not ds:
        st.info("Save at least one valid lineup to unlock portfolio analysis.")
    else:
        l,r=st.columns([1.05,.95],gap="large")
        with l:
            st.markdown('<div class="nuke-section-kicker">PORTFOLIO HEAT</div>',unsafe_allow_html=True)
            st.subheader("Player exposure")
            expdf=saved_exposure()
            for _,er in expdf.head(12).iterrows():
                pct=float(er["Exposure %"])
                color="#19c37d" if pct<35 else "#f2c94c" if pct<60 else "#ff5d5d"
                st.markdown(
                    '<div class="exposure-row">'
                    '<div class="exposure-name">'+str(er["Player"])+'</div>'
                    '<div class="exposure-track"><div class="exposure-fill" style="width:'+str(min(pct,100))+'%;background:'+color+'"></div></div>'
                    '<div style="font-size:.72rem;font-weight:950;min-width:38px;text-align:right">'+f'{pct:.0f}%</div>'
                    '</div>',
                    unsafe_allow_html=True
                )
            st.dataframe(expdf,hide_index=True,use_container_width=True,height=400)
        with r:
            st.subheader("Combo exposure")
            mode=st.radio("Combo size",["Pairs","Trios"],horizontal=True)
            st.session_state.combo_threshold=st.slider("Warning threshold",5,100,st.session_state.combo_threshold,5)
            cd=saved_combo_df(2 if mode=="Pairs" else 3)
            cd["Alert"]=cd["Exposure %"].apply(lambda x:"HIGH" if x>st.session_state.combo_threshold else "")
            st.dataframe(cd.head(100),hide_index=True,use_container_width=True,height=520)

        st.subheader("Build DNA")
        dd=saved_dna()
        cols=st.columns(3)
        for i,(k,v) in enumerate(dd.items()):
            cols[i%3].metric(k,f"{v}%")

        dg=saved_duplicate_groups()
        if dg:
            st.error("Duplicate saved lineup groups: "+"; ".join(", ".join(f"L{x}" for x in g) for g in dg))



import streamlit as st
import pandas as pd
import json
import re
import math
import unicodedata
import numpy as np
from itertools import combinations
from pathlib import Path

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
    cn=f("Name"); cid=f("ID","Id"); cs=f("Salary"); cg=f("Game Info","GameInfo")
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
    o["Opp"]=[opp_from_game(t,g) for t,g in zip(o["Team"],o["Game Info"])]
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
st.caption("Player Pool • Hand Building • Exposure • Combo Intelligence")

with st.sidebar:
    st.subheader("Slate")
    up=st.file_uploader("DraftKings salary CSV",type="csv")
    if up is not None:
        # only re-parse when the upload filename changes or no slate exists
        if st.session_state.slate is None or st.session_state.slate_name!=up.name:
            try:
                sl=normalize(pd.read_csv(up))
                st.session_state.slate=sl;st.session_state.slate_name=up.name
                valid_ids=set(sl["Name + ID"])
                st.session_state.pool_ids={x for x in st.session_state.pool_ids if x in valid_ids}
                st.session_state.pending_pool_ids={x for x in st.session_state.pending_pool_ids if x in valid_ids}
                for lu in st.session_state.lineups:
                    for s in SLOTS:
                        if lu.get(s) not in valid_ids:lu[s]=None
                if not st.session_state.pending_pool_ids and st.session_state.pool_ids:
                    st.session_state.pending_pool_ids=set(st.session_state.pool_ids)
                st.success(f"{len(sl)} players loaded")
            except Exception as e:st.error(str(e))
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
    st.info("Upload your DraftKings NFL salary CSV in the sidebar.")
    st.stop()

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
        st.info("Click **LOAD / REFRESH MODEL** once after uploading the DraftKings slate. The app will not fetch historical data until you ask it to.")
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
    st.subheader("Choose the players you actually want to use")
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
                    <div style="border:1px solid rgba(128,128,128,.28);border-radius:16px;padding:16px 18px;margin:4px 0 14px 0;background:rgba(128,128,128,.055)">
                      <div style="display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap">
                        <div style="min-width:190px">
                          <div style="font-size:.72rem;opacity:.58;font-weight:800">AWAY</div>
                          <div style="font-size:1.45rem;font-weight:950">{away}</div>
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
                          <div style="font-size:1.45rem;font-weight:950">{home}</div>
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

            # Very obvious staged-pool status by team.
            c1,c2=st.columns(2,gap="large")
            with c1:
                pct=(away_selected/max(len(away_df),1))*100
                st.markdown(
                    f"""<div style="border:2px solid {away_conc_color};border-radius:14px;padding:13px 15px;background:{away_conc_color+'18'}">
                    <div style="font-size:1.1rem;font-weight:950">{away}</div>
                    <div style="font-size:1.7rem;font-weight:1000;color:{away_conc_color}">{away_selected} SELECTED</div>
                    <div style="font-size:.78rem;opacity:.6">of {len(away_df)} slate players staged • concentration rank #{away_conc_rank} of {conc_total}</div>
                    </div>""",unsafe_allow_html=True)
                st.progress(min(int(pct),100))
            with c2:
                pct=(home_selected/max(len(home_df),1))*100
                st.markdown(
                    f"""<div style="border:2px solid {home_conc_color};border-radius:14px;padding:13px 15px;background:{home_conc_color+'18'}">
                    <div style="font-size:1.1rem;font-weight:950">{home}</div>
                    <div style="font-size:1.7rem;font-weight:1000;color:{home_conc_color}">{home_selected} SELECTED</div>
                    <div style="font-size:.78rem;opacity:.6">of {len(home_df)} slate players staged • concentration rank #{home_conc_rank} of {conc_total}</div>
                    </div>""",unsafe_allow_html=True)
                st.progress(min(int(pct),100))

            st.markdown("#### Players in this game")
            game_table=gdf.sort_values(["Team","Position","Salary"],ascending=[True,True,False]).copy()
            game_table.insert(0,"Use",game_table["Name + ID"].isin(st.session_state.pending_pool_ids))
            game_table.insert(1,"Status",game_table["Use"].map({True:"IN POOL",False:"—"}))
            st.session_state.game_editor_map=game_table["Name + ID"].tolist()

            st.data_editor(
                game_table[["Use","Status","Name","Position","Team","Salary","Name + ID"]],
                hide_index=True,
                use_container_width=True,
                height=520,
                disabled=["Status","Name","Position","Team","Salary","Name + ID"],
                column_config={
                    "Use":st.column_config.CheckboxColumn("Use",width="small"),
                    "Status":st.column_config.TextColumn("Staged",width="small"),
                    "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
                    "Name + ID":None
                },
                key="game_pool_editor",
                on_change=sync_game_editor
            )

            selected_names=game_table.loc[
                game_table["Name + ID"].isin(st.session_state.pending_pool_ids),
                ["Name","Team","Position","Salary"]
            ].copy()

            st.markdown("#### Staged From This Game")

            if selected_names.empty:
                st.caption("No players from this matchup are currently staged.")
            else:
                total_selected=len(selected_names)
                team_counts=selected_names.groupby("Team").size().to_dict()
                pos_counts=selected_names.groupby("Position").size().to_dict()

                s1,s2,s3=st.columns(3)
                s1.metric("Players staged",total_selected)
                s2.metric(away,int(team_counts.get(away,0)))
                s3.metric(home,int(team_counts.get(home,0)))

                pos_order=["QB","RB","WR","TE","DST"]
                pos_summary=" • ".join(
                    f"{p}: {int(pos_counts[p])}"
                    for p in pos_order
                    if p in pos_counts
                )
                if pos_summary:
                    st.caption(pos_summary)

                tc1,tc2=st.columns(2,gap="large")
                for col,team_name in zip([tc1,tc2],[away,home]):
                    with col:
                        team_selected=selected_names[selected_names["Team"]==team_name].copy()
                        color=away_conc_color if team_name==away else home_conc_color

                        st.markdown(
                            "<div style='border:1px solid "+color+";border-radius:14px;padding:11px 13px;"
                            "background:"+color+"12;margin-bottom:8px'>"
                            "<div style='font-size:.76rem;opacity:.62;font-weight:900'>STAGED PLAYERS</div>"
                            "<div style='font-size:1.15rem;font-weight:950'>"+team_name+" • "+str(len(team_selected))+"</div>"
                            "</div>",
                            unsafe_allow_html=True
                        )

                        if team_selected.empty:
                            st.caption("None staged")
                        else:
                            for pos in pos_order:
                                pdf=team_selected[team_selected["Position"]==pos].sort_values(
                                    ["Salary","Name"],ascending=[False,True]
                                )
                                if pdf.empty:
                                    continue

                                st.markdown(
                                    f"<div style='font-size:.70rem;letter-spacing:.08em;font-weight:950;"
                                    f"opacity:.62;margin:7px 0 2px 0'>{pos} • {len(pdf)}</div>",
                                    unsafe_allow_html=True
                                )

                                for _,r in pdf.iterrows():
                                    st.markdown(
                                        "<div style='display:flex;justify-content:space-between;align-items:center;"
                                        "gap:8px;padding:5px 0;border-bottom:1px solid rgba(128,128,128,.14)'>"
                                        "<span style='font-size:.82rem;font-weight:800'>"+str(r["Name"])+"</span>"
                                        "<span style='font-size:.76rem;opacity:.58'>$"+f"{int(r['Salary']):,}"+"</span>"
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
        st.success(f"Player pool updated: {len(st.session_state.pool_ids)} players.")
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
            cand["In Active Lineup"]=cand["Name + ID"].isin(used)
            cand=cand.sort_values(["Salary","Name"],ascending=[False,True]).reset_index(drop=True)

            st.caption(f"Target: **Lineup {active_idx+1}** • Filling **{current_slot}** • {len(cand)} eligible")

            if cand.empty:
                st.info("No eligible players match the current filters.")
            else:
                event=st.dataframe(
                    cand.assign(Kickoff=cand["Start"].map(fmt_start))[["Name","Position","Team","Opp","Kickoff","Salary","In Active Lineup"]],
                    hide_index=True,
                    use_container_width=True,
                    height=560,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config={
                        "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
                        "In Active Lineup":st.column_config.CheckboxColumn("Used",disabled=True)
                    },
                    key=f"multi_player_table_{active_idx}_{current_slot}"
                )
                selected_rows=event.selection.rows if event and hasattr(event,"selection") else []
                selected_player=None
                if selected_rows:
                    ridx=selected_rows[0]
                    if 0<=ridx<len(cand):
                        selected_player=cand.iloc[ridx].to_dict()

                if selected_player:
                    st.markdown(
                        '<div class="stack-card"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center">'
                        + '<div>' + team_badge(selected_player["Team"]) + ' <b>' + str(selected_player["Name"]) + '</b><br>'
                        + '<span class="meta">' + str(selected_player["Position"]) + ' • ' + str(selected_player["Team"]) + ' vs ' + str(selected_player["Opp"]) + ' • ' + fmt_start(selected_player.get("Start")) + '</span></div>'
                        + '<div style="font-size:1.05rem;font-weight:950">$' + f'{int(selected_player["Salary"]):,}' + '</div>'
                        + '</div></div>',
                        unsafe_allow_html=True
                    )
                    if st.button(
                        f"ADD TO LINEUP {active_idx+1} • {current_slot}",
                        type="primary",
                        use_container_width=True,
                        disabled=selected_player["Name + ID"] in used,
                        key=f"multi_add_{active_idx}_{current_slot}"
                    ):
                        active_lu[current_slot]=selected_player["Name + ID"]
                        idx=SLOTS.index(current_slot)
                        nxt=next((s for s in SLOTS[idx+1:] if not active_lu.get(s)),None) or next((s for s in SLOTS if not active_lu.get(s)),current_slot)
                        st.session_state.slot=nxt
                        st.rerun()
                else:
                    st.caption("Click a player row, then add him to the active lineup.")

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

                    st.markdown(
                        f'<div style="border:2px solid {border};border-radius:16px;padding:10px 11px;background:{bg};margin-bottom:6px">'
                        f'<div style="font-size:.70rem;font-weight:950;letter-spacing:.08em;color:{border}">'
                        f'{"ACTIVE • " if is_active else ""}LINEUP {draft_idx+1}</div></div>',
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
                    st.caption(f'{s["label"]} • {count}/9 players')

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
            st.subheader("Player exposure")
            st.dataframe(saved_exposure(),hide_index=True,use_container_width=True,height=520)
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


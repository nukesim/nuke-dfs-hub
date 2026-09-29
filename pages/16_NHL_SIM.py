import streamlit as st
import pandas as pd
import numpy as np
import requests
import re
import csv
import io
import itertools
import time
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from nuke_nav import render_nav

st.set_page_config(page_title="NUKE NHL Sim", page_icon="🏒", layout="wide")
render_nav()

CAP = 50000
ROSTER = 9
SKATERS = 8
DEFAULT_MIN_SALARY = 49600
DEFAULT = Path(__file__).resolve().parents[1] / "data" / "nhl_current.csv"

TEAM_SLUGS = {
    "ANA":"anaheim-ducks","BOS":"boston-bruins","BUF":"buffalo-sabres","CGY":"calgary-flames",
    "CAR":"carolina-hurricanes","CHI":"chicago-blackhawks","COL":"colorado-avalanche",
    "CBJ":"columbus-blue-jackets","DAL":"dallas-stars","DET":"detroit-red-wings",
    "EDM":"edmonton-oilers","FLA":"florida-panthers","LAK":"los-angeles-kings","LA":"los-angeles-kings",
    "MIN":"minnesota-wild","MTL":"montreal-canadiens","NSH":"nashville-predators",
    "NJD":"new-jersey-devils","NJ":"new-jersey-devils","NYI":"new-york-islanders",
    "NYR":"new-york-rangers","OTT":"ottawa-senators","PHI":"philadelphia-flyers",
    "PIT":"pittsburgh-penguins","SJS":"san-jose-sharks","SJ":"san-jose-sharks",
    "SEA":"seattle-kraken","STL":"st-louis-blues","TBL":"tampa-bay-lightning","TB":"tampa-bay-lightning",
    "TOR":"toronto-maple-leafs","UTA":"utah-mammoth","VAN":"vancouver-canucks",
    "VGK":"vegas-golden-knights","WSH":"washington-capitals","WPG":"winnipeg-jets",
}

class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
    def handle_data(self, data):
        x=" ".join(str(data).split())
        if x: self.parts.append(x)

def _html_text(raw):
    p=_Text()
    try: p.feed(raw)
    except Exception: pass
    return " ".join(p.parts)

def _norm_team(x):
    x=str(x).upper().strip()
    return {"LA":"LAK","SJ":"SJS","TB":"TBL","NJ":"NJD"}.get(x,x)

def _norm_pos(x):
    x=str(x).upper().replace("LW","W").replace("RW","W")
    if "G" in x: return "G"
    if "D" in x: return "D"
    if "C" in x: return "C"
    if "W" in x: return "W"
    return x[:1]

def _slate_date(d):
    if "Game Info" in d.columns:
        for v in d["Game Info"].astype(str):
            m=re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})",v)
            if m:
                return f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
            m=re.search(r"(\d{4})-(\d{2})-(\d{2})",v)
            if m: return m.group(0)
    return datetime.now().strftime("%Y-%m-%d")

def _opponent(game_info, team):
    s=str(game_info).upper()
    m=re.search(r"\b([A-Z]{2,3})@([A-Z]{2,3})\b",s)
    if not m: return ""
    a,b=_norm_team(m.group(1)),_norm_team(m.group(2))
    t=_norm_team(team)
    return b if t==a else a if t==b else ""

def load_csv(src):
    d=pd.read_csv(src)
    required={"Name","ID","Salary"}
    if not required.issubset(d.columns):
        raise ValueError("This does not look like a DraftKings NHL salary CSV. Name, ID and Salary are required.")
    team_col="TeamAbbrev" if "TeamAbbrev" in d.columns else ("Team" if "Team" in d.columns else None)
    pos_col="Position" if "Position" in d.columns else ("Roster Position" if "Roster Position" in d.columns else None)
    if team_col is None or pos_col is None:
        raise ValueError("The DraftKings NHL CSV must include team and position columns.")
    d=d.copy()
    d["ID"]=pd.to_numeric(d["ID"],errors="coerce").astype("Int64")
    d["Salary"]=pd.to_numeric(d["Salary"],errors="coerce").fillna(0).astype(int)
    fppg_src=d["AvgPointsPerGame"] if "AvgPointsPerGame" in d.columns else pd.Series(0.0,index=d.index)
    status_src=d["Status"] if "Status" in d.columns else pd.Series("",index=d.index)
    d["FPPG"]=pd.to_numeric(fppg_src,errors="coerce").fillna(0.0)
    d["Team"]=d[team_col].map(_norm_team)
    d["Pos"]=d[pos_col].map(_norm_pos)
    d["Status"]=status_src.fillna("").astype(str).str.upper()
    d=d[~d["Status"].isin(["OUT","O","IR"])].dropna(subset=["ID"])
    d=d[d["Pos"].isin(["C","W","D","G"])].drop_duplicates("ID").reset_index(drop=True)
    if "Game Info" in d.columns:
        d["Opp"]=[_opponent(g,t) for g,t in zip(d["Game Info"],d["Team"])]
    else:
        d["Opp"]=""
    return d

@st.cache_data(ttl=900, show_spinner=False)
def _fetch_text(url):
    try:
        r=requests.get(url,timeout=9,headers={"User-Agent":"Mozilla/5.0 NUKE-DFS"})
        if r.ok: return _html_text(r.text)
    except Exception:
        pass
    return ""

def _section(txt,start,end=None):
    lo=txt.lower()
    a=lo.find(start.lower())
    if a<0: return ""
    b=lo.find(end.lower(),a+len(start)) if end else -1
    return txt[a:(b if b>=0 else len(txt))]

def _find_order(section, names):
    low=section.lower()
    hits=[]
    for name in names:
        p=low.find(str(name).lower())
        if p>=0: hits.append((p,name))
    return [name for _,name in sorted(hits)]

@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_roles(team, names):
    slug=TEAM_SLUGS.get(_norm_team(team))
    if not slug: return {}
    txt=_fetch_text(f"https://www.dailyfaceoff.com/teams/{slug}/line-combinations")
    if not txt: return {}
    names=list(names)
    out={n:{"Line":"?","PP":"-"} for n in names}
    fsec=_section(txt,"Forwards","Defensive Pairings")
    dsec=_section(txt,"Defensive Pairings","1st Powerplay Unit")
    pp1=_section(txt,"1st Powerplay Unit","2nd Powerplay Unit")
    pp2=_section(txt,"2nd Powerplay Unit","1st Penalty Kill Unit")
    forwards=_find_order(fsec,names)
    defense=_find_order(dsec,names)
    for j,n in enumerate(forwards[:12]): out[n]["Line"]=f"F{j//3+1}"
    for j,n in enumerate(defense[:6]): out[n]["Line"]=f"D{j//2+1}"
    for n in names:
        if str(n).lower() in pp1.lower(): out[n]["PP"]="PP1"
        elif str(n).lower() in pp2.lower(): out[n]["PP"]="PP2"
    return out

@st.cache_data(ttl=600, show_spinner=False)
def fetch_goalie_status(date_str, goalie_names):
    txt=_fetch_text(f"https://www.dailyfaceoff.com/starting-goalies/{date_str}")
    out={n:"Unknown" for n in goalie_names}
    low=txt.lower()
    for n in goalie_names:
        p=low.find(str(n).lower())
        if p<0: continue
        window=txt[p:p+500]
        m=re.search(r"\b(Confirmed|Likely|Unconfirmed|Projected|Probable)\b",window,re.I)
        if m: out[n]=m.group(1).title()
    return out

def enrich_context(d):
    x=d.copy()
    x["Line"]="?"
    x["PP"]="-"
    teams=sorted(x.loc[x["Pos"]!="G","Team"].dropna().unique())
    def job(t):
        names=x.loc[(x["Team"]==t)&(x["Pos"]!="G"),"Name"].astype(str).tolist()
        return t,fetch_team_roles(t,names)
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(teams)))) as ex:
        futs=[ex.submit(job,t) for t in teams]
        for f in as_completed(futs):
            try:
                t,roles=f.result()
                for n,role in roles.items():
                    mask=(x["Team"]==t)&(x["Name"].astype(str)==str(n))
                    x.loc[mask,"Line"]=role["Line"]
                    x.loc[mask,"PP"]=role["PP"]
            except Exception:
                pass
    goalies=x.loc[x["Pos"]=="G","Name"].astype(str).tolist()
    gs=fetch_goalie_status(_slate_date(x),goalies) if goalies else {}
    x.loc[x["Pos"]=="G","Line"]="—"
    x.loc[x["Pos"]=="G","PP"]="—"
    x["G Status"]="-"
    # DraftKings sometimes includes a Starting flag in the salary CSV. Use it first,
    # then let the live goalie feed overwrite it when a more explicit status is available.
    if "Starting" in x.columns:
        start=x["Starting"].fillna("").astype(str).str.upper().str.strip()
        x.loc[(x["Pos"]=="G") & start.isin(["P","PROBABLE","PROJECTED"]),"G Status"]="Probable"
        x.loc[(x["Pos"]=="G") & start.isin(["C","CONFIRMED","Y","YES"]),"G Status"]="Confirmed"
    for n,status in gs.items():
        if status and str(status).lower()!="unknown":
            x.loc[x["Name"].astype(str)==str(n),"G Status"]=status
    return x

def base_projection(d):
    f=d["FPPG"].to_numpy(float)
    sal=d["Salary"].to_numpy(float)
    pos=d["Pos"].astype(str).to_numpy()
    fallback=np.zeros(len(d),dtype=float)
    for i,p in enumerate(pos):
        if p=="G": fallback[i]=np.interp(sal[i],[6500,9000],[10,18])
        elif p=="D": fallback[i]=np.interp(sal[i],[2500,8000],[5,15])
        else: fallback[i]=np.interp(sal[i],[2500,9500],[5,18])
    mu=np.where(f>0,f,fallback)
    line=d.get("Line",pd.Series(["?"]*len(d))).astype(str).to_numpy()
    pp=d.get("PP",pd.Series(["-"]*len(d))).astype(str).to_numpy()
    for i in range(len(mu)):
        if line[i]=="F1": mu[i]*=1.025
        elif line[i]=="F2": mu[i]*=1.01
        elif line[i]=="F4": mu[i]*=.94
        if pp[i]=="PP1": mu[i]*=1.045
        elif pp[i]=="PP2": mu[i]*=1.02
        if pos[i]=="G" and str(d.iloc[i].get("G Status","")).lower()=="confirmed": mu[i]*=1.03
    return mu

def ownership_estimate(d):
    mu=base_projection(d)
    sal=d["Salary"].to_numpy(float)
    out=np.zeros(len(d),dtype=float)
    for goalie in [False,True]:
        mask=(d["Pos"].to_numpy()=="G") if goalie else (d["Pos"].to_numpy()!="G")
        if not mask.any(): continue
        z1=(mu[mask]-mu[mask].mean())/(mu[mask].std()+1e-9)
        z2=(sal[mask]-sal[mask].mean())/(sal[mask].std()+1e-9)
        role=np.zeros(mask.sum())
        sub=d.loc[mask]
        role += (sub["PP"].astype(str).to_numpy()=="PP1")*.22
        role += (sub["Line"].astype(str).to_numpy()=="F1")*.16
        role += sub["G Status"].astype(str).str.lower().isin(["confirmed","likely","probable","projected"]).to_numpy()*.32
        raw=np.exp(np.clip(.56*z1+.28*z2+role,-2.7,2.7))
        total=100.0 if goalie else 800.0
        own=raw/raw.sum()*total
        out[np.where(mask)[0]]=np.clip(own,.3,65)
    return out

def _lineup_position_ok(pos):
    vals=list(pos)
    c=vals.count("C"); w=vals.count("W"); de=vals.count("D")
    return len(vals)==8 and c>=2 and w>=3 and de>=2 and c<=3 and w<=4 and de<=3

def _combo_score(sub):
    """Score a same-team mini-stack for GPP correlation, not just raw median projection."""
    mu=base_projection(sub)
    score=float(mu.sum())
    lines=sub["Line"].astype(str).tolist()
    pps=sub["PP"].astype(str).tolist()
    pos=sub["Pos"].astype(str).tolist()
    for a,b in itertools.combinations(range(len(sub)),2):
        if lines[a] in ["F1","F2"] and lines[a]==lines[b]: score+=5.0
        elif lines[a] not in ["?","-"] and lines[a]==lines[b]: score+=2.4
        if pps[a]=="PP1" and pps[b]=="PP1": score+=3.2
        elif pps[a]=="PP2" and pps[b]=="PP2": score+=1.0
    # A complete forward line is one of the strongest NHL DFS correlation structures.
    for ln in ["F1","F2","F3","F4"]:
        if sum(1 for z in lines if z==ln)>=3:
            score += 11.0 if ln in ["F1","F2"] else 6.0
    # Reward the classic 4-man line + power-play defenseman construction.
    if "D" in pos and any(p=="PP1" for p in pps):
        score+=4.0
    return score

def build_group_cache(d):
    """Pre-build correlated same-team groups plus fast lineup-generation metadata."""
    cache={}
    sk=d[d["Pos"]!="G"]
    for team,g in sk.groupby("Team"):
        tmp=g.copy()
        tmp["_rank"]=base_projection(tmp)+np.where(tmp["PP"].eq("PP1"),3.2,0)+np.where(tmp["Line"].isin(["F1","F2"]),2.2,0)
        pool=tmp.sort_values("_rank",ascending=False).head(13)
        idxs=pool.index.tolist()
        role_coverage=float(((pool["Line"]!="?") | (pool["PP"].isin(["PP1","PP2"]))).mean()) if len(pool) else 0.0
        known_roles=role_coverage>=0.60
        for size in [1,2,3,4,5]:
            strict=[]; fallback=[]
            for combo in itertools.combinations(idxs,size):
                sub=d.loc[list(combo)]
                lines=sub["Line"].astype(str)
                pps=sub["PP"].astype(str)
                positions=sub["Pos"].astype(str)
                same_line=max([int((lines==ln).sum()) for ln in ["F1","F2","F3","F4"]]+[0])
                same_pp1=int((pps=="PP1").sum())
                same_pp2=int((pps=="PP2").sum())
                score=_combo_score(sub)
                meta={
                    "idx":tuple(combo),
                    "salary":int(sub["Salary"].sum()),
                    "c":int((positions=="C").sum()),
                    "w":int((positions=="W").sum()),
                    "d":int((positions=="D").sum()),
                    "ids":tuple(sub["ID"].astype(int).tolist()),
                    "score":float(score),
                }
                fallback.append(meta)
                if not known_roles or size==1:
                    strict.append(meta); continue
                if size==2 and (same_line>=2 or same_pp1>=2 or same_pp2>=2):
                    strict.append(meta)
                elif size==3 and (same_line>=3 or (same_line>=2 and same_pp1>=2)):
                    strict.append(meta)
                elif size==4 and (same_line>=3 and ("D" in set(positions) or same_pp1>=3)):
                    strict.append(meta)
                elif size==5 and (same_line>=3 and (same_pp1>=2 or "D" in set(positions))):
                    strict.append(meta)
            items=sorted((strict if strict else fallback),key=lambda z:z["score"],reverse=True)[:220]
            if items:
                scores=np.array([z["score"] for z in items],dtype=float)
                zz=(scores-scores.mean())/(scores.std()+1e-9)
                probs=np.exp(np.clip(.45*zz,-3,3)); probs=probs/probs.sum()
            else:
                probs=np.array([],dtype=float)
            cache[(team,size)]={"items":items,"p":probs}
    return cache

def _weighted_pick(items,rng):
    if not items: return None
    scores=np.array([x[1] for x in items],float)
    z=(scores-scores.mean())/(scores.std()+1e-9)
    w=np.exp(np.clip(.45*z,-3,3)); w=w/w.sum()
    return items[int(rng.choice(len(items),p=w))][0]

def _shape_counts(shape):
    return [int(x) for x in shape.split("-")]

def generate_candidates(d,n,min_salary,seed,shape_mix,no_vs_goalie=True,prefer_stack_goalie=True,avoid_fourth_line=True,locked_ids=None,excluded_ids=None):
    """Fast GPP candidate generator. Keeps correlation rules but avoids pandas work inside the hot loop."""
    rng=np.random.default_rng(seed)
    locked_ids=set(locked_ids or [])
    excluded_ids=set(excluded_ids or [])
    active=d[~d["ID"].astype(int).isin(excluded_ids)].copy()
    if avoid_fourth_line:
        fourth=(active["Pos"]!="G") & (active["Line"].astype(str)=="F4") & (~active["PP"].astype(str).isin(["PP1","PP2"])) & (~active["ID"].astype(int).isin(locked_ids))
        active=active[~fourth].copy()
    if len(active)<9: return []

    group_cache=build_group_cache(active)
    teams=sorted(active.loc[active["Pos"]!="G","Team"].unique())
    if len(teams)<3: return []

    tstrength={}
    for t in teams:
        g=active[(active["Team"]==t)&(active["Pos"]!="G")]
        tstrength[t]=float(np.sort(base_projection(g))[-min(6,len(g)):].sum()) if len(g) else 1
    tw=np.array([tstrength[t] for t in teams],float)
    tw=np.exp((tw-tw.mean())/(tw.std()+1e-9)*.35); tw=tw/tw.sum()

    shapes=[k for k,v in shape_mix.items() if v>0]
    sw=np.array([shape_mix[k] for k in shapes],float); sw=sw/sw.sum()

    goalies=active[active["Pos"]=="G"].copy()
    if goalies.empty: return []
    gmu=base_projection(goalies)
    gst=goalies["G Status"].astype(str).str.lower()
    base_gw=np.maximum(gmu,1.0)*np.where(gst.eq("confirmed"),1.8,np.where(gst.isin(["likely","probable","projected"]),1.35,.75))
    base_gw=base_gw/base_gw.sum()

    goalie_meta=[]
    for j,(idx,gr) in enumerate(goalies.iterrows()):
        goalie_meta.append({
            "idx":idx,"id":int(gr["ID"]),"salary":int(gr["Salary"]),
            "team":str(gr["Team"]),"opp":str(gr["Opp"]),"w":float(base_gw[j])
        })

    own=ownership_estimate(active)
    posmap={idx:k for k,idx in enumerate(active.index)}
    seen=set(); out=[]; attempts=0
    # Candidate count is a target, not a reason to hang the app. A strong 20-lineup
    # portfolio does not need the generator to chase the final few rare combinations forever.
    max_attempts=max(25000,n*12)
    min_viable=min(n,max(1000,n//3))
    started=time.monotonic()
    soft_seconds=12.0
    hard_seconds=22.0

    while len(out)<n and attempts<max_attempts:
        attempts+=1
        elapsed=time.monotonic()-started
        if elapsed>=hard_seconds and len(out)>=500:
            break
        if elapsed>=soft_seconds and len(out)>=min_viable:
            break
        shape=str(rng.choice(shapes,p=sw))
        counts=_shape_counts(shape)
        chosen=list(rng.choice(teams,size=len(counts),replace=False,p=tw))

        sk_idx=[]; ids=[]; sk_salary=0; cc=ww=dd=0
        valid=True
        for team,size in zip(chosen,counts):
            pack=group_cache.get((team,size),{})
            items=pack.get("items",[])
            probs=pack.get("p",np.array([]))
            if not items:
                valid=False; break
            meta=items[int(rng.choice(len(items),p=probs))]
            sk_idx.extend(meta["idx"]); ids.extend(meta["ids"])
            sk_salary+=meta["salary"]; cc+=meta["c"]; ww+=meta["w"]; dd+=meta["d"]
        if not valid or len(sk_idx)!=SKATERS:
            continue
        if not (cc>=2 and ww>=3 and dd>=2 and cc<=3 and ww<=4 and dd<=3):
            continue

        # Choose only goalies that keep the lineup legal before doing any expensive work.
        elig=[]; gweights=[]
        for gm in goalie_meta:
            if no_vs_goalie and gm["opp"] in chosen:
                continue
            total_salary=sk_salary+gm["salary"]
            if total_salary<min_salary or total_salary>CAP:
                continue
            weight=gm["w"]*(2.0 if prefer_stack_goalie and gm["team"]==chosen[0] else 1.0)
            elig.append(gm); gweights.append(weight)
        if not elig:
            continue
        gweights=np.asarray(gweights,dtype=float); gweights=gweights/gweights.sum()
        gm=elig[int(rng.choice(len(elig),p=gweights))]

        lineup_ids=set(ids+[gm["id"]])
        if locked_ids and not locked_ids.issubset(lineup_ids):
            continue
        key=tuple(sorted(lineup_ids))
        if key in seen:
            continue

        seen.add(key)
        own_idx=[posmap[i] for i in sk_idx+[gm["idx"]]]
        out.append({
            "idx":sk_idx+[gm["idx"]],
            "salary":sk_salary+gm["salary"],
            "shape":shape,
            "primary":chosen[0],
            "own_product":float(np.prod(np.clip(own[own_idx]/100,.002,.95))),
        })


    return out

def simulate_players(d,n_sims,seed):
    rng=np.random.default_rng(seed+971)
    mu=base_projection(d)
    teams=sorted(d["Team"].unique())
    tmap={t:i for i,t in enumerate(teams)}
    team_z=rng.normal(0,1,size=(n_sims,len(teams)))
    line_keys=sorted(set((str(r.Team),str(r.Line)) for _,r in d.iterrows() if r.Pos!="G" and str(r.Line)!="?"))
    lmap={k:i for i,k in enumerate(line_keys)}
    line_z=rng.normal(0,1,size=(n_sims,max(1,len(line_keys))))
    pp_keys=sorted(set((str(r.Team),str(r.PP)) for _,r in d.iterrows() if r.Pos!="G" and str(r.PP) in ["PP1","PP2"]))
    pmap={k:i for i,k in enumerate(pp_keys)}
    pp_z=rng.normal(0,1,size=(n_sims,max(1,len(pp_keys))))
    scores=np.empty((n_sims,len(d)),dtype=np.float32)
    for j,(_,r) in enumerate(d.iterrows()):
        if r["Pos"]=="G":
            own_t=team_z[:,tmap.get(r["Team"],0)]
            opp_t=team_z[:,tmap[r["Opp"]]] if r["Opp"] in tmap else 0
            sc=rng.normal(mu[j],7.8,size=n_sims)+2.0*own_t-2.35*opp_t
            scores[:,j]=np.clip(sc,-8,42)
        else:
            shape=1.65 if r["Pos"]!="D" else 2.05
            base=rng.gamma(shape,max(mu[j],.5)/shape,size=n_sims)
            z=.16*team_z[:,tmap[r["Team"]]]
            lk=(str(r["Team"]),str(r["Line"]))
            if lk in lmap: z+=.18*line_z[:,lmap[lk]]
            pk=(str(r["Team"]),str(r["PP"]))
            if pk in pmap: z+=(.11 if r["PP"]=="PP1" else .06)*pp_z[:,pmap[pk]]
            var=.16**2+(.18**2 if lk in lmap else 0)+((.11 if r["PP"]=="PP1" else .06)**2 if pk in pmap else 0)
            factor=np.exp(z-.5*var)
            scores[:,j]=np.clip(base*factor,0,55)
    return scores

def evaluate(cands,sims,d,own):
    index_to_col={idx:j for j,idx in enumerate(d.index)}
    rows=[]
    for j,c in enumerate(cands):
        cols=[index_to_col[i] for i in c["idx"]]
        sc=sims[:,cols].sum(axis=1)
        rows.append({"_candidate":j,"Salary":c["salary"],"Stack":c["shape"],"Primary":c["primary"],
                     "Mean":round(float(sc.mean()),2),"P95":round(float(np.quantile(sc,.95)),2),
                     "Top 1%":round(float(np.quantile(sc,.99)),2),
                     "Own Sum %":round(float(own[cols].sum()),1),"Dup Proxy":float(c["own_product"])})
    r=pd.DataFrame(rows)
    if r.empty: return r
    for col in ["Mean","P95","Top 1%"]:
        r["_z_"+col]=(r[col]-r[col].mean())/(r[col].std()+1e-9)
    lev=-np.log(np.maximum(r["Dup Proxy"],1e-15))
    lev=(lev-lev.mean())/(lev.std()+1e-9)
    r["NUKE Score"]=.8*r["_z_Mean"]+1.35*r["_z_P95"]+1.1*r["_z_Top 1%"]+.28*lev
    return r.sort_values("NUKE Score",ascending=False).reset_index(drop=True)

def contest_metrics(results,cands,sims,d,seed):
    if results.empty: return results
    rng=np.random.default_rng(seed+443)
    index_to_col={idx:j for j,idx in enumerate(d.index)}
    scoremat=np.empty((len(cands),sims.shape[0]),dtype=np.float32)
    for j,c in enumerate(cands):
        cols=[index_to_col[i] for i in c["idx"]]
        scoremat[j]=sims[:,cols].sum(axis=1)
    dup=np.array([max(c["own_product"],1e-14) for c in cands],float)
    score_by_candidate=results.set_index("_candidate").reindex(range(len(cands)))["NUKE Score"].fillna(-5).to_numpy(float)
    w=np.power(dup,.24)*np.exp(np.clip(score_by_candidate-score_by_candidate.mean(),-4,4)*.10)
    w=w/w.sum()
    sample=min(3500,max(500,len(cands)))
    field_idx=rng.choice(len(cands),size=sample,replace=True,p=w)
    fs=scoremat[field_idx]
    win_thr=np.max(fs,axis=0); top_thr=np.quantile(fs,.99,axis=0); cash_thr=np.quantile(fs,.80,axis=0)
    out=results.copy()
    wins=[]; tops=[]; cash=[]
    for _,row in out.iterrows():
        sc=scoremat[int(row["_candidate"])]
        wins.append(float(np.mean(sc>=win_thr))*100)
        tops.append(float(np.mean(sc>=top_thr))*100)
        cash.append(float(np.mean(sc>=cash_thr))*100)
    out["Win %"]=np.round(wins,3); out["Top 1% %"]=np.round(tops,2); out["Cash %"]=np.round(cash,1)
    for col,wgt in [("Win %",1.1),("Top 1% %",.55)]:
        z=(out[col]-out[col].mean())/(out[col].std()+1e-9)
        out["NUKE Score"]+=wgt*z
    return out.sort_values("NUKE Score",ascending=False).reset_index(drop=True)

def select_portfolio(results,cands,d,target,max_exp,min_unique,shape_mix,personal_max):
    counts={int(x):0 for x in d["ID"]}
    selected=[]
    shape_targets={k:int(np.floor(target*v/100)) for k,v in shape_mix.items()}
    remain=target-sum(shape_targets.values())
    raw={k:target*v/100 for k,v in shape_mix.items()}
    for k in sorted(raw,key=lambda z:raw[z]-shape_targets[z],reverse=True)[:remain]: shape_targets[k]+=1
    shape_used={k:0 for k in shape_mix}
    for _,r in results.iterrows():
        c=cands[int(r["_candidate"])]
        if shape_used.get(c["shape"],0)>=shape_targets.get(c["shape"],0): continue
        ids=set(int(d.loc[i,"ID"]) for i in c["idx"])
        ok=True
        for pid in ids:
            cap=min(float(max_exp),float(personal_max.get(pid,100)))
            if counts.get(pid,0)+1 > max(1,int(np.floor(target*cap/100+1e-9))): ok=False; break
        if ok:
            for old in selected:
                oldc=cands[int(old["_candidate"])]
                oldids=set(int(d.loc[i,"ID"]) for i in oldc["idx"])
                if len(ids&oldids)>ROSTER-int(min_unique):
                    ok=False; break
        if ok:
            selected.append(r)
            shape_used[c["shape"]]=shape_used.get(c["shape"],0)+1
            for pid in ids: counts[pid]=counts.get(pid,0)+1
        if len(selected)>=target: break
    return pd.DataFrame(selected)

def assign_slots(c,d):
    rows=d.loc[c["idx"]]
    g=rows[rows["Pos"]=="G"].iloc[0]
    sk=rows[rows["Pos"]!="G"].copy()
    chosen=[]; used=set()
    for pos,n in [("C",2),("W",3),("D",2)]:
        q=sk[(sk["Pos"]==pos)&(~sk.index.isin(used))].sort_values("Salary",ascending=False).head(n)
        chosen.extend(q.index.tolist()); used.update(q.index.tolist())
    left=sk[~sk.index.isin(used)]
    if len(left)!=1: return None
    def fmt(idx):
        r=d.loc[idx]; return f'{r["Name"]} ({int(r["ID"])})'
    return [fmt(i) for i in chosen[:2]]+[fmt(i) for i in chosen[2:5]]+[fmt(i) for i in chosen[5:7]]+[fmt(g.name),fmt(left.index[0])]

def export_portfolio(portfolio,cands,d):
    rows=[]
    for rank,r in portfolio.reset_index(drop=True).iterrows():
        c=cands[int(r["_candidate"])]
        slots=assign_slots(c,d)
        if slots is None: continue
        rows.append({"#":rank+1,"C1":slots[0],"C2":slots[1],"W1":slots[2],"W2":slots[3],"W3":slots[4],
                     "D1":slots[5],"D2":slots[6],"G":slots[7],"UTIL":slots[8],"Salary":int(r["Salary"]),
                     "Stack":r["Stack"],"Primary":r["Primary"],"Mean":r["Mean"],"P95":r["P95"],"Top 1%":r["Top 1%"],
                     "Win %":r["Win %"],"Top 1% %":r["Top 1% %"],"Cash %":r["Cash %"],
                     "Own Sum %":r["Own Sum %"],"NUKE Score":round(float(r["NUKE Score"]),3)})
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")

def export_dk(portfolio,cands,d):
    buf=io.StringIO()
    w=csv.writer(buf)
    w.writerow(["C","C","W","W","W","D","D","G","UTIL"])
    for _,r in portfolio.iterrows():
        slots=assign_slots(cands[int(r["_candidate"])],d)
        if slots: w.writerow(slots)
    return buf.getvalue().encode("utf-8-sig")

st.title("🏒 NUKE NHL")
st.caption("DraftKings NHL GPP simulator · 2 C · 3 W · 2 D · 1 G · 1 UTIL · $50,000 cap")

with st.expander("Optional: upload a different DraftKings NHL salary CSV", expanded=False):
    up=st.file_uploader("Different NHL slate CSV",type=["csv"],key="nhl_optional_upload")

try:
    if up is not None:
        golfers=load_csv(up)
        source="Uploaded slate"
    elif DEFAULT.exists():
        golfers=load_csv(DEFAULT)
        source="Loaded automatically"
    else:
        st.info("No bundled NHL slate is available yet.")
        st.stop()
except Exception as e:
    st.error(str(e)); st.stop()

slate_games=sorted(golfers["Game Info"].astype(str).unique().tolist()) if "Game Info" in golfers.columns else []
st.success(f"{source}: {_slate_date(golfers)} · {len(golfers)} active players · {golfers['Team'].nunique()} teams")

if st.sidebar.button("🔄 Refresh NHL lines / goalies",use_container_width=True):
    st.cache_data.clear(); st.rerun()

with st.spinner("Matching current NHL lines, power-play units and goalie status..."):
    players=enrich_context(golfers)

own=ownership_estimate(players)
players["pOwn%"]=np.round(own,1)
line_cov=float((players.loc[players["Pos"]!="G","Line"]!="?").mean()*100) if (players["Pos"]!="G").any() else 0
goalie_cov=float(players.loc[players["Pos"]=="G","G Status"].str.lower().isin(["confirmed","likely","probable","projected","unconfirmed"]).mean()*100) if (players["Pos"]=="G").any() else 0

m1,m2,m3,m4=st.columns(4)
m1.metric("Players",len(players)); m2.metric("Teams",players["Team"].nunique()); m3.metric("Skater Line Match",f"{line_cov:.0f}%"); m4.metric("Salary Cap","$50,000")
st.caption(f"Slate date detected: {_slate_date(players)} · Role data: Daily Faceoff best-effort live match · Goalies intentionally show — under Line/PP.")
if line_cov < 60:
    st.warning("⚠️ Line-combination coverage is currently low. NUKE will automatically fall back to team/PP correlation instead of waiting on missing line data.")

with st.expander("🧠 How NUKE is constructing NHL GPP lineups", expanded=False):
    st.markdown("""
**The core idea is correlation, not nine isolated projections.** A goal can score for the goal-scorer and one or two teammates on the same play, which is why NUKE prioritizes linemates and overlapping power-play units.

- **4-3-1 (default 50%)** — primary four-man team stack, usually a correlated forward core plus a defenseman/PP piece; three correlated skaters from another team; one skater from a third team.
- **3-3-2 (default 35%)** — two correlated three-man stacks plus a two-man mini-stack. This is one of the standard tournament constructions.
- **4-2-2 / 5-2-1** — smaller portfolio shares for alternate ceiling paths and differentiation.
- **Goalie correlation** — NUKE prefers pairing the goalie with the primary offensive stack because team scoring and the goalie win can succeed together.
- **No skaters against your goalie** is on by default because those outcomes are strongly negatively correlated.
- **Power-play overlap matters.** PP1 teammates get additional correlation weight, especially when a defenseman shares the unit with a forward stack.
- **GPP score favors tails.** P95, top-1% outcomes and simulated win rate matter more than median projection alone.
- **Portfolio diversity matters.** Minimum-unique and max-exposure settings prevent 20 entries from becoming tiny variations of one lineup.
""")
    st.caption("DraftKings NHL scoring rewards goals, assists, shots, blocked shots and ceiling bonuses; goalie scoring includes saves, wins and shutouts. NUKE uses DK FPPG as the player baseline and adds correlated team/line/power-play simulation around it.")

st.subheader("🏒 Player Pool")
st.caption("Lines and PP roles matter in NHL GPPs because linemates and power-play teammates can score together on the same goal.")
editor=players[["ID","Name","Pos","Team","Opp","Salary","pOwn%","FPPG","Line","PP","G Status"]].copy()
editor.insert(0,"In",True); editor.insert(1,"Lock",False); editor["Boost %"]=0; editor["Min %"]=0; editor["Max %"]=100

b1,b2,b3=st.columns([1,1,6])
with b1:
    if st.button("✅ ADD ALL",use_container_width=True,key="nhl_add_all"):
        st.session_state["nhl_bulk"]=True; st.session_state.pop("nhl_pool_editor",None); st.rerun()
with b2:
    if st.button("🚫 REMOVE ALL",use_container_width=True,key="nhl_remove_all"):
        st.session_state["nhl_bulk"]=False; st.session_state.pop("nhl_pool_editor",None); st.rerun()
if "nhl_bulk" in st.session_state:
    editor["In"]=bool(st.session_state.pop("nhl_bulk"))

edited=st.data_editor(
    editor,hide_index=True,use_container_width=True,height=500,
    column_order=[c for c in editor.columns if c!="ID"],
    disabled=["ID","Name","Pos","Team","Opp","Salary","pOwn%","FPPG","Line","PP","G Status"],
    column_config={
        "In":st.column_config.CheckboxColumn("In"),"Lock":st.column_config.CheckboxColumn("🔒 Lock"),
        "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
        "pOwn%":st.column_config.NumberColumn("pOwn%",format="%.1f%%"),
        "FPPG":st.column_config.NumberColumn("DK FPPG",format="%.1f"),
        "Boost %":st.column_config.NumberColumn("Boost %",min_value=-50,max_value=100,step=5),
        "Min %":st.column_config.NumberColumn("Min %",min_value=0,max_value=100,step=5),
        "Max %":st.column_config.NumberColumn("Max %",min_value=0,max_value=100,step=5),
    },key="nhl_pool_editor"
)

with st.sidebar:
    st.markdown("## 🏒 NHL SIM")
    candidates_n=st.number_input("Candidate lineups",500,20000,5000,500,key="nhl_candidates")
    universes=st.number_input("Game universes",250,10000,3000,250,key="nhl_universes")
    portfolio_n=st.number_input("Portfolio lineups",1,150,20,1,key="nhl_portfolio")
    min_salary=st.number_input("Minimum salary",30000,50000,DEFAULT_MIN_SALARY,100,key="nhl_min_salary")
    max_exp=st.slider("Max player exposure",1,100,60,key="nhl_max_exp")
    min_unique=st.slider("Minimum unique players",1,6,3,key="nhl_unique",
                         help="Each portfolio lineup must differ from every selected lineup by at least this many players.")
    no_vs_goalie=st.checkbox("No skaters vs own goalie",True,key="nhl_no_vs_g")
    prefer_stack_goalie=st.checkbox("Prefer goalie with primary stack",True,key="nhl_g_stack")
    avoid_fourth_line=st.checkbox("Avoid non-PP 4th-line skaters",True,key="nhl_avoid_f4",
                                   help="Research-based GPP default: fourth-line players usually lack enough ice time unless they retain a power-play role.")
    st.markdown("### Stack Construction")
    st.caption("Percent of portfolio by skater team-stack shape. The goalie is separate.")
    mix={}
    mix["4-3-1"]=st.number_input("4-3-1 %",0,100,50,5,key="nhl_431")
    mix["3-3-2"]=st.number_input("3-3-2 %",0,100,35,5,key="nhl_332")
    mix["5-2-1"]=st.number_input("5-2-1 %",0,100,5,5,key="nhl_521")
    mix["4-2-2"]=st.number_input("4-2-2 %",0,100,10,5,key="nhl_422")
    mix_total=sum(mix.values())
    if mix_total==100: st.success("Stack mix: 100%")
    else: st.warning(f"Stack mix totals {mix_total}%")

if st.button("☢️ RUN NHL GPP SIM",type="primary",use_container_width=True):
    if mix_total!=100:
        st.error("Stack construction percentages must total 100%."); st.stop()
    included=set(edited.loc[edited["In"],"ID"].astype(int))
    excluded=set(edited.loc[~edited["In"],"ID"].astype(int))
    locked=set(edited.loc[edited["Lock"] & edited["In"],"ID"].astype(int))
    if len(locked)>9:
        st.error("You can lock at most 9 players."); st.stop()
    run_players=players.copy()
    seed=int(np.random.default_rng().integers(1,2_000_000_000))
    with st.status("🏒 Building NHL GPP candidate universe...",expanded=True) as run_status:
        st.write("Generating correlated line / power-play stacks...")
        cands=generate_candidates(run_players,int(candidates_n),int(min_salary),seed,mix,bool(no_vs_goalie),bool(prefer_stack_goalie),bool(avoid_fourth_line),locked,excluded)
        if not cands:
            run_status.update(label="No legal candidates generated",state="error")
            st.error("No legal NHL lineups were generated. Loosen the pool/exposure rules or lower the minimum salary."); st.stop()
        st.write(f"✅ Generated {len(cands):,} legal candidates (target {int(candidates_n):,}). Simulating {int(universes):,} slate outcomes...")
        sims=simulate_players(run_players,int(universes),seed)
        own=ownership_estimate(run_players)
        st.write("Scoring ceiling, leverage and tournament outcomes...")
        results=evaluate(cands,sims,run_players,own)
        results=contest_metrics(results,cands,sims,run_players,seed)
        run_status.update(label=f"✅ NHL SIM complete — {len(cands):,} candidates evaluated",state="complete",expanded=False)
        boosts=dict(zip(edited["ID"].astype(int),edited["Boost %"].astype(float)))
        for ri in results.index:
            c=cands[int(results.at[ri,"_candidate"])]
            results.at[ri,"NUKE Score"] += sum(boosts.get(int(run_players.loc[i,"ID"]),0) for i in c["idx"])/100
        results=results.sort_values("NUKE Score",ascending=False).reset_index(drop=True)
        pmax=dict(zip(edited["ID"].astype(int),edited["Max %"].astype(float)))
        portfolio=select_portfolio(results,cands,run_players,int(portfolio_n),float(max_exp),int(min_unique),mix,pmax)
        st.session_state["nhl_results"]=(results,cands,portfolio,run_players,seed,int(universes))

if "nhl_results" in st.session_state:
    results,cands,portfolio,run_players,seed,run_universes=st.session_state["nhl_results"]
    st.divider(); st.header("🏆 NUKE NHL GPP Portfolio")
    a,b,c,d=st.columns(4)
    a.metric("Candidates",len(results)); b.metric("Portfolio",len(portfolio)); c.metric("Universes",f"{run_universes:,}"); d.metric("Seed",seed)
    if len(portfolio)<int(portfolio_n):
        st.warning(f"Built {len(portfolio)} of {int(portfolio_n)} requested lineups because the exposure/uniqueness/stack constraints became too tight.")
    show=[]
    for rank,r in portfolio.reset_index(drop=True).iterrows():
        cnd=cands[int(r["_candidate"])]
        names=" · ".join(run_players.loc[cnd["idx"],"Name"].astype(str).tolist())
        show.append({"#":rank+1,"Players":names,"Salary":int(r["Salary"]),"Stack":r["Stack"],"Primary":r["Primary"],
                     "Mean":r["Mean"],"P95":r["P95"],"Top 1%":r["Top 1%"],"Win %":r["Win %"],
                     "Top 1% %":r["Top 1% %"],"Cash %":r["Cash %"],"Own Sum %":r["Own Sum %"],
                     "NUKE Score":round(float(r["NUKE Score"]),3)})
    st.dataframe(pd.DataFrame(show),hide_index=True,use_container_width=True,height=480)
    c1,c2=st.columns(2)
    with c1:
        st.download_button("DOWNLOAD NHL PORTFOLIO + STATS CSV",export_portfolio(portfolio,cands,run_players),
                           file_name="nuke_nhl_portfolio.csv",mime="text/csv",type="primary",use_container_width=True)
    with c2:
        st.download_button("DOWNLOAD DK LINEUP-ONLY CSV",export_dk(portfolio,cands,run_players),
                           file_name="nuke_nhl_dk_lineups.csv",mime="text/csv",use_container_width=True)

    st.subheader("Player Exposure")
    denom=max(1,len(portfolio)); exp=[]
    own=ownership_estimate(run_players)
    for j,(idx,row) in enumerate(run_players.iterrows()):
        ct=sum(1 for _,rr in portfolio.iterrows() if idx in cands[int(rr["_candidate"])]["idx"])
        if ct:
            exp.append({"Player":row["Name"],"Pos":row["Pos"],"Team":row["Team"],"Line":row["Line"],"PP":row["PP"],
                        "Lineups":ct,"Exposure %":round(ct/denom*100,1),"pOwn%":round(float(own[j]),1)})
    st.dataframe(pd.DataFrame(exp).sort_values(["Exposure %","Player"],ascending=[False,True]),hide_index=True,use_container_width=True)

    st.subheader("Stack Mix")
    mixrows=[]
    for shape in ["5-2-1","4-3-1","3-3-2","4-2-2"]:
        ct=int((portfolio["Stack"]==shape).sum()) if len(portfolio) else 0
        mixrows.append({"Stack":shape,"Lineups":ct,"Portfolio %":round(ct/denom*100,1)})
    st.dataframe(pd.DataFrame(mixrows),hide_index=True,use_container_width=True)

    with st.expander("Top simulated candidate lineups"):
        st.dataframe(results[["Salary","Stack","Primary","Mean","P95","Top 1%","Win %","Top 1% %","Cash %","Own Sum %","NUKE Score"]].head(100),
                     hide_index=True,use_container_width=True)

import streamlit as st
import pandas as pd
import numpy as np
import itertools, re, time, html, unicodedata
import requests
from urllib.parse import quote_plus
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from nuke_nav import render_nav

st.set_page_config(page_title="NUKE MMA Sim",page_icon="🥊",layout="wide")
render_nav()

CAP=50000
ROSTER=6
DEFAULT=Path(__file__).resolve().parents[1]/"data"/"mma_current.csv"

def load_csv(src):
    d=pd.read_csv(src).copy()
    req={"Name","ID","Salary","Game Info","AvgPointsPerGame"}
    if not req.issubset(d.columns): raise ValueError("This does not look like a DraftKings MMA Classic salary CSV.")
    d["ID"]=pd.to_numeric(d["ID"],errors="coerce").astype("Int64")
    d["Salary"]=pd.to_numeric(d["Salary"],errors="coerce").fillna(0).astype(int)
    d["FPPG"]=pd.to_numeric(d["AvgPointsPerGame"],errors="coerce").fillna(0.0)
    status=d["Status"] if "Status" in d.columns else pd.Series("",index=d.index)
    d["Status"]=status.fillna("").astype(str).str.upper()
    d=d[~d["Status"].isin(["OUT","O","IR","WD"])].dropna(subset=["ID"]).drop_duplicates("ID").reset_index(drop=True)
    d["Fight"]=d["Game Info"].astype(str).str.replace(r"\s+\d{1,2}/\d{1,2}/\d{4}.*$","",regex=True)
    d["Opp"]=""
    for _,idxs in d.groupby("Fight").groups.items():
        z=list(idxs)
        if len(z)==2:
            d.loc[z[0],"Opp"]=d.loc[z[1],"Name"]; d.loc[z[1],"Opp"]=d.loc[z[0],"Name"]
    raw=d["Game Info"].astype(str).str.extract(r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}[AP]M)")[0]
    d["_start"]=pd.to_datetime(raw,format="%m/%d/%Y %I:%M%p",errors="coerce")
    d["Rounds"]=np.where(d["_start"].eq(d["_start"].max()),5,3)
    return d


def _norm_name(x):
    x=unicodedata.normalize("NFKD",str(x)).encode("ascii","ignore").decode()
    return re.sub(r"[^a-z0-9]","",x.lower())

def _slug_name(x):
    x=unicodedata.normalize("NFKD",str(x)).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+","-",x).strip("-")

def _strip_html(x):
    x=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",x)
    x=re.sub(r"(?s)<[^>]+>"," ",x)
    return re.sub(r"\s+"," ",html.unescape(x)).strip()

def _american_prob(odds):
    try: o=float(odds)
    except Exception: return np.nan
    if o<0: return (-o)/((-o)+100.0)
    if o>0: return 100.0/(o+100.0)
    return np.nan

@st.cache_data(ttl=900,show_spinner=False)
def fetch_fight_market(name_a,name_b,refresh_token=0):
    """Best-effort DK moneyline from UFCalendar, falling back to its multi-book consensus."""
    headers={"User-Agent":"Mozilla/5.0 NUKE-DFS"}
    orders=[(name_a,name_b),(name_b,name_a)]
    for a,b in orders:
        url=f"https://www.ufcalendar.com/fights/{_slug_name(a)}-vs-{_slug_name(b)}"
        try:
            r=requests.get(url,timeout=7,headers=headers)
            if not r.ok: continue
            txt=_strip_html(r.text)
            low=txt.lower()
            if _norm_name(a) not in _norm_name(txt) or _norm_name(b) not in _norm_name(txt): continue

            # Prefer the DraftKings row from the line-movement table.
            pos=low.find("draftkings")
            source="DraftKings"
            odds=[]
            if pos>=0:
                window=txt[pos:pos+260]
                odds=re.findall(r"(?<!\d)([+-]\d{3,4})(?!\d)",window)
            # If DK is not present/parsable, use the page's displayed consensus lines.
            if len(odds)<2:
                source="Consensus"
                p=low.find("betting odds")
                window=txt[p:p+1200] if p>=0 else txt[:1600]
                odds=re.findall(r"(?<!\d)([+-]\d{3,4})(?!\d)",window)
            if len(odds)<2: continue

            o1,o2=int(odds[0]),int(odds[1])
            p1,p2=_american_prob(o1),_american_prob(o2)
            if not np.isfinite(p1) or not np.isfinite(p2) or not (.80<=p1+p2<=1.35): continue
            fair1=p1/(p1+p2); fair2=p2/(p1+p2)
            return {
                _norm_name(a):{"Moneyline":o1,"Market Win %":fair1*100,"Odds Source":source},
                _norm_name(b):{"Moneyline":o2,"Market Win %":fair2*100,"Odds Source":source},
            }
        except Exception:
            continue
    return {}

def _grab_after(txt,patterns):
    for pattern in patterns:
        m=re.search(pattern+r"\\s*[:\\-]?\\s*([0-9]+(?:\\.[0-9]+)?)\\s*%?",txt,re.I)
        if m:
            try: return float(m.group(1))
            except Exception: pass
    return np.nan

def _grab_before(txt,patterns):
    for pattern in patterns:
        m=re.search(r"([0-9]+(?:\\.[0-9]+)?)\\s*%?\\s*"+pattern,txt,re.I)
        if m:
            try: return float(m.group(1))
            except Exception: pass
    return np.nan

def _stats_payload(vals,source):
    out={}
    for col,val in vals.items():
        try:
            v=float(val)
            if np.isfinite(v): out[col]=v
        except Exception:
            pass
    if out: out["Stats Source"]=source
    return out

@st.cache_data(ttl=21600,show_spinner=False)
def fetch_ufcstats(name,refresh_token=0):
    """Pull fighter style rates with multiple fallbacks so cloud blocking does not blank the MMA model."""
    headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":"en-US,en;q=0.9",
    }
    slug=_slug_name(name)

    # Primary: UFCalendar exposes current career-rate pages and is already used by NUKE for fight markets.
    try:
        r=requests.get(f"https://www.ufcalendar.com/fighters/{slug}/stats",timeout=8,headers=headers)
        if r.ok:
            txt=_strip_html(r.text)
            if _norm_name(name) in _norm_name(txt):
                vals={
                    "SLpM":_grab_after(txt,[r"Strikes landed\\s*/\\s*min",r"Significant strikes"]),
                    "SApM":_grab_after(txt,[r"Strikes absorbed\\s*/\\s*min",r"SApM"]),
                    "TD Avg":_grab_after(txt,[r"Takedowns\\s*/\\s*15\\s*min",r"TD Avg\\.?"]),
                    "TD Def %":_grab_after(txt,[r"TD Def\\.?",r"Takedown defense"]),
                    "Sub Avg":_grab_after(txt,[r"Submission attempts",r"Sub\\.?\\s*Avg\\.?"]),
                }
                out=_stats_payload(vals,"UFCalendar")
                if "SLpM" in out and "SApM" in out: return out
    except Exception:
        pass

    # Secondary: official UFC athlete pages use number-before-label metric cards.
    try:
        r=requests.get(f"https://www.ufc.com/athlete/{slug}",timeout=8,headers=headers)
        if r.ok:
            txt=_strip_html(r.text)
            if _norm_name(name) in _norm_name(txt):
                vals={
                    "SLpM":_grab_before(txt,[r"Sig\\.?\\s*Str\\.?\\s*Landed\\s*Per\\s*Min"]),
                    "SApM":_grab_before(txt,[r"Sig\\.?\\s*Str\\.?\\s*Absorbed\\s*Per\\s*Min"]),
                    "TD Avg":_grab_before(txt,[r"Takedown\\s*avg\\s*Per\\s*15\\s*Min"]),
                    "TD Def %":_grab_before(txt,[r"Takedown\\s*Defense"]),
                    "Sub Avg":_grab_before(txt,[r"Submission\\s*avg\\s*Per\\s*15\\s*Min"]),
                }
                out=_stats_payload(vals,"UFC.com")
                if "SLpM" in out and "SApM" in out: return out
    except Exception:
        pass

    # Final live fallback: UFCStats. HTTPS is important in hosted Streamlit environments.
    detail_url=None
    try:
        urls=[
            f"https://ufcstats.com/statistics/fighters/search?query={quote_plus(str(name))}",
            f"https://ufcstats.com/statistics/fighters?char={slug[:1]}&page=all",
        ]
        for url in urls:
            r=requests.get(url,timeout=8,headers=headers)
            if not r.ok: continue
            links=re.findall(r"href=[\\\"'](https?://ufcstats\\.com/fighter-details/[a-zA-Z0-9]+)[\\\"'][^>]*>(.*?)</a>",r.text,re.I|re.S)
            for href,_ in links:
                ix=r.text.find(href)
                row=_strip_html(r.text[max(0,ix-650):ix+1250])
                if _norm_name(name) in _norm_name(row):
                    detail_url=href.replace("http://","https://")
                    break
            if detail_url: break
        if not detail_url: return {}

        d=requests.get(detail_url,timeout=8,headers=headers)
        if not d.ok: return {}
        txt=_strip_html(d.text)
        def grab(label):
            m=re.search(re.escape(label)+r"\\s*([0-9.]+)%?",txt,re.I)
            return float(m.group(1)) if m else np.nan
        return _stats_payload({
            "SLpM":grab("SLpM:"),
            "SApM":grab("SApM:"),
            "TD Avg":grab("TD Avg.:"),
            "TD Acc %":grab("TD Acc.:"),
            "TD Def %":grab("TD Def.:"),
            "Sub Avg":grab("Sub. Avg.:"),
        },"UFCStats")
    except Exception:
        return {}

def enrich_live_context(d,refresh_token=0):
    x=d.copy()
    # Moneylines: one request per fight, in parallel.
    market={}
    fights=[]
    for _,g in x.groupby("Fight"):
        if len(g)==2:
            fights.append((str(g.iloc[0]["Name"]),str(g.iloc[1]["Name"])))
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(fights)))) as ex:
        futs=[ex.submit(fetch_fight_market,a,b,refresh_token) for a,b in fights]
        for f in as_completed(futs):
            try: market.update(f.result() or {})
            except Exception: pass

    stats={}
    names=x["Name"].astype(str).tolist()
    with ThreadPoolExecutor(max_workers=min(10,max(1,len(names)))) as ex:
        futs={ex.submit(fetch_ufcstats,n,refresh_token):n for n in names}
        for f in as_completed(futs):
            n=futs[f]
            try: stats[_norm_name(n)]=f.result() or {}
            except Exception: stats[_norm_name(n)]={}

    # Preserve bundled snapshot values when a live source is temporarily blocked.
    # Fresh live values overwrite the snapshot below whenever a request succeeds.
    for col,default in [
        ("Moneyline",np.nan),("Market Win %",np.nan),("Odds Source","Fallback"),
        ("SLpM",np.nan),("SApM",np.nan),("TD Avg",np.nan),("TD Acc %",np.nan),
        ("TD Def %",np.nan),("Sub Avg",np.nan),("Stats Source","Fallback")
    ]:
        if col not in x.columns:
            x[col]=default
        elif col in ("Odds Source","Stats Source"):
            x[col]=x[col].fillna(default).astype(str)
            x.loc[x[col].str.strip().isin(["","nan","None"] ),col]=default
        else:
            x[col]=pd.to_numeric(x[col],errors="coerce")

    for i,row in x.iterrows():
        k=_norm_name(row["Name"])
        for col,val in market.get(k,{}).items(): x.at[i,col]=val
        for col,val in stats.get(k,{}).items(): x.at[i,col]=val
    return x

def model(d):
    sal=d["Salary"].to_numpy(float); fppg=d["FPPG"].to_numpy(float)

    # Salary-implied prior, then market moneyline if available.
    win=np.full(len(d),.5,dtype=float)
    for _,idxs in d.groupby("Fight").groups.items():
        z=list(idxs)
        if len(z)==2:
            a,b=z
            pa=1/(1+np.exp(-(float(d.loc[a,"Salary"])-float(d.loc[b,"Salary"]))/1850))
            win[a]=pa; win[b]=1-pa
            ma=float(d.loc[a,"Market Win %"]) if pd.notna(d.loc[a,"Market Win %"]) else np.nan
            mb=float(d.loc[b,"Market Win %"]) if pd.notna(d.loc[b,"Market Win %"]) else np.nan
            if np.isfinite(ma) and np.isfinite(mb) and ma>0 and mb>0:
                total=ma+mb; win[a]=(ma/total); win[b]=(mb/total)

    # UFCStats adds style/volume context. Missing stats stay neutral.
    def zfill(col):
        a=pd.to_numeric(d.get(col,pd.Series(np.nan,index=d.index)),errors="coerce").to_numpy(float)
        med=np.nanmedian(a) if np.isfinite(a).any() else 0.0
        a=np.where(np.isfinite(a),a,med)
        sd=np.nanstd(a)
        return (a-np.nanmean(a))/(sd+1e-9)

    z_slpm=zfill("SLpM"); z_sapm=zfill("SApM"); z_td=zfill("TD Avg"); z_sub=zfill("Sub Avg"); z_tddef=zfill("TD Def %")
    pressure=.48*z_slpm+.32*z_td+.20*z_sub
    defense=.55*z_tddef-.45*z_sapm
    five=(d["Rounds"].to_numpy()==5)

    # Finish probability is a ceiling prior, not a sportsbook prop.
    favorite=np.abs(win-.5)*2
    finish=np.clip(.34+.15*favorite+.065*pressure-.025*defense+.055*five,.22,.78)

    # Projection blends DK FPPG with market win probability and style scoring opportunity.
    style_pts=4.5*z_slpm+4.0*z_td+2.2*z_sub
    market_proj=win*(82+43*finish+9*five)+(1-win)*(33+8*five)+style_pts
    proj=np.where(fppg>0,.58*market_proj+.42*fppg,market_proj)

    # Ownership estimate uses salary + projection + market strength, then normalizes to 600%.
    z=.43*(sal-sal.mean())/(sal.std()+1e-9)+.35*(proj-proj.mean())/(proj.std()+1e-9)+.22*(win-win.mean())/(win.std()+1e-9)
    raw=np.exp(np.clip(.72*z,-2.4,2.4)); own=raw/raw.sum()*600
    return win,finish,proj,own

def simulate_card(d,n,seed):
    rng=np.random.default_rng(seed)
    win,finish,_,_=model(d)
    scores=np.zeros((n,len(d)),dtype=np.float32)
    for _,idxs in d.groupby("Fight").groups.items():
        z=list(idxs)
        if len(z)!=2: continue
        a,b=z; aw=rng.random(n)<win[a]
        for w,l,mask in [(a,b,aw),(b,a,~aw)]:
            rows=np.where(mask)[0]
            if not len(rows): continue
            is5=bool(d.loc[w,"Rounds"]==5)
            fin=rng.random(len(rows))<finish[w]
            probs=np.array([.46,.27,.16,.07,.04]) if is5 else np.array([.50,.30,.20])
            fr=np.zeros(len(rows),dtype=int)
            if fin.any(): fr[fin]=rng.choice(np.arange(1,len(probs)+1),size=int(fin.sum()),p=probs)
            wh=float(d.loc[w,"FPPG"]); lh=float(d.loc[l,"FPPG"])
            wadj=float(np.clip((wh-75)*.12 if wh>0 else 0,-7,9))
            ladj=float(np.clip((lh-70)*.06 if lh>0 else 0,-4,5))
            wstyle=0.0; lstyle=0.0
            for col,wt in [("SLpM",2.0),("TD Avg",2.6),("Sub Avg",1.8)]:
                vals=pd.to_numeric(d[col],errors="coerce") if col in d.columns else pd.Series(np.nan,index=d.index)
                med=float(vals.median()) if vals.notna().any() else 0.0
                sd=float(vals.std()) if vals.notna().any() else 1.0
                wstyle+=wt*((float(d.loc[w,col]) if pd.notna(d.loc[w,col]) else med)-med)/(sd+1e-9)
                lstyle+=wt*((float(d.loc[l,col]) if pd.notna(d.loc[l,col]) else med)-med)/(sd+1e-9)
            bonus=np.array([119,104,92,86,82],float)
            wbase=np.where(fin,bonus[np.maximum(fr-1,0)],96 if is5 else 78)+wadj+wstyle
            lbase=np.where(fin,10+fr*12,66 if is5 else 48)+ladj+lstyle
            scores[rows,w]=np.clip(wbase+rng.normal(0,10,len(rows)),0,170)
            scores[rows,l]=np.clip(lbase+rng.normal(0,10,len(rows)),0,110)
    return scores

def candidates(d,n,min_sal,max_sal,seed,no_same,locked,excluded):
    ids=d["ID"].astype(int).to_numpy(); sal=d["Salary"].to_numpy(int); fights=d["Fight"].astype(str).to_numpy()
    win,finish,proj,own=model(d)
    avail=[i for i,p in enumerate(ids) if p not in excluded]
    lock=[i for i,p in enumerate(ids) if p in locked and p not in excluded]
    need=ROSTER-len(lock)
    if need<0: return []
    rest=[i for i in avail if i not in lock]
    rng=np.random.default_rng(seed); pool=[]
    for comb in itertools.combinations(rest,need):
        idx=tuple(sorted(lock+list(comb))); s=int(sal[list(idx)].sum())
        if s<min_sal or s>max_sal: continue
        if no_same and len(set(fights[list(idx)]))<ROSTER: continue
        o=float(own[list(idx)].sum()); low=int(np.sum(own[list(idx)]<15)); dog=int(np.sum(win[list(idx)]<.5))
        upside=proj[list(idx)].sum()+10*np.sqrt(np.sum((finish[list(idx)]*35)**2))
        pre=float(upside+2.5*min(low,2)-1.5*max(0,low-3)-.025*max(0,o-175)+rng.normal(0,10))
        pool.append((pre,idx,s,o,low,dog))
    pool.sort(key=lambda x:x[0],reverse=True)
    if len(pool)>n:
        core=max(1,int(n*.8)); tail=pool[core:]; take=min(n-core,len(tail))
        choice=rng.choice(len(tail),size=take,replace=False) if take else []
        pool=pool[:core]+[tail[int(i)] for i in choice]
    return [{"idx":x[1],"salary":x[2],"own_sum":x[3],"low":x[4],"dogs":x[5],
             "dup":float(np.prod(np.clip(own[list(x[1])]/100,.002,.95)))} for x in pool[:n]]

def evaluate(cands,sims,d,field_size,seed):
    n=len(cands); u=sims.shape[0]
    mat=np.empty((n,u),dtype=np.float32)
    for j,c in enumerate(cands): mat[j]=sims[:,list(c["idx"])].sum(axis=1)
    optimal=(mat>=mat.max(axis=0)[None,:]-1e-5).mean(axis=1)*100
    rng=np.random.default_rng(seed+818)
    dup=np.array([max(c["dup"],1e-12) for c in cands]); means=mat.mean(axis=1)
    z=(means-means.mean())/(means.std()+1e-9); fw=np.power(dup,.30)*np.exp(np.clip(.12*z,-1.5,1.5)); fw/=fw.sum()
    fi=rng.choice(n,size=int(min(max(500,field_size),3000)),replace=True,p=fw); fs=mat[fi]
    wthr=fs.max(axis=0); tthr=np.quantile(fs,.99,axis=0); cthr=np.quantile(fs,.80,axis=0)
    rows=[]
    for j,c in enumerate(cands):
        sc=mat[j]
        rows.append({"_candidate":j,"Salary":c["salary"],"Salary Left":CAP-c["salary"],"Mean":float(sc.mean()),
            "P95":float(np.quantile(sc,.95)),"P99":float(np.quantile(sc,.99)),"Optimal %":float(optimal[j]),
            "Win %":float(np.mean(sc>=wthr)*100),"Top 1% %":float(np.mean(sc>=tthr)*100),"Cash %":float(np.mean(sc>=cthr)*100),
            "Own Sum %":float(c["own_sum"]),"Low-Owned":int(c["low"]),"Underdogs":int(c["dogs"]),"Dup":float(c["dup"])})
    r=pd.DataFrame(rows); score=np.zeros(len(r))
    for col,w in [("P95",1),("P99",1.25),("Optimal %",1.2),("Win %",1.4),("Top 1% %",.75)]:
        zz=(r[col]-r[col].mean())/(r[col].std()+1e-9); score+=w*zz
    lev=-np.log(np.maximum(r["Dup"].to_numpy(),1e-12)); lev=(lev-lev.mean())/(lev.std()+1e-9)
    score+=.30*lev+.12*np.clip(r["Salary Left"].to_numpy(),0,1800)/1800
    r["NUKE Score"]=score
    return r.sort_values("NUKE Score",ascending=False).reset_index(drop=True)

def portfolio(results,cands,d,n,max_exp,min_unique,pmax,pmin):
    ids=d["ID"].astype(int).to_numpy(); global_lim=max(1,int(np.ceil(n*max_exp/100)))
    counts={int(p):0 for p in ids}; picked=[]; used=set()
    for slot in range(n):
        best=None; bestv=-1e18
        for ri,row in results.iterrows():
            if ri in used: continue
            c=cands[int(row["_candidate"])]; pids=[int(ids[i]) for i in c["idx"]]
            bad=False
            for p in pids:
                indiv=int(np.ceil(n*pmax.get(p,100)/100))
                if counts[p]>=min(global_lim,indiv): bad=True; break
            if bad: continue
            if any(len(set(pids)-set(prev))<min_unique for prev in picked): continue
            bonus=sum(1.25*max(0,int(np.ceil(n*pmin.get(p,0)/100))-counts[p]) for p in pids)
            v=float(row["NUKE Score"])+bonus
            if v>bestv: bestv=v; best=(ri,pids,row)
        if best is None: break
        ri,pids,row=best; used.add(ri); picked.append(pids)
        for p in pids: counts[p]+=1
    out=[]
    for pids in picked:
        ps=set(pids)
        for _,row in results.iterrows():
            c=cands[int(row["_candidate"])]
            if set(int(ids[i]) for i in c["idx"])==ps: out.append(row); break
    return pd.DataFrame(out).reset_index(drop=True)

def lineup_csv(port,cands,d):
    rows=[]
    for _,r in port.iterrows():
        c=cands[int(r["_candidate"])]; ps=d.iloc[list(c["idx"])].sort_values("Salary",ascending=False)
        vals=[f'{x["Name"]} ({int(x["ID"])})' for _,x in ps.iterrows()]
        rows.append({f"F{i+1}":vals[i] for i in range(6)})
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")

st.title("🥊 NUKE MMA")
st.caption("DraftKings MMA large-field GPP simulator · 6 fighters · $50,000 salary cap")

with st.expander("Optional: upload a different DraftKings MMA salary CSV",expanded=False):
    up=st.file_uploader("Different MMA slate CSV",type=["csv"],key="mma_upload")
try:
    if up is not None: fighters=load_csv(up); source="Uploaded slate"
    elif DEFAULT.exists(): fighters=load_csv(DEFAULT); source="Loaded automatically"
    else: st.info("No bundled MMA slate is available yet."); st.stop()
except Exception as e:
    st.error(str(e)); st.stop()

event_date=""
m=re.search(r"(\d{1,2}/\d{1,2}/\d{4})",str(fighters["Game Info"].iloc[0])) if len(fighters) else None
if m: event_date=m.group(1)
refresh_nonce=int(st.session_state.get("mma_live_refresh_nonce",0))
refresh_token=f"{int(time.time()//900)}:{refresh_nonce}"
with st.spinner("Pulling current MMA moneylines and UFCStats style data..."):
    fighters=enrich_live_context(fighters,refresh_token)

if st.session_state.get("mma_live_context_token")!=refresh_token:
    now=datetime.now(ZoneInfo("America/Chicago"))
    st.session_state["mma_live_context_token"]=refresh_token
    st.session_state["mma_live_updated_at"]=now.strftime("%b %d, %Y at %I:%M %p %Z").replace(" 0"," ")

winp,finishp,proj,pown=model(fighters)
fighters["Win %"]=np.round(winp*100,1); fighters["Finish %"]=np.round(finishp*100,1)
fighters["Projection"]=np.round(proj,1); fighters["pOwn%"]=np.round(pown,1)

st.success(f"{source}: {event_date or 'current card'} · {len(fighters)} fighters · {fighters['Fight'].nunique()} fights")
odds_cov=int(fighters["Market Win %"].notna().sum())
stats_cov=int(fighters["SLpM"].notna().sum())
last_live=st.session_state.get("mma_live_updated_at","Just now")
c1,c2,c3=st.columns([1,1,2])
c1.metric("Live odds",f"{odds_cov}/{len(fighters)}")
c2.metric("Fighter stats",f"{stats_cov}/{len(fighters)}")
c3.caption(f"🕒 Live data last refreshed: **{last_live}** · auto-checks every 15 minutes while active.")
if odds_cov<len(fighters):
    st.caption("Missing odds safely fall back to DraftKings salary-implied win probability. Missing fighter stats stay neutral in the style model.")
if st.button("🔄 REFRESH LIVE MMA DATA",use_container_width=True,key="mma_refresh_live"):
    st.session_state["mma_live_refresh_nonce"]=refresh_nonce+1
    fetch_fight_market.clear(); fetch_ufcstats.clear()
    st.rerun()

m1,m2,m3,m4=st.columns(4)
m1.metric("Fighters",len(fighters)); m2.metric("Fights",fighters["Fight"].nunique()); m3.metric("Roster","6 F"); m4.metric("Salary Cap","$50,000")

with st.expander("🧠 Large-field GPP construction baked into NUKE",expanded=False):
    st.markdown("""
- No same-fight pairing by default: one fighter's success directly hurts the opponent's ceiling.
- Whole-card simulations force one winner per fight and model finish/decision tails instead of six independent projections.
- The final scheduled fight is automatically treated as five rounds, adding ceiling to both sides.
- Salary is not forced to $50K. Historical perfect lineups often leave salary unused; NUKE defaults to a $49,800 maximum.
- One or two leverage fighters are useful; forcing an entire lineup of low-owned darts is not.
- **Current moneylines** are pulled automatically when available and de-vigged into fair market win probabilities.
- **Fighter style data** (SLpM, SApM, takedowns, takedown defense, submission attempts) changes fighter ceiling and score distributions.
- Max exposure, Min/Max fighter exposure and minimum uniques build a portfolio across different card outcomes.
""")
    st.caption("Moneylines are live market inputs when available. Finish %, pOwn%, projections and tournament outputs remain model estimates, not sportsbook props.")

st.subheader("🥋 Fighter Pool")
ed=fighters[["ID","Name","Opp","Salary","Moneyline","Market Win %","pOwn%","FPPG","Win %","Finish %","Projection","SLpM","TD Avg","Sub Avg","Rounds","Fight"]].copy()
ed.insert(0,"In",True); ed.insert(1,"Lock",False); ed["Boost %"]=0; ed["Min %"]=0; ed["Max %"]=100
prefs=st.session_state.get("mma_prefs",{})
for i,row in ed.iterrows():
    p=prefs.get(str(int(row["ID"])),{})
    for c in ["In","Lock","Boost %","Min %","Max %"]:
        if c in p: ed.at[i,c]=p[c]
b1,b2=st.columns(2)
if b1.button("✅ ADD ALL",use_container_width=True): st.session_state["mma_bulk"]=True; st.session_state.pop("mma_editor",None); st.rerun()
if b2.button("🚫 REMOVE ALL",use_container_width=True): st.session_state["mma_bulk"]=False; st.session_state.pop("mma_editor",None); st.rerun()
if "mma_bulk" in st.session_state: ed["In"]=bool(st.session_state.pop("mma_bulk"))
edited=st.data_editor(ed,hide_index=True,use_container_width=True,height=520,column_order=[c for c in ed.columns if c!="ID"],
    disabled=["ID","Name","Opp","Salary","Moneyline","Market Win %","pOwn%","FPPG","Win %","Finish %","Projection","SLpM","TD Avg","Sub Avg","Rounds","Fight"],
    column_config={"In":st.column_config.CheckboxColumn("In"),"Lock":st.column_config.CheckboxColumn("🔒 Lock"),
    "Salary":st.column_config.NumberColumn("Salary",format="$%d"),"Moneyline":st.column_config.NumberColumn("Odds",format="%d"),
    "Market Win %":st.column_config.NumberColumn("Market Win",format="%.1f%%"),"pOwn%":st.column_config.NumberColumn("pOwn%",format="%.1f%%"),
    "FPPG":st.column_config.NumberColumn("DK FPPG",format="%.1f"),"Win %":st.column_config.NumberColumn("Win %",format="%.1f%%"),
    "Finish %":st.column_config.NumberColumn("Finish %",format="%.1f%%"),"Projection":st.column_config.NumberColumn("Proj",format="%.1f"),
    "Boost %":st.column_config.NumberColumn("Boost %",min_value=-50,max_value=100,step=5),
    "Min %":st.column_config.NumberColumn("Min %",min_value=0,max_value=100,step=5),
    "Max %":st.column_config.NumberColumn("Max %",min_value=0,max_value=100,step=5)},key="mma_editor")
st.session_state["mma_prefs"]={str(int(r["ID"])):{"In":bool(r["In"]),"Lock":bool(r["Lock"]),"Boost %":float(r["Boost %"]),"Min %":float(r["Min %"]),"Max %":float(r["Max %"])} for _,r in edited.iterrows()}

with st.sidebar:
    st.markdown("## 🥊 MMA SIM")
    n_cand=st.number_input("Candidate lineups",500,20000,5000,500)
    n_sim=st.number_input("Card simulations",500,10000,3000,500)
    n_port=st.number_input("Portfolio lineups",1,150,20,1)
    min_sal=st.number_input("Minimum salary",30000,50000,47500,100)
    max_sal=st.number_input("Maximum salary",30000,50000,49800,100)
    max_exp=st.slider("Max fighter exposure",1,100,40)
    min_unique=st.slider("Minimum unique fighters",1,5,2)
    no_same=st.checkbox("No fighters from same fight",value=True)
    field_size=st.number_input("Contest field size",100,100000,10000,100)

if min_sal>max_sal: st.error("Minimum salary cannot exceed maximum salary."); st.stop()

if st.button("☢️ RUN MMA GPP SIM",type="primary",use_container_width=True):
    excluded=set(edited.loc[~edited["In"],"ID"].astype(int))
    locked=set(edited.loc[edited["In"]&edited["Lock"],"ID"].astype(int))
    if len(locked)>6: st.error("You can lock at most 6 fighters."); st.stop()
    seed=int(np.random.default_rng().integers(1,2_000_000_000))
    with st.status("🥊 Simulating the MMA card...",expanded=True) as status:
        st.write("Enumerating legal GPP builds...")
        cands=candidates(fighters,int(n_cand),int(min_sal),int(max_sal),seed,bool(no_same),locked,excluded)
        if not cands: status.update(label="No legal lineups",state="error"); st.error("No legal lineups fit these rules."); st.stop()
        st.write(f"✅ {len(cands):,} candidates · simulating {int(n_sim):,} whole-card outcomes...")
        sims=simulate_card(fighters,int(n_sim),seed+11)
        boosts=dict(zip(edited["ID"].astype(int),edited["Boost %"].astype(float)))
        idcol={int(p):i for i,p in enumerate(fighters["ID"].astype(int))}
        for p,b in boosts.items():
            if abs(b)>1e-9 and p in idcol: sims[:,idcol[p]]*=1+b/100
        st.write("Calculating optimal rate, tournament win rate and leverage...")
        results=evaluate(cands,sims,fighters,int(field_size),seed)
        pmax=dict(zip(edited["ID"].astype(int),edited["Max %"].astype(float))); pmin=dict(zip(edited["ID"].astype(int),edited["Min %"].astype(float)))
        port=portfolio(results,cands,fighters,int(n_port),float(max_exp),int(min_unique),pmax,pmin)
        st.session_state["mma_results"]=(results,cands,port,fighters,int(n_sim))
        status.update(label=f"✅ MMA SIM complete — {len(cands):,} candidates evaluated",state="complete",expanded=False)

if "mma_results" in st.session_state:
    results,cands,port,rf,n_sim=st.session_state["mma_results"]
    st.divider(); st.header("🏆 NUKE MMA GPP Portfolio")
    a,b,c=st.columns(3); a.metric("Candidates",len(results)); b.metric("Portfolio",len(port)); c.metric("Card Sims",f"{n_sim:,}")
    if len(port)<int(n_port): st.warning(f"Built {len(port)} of {int(n_port)} requested lineups because exposure/uniqueness settings became too tight.")
    show=[]
    for rank,r in port.reset_index(drop=True).iterrows():
        cnd=cands[int(r["_candidate"])]; names=" · ".join(rf.iloc[list(cnd["idx"])]["Name"].astype(str))
        show.append({"#":rank+1,"Fighters":names,"Salary":int(r["Salary"]),"Left":int(r["Salary Left"]),
        "Mean":round(float(r["Mean"]),1),"P95":round(float(r["P95"]),1),"P99":round(float(r["P99"]),1),
        "Optimal %":round(float(r["Optimal %"]),2),"Win %":round(float(r["Win %"]),3),"Top 1% %":round(float(r["Top 1% %"]),2),
        "Cash %":round(float(r["Cash %"]),1),"Own Sum %":round(float(r["Own Sum %"]),1),"Low-Owned":int(r["Low-Owned"]),
        "Underdogs":int(r["Underdogs"]),"NUKE Score":round(float(r["NUKE Score"]),3)})
    st.dataframe(pd.DataFrame(show),hide_index=True,use_container_width=True,height=520)
    st.download_button("⬇️ DOWNLOAD DK LINEUP CSV",lineup_csv(port,cands,rf),file_name="NUKE_MMA_DK_LINEUPS.csv",mime="text/csv",type="primary",use_container_width=True)
    st.subheader("📊 Fighter Exposure")
    rows=[]
    for _,f in rf.iterrows():
        pid=int(f["ID"]); used=0
        for _,r in port.iterrows():
            if pid in [int(rf.iloc[i]["ID"]) for i in cands[int(r["_candidate"])]["idx"]]: used+=1
        if used: rows.append({"Fighter":f["Name"],"Exposure %":round(used/max(1,len(port))*100,1),"pOwn%":float(f["pOwn%"]),"Win %":float(f["Win %"]),"Finish %":float(f["Finish %"])})
    if rows: st.dataframe(pd.DataFrame(rows).sort_values("Exposure %",ascending=False),hide_index=True,use_container_width=True)
    st.caption("Simulation and ownership outputs are estimates and do not guarantee contest results.")

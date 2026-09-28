import streamlit as st
import pandas as pd
import numpy as np
import io
import re
import requests
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from nuke_nav import render_nav

st.set_page_config(page_title="NUKE PGA Sim", page_icon="⛳", layout="wide")
render_nav()

CAP=50000
ROSTER=6
DEFAULT=Path(__file__).resolve().parents[1]/"data"/"pga_current.csv"

def load_csv(src):
    d=pd.read_csv(src)
    req={"Name","ID","Salary","AvgPointsPerGame"}
    if not req.issubset(d.columns):
        raise ValueError("This does not look like a DraftKings PGA salary CSV.")
    d=d.copy()
    d["ID"]=pd.to_numeric(d["ID"],errors="coerce").astype("Int64")
    d["Salary"]=pd.to_numeric(d["Salary"],errors="coerce").fillna(0).astype(int)
    d["AvgPointsPerGame"]=pd.to_numeric(d["AvgPointsPerGame"],errors="coerce").fillna(0.0)
    d["Status"]=d.get("Status","").fillna("").astype(str).str.upper()
    d=d[~d["Status"].isin(["OUT","O","IR"])].dropna(subset=["ID"])
    d=d.drop_duplicates("ID").reset_index(drop=True)
    return d

def base_projection(d):
    f=d["AvgPointsPerGame"].to_numpy(float)
    sal=d["Salary"].to_numpy(float)
    fallback=np.interp(sal,[sal.min(),sal.max()],[42,78])
    return np.where(f>0,f,fallback)

def ownership_estimate(d):
    sal=d["Salary"].to_numpy(float)
    form=base_projection(d)
    z=.58*(sal-sal.mean())/(sal.std()+1e-9)+.42*(form-form.mean())/(form.std()+1e-9)
    raw=np.exp(np.clip(z,-2.5,2.5))
    # six roster spots across the field -> ownership sums to ~600%
    return raw/raw.sum()*600


def _norm_name(x):
    return re.sub(r"[^a-z0-9]","",str(x).lower())

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_pga_context(event_name):
    """Best-effort automatic event/venue/tee-time discovery from ESPN public golf data."""
    out={"event_id":None,"event_name":event_name,"course":"","location":"","lat":None,"lon":None,"tee_times":{},"status":"Tee times not released"}
    try:
        sb=requests.get("https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard",timeout=8).json()
        choices=[]
        for ev in sb.get("events",[]):
            choices.append((ev.get("id"),ev.get("name",""),ev))
        for cal in (sb.get("leagues") or [{}])[0].get("calendar",[]):
            choices.append((cal.get("id"),cal.get("label",""),cal))
        if not choices: return out
        wanted=_norm_name(event_name)
        def sim(x):
            n=_norm_name(x[1])
            return SequenceMatcher(None,wanted,n).ratio() + (0.5 if (wanted in n or n in wanted) else 0)
        eid,ename,raw=max(choices,key=sim)
        if sim((eid,ename,raw))<0.35: return out
        out["event_id"]=str(eid); out["event_name"]=ename or event_name
        # Event detail usually carries venue/address even before play begins.
        try:
            core=requests.get(f"https://sports.core.api.espn.com/v2/sports/golf/leagues/pga/events/{eid}",timeout=8).json()
            comp=(core.get("competitions") or [{}])[0]
            venue=comp.get("venue") or core.get("venue") or {}
            out["course"]=venue.get("fullName") or venue.get("name") or ""
            addr=venue.get("address") or {}
            city=addr.get("city",""); state=addr.get("state",""); country=addr.get("country","")
            out["location"]=", ".join(x for x in [city,state,country] if x)
            geo=venue.get("geo") or venue.get("location") or {}
            out["lat"]=geo.get("latitude"); out["lon"]=geo.get("longitude")
        except Exception: pass
        # Site summary/leaderboard can expose teeTime alongside athlete records once pairings are published.
        payloads=[]
        for url in [
            f"https://site.api.espn.com/apis/site/v2/sports/golf/pga/summary?event={eid}",
            f"https://site.api.espn.com/apis/site/v2/sports/golf/pga/leaderboard?tournamentId={eid}"
        ]:
            try: payloads.append(requests.get(url,timeout=8).json())
            except Exception: pass
        def walk(obj):
            if isinstance(obj,dict):
                athlete=obj.get("athlete") if isinstance(obj.get("athlete"),dict) else obj
                name=athlete.get("displayName") or athlete.get("fullName") or obj.get("displayName")
                tt=obj.get("teeTime") or obj.get("startTime") or obj.get("date")
                period=obj.get("period") or obj.get("round") or 1
                if name and tt and "T" in str(tt):
                    key=_norm_name(name)
                    rec=out["tee_times"].setdefault(key,{})
                    try: rec[int(period)]=str(tt)
                    except Exception: rec.setdefault(1,str(tt))
                for v in obj.values(): walk(v)
            elif isinstance(obj,list):
                for v in obj: walk(v)
        for p in payloads: walk(p)
        if out["tee_times"]: out["status"]="Tee times loaded automatically"
    except Exception:
        pass
    return out

@st.cache_data(ttl=1800, show_spinner=False)
def geocode_location(location):
    if not location: return None,None
    try:
        j=requests.get("https://geocoding-api.open-meteo.com/v1/search",params={"name":location,"count":1,"language":"en","format":"json"},timeout=8).json()
        x=(j.get("results") or [None])[0]
        return (x.get("latitude"),x.get("longitude")) if x else (None,None)
    except Exception: return None,None

@st.cache_data(ttl=900, show_spinner=False)
def fetch_hourly_weather(lat,lon):
    if lat is None or lon is None: return pd.DataFrame()
    try:
        j=requests.get("https://api.open-meteo.com/v1/forecast",params={
            "latitude":lat,"longitude":lon,"timezone":"auto","forecast_days":10,
            "temperature_unit":"fahrenheit","wind_speed_unit":"mph","precipitation_unit":"inch",
            "hourly":"temperature_2m,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m"
        },timeout=10).json()
        h=j.get("hourly",{})
        df=pd.DataFrame(h)
        if len(df): df["time"]=pd.to_datetime(df["time"])
        return df
    except Exception: return pd.DataFrame()

def weather_severity(row):
    wind=float(row.get("wind_speed_10m",0) or 0); gust=float(row.get("wind_gusts_10m",0) or 0)
    rain=float(row.get("precipitation_probability",0) or 0); amt=float(row.get("precipitation",0) or 0)
    temp=float(row.get("temperature_2m",70) or 70)
    return wind*.55 + max(0,gust-15)*.35 + rain*.035 + amt*18 + max(0,45-temp)*.08 + max(0,temp-95)*.06

def weather_dot(sev):
    if sev < 8: return "🟢"
    if sev < 13: return "🟡"
    if sev < 18: return "🟠"
    return "🔴"

def attach_tee_weather(d,ctx,weather):
    x=d.copy()
    x["R1 Tee"]="—"; x["R2 Tee"]="—"; x["Wave"]="TBD"; x["Weather"]="⚪ TBD"; x["Weather Edge"]=0.0
    for i,row in x.iterrows():
        rec=ctx.get("tee_times",{}).get(_norm_name(row["Name"]),{})
        parsed=[]
        for rnd in [1,2]:
            raw=rec.get(rnd)
            if not raw: continue
            try:
                dt=pd.to_datetime(raw)
                if getattr(dt,"tzinfo",None) is not None: dt=dt.tz_convert(None)
                x.at[i,f"R{rnd} Tee"]=dt.strftime("%-I:%M %p") if hasattr(dt,"strftime") else str(raw)
                parsed.append((rnd,dt))
            except Exception: pass
        if parsed:
            hr=parsed[0][1].hour
            x.at[i,"Wave"]="AM" if hr<12 else "PM"
            sevs=[]
            for _,dt in parsed:
                if not weather.empty:
                    mask=(weather["time"]>=dt.floor("h")) & (weather["time"]<=dt+pd.Timedelta(hours=5))
                    if mask.any(): sevs.extend([weather_severity(r) for _,r in weather.loc[mask].iterrows()])
            if sevs:
                sev=float(np.mean(sevs))
                x.at[i,"Weather"]=f"{weather_dot(sev)} {sev:.1f}"
                # Positive edge = easier than field average; populated relative to all players below.
                x.at[i,"Weather Edge"]=-sev
    vals=x.loc[x["Weather Edge"]!=0,"Weather Edge"]
    if len(vals):
        baseline=float(vals.mean())
        x.loc[x["Weather Edge"]!=0,"Weather Edge"]=(x.loc[x["Weather Edge"]!=0,"Weather Edge"]-baseline)*0.22
    return x

def generate_candidates(d,n,min_salary,seed,locked_ids,excluded_ids):
    rng=np.random.default_rng(seed)
    ids=d["ID"].astype(int).to_numpy()
    salaries=d["Salary"].to_numpy(int)
    proj=base_projection(d)
    own=ownership_estimate(d)
    active=np.array([i not in excluded_ids for i in ids])
    locked_idx=np.where(np.isin(ids,list(locked_ids)) & active)[0]
    if len(locked_idx)>ROSTER:
        return []
    avail=np.where(active & ~np.isin(ids,list(locked_ids)))[0]
    # quality-weighted but stochastic candidate creation
    value=proj/np.maximum(salaries,1)*1000
    z=(value-value.mean())/(value.std()+1e-9)
    w=np.exp(np.clip(.45*z,-2,2)); w=w[avail]; w=w/w.sum()
    seen=set(); out=[]
    attempts=0; max_attempts=max(20000,n*80)
    while len(out)<n and attempts<max_attempts:
        attempts+=1
        need=ROSTER-len(locked_idx)
        if need<0 or len(avail)<need: break
        pick=rng.choice(avail,size=need,replace=False,p=w)
        idx=np.concatenate([locked_idx,pick])
        salary=int(salaries[idx].sum())
        if salary<min_salary or salary>CAP: continue
        key=tuple(sorted(ids[idx].tolist()))
        if key in seen: continue
        seen.add(key)
        out.append({"idx":idx,"salary":salary,"own_product":float(np.prod(np.clip(own[idx]/100,.002,.99)))})
    return out

def simulate_golfers(d,n_sims,seed):
    rng=np.random.default_rng(seed+991)
    mu=base_projection(d)
    # Tee-time weather edge is deliberately modest and uncertain rather than treated as certain points.
    edge=pd.to_numeric(d.get("Weather Edge",pd.Series(np.zeros(len(d)))),errors="coerce").fillna(0).to_numpy(float)
    mu=mu+edge
    salary=d["Salary"].to_numpy(float)
    # salary/form-informed cut probability; missed cuts score much lower
    strength=.55*(mu-mu.mean())/(mu.std()+1e-9)+.45*(salary-salary.mean())/(salary.std()+1e-9)
    make_cut=1/(1+np.exp(-(.25+strength)))
    cut=rng.random((n_sims,len(d)))<make_cut
    made=rng.normal(mu,14+np.maximum(0,7600-salary)/800,size=(n_sims,len(d)))
    missed=rng.normal(np.maximum(8,mu*.43),9,size=(n_sims,len(d)))
    # shared tournament environment + player volatility
    event=rng.normal(0,4,size=(n_sims,1))
    scores=np.where(cut,made,missed)+event
    return np.clip(scores,-10,None),make_cut

def evaluate(cands,sims,own):
    if not cands: return pd.DataFrame()
    rows=[]
    for j,c in enumerate(cands):
        s=sims[:,c["idx"]].sum(axis=1)
        rows.append({
            "_candidate":j,
            "Salary":c["salary"],
            "Mean":round(float(s.mean()),2),
            "Ceiling":round(float(np.quantile(s,.90)),2),
            "P95":round(float(np.quantile(s,.95)),2),
            "Top 1%":round(float(np.quantile(s,.99)),2),
            "Ownership Sum":round(float(own[c["idx"]].sum()),1),
            "Duplication Proxy":float(c["own_product"]),
        })
    r=pd.DataFrame(rows)
    for col in ["Mean","P95","Top 1%"]:
        r["_z_"+col]=(r[col]-r[col].mean())/(r[col].std()+1e-9)
    lev=-(np.log(np.maximum(r["Duplication Proxy"],1e-12)))
    lev=(lev-lev.mean())/(lev.std()+1e-9)
    r["NUKE Score"]=1.0*r["_z_Mean"]+1.25*r["_z_P95"]+.9*r["_z_Top 1%"]+.25*lev
    return r.sort_values("NUKE Score",ascending=False).reset_index(drop=True)

def simulate_contest_metrics(results,cands,sims,cut_prob,field_size,entry_fee,first_prize,seed):
    """Approximate large-field contest outcomes against ownership-weighted field lineups."""
    if results.empty:
        return results
    rng=np.random.default_rng(seed+4242)
    n_sims=sims.shape[0]
    # Evaluate a practical field sample, then use percentile thresholds to represent the full contest.
    sample_n=int(min(max(250,field_size),5000))
    candidate_scores=np.empty((len(cands),n_sims),dtype=np.float32)
    six6=np.empty(len(cands),dtype=float)
    five6=np.empty(len(cands),dtype=float)
    for j,c in enumerate(cands):
        candidate_scores[j]=sims[:,c["idx"]].sum(axis=1)
        probs=cut_prob[c["idx"]]
        six6[j]=float(np.prod(probs))
        five6[j]=float(sum(np.prod(np.delete(probs,k))*(1-probs[k]) for k in range(6)))
    dup=np.array([max(c["own_product"],1e-12) for c in cands],dtype=float)
    quality=np.array([max(float(x),1e-9) for x in results.set_index("_candidate").reindex(range(len(cands)))["NUKE Score"].fillna(-5)+8])
    field_w=np.power(dup,.32)*np.exp(np.clip(quality-quality.mean(),-3,3)*.12)
    field_w=field_w/field_w.sum()
    field_idx=rng.choice(len(cands),size=sample_n,replace=True,p=field_w)
    field_scores=candidate_scores[field_idx]
    # Per-universe field thresholds.
    win_thr=np.max(field_scores,axis=0)
    top1_thr=np.quantile(field_scores,.99,axis=0)
    cash_thr=np.quantile(field_scores,.80,axis=0)
    out=results.copy()
    wins=[]; top1=[]; cash=[]; roi=[]; s6=[]; s5=[]; dup_est=[]
    for _,row in out.iterrows():
        j=int(row["_candidate"]); sc=candidate_scores[j]
        w=float(np.mean(sc>=win_thr)); t=float(np.mean(sc>=top1_thr)); ca=float(np.mean(sc>=cash_thr))
        # Transparent payout approximation when no full payout table is supplied.
        top1_pay=max(entry_fee*4.0, first_prize/max(1,field_size*.01))
        cash_pay=max(entry_fee*1.8, entry_fee)
        expected=w*first_prize + max(0,t-w)*top1_pay + max(0,ca-t)*cash_pay
        wins.append(w*100); top1.append(t*100); cash.append(ca*100)
        roi.append(((expected-entry_fee)/entry_fee*100) if entry_fee>0 else np.nan)
        s6.append(six6[j]*100); s5.append((six6[j]+five6[j])*100)
        dup_est.append(max(1.0,float(field_size)*dup[j]))
    out["Win %"]=np.round(wins,3)
    out["Top 1% %"]=np.round(top1,2)
    out["Cash %"]=np.round(cash,1)
    out["Est. ROI %"]=np.round(roi,1)
    out["6/6 %"]=np.round(s6,1)
    out["5+/6 %"]=np.round(s5,1)
    out["Est. Duplicates"]=np.round(dup_est,1)
    # Contest score emphasizes actual simulated tournament success.
    for col in ["Win %","Top 1% %","6/6 %"]:
        z=(out[col]-out[col].mean())/(out[col].std()+1e-9)
        out["NUKE Score"]=out["NUKE Score"] + (1.0 if col=="Win %" else .45)*z
    return out.sort_values("NUKE Score",ascending=False).reset_index(drop=True)

def lineup_names(c,d):
    return [str(d.iloc[i]["Name"]) for i in c["idx"]]

def export_csv(portfolio,cands,d):
    rows=[]
    for rank,row in portfolio.reset_index(drop=True).iterrows():
        c=cands[int(row["_candidate"])]
        ps=d.iloc[c["idx"]].sort_values("Salary",ascending=False)
        vals=[f'{r["Name"]} ({int(r["ID"])})' for _,r in ps.iterrows()]
        rows.append({**{f"G{i+1}":vals[i] for i in range(6)},
                     "Salary":int(row["Salary"]),
                     "Mean":row["Mean"],
                     "P95":row["P95"],
                     "Top 1%":row["Top 1%"],
                     "6/6 %":row["6/6 %"],
                     "5+/6 %":row["5+/6 %"],
                     "Win %":row["Win %"],
                     "Top 1% %":row["Top 1% %"],
                     "Cash %":row["Cash %"],
                     "Est. ROI %":row["Est. ROI %"],
                     "Est. Duplicates":row["Est. Duplicates"],
                     "Own Sum %":row["Ownership Sum"],
                     "NUKE Score":round(float(row["NUKE Score"]),3)})
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")

st.title("⛳ NUKE PGA")
st.caption("DraftKings PGA tournament simulation · 6 golfers · $50,000 salary cap")

up=st.file_uploader("Optional: upload a different DraftKings PGA salary CSV",type=["csv"])
try:
    if up is not None:
        golfers=load_csv(up); source="Uploaded slate"
    elif DEFAULT.exists():
        golfers=load_csv(DEFAULT); source="Loaded automatically"
    else:
        st.info("Upload this week's DraftKings PGA salary CSV to begin.")
        st.stop()
except Exception as e:
    st.error(str(e)); st.stop()

event=str(golfers["Game Info"].iloc[0]) if "Game Info" in golfers.columns and len(golfers) else "PGA"
st.success(f"{source}: {event} · {len(golfers)} active golfers")

ctx=fetch_pga_context(event)
lat,lon=ctx.get("lat"),ctx.get("lon")
if lat is None or lon is None:
    lat,lon=geocode_location(ctx.get("location",""))
weather=fetch_hourly_weather(lat,lon)
golfers=attach_tee_weather(golfers,ctx,weather)

course_label=ctx.get("course") or ctx.get("location") or "Course locating automatically"
tee_ready=bool(ctx.get("tee_times"))
wcols=st.columns([2,2,2])
wcols[0].info(f"📍 {course_label}" + (f" · {ctx.get('location')}" if ctx.get("location") else ""))
wcols[1].info(("✅ " if tee_ready else "⏳ ") + ctx.get("status","Tee times not released"))
if tee_ready and (golfers["Weather Edge"]!=0).any():
    am=golfers.loc[golfers["Wave"]=="AM","Weather Edge"].mean(); pm=golfers.loc[golfers["Wave"]=="PM","Weather Edge"].mean()
    leader="AM" if am>pm else "PM"; gap=abs(float(am-pm))
    dot="🟢" if gap<.5 else ("🟡" if gap<1.25 else ("🟠" if gap<2.25 else "🔴"))
    wcols[2].info(f"{dot} Wave edge: {leader} +{gap:.2f} sim pts")
else:
    wcols[2].info("⚪ Weather/wave edge activates when tee times are published")

m1,m2,m3,m4=st.columns(4)
m1.metric("Golfers",len(golfers)); m2.metric("Roster","6 G"); m3.metric("Salary Cap","$50,000"); m4.metric("Event",event)

st.subheader("🏌️ Golfer Pool")
st.caption("Include/exclude golfers, lock golfers into every candidate lineup, and optionally boost or limit portfolio exposure.")
editor=golfers[["ID","Name","Salary","AvgPointsPerGame","R1 Tee","R2 Tee","Wave","Weather","Weather Edge"]].copy()
# Show the same projected ownership model used by the PGA contest SIM directly in the player pool.
editor["pOwn%"] = np.round(ownership_estimate(golfers), 1)
editor.insert(0,"In",True); editor.insert(1,"Lock",False); editor["Boost %"]=0; editor["Min %"]=0; editor["Max %"]=100

# Fast bulk controls for the PGA player pool.
bulk1, bulk2, bulk_spacer = st.columns([1,1,6])
with bulk1:
    if st.button("✅ ADD ALL", use_container_width=True, key="pga_add_all"):
        st.session_state["pga_pool_bulk_in"] = True
        st.session_state.pop("pga_pool_editor", None)
        st.rerun()
with bulk2:
    if st.button("🚫 REMOVE ALL", use_container_width=True, key="pga_remove_all"):
        st.session_state["pga_pool_bulk_in"] = False
        st.session_state.pop("pga_pool_editor", None)
        st.rerun()

if "pga_pool_bulk_in" in st.session_state:
    editor["In"] = bool(st.session_state.pop("pga_pool_bulk_in"))

edited=st.data_editor(editor,hide_index=True,use_container_width=True,height=430,
    disabled=["ID","Name","Salary","AvgPointsPerGame","pOwn%","R1 Tee","R2 Tee","Wave","Weather","Weather Edge"],
    column_config={
      "In":st.column_config.CheckboxColumn("In"),
      "Lock":st.column_config.CheckboxColumn("🔒 Lock"),
      "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
      "AvgPointsPerGame":st.column_config.NumberColumn("DK FPPG",format="%.1f"),
      "pOwn%":st.column_config.NumberColumn("pOwn%",format="%.1f%%"),
      "Weather Edge":st.column_config.NumberColumn("Wx Edge",format="%+.2f"),
      "Boost %":st.column_config.NumberColumn("Boost %",min_value=-50,max_value=100,step=5),
      "Min %":st.column_config.NumberColumn("Min %",min_value=0,max_value=100,step=5),
      "Max %":st.column_config.NumberColumn("Max %",min_value=0,max_value=100,step=5),
    },key="pga_pool_editor")

with st.sidebar:
    st.markdown("## ⛳ PGA SIM")
    candidates_n=st.number_input("Candidate lineups",500,20000,5000,500, key="pga_candidates")
    universes=st.number_input("Tournament universes",250,10000,3000,250,key="pga_universes")
    portfolio_n=st.number_input("Portfolio lineups",1,150,20,1,key="pga_portfolio")
    min_salary=st.number_input("Minimum salary",30000,50000,49600,100,key="pga_min_salary")
    max_player=st.slider("Max golfer exposure",1,100,60,key="pga_max_exp")
    max_pair=st.slider("Max pair exposure",10,100,30,5,key="pga_max_pair",
                       help="Maximum share of portfolio lineups that may contain the same 2-golfer combination.")
    max_triple=st.slider("Max 3-golfer combo exposure",5,100,20,5,key="pga_max_triple",
                         help="Maximum share of portfolio lineups that may contain the same 3-golfer combination.")
    st.markdown("### 🌦️ Wave Construction")
    st.caption("Set the exact mix of Thursday AM/PM golfer counts. Must total 100%. Ignored until tee times load.")
    wave_mix={}
    wc1,wc2=st.columns(2)
    with wc1:
        wave_mix[6]=st.number_input("6 AM / 0 PM %",0,100,0,5,key="wave60")
        wave_mix[5]=st.number_input("5 AM / 1 PM %",0,100,20,5,key="wave51")
        wave_mix[4]=st.number_input("4 AM / 2 PM %",0,100,40,5,key="wave42")
        wave_mix[3]=st.number_input("3 AM / 3 PM %",0,100,20,5,key="wave33")
    with wc2:
        wave_mix[2]=st.number_input("2 AM / 4 PM %",0,100,20,5,key="wave24")
        wave_mix[1]=st.number_input("1 AM / 5 PM %",0,100,0,5,key="wave15")
        wave_mix[0]=st.number_input("0 AM / 6 PM %",0,100,0,5,key="wave06")
    wave_total=sum(wave_mix.values())
    if wave_total==100: st.success("Wave mix: 100%")
    else: st.warning(f"Wave mix totals {wave_total}% — set to 100% before running once tee times are live.")
    field_size=st.number_input("Contest field size",2,1000000,2378,1,key="pga_field")
    entry_fee=st.number_input("Entry fee ($)",0.0,10000.0,3.0,1.0,key="pga_fee")
    first_prize=st.number_input("1st prize ($)",0.0,10000000.0,600.0,100.0,key="pga_first")

if st.button("☢️ RUN PGA CONTEST SIM",type="primary",use_container_width=True):
    included=set(edited.loc[edited["In"],"ID"].astype(int))
    excluded=set(edited.loc[~edited["In"],"ID"].astype(int))
    locked=set(edited.loc[edited["Lock"] & edited["In"],"ID"].astype(int))
    if len(locked)>6:
        st.error("You can lock at most 6 golfers."); st.stop()
    seed=int(np.random.default_rng().integers(1,2_000_000_000))
    with st.spinner("Generating PGA lineups and simulating tournament outcomes..."):
        cands=generate_candidates(golfers,int(candidates_n),int(min_salary),seed,locked,excluded)
        if not cands:
            st.error("No legal 6-golfer lineups were generated. Lower the salary floor or loosen the pool."); st.stop()
        sims,cut_prob=simulate_golfers(golfers,int(universes),seed)
        own=ownership_estimate(golfers)
        results=evaluate(cands,sims,own)
        results=simulate_contest_metrics(results,cands,sims,cut_prob,int(field_size),float(entry_fee),float(first_prize),seed)
        # apply user boosts to selection score
        boosts=dict(zip(edited["ID"].astype(int),edited["Boost %"].astype(float)))
        for ri in results.index:
            c=cands[int(results.at[ri,"_candidate"])]
            results.at[ri,"NUKE Score"] += sum(boosts.get(int(golfers.iloc[i]["ID"]),0) for i in c["idx"])/100
        results=results.sort_values("NUKE Score",ascending=False).reset_index(drop=True)
        # greedy diversified portfolio honoring max exposure + per-golfer max/min as best effort
        counts={int(x):0 for x in golfers["ID"]}
        pair_counts={}
        triple_counts={}
        selected=[]
        target=int(portfolio_n)
        personal_max=dict(zip(edited["ID"].astype(int),edited["Max %"].astype(float)))
        pair_cap=max(1,int(np.floor(target*float(max_pair)/100+1e-9)))
        triple_cap=max(1,int(np.floor(target*float(max_triple)/100+1e-9)))
        waves=golfers["Wave"].astype(str).to_numpy()
        wave_active=tee_ready and set(waves).intersection({"AM","PM"})=={"AM","PM"} and wave_total==100
        wave_targets={}
        if wave_active:
            raw_targets={k:target*float(v)/100 for k,v in wave_mix.items()}
            wave_targets={k:int(np.floor(v)) for k,v in raw_targets.items()}
            remain=target-sum(wave_targets.values())
            for k in sorted(raw_targets,key=lambda z:raw_targets[z]-wave_targets[z],reverse=True)[:remain]:
                wave_targets[k]+=1
        wave_used={k:0 for k in range(7)}
        for _,r in results.iterrows():
            c=cands[int(r["_candidate"])]
            ids=sorted(int(golfers.iloc[i]["ID"]) for i in c["idx"])
            pairs=[(ids[a],ids[b]) for a in range(6) for b in range(a+1,6)]
            triples=[(ids[a],ids[b],ids[c3]) for a in range(6) for b in range(a+1,6) for c3 in range(b+1,6)]
            ok=True
            for pid in ids:
                cap=min(float(max_player),personal_max.get(pid,100.0))
                if counts.get(pid,0)+1 > max(1,int(np.floor(target*cap/100+1e-9))):
                    ok=False; break
            if ok and any(pair_counts.get(combo,0)+1 > pair_cap for combo in pairs):
                ok=False
            if ok and any(triple_counts.get(combo,0)+1 > triple_cap for combo in triples):
                ok=False
            am_count=sum(1 for idx in c["idx"] if waves[idx]=="AM")
            if ok and wave_active and wave_used.get(am_count,0)>=wave_targets.get(am_count,0):
                ok=False
            if ok:
                selected.append(r)
                if wave_active: wave_used[am_count]=wave_used.get(am_count,0)+1
                for pid in ids: counts[pid]=counts.get(pid,0)+1
                for combo in pairs: pair_counts[combo]=pair_counts.get(combo,0)+1
                for combo in triples: triple_counts[combo]=triple_counts.get(combo,0)+1
            if len(selected)>=target: break
        portfolio=pd.DataFrame(selected)
        st.session_state["pga_results"]=(results,cands,portfolio,golfers,own,cut_prob,seed)

if "pga_results" in st.session_state:
    results,cands,portfolio,golfers,own,cut_prob,seed=st.session_state["pga_results"]
    st.divider(); st.header("🏆 PGA Contest Sim Results")
    a,b,c,d=st.columns(4)
    a.metric("Candidates",len(results)); b.metric("Portfolio",len(portfolio)); c.metric("Universes",f"{universes:,}"); d.metric("Seed",seed)
    st.subheader("NUKE PGA Portfolio")
    show=[]
    for rank,r in portfolio.reset_index(drop=True).iterrows():
        cand=cands[int(r["_candidate"])]
        show.append({"#":rank+1,"Golfers":" · ".join(lineup_names(cand,golfers)),"Salary":int(r["Salary"]),
                     "Mean":r["Mean"],"P95":r["P95"],"Top 1%":r["Top 1%"],"6/6 %":r["6/6 %"],"5+/6 %":r["5+/6 %"],
                     "Win %":r["Win %"],"Top 1% %":r["Top 1% %"],"Cash %":r["Cash %"],"Est. ROI %":r["Est. ROI %"],
                     "Est. Duplicates":r["Est. Duplicates"],"Own Sum %":r["Ownership Sum"],"NUKE Score":round(float(r["NUKE Score"]),3)})
    st.dataframe(pd.DataFrame(show),hide_index=True,use_container_width=True,height=430)
    if tee_ready and len(portfolio):
        wave_rows=[]
        for am_n in range(6,-1,-1):
            ct=0
            for _,rr in portfolio.iterrows():
                cc=cands[int(rr["_candidate"])]
                if sum(1 for ix in cc["idx"] if str(golfers.iloc[ix]["Wave"])=="AM")==am_n: ct+=1
            wave_rows.append({"Construction":f"{am_n} AM / {6-am_n} PM","Lineups":ct,"Portfolio %":round(ct/len(portfolio)*100,1)})
        st.markdown("#### 🌦️ Portfolio Wave Construction")
        st.dataframe(pd.DataFrame(wave_rows),hide_index=True,use_container_width=True)
    st.download_button("DOWNLOAD PGA PORTFOLIO + STATS CSV",export_csv(portfolio,cands,golfers),
                       file_name="nuke_pga_portfolio.csv",mime="text/csv",type="primary",use_container_width=True)

    st.subheader("Golfer Exposure")
    exp=[]
    denom=max(1,len(portfolio))
    for i,row in golfers.iterrows():
        pid=int(row["ID"]); ct=0
        for _,r in portfolio.iterrows():
            if i in cands[int(r["_candidate"])]["idx"]: ct+=1
        if ct:
            exp.append({"Golfer":row["Name"],"Salary":int(row["Salary"]),"Lineups":ct,
                        "Exposure %":round(100*ct/denom,1),"Est. Own %":round(float(own[i]),1),
                        "Make Cut %":round(float(cut_prob[i])*100,1)})
    st.dataframe(pd.DataFrame(exp).sort_values(["Exposure %","Salary"],ascending=[False,False]),hide_index=True,use_container_width=True)

    with st.expander("Top simulated candidate lineups"):
        top=[]
        for rank,r in results.head(100).iterrows():
            cand=cands[int(r["_candidate"])]
            top.append({"Rank":rank+1,"Golfers":" · ".join(lineup_names(cand,golfers)),"Salary":int(r["Salary"]),
                        "Mean":r["Mean"],"P95":r["P95"],"Top 1%":r["Top 1%"],"6/6 %":r["6/6 %"],"Win %":r["Win %"],"Top 1% %":r["Top 1% %"],"Cash %":r["Cash %"],"Est. ROI %":r["Est. ROI %"],"Est. Duplicates":r["Est. Duplicates"],"NUKE Score":round(float(r["NUKE Score"]),3)})
        st.dataframe(pd.DataFrame(top),hide_index=True,use_container_width=True)

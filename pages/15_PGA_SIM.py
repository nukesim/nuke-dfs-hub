import streamlit as st
import pandas as pd
import numpy as np
import io
import re
import html
import requests
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from nuke_nav import render_nav
from nuke_pga_portfolio import (PortfolioError, automatic_exposure_caps,
    generate_pga_candidates, select_pga_portfolio, wave_lineup_bounds,
    salary_build_type, build_type_summary)

st.set_page_config(page_title="NUKE PGA Sim", page_icon="⛳", layout="wide")
render_nav()

PGA_PORTFOLIO_VERSION=6
if st.session_state.get("pga_results_version") != PGA_PORTFOLIO_VERSION:
    st.session_state.pop("pga_results",None)
    st.session_state.pop("pga_run_settings",None)

CAP=50000
ROSTER=6
DEFAULT=Path(__file__).resolve().parents[1]/"data"/"pga_current.csv"

def load_csv(src):
    d=pd.read_csv(src)
    req={"Name","ID","Salary"}
    if not req.issubset(d.columns):
        raise ValueError("This does not look like a DraftKings PGA salary CSV.")
    d=d.copy()
    d["ID"]=pd.to_numeric(d["ID"],errors="coerce").astype("Int64")
    d["Salary"]=pd.to_numeric(d["Salary"],errors="coerce").fillna(0).astype(int)
    d["Status"]=d.get("Status",pd.Series("",index=d.index)).fillna("").astype(str).str.upper()
    d=d[~d["Status"].isin(["OUT","O","IR"])].dropna(subset=["ID"])
    d=d.drop_duplicates("ID").reset_index(drop=True)
    return d

def salary_baseline(d):
    sal=d["Salary"].to_numpy(float)
    if not len(sal):
        return np.array([],dtype=float)
    lo=float(sal.min()); hi=float(sal.max())
    if np.isclose(lo,hi):
        return np.full(len(sal),60.0,dtype=float)
    return np.interp(sal,[lo,hi],[42,78])

def ownership_estimate(d):
    sal=d["Salary"].to_numpy(float)
    z=(sal-sal.mean())/(sal.std()+1e-9)
    raw=np.exp(np.clip(z,-2.5,2.5))
    # six roster spots across the field -> ownership sums to ~600%
    return raw/raw.sum()*600


def _norm_name(x):
    return re.sub(r"[^a-z0-9]","",str(x).lower())

def _bank_utah_2026_pairings():
    """Published Golf Channel R1/R2 tee sheet, stored as a current-event fallback."""
    rounds={
        1:[
            ("9:35 AM","Peter Malnati|Doug Ghim|Vince Whaley"),("9:35 AM","Patton Kizzire|Dylan Wu|Johnny Keefer"),
            ("9:46 AM","Rafael Campos|Denny McCarthy|Patrick Rodgers"),("9:46 AM","Tom Hoge|Mac Meissner|Sudarshan Yellamaraju"),
            ("9:57 AM","Mark Hubbard|David Lipsky|David Skinns"),("9:57 AM","Max Greyserman|Rasmus Højgaard|Jackson Suber"),
            ("10:08 AM","Garrick Higgo|Kevin Yu|Aaron Wise"),("10:08 AM","Michael Brennan|Jackson Koivun|Benjamin James"),
            ("10:19 AM","Davis Thompson|Davis Riley|Stephan Jaeger"),("10:19 AM","Matthew McCarty|Harry Hall|Neal Shipley"),
            ("10:30 AM","Steven Fisk|William Mouw|Joe Highsmith"),("10:30 AM","Zac Blair|Max McGreevy|Will Gordon"),
            ("10:41 AM","Matt Wallace|Seamus Power|Rico Hoey"),("10:41 AM","Joel Dahmen|Andrew Putnam|Chandler Phillips"),
            ("10:52 AM","Michael Thompson|Haotong Li|Jeffrey Kang"),("10:52 AM","Patrick Fishburn|Trace Crowe|Kensei Hirata"),
            ("11:03 AM","Adrien Dumont de Chassart|Paul Peterson|Matt Snyder"),("11:03 AM","Jimmy Stanger|David Ford|Kihei Akina"),
            ("11:14 AM","Pontus Nyholm|John VanDerLaan|Seonghyeon An"),("11:14 AM","Alejandro Tosti|Jesper Svensson|Bowen Mauss"),
            ("2:30 PM","Austin Eckroat|Taylor Moore|Hank Lebioda"),("2:30 PM","Mackenzie Hughes|Brendon Todd|Jordan Smith"),
            ("2:41 PM","Ben Martin|Kevin Roy|Danny Walker"),("2:41 PM","Matthieu Pavon|Tyler Duncan|Ben Silverman"),
            ("2:52 PM","Erik van Rooyen|Christiaan Bezuidenhout|Zach Bauchou"),("2:52 PM","C.T. Pan|Rasmus Neergaard-Petersen|John Parry"),
            ("3:03 PM","Nick Taylor|Maverick McNealy|Max Homa"),("3:03 PM","Cam Davis|Billy Horschel|Chris Kirk"),
            ("3:14 PM","Aldrich Potgieter|Tony Finau|Eric Cole"),("3:14 PM","Adam Schenk|Lucas Glover|Kevin Streelman"),
            ("3:25 PM","Emiliano Grillo|Pierceson Coody|Takumi Kanaya"),("3:25 PM","Nick Dunlap|Lee Hodges|Ben Kohles"),
            ("3:36 PM","Chad Ramey|Beau Hossler|Justin Lower"),("3:36 PM","Brice Garnett|Adam Svensson|Austin Smotherman"),
            ("3:47 PM","Kristoffer Ventura|A.J. Ewart|Rhett Rasmussen"),("3:47 PM","David Lingmerth|Marco Penge|Isaiah Salinda"),
            ("3:58 PM","Luke Clanton|Davis Chatfield|Tyson Shelley"),("3:58 PM","Hayden Springer|Marcelo Rozo|Boston Bracken"),
            ("4:09 PM","Chandler Blanchet|Christo Lamprecht|Carson Lundell"),("4:09 PM","Zecheng Dou|Gordon Sargent|Zach Johnson"),
        ],
        2:[
            ("9:35 AM","Mackenzie Hughes|Brendon Todd|Jordan Smith"),("9:35 AM","Austin Eckroat|Taylor Moore|Hank Lebioda"),
            ("9:46 AM","Matthieu Pavon|Tyler Duncan|Ben Silverman"),("9:46 AM","Ben Martin|Kevin Roy|Danny Walker"),
            ("9:57 AM","C.T. Pan|Rasmus Neergaard-Petersen|John Parry"),("9:57 AM","Erik van Rooyen|Christiaan Bezuidenhout|Zach Bauchou"),
            ("10:08 AM","Cam Davis|Billy Horschel|Chris Kirk"),("10:08 AM","Nick Taylor|Maverick McNealy|Max Homa"),
            ("10:19 AM","Adam Schenk|Lucas Glover|Kevin Streelman"),("10:19 AM","Aldrich Potgieter|Tony Finau|Eric Cole"),
            ("10:30 AM","Nick Dunlap|Lee Hodges|Ben Kohles"),("10:30 AM","Emiliano Grillo|Pierceson Coody|Takumi Kanaya"),
            ("10:41 AM","Brice Garnett|Adam Svensson|Austin Smotherman"),("10:41 AM","Chad Ramey|Beau Hossler|Justin Lower"),
            ("10:52 AM","David Lingmerth|Marco Penge|Isaiah Salinda"),("10:52 AM","Kristoffer Ventura|A.J. Ewart|Rhett Rasmussen"),
            ("11:03 AM","Hayden Springer|Marcelo Rozo|Boston Bracken"),("11:03 AM","Luke Clanton|Davis Chatfield|Tyson Shelley"),
            ("11:14 AM","Zecheng Dou|Gordon Sargent|Zach Johnson"),("11:14 AM","Chandler Blanchet|Christo Lamprecht|Carson Lundell"),
            ("2:30 PM","Patton Kizzire|Dylan Wu|Johnny Keefer"),("2:30 PM","Peter Malnati|Doug Ghim|Vince Whaley"),
            ("2:41 PM","Tom Hoge|Mac Meissner|Sudarshan Yellamaraju"),("2:41 PM","Rafael Campos|Denny McCarthy|Patrick Rodgers"),
            ("2:52 PM","Max Greyserman|Rasmus Højgaard|Jackson Suber"),("2:52 PM","Mark Hubbard|David Lipsky|David Skinns"),
            ("3:03 PM","Michael Brennan|Jackson Koivun|Benjamin James"),("3:03 PM","Garrick Higgo|Kevin Yu|Aaron Wise"),
            ("3:14 PM","Matthew McCarty|Harry Hall|Neal Shipley"),("3:14 PM","Davis Thompson|Davis Riley|Stephan Jaeger"),
            ("3:25 PM","Zac Blair|Max McGreevy|Will Gordon"),("3:25 PM","Steven Fisk|William Mouw|Joe Highsmith"),
            ("3:36 PM","Joel Dahmen|Andrew Putnam|Chandler Phillips"),("3:36 PM","Matt Wallace|Seamus Power|Rico Hoey"),
            ("3:47 PM","Patrick Fishburn|Trace Crowe|Kensei Hirata"),("3:47 PM","Michael Thompson|Haotong Li|Jeffrey Kang"),
            ("3:58 PM","Jimmy Stanger|David Ford|Kihei Akina"),("3:58 PM","Adrien Dumont de Chassart|Paul Peterson|Matt Snyder"),
            ("4:09 PM","Alejandro Tosti|Jesper Svensson|Bowen Mauss"),("4:09 PM","Pontus Nyholm|John VanDerLaan|Seonghyeon An"),
        ]
    }
    out={}
    for rnd,groups in rounds.items():
        day="2026-10-01" if rnd==1 else "2026-10-02"
        for tm,names in groups:
            dt=pd.Timestamp(f"{day} {tm}",tz="America/New_York")
            for name in names.split("|"):
                out.setdefault(_norm_name(name),{})[rnd]=dt.isoformat()

    # DraftKings naming variants -> published pairing names.
    aliases={
        "Jordan L. Smith":"Jordan Smith",
        "Kris Ventura":"Kristoffer Ventura",
        "Zachary Bauchou":"Zach Bauchou",
        "Cameron Davis":"Cam Davis",
        "Zach J. Johnson":"Zach Johnson",
    }
    for dk_name,published_name in aliases.items():
        src=out.get(_norm_name(published_name))
        if src: out[_norm_name(dk_name)]=dict(src)
    return out

def _baycurrent_2026_context():
    """PGA TOUR's October 8/9 tee sheet; all timestamps are course-local JST.

    Source: https://pgatourmedia.pgatourhq.com/tours/2026/pgatour/baycurrentclassic
    R1-R2 Tee Times.pdf, published October 6. Names below use DraftKings aliases.
    """
    groups=[
        "Beau Hossler|Pierceson Coody|Ren Yonezawa",
        "Denny McCarthy|Max Greyserman|Keita Nakajima",
        "Michael Thorbjornsen|Matthew McCarty|Stephan Jaeger",
        "Nicolas Echavarria|Maverick McNealy|Alex Smalley",
        "Aldrich Potgieter|Nick Taylor|Taylor Pendrith",
        "Jackson Suber|Takumi Kanaya|Kosuke Sunagawa",
        "Kevin Roy|Johnny Keefer|Yoshinori Fujimoto",
        "Taylor Moore|Ryo Hisatsune|Yusaku Hosono",
        "Steven Fisk|Kurt Kitayama|Max Homa",
        "Wyndham Clark|Justin Thomas|Adam Scott",
        "Keegan Bradley|Hideki Matsuyama|Rickie Fowler",
        "Doug Ghim|Zachary Bauchou|Koshin Nagasaki",
        "Keith Mitchell|Michael Kim|Ben Kohles",
        "Mac Meissner|Kris Ventura|Sang-hee Lee",
        "Michael Brennan|Ricky Castillo|Billy Horschel",
        "Min Woo Lee|Jordan Spieth|Sungjae Im",
        "Jacob Bridgeman|Collin Morikawa|Xander Schauffele",
        "Matt Wallace|John Parry|Jinichiro Kozuma",
        "Christiaan Bezuidenhout|Rasmus Neergaard-Petersen|Hiroshi Iwata",
        "Patrick Rodgers|Chandler Phillips|Aguri Iwasaki",
        "Sahith Theegala|Jordan L. Smith|Tomohiro Ishizaka",
        "Ryan Gerard|Kevin Yu|Tony Finau",
        "Brian Harman|Davis Thompson|Tom Hoge",
        "Lee Hodges|Andrew Putnam|David Lipsky",
    ]
    tee={}
    for i,group in enumerate(groups):
        slot=i%12
        r1=pd.Timestamp("2026-10-08 08:45",tz="Asia/Tokyo")+pd.Timedelta(minutes=11*slot)
        r2=pd.Timestamp("2026-10-09 08:45",tz="Asia/Tokyo")+pd.Timedelta(minutes=11*((slot+6)%12))
        for name in group.split("|"):
            tee[_norm_name(name)]={1:r1.isoformat(),2:r2.isoformat()}
    return {"event_id":None,"event_name":"Baycurrent Classic","course":"Yokohama Country Club",
        "location":"Yokohama, Japan","lat":35.444785,"lon":139.547239,
        "timezone":"Asia/Tokyo","timezone_label":"JST","has_cut":False,
        "round_dates":["2026-10-08","2026-10-09","2026-10-10","2026-10-11"],
        "tee_times":tee,"tee_source":"PGA TOUR","status":"Published R1/R2 tee times loaded",
        "tee_url":"https://pgatourmedia.pgatourhq.com/static-assets/page/files/tours/2026/pgatour/baycurrentclassic/roundInfo/R1-R2%20Tee%20Times.pdf",
        "forecast_summary":"Dry conditions expected for all four rounds. Thursday/Friday: 61–74°F, NE to E wind 6–12 mph. Saturday/Sunday: 63–75°F, NE wind 8–14 mph.",
        "forecast_as_of":"October 7, 2026, 5:30 AM JST",
        "forecast_url":"https://pgatourmedia.pgatourhq.com/static-assets/page/files/tours/2026/pgatour/baycurrentclassic/weather/Wednesday.pdf"}

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_pga_context(event_name, player_names=(), refresh_token=0):
    """Automatic event, course and tee-time context with a published current-event fallback."""
    out={"event_id":None,"event_name":event_name,"course":"","location":"","lat":None,"lon":None,"tee_times":{},"status":"Tee times not released"}
    wanted=_norm_name(event_name)
    if "baycurrent" in wanted:
        # Pin this week's verified course and tee sheet; unrelated ESPN events cannot overwrite it.
        return _baycurrent_2026_context()

    # Current Bank of Utah Championship: authoritative event/course metadata plus the
    # published Golf Channel R1/R2 tee sheet. This makes the current slate deterministic
    # even if ESPN's pre-event JSON is late or Golf Channel blocks server-side scraping.
    if "bankofutah" in wanted:
        out["course"]="Black Desert Resort"
        out["location"]="Ivins, UT"
        out["lat"]=37.16258
        out["lon"]=-113.64453
        out["timezone"]="America/Denver"
        out["timezone_label"]="MDT"
        out["tee_source"]="Golf Channel"
        out["tee_times"]=_bank_utah_2026_pairings()
        out["status"]="Published R1/R2 tee times loaded"
        return out

    # Generic ESPN discovery remains in place for future events and may fill richer metadata.
    try:
        sb=requests.get("https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard",timeout=8).json()
        choices=[]
        for ev in sb.get("events",[]): choices.append((ev.get("id"),ev.get("name",""),ev))
        for cal in (sb.get("leagues") or [{}])[0].get("calendar",[]): choices.append((cal.get("id"),cal.get("label",""),cal))
        if choices:
            def sim(x):
                n=_norm_name(x[1])
                return SequenceMatcher(None,wanted,n).ratio() + (0.5 if (wanted in n or n in wanted) else 0)
            eid,ename,raw=max(choices,key=sim)
            if sim((eid,ename,raw))>=0.35:
                out["event_id"]=str(eid); out["event_name"]=ename or event_name
                try:
                    core=requests.get(f"https://sports.core.api.espn.com/v2/sports/golf/leagues/pga/events/{eid}",timeout=8).json()
                    comp=(core.get("competitions") or [{}])[0]
                    venue=comp.get("venue") or core.get("venue") or {}
                    if venue.get("fullName") or venue.get("name"): out["course"]=venue.get("fullName") or venue.get("name")
                    addr=venue.get("address") or {}
                    loc=", ".join(x for x in [addr.get("city",""),addr.get("state",""),addr.get("country","")] if x)
                    if loc: out["location"]=loc
                    geo=venue.get("geo") or venue.get("location") or {}
                    if geo.get("latitude") is not None: out["lat"]=geo.get("latitude")
                    if geo.get("longitude") is not None: out["lon"]=geo.get("longitude")
                except Exception: pass

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
                            rec=out["tee_times"].setdefault(_norm_name(name),{})
                            try: rec[int(period)]=str(tt)
                            except Exception: rec.setdefault(1,str(tt))
                        for v in obj.values(): walk(v)
                    elif isinstance(obj,list):
                        for v in obj: walk(v)
                for p in payloads: walk(p)
    except Exception:
        pass

    if out["tee_times"] and out["status"]=="Tee times not released":
        out["status"]=f"Tee times loaded automatically ({len(out['tee_times'])} golfers)"
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
def fetch_hourly_weather(lat,lon,timezone="auto",refresh_token=0):
    if lat is None or lon is None: return pd.DataFrame()
    try:
        j=requests.get("https://api.open-meteo.com/v1/forecast",params={
            "latitude":lat,"longitude":lon,"timezone":timezone,"forecast_days":10,
            "temperature_unit":"fahrenheit","wind_speed_unit":"mph","precipitation_unit":"inch",
            "hourly":"temperature_2m,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m"
        },timeout=10).json()
        h=j.get("hourly",{})
        df=pd.DataFrame(h)
        if len(df): df["time"]=pd.to_datetime(df["time"])
        df.attrs["timezone"]=j.get("timezone",timezone)
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
    x.attrs["has_cut"]=ctx.get("has_cut",True)
    timezone=ctx.get("timezone") or weather.attrs.get("timezone") or "UTC"
    x["R1 Tee"]="—"; x["R2 Tee"]="—"; x["Wave"]="TBD"; x["Weather"]="⚪ TBD"; x["Weather Edge"]=0.0
    for i,row in x.iterrows():
        rec=ctx.get("tee_times",{}).get(_norm_name(row["Name"]),{})
        parsed=[]
        for rnd in [1,2]:
            raw=rec.get(rnd)
            if not raw: continue
            try:
                dt=pd.to_datetime(raw)
                if getattr(dt,"tzinfo",None) is not None:
                    dt=dt.tz_convert(timezone).tz_localize(None)
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

def generate_candidates(d,n,min_salary,seed,locked_ids,excluded_ids,wave_targets=None,wave_bounds=None):
    return generate_pga_candidates(
        d["ID"].astype(int).to_numpy(), d["Salary"].to_numpy(int),
        salary_baseline(d), ownership_estimate(d), n, min_salary, seed,
        locked_ids, excluded_ids, d["Wave"].to_numpy(), wave_targets, wave_bounds)

def simulate_golfers(d,n_sims,seed):
    rng=np.random.default_rng(seed+991)
    mu=salary_baseline(d)
    # Tee-time weather edge is deliberately modest and uncertain rather than treated as certain points.
    edge=pd.to_numeric(d.get("Weather Edge",pd.Series(np.zeros(len(d)))),errors="coerce").fillna(0).to_numpy(float)
    mu=mu+edge
    salary=d["Salary"].to_numpy(float)
    # Salary-tier-informed cut probability; missed cuts score much lower.
    strength=(salary-salary.mean())/(salary.std()+1e-9)
    make_cut=1/(1+np.exp(-(.25+strength))) if d.attrs.get("has_cut",True) else np.ones(len(d))
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
                     "Build Type":salary_build_type(ps["Salary"]),
                     "Wave Build":row.get("Wave Build","TBD"),
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
slate_key=(event,tuple(zip(golfers["ID"].astype(int),golfers["Salary"])))
if st.session_state.get("pga_slate_key") != slate_key:
    for key in ["pga_results","pga_run_settings","pga_pool_editor","pga_pool_bulk_in",
                "pga_wave_range_editor"]:
        st.session_state.pop(key,None)
    for key in list(st.session_state):
        if key.startswith("pga_build_range_editor_"):
            st.session_state.pop(key,None)
    st.session_state["pga_slate_key"]=slate_key
st.success(f"{source}: {event} · {len(golfers)} active golfers")

pga_refresh_nonce=int(st.session_state.get("pga_tee_refresh_nonce",0))
pga_refresh_token=f"{int(datetime.now().timestamp()//900)}:{pga_refresh_nonce}"
ctx=fetch_pga_context(event,tuple(golfers["Name"].astype(str)),pga_refresh_token)
lat,lon=ctx.get("lat"),ctx.get("lon")
if lat is None or lon is None:
    lat,lon=geocode_location(ctx.get("location",""))
weather=fetch_hourly_weather(lat,lon,ctx.get("timezone","auto"),pga_refresh_token)
golfers=attach_tee_weather(golfers,ctx,weather)

course_label=ctx.get("course") or ctx.get("location") or "Course locating automatically"
tee_ready=bool(ctx.get("tee_times"))
tee_matches=int(((golfers["R1 Tee"]!="—") & (golfers["R2 Tee"]!="—")).sum())
wcols=st.columns([2,2,2])
wcols[0].info(f"📍 {course_label}" + (f" · {ctx.get('location')}" if ctx.get("location") else ""))
if tee_ready:
    wcols[1].info(f"✅ R1/R2 tee times: {tee_matches}/{len(golfers)} DK golfers · {ctx.get('tee_source','ESPN')}")
else:
    wcols[1].info("⏳ Tee times not loaded")
if wcols[1].button("🔄 REFRESH TEE TIMES & WEATHER",use_container_width=True,key="pga_refresh_tee"):
    st.session_state["pga_tee_refresh_nonce"]=pga_refresh_nonce+1
    fetch_pga_context.clear()
    fetch_hourly_weather.clear()
    st.rerun()
weather_ready=bool(golfers["Weather"].ne("⚪ TBD").any())
if weather_ready and {"AM","PM"}.issubset(set(golfers["Wave"])):
    am=golfers.loc[golfers["Wave"]=="AM","Weather Edge"].mean(); pm=golfers.loc[golfers["Wave"]=="PM","Weather Edge"].mean()
    leader="AM" if am>pm else "PM"; gap=abs(float(am-pm))
    dot="🟢" if gap<.5 else ("🟡" if gap<1.25 else ("🟠" if gap<2.25 else "🔴"))
    wcols[2].info(f"{dot} Wave edge: {leader} +{gap:.2f} sim pts")
elif weather_ready:
    wcols[2].info("🌤️ Hourly weather loaded · single morning wave")
elif tee_ready:
    wcols[2].info("⚪ Hourly weather unavailable · sim weather edge is neutral")
else:
    wcols[2].info("⚪ Weather/wave edge activates when tee times are published")
if ctx.get("round_dates"):
    st.caption(f"October 8–11, 2026 · No-cut event · Tee times and weather shown in {ctx.get('timezone_label','course local time')} (Japan). R1/R2: all golfers start in the morning.")
    st.markdown(f"[Published R1/R2 tee sheet]({ctx['tee_url']})")
if ctx.get("forecast_summary"):
    st.info("🌦️ " + ctx["forecast_summary"])
    st.caption(f"PGA TOUR forecast issued {ctx['forecast_as_of']} · [Official forecast]({ctx['forecast_url']}). Golfer weather edges use the latest Open-Meteo hourly forecast when available.")
if not weather.empty and ctx.get("round_dates"):
    daily=[]
    for rnd,date in enumerate(ctx["round_dates"],1):
        day=weather.loc[weather["time"].dt.strftime("%Y-%m-%d")==date]
        play=day.loc[day["time"].dt.hour.between(8,16)]
        if not play.empty:
            daily.append({"Round":f"R{rnd} · {date}",
                "Temperature °F":f"{day['temperature_2m'].min():.0f}–{day['temperature_2m'].max():.0f}",
                "Wind mph (8 AM–4 PM)":f"{play['wind_speed_10m'].min():.0f}–{play['wind_speed_10m'].max():.0f}",
                "Max gust mph":round(float(play['wind_gusts_10m'].max())),
                "Max rain chance %":round(float(play['precipitation_probability'].max()))})
    if daily:
        with st.expander("Yokohama hourly forecast by round"):
            st.dataframe(pd.DataFrame(daily),hide_index=True,use_container_width=True)

m1,m2,m3,m4=st.columns(4)
m1.metric("Golfers",len(golfers)); m2.metric("Roster","6 G"); m3.metric("Salary Cap","$50,000"); m4.metric("Event",event)

st.subheader("🏌️ Golfer Pool")
st.caption("Include/exclude golfers, lock golfers, and set boosts or exposure limits. Automatic caps use salary tier, simulated cut strength, and estimated ownership. An explicit Max % overrides the automatic cap within the global limit; locks use 100%. In portfolios of 10+ lineups, every golfer used appears at least twice.")
editor=golfers[["ID","Name","Salary","R1 Tee","R2 Tee","Wave","Weather","Weather Edge"]].copy()
_, preview_cut=simulate_golfers(golfers,1,0)
editor["Auto Max %"]=automatic_exposure_caps(golfers["Salary"],salary_baseline(golfers),preview_cut,ownership_estimate(golfers))
# Show the same projected ownership model used by the PGA contest SIM directly in the player pool.
editor["pOwn%"] = np.round(ownership_estimate(golfers), 1)
# Keep projected ownership directly to the right of Salary.
pown = editor.pop("pOwn%")
editor.insert(editor.columns.get_loc("Salary") + 1, "pOwn%", pown)
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
    column_order=[c for c in editor.columns if c != "ID"],
    disabled=["Auto Max %","ID","Name","Salary","pOwn%","R1 Tee","R2 Tee","Wave","Weather","Weather Edge"],
    column_config={
      "In":st.column_config.CheckboxColumn("In"),
      "Lock":st.column_config.CheckboxColumn("🔒 Lock"),
      "Salary":st.column_config.NumberColumn("Salary",format="$%d"),
      "pOwn%":st.column_config.NumberColumn("pOwn%",format="%.1f%%"),
      "Weather Edge":st.column_config.NumberColumn("Wx Edge",format="%+.2f"),
      "Boost %":st.column_config.NumberColumn("Boost %",min_value=-50,max_value=100,step=5),
      "Min %":st.column_config.NumberColumn("Min %",min_value=0,max_value=100,step=5),
      "Max %":st.column_config.NumberColumn("Max %",min_value=0,max_value=100,step=5,help="100 uses the automatic cap. Any lower value is an explicit override, bounded by the global cap. Zero excludes this golfer from the portfolio."),
      "Auto Max %":st.column_config.NumberColumn("Auto Max %",format="%d%%"),
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
    with st.expander("🌦️ Wave ranges",expanded=False):
        st.caption("Min/max % of portfolio lineups. 0–100 leaves a type open; 0 max excludes it. No exact mix required. Activates when tee times load.")
        if set(golfers["Wave"])=={"AM"}:
            st.caption("All golfers start in the morning this week. Every lineup is 6A / 0P.")
        wave_table=pd.DataFrame({"Wave":[f"{am}A / {6-am}P" for am in range(6,-1,-1)],
                                 "Min %":[0]*7,"Max %":[100]*7})
        wave_edit=st.data_editor(wave_table,hide_index=True,use_container_width=True,
            height=282,key="pga_wave_range_editor",disabled=["Wave"],
            column_config={"Wave":st.column_config.TextColumn("AM / PM",width="small"),
                "Min %":st.column_config.NumberColumn("Min %",min_value=0,max_value=100,step=1,required=True),
                "Max %":st.column_config.NumberColumn("Max %",min_value=0,max_value=100,step=1,required=True)})
    wave_ranges={6-i:(r["Min %"],r["Max %"]) for i,r in wave_edit.iterrows()}
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
    st.session_state.pop("pga_results",None)
    # Zero max is an exclusion during generation as well as selection.
    excluded.update(edited.loc[edited["Max %"]==0,"ID"].astype(int))
    personal_min=dict(zip(edited["ID"].astype(int),edited["Min %"].astype(float)))
    personal_max=dict(zip(edited["ID"].astype(int),edited["Max %"].astype(float)))
    if any(personal_min[pid]>0 for pid in excluded):
        st.error("An excluded golfer has a positive minimum. Include that golfer or clear the minimum."); st.stop()
    waves=golfers["Wave"].astype(str).to_numpy()
    wave_active=tee_ready and bool(set(waves).intersection({"AM","PM"}))
    try:
        wave_bounds=wave_lineup_bounds(int(portfolio_n),wave_ranges) if wave_active else None
        with st.spinner("Generating PGA lineups and simulating tournament outcomes..."):
            cands=generate_candidates(golfers,int(candidates_n),int(min_salary),seed,locked,excluded,wave_bounds=wave_bounds)
    except PortfolioError as e:
        st.error(str(e)); st.stop()
    with st.spinner("Simulating golfers and selecting a complete constrained portfolio..."):

        if not cands:
            st.error("No legal 6-golfer lineups were generated. Lower the salary floor or loosen the pool."); st.stop()
        sims,cut_prob=simulate_golfers(golfers,int(universes),seed)
        own=ownership_estimate(golfers)
        boosts=dict(zip(edited["ID"].astype(int),edited["Boost %"].astype(float)))
        auto_caps=automatic_exposure_caps(golfers["Salary"],salary_baseline(golfers),cut_prob,own)
        candidate_budget=int(candidates_n)
        while True:
            results=evaluate(cands,sims,own)
            results=simulate_contest_metrics(results,cands,sims,cut_prob,int(field_size),float(entry_fee),float(first_prize),seed)
            for ri in results.index:
                cand=cands[int(results.at[ri,"_candidate"])]
                results.at[ri,"NUKE Score"] += sum(boosts.get(int(golfers.iloc[i]["ID"]),0) for i in cand["idx"])/100
            results=results.sort_values("NUKE Score",ascending=False).reset_index(drop=True)
            try:
                portfolio=select_pga_portfolio(results,cands,golfers,int(portfolio_n),
                    float(max_player),float(max_pair),float(max_triple),personal_min,
                    personal_max,auto_caps,locked,wave_bounds=wave_bounds)
                break
            except PortfolioError as e:
                if not e.retryable or candidate_budget>=20000:
                    st.error(str(e)); st.stop()
                candidate_budget=min(20000,max(10000,candidate_budget*2))
                st.info(f"Expanding the candidate pool to {candidate_budget:,} to complete the requested portfolio under your constraints.")
                expanded=generate_candidates(golfers,candidate_budget,int(min_salary),seed,locked,excluded,wave_bounds=wave_bounds)
                if len(expanded)<=len(cands):
                    st.error(str(e)); st.stop()
                cands=expanded
        st.session_state["pga_results_version"]=PGA_PORTFOLIO_VERSION
        st.session_state["pga_results"]=(results,cands,portfolio,golfers,own,cut_prob,seed)
        st.session_state["pga_run_settings"]={"locked":locked,"personal_min":personal_min,
            "personal_max":personal_max,"auto_caps":auto_caps,"wave_active":wave_active,
            "universes":int(universes),"wave_ranges":wave_ranges,"build_ranges":{}}

if "pga_results" in st.session_state:
    results,cands,portfolio,golfers,own,cut_prob,seed=st.session_state["pga_results"]
    st.divider(); st.header("🏆 PGA Contest Sim Results")
    a,b,c,d=st.columns(4)
    settings=st.session_state["pga_run_settings"]
    a.metric("Candidates",len(results)); b.metric("Portfolio",len(portfolio)); c.metric("Universes",f"{settings['universes']:,}"); d.metric("Seed",seed)
    st.success(f"Complete portfolio: {len(portfolio)} unique lineups. Golfer, pair/triple, minimum-use, and wave constraints validated.")
    with st.expander("Salary build types · view mix / adjust ranges",expanded=False):
        st.caption("10/9/8/7/7/6 means one $10K, one $9K, one $8K, two $7K and one $6K golfer. Each tier covers the full $1,000 band. Raise Min % to increase a build's share; lower Max % to cap it. Other types stay flexible.")
        mix=build_type_summary(results,cands,golfers,portfolio)
        saved_build_ranges=settings.get("build_ranges",{})
        mix["Min %"]=[saved_build_ranges.get(kind,(0,100))[0] for kind in mix["Build Type"]]
        mix["Max %"]=[saved_build_ranges.get(kind,(0,100))[1] for kind in mix["Build Type"]]
        build_edit=st.data_editor(mix,hide_index=True,use_container_width=True,
            height=min(360,38+35*len(mix)),key=f"pga_build_range_editor_{seed}",
            disabled=["Build Type","Lineups","Portfolio %","Candidates"],
            column_config={"Min %":st.column_config.NumberColumn("Min %",min_value=0,max_value=100,step=1,required=True),
                           "Max %":st.column_config.NumberColumn("Max %",min_value=0,max_value=100,step=1,required=True)})
        st.caption("Rebuild uses the existing simulated candidates, golfer pool and boosts. Portfolio size, global exposure caps and sidebar wave ranges apply on rebuild. No new tournament simulations are needed.")
        if st.button("REBUILD PORTFOLIO",type="primary",key="pga_rebuild_portfolio"):
            requested_builds={r["Build Type"]:(r["Min %"],r["Max %"]) for _,r in build_edit.iterrows()}
            try:
                requested_waves=wave_lineup_bounds(int(portfolio_n),wave_ranges) if settings["wave_active"] else None
                with st.spinner("Selecting a new portfolio from the existing sim..."):
                    rebuilt=select_pga_portfolio(results,cands,golfers,int(portfolio_n),
                        float(max_player),float(max_pair),float(max_triple),settings["personal_min"],
                        settings["personal_max"],settings["auto_caps"],settings["locked"],
                        wave_bounds=requested_waves,build_ranges=requested_builds)
            except PortfolioError as e:
                st.error(f"{e} Your last valid portfolio and downloads are unchanged.")
            else:
                settings["wave_ranges"]=dict(wave_ranges)
                settings["build_ranges"]=requested_builds
                st.session_state["pga_run_settings"]=settings
                st.session_state["pga_results"]=(results,cands,rebuilt,golfers,own,cut_prob,seed)
                st.rerun()
    mix=build_type_summary(results,cands,golfers,portfolio)
    if not mix.empty:
        most_used=mix.sort_values("Lineups",ascending=False).head(3)
        st.caption("Top salary builds: " + " · ".join(f"{r['Build Type']} ({r['Portfolio %']:g}%)" for _,r in most_used.iterrows() if r["Lineups"]))
    st.subheader("NUKE PGA Portfolio")
    show=[]
    for rank,r in portfolio.reset_index(drop=True).iterrows():
        cand=cands[int(r["_candidate"])]
        show.append({"#":rank+1,"Golfers":" · ".join(lineup_names(cand,golfers)),"Salary":int(r["Salary"]),
                     "Build Type":r["Build Type"],
                     "Mean":r["Mean"],"P95":r["P95"],"Top 1%":r["Top 1%"],"6/6 %":r["6/6 %"],"5+/6 %":r["5+/6 %"],
                     "Win %":r["Win %"],"Top 1% %":r["Top 1% %"],"Cash %":r["Cash %"],"Est. ROI %":r["Est. ROI %"],
                     "Est. Duplicates":r["Est. Duplicates"],"Own Sum %":r["Ownership Sum"],"NUKE Score":round(float(r["NUKE Score"]),3)})
    st.dataframe(pd.DataFrame(show),hide_index=True,use_container_width=True,height=430)
    if settings["wave_active"] and len(portfolio):
        wave_rows=[]
        for am_n in range(6,-1,-1):
            ct=0
            for _,rr in portfolio.iterrows():
                cc=cands[int(rr["_candidate"])]
                if sum(1 for ix in cc["idx"] if str(golfers.iloc[ix]["Wave"])=="AM")==am_n: ct+=1
            applied=settings["wave_ranges"].get(am_n,(0,100))
            wave_rows.append({"Construction":f"{am_n} AM / {6-am_n} PM","Lineups":ct,"Portfolio %":round(ct/len(portfolio)*100,1),"Min %":applied[0],"Max %":applied[1]})
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
                        "Exposure %":round(100*ct/denom,1),"Cap Lineups":portfolio.attrs.get("exposure_caps",{}).get(pid),"Est. Own %":round(float(own[i]),1),
                        "Make Cut %":round(float(cut_prob[i])*100,1)})
    st.dataframe(pd.DataFrame(exp).sort_values(["Exposure %","Salary"],ascending=[False,False]),hide_index=True,use_container_width=True)

    with st.expander("Top simulated candidate lineups"):
        top=[]
        for rank,r in results.head(100).iterrows():
            cand=cands[int(r["_candidate"])]
            top.append({"Rank":rank+1,"Golfers":" · ".join(lineup_names(cand,golfers)),"Salary":int(r["Salary"]),
                        "Build Type":salary_build_type(golfers.iloc[cand["idx"]]["Salary"]),
                        "Mean":r["Mean"],"P95":r["P95"],"Top 1%":r["Top 1%"],"6/6 %":r["6/6 %"],"Win %":r["Win %"],"Top 1% %":r["Top 1% %"],"Cash %":r["Cash %"],"Est. ROI %":r["Est. ROI %"],"Est. Duplicates":r["Est. Duplicates"],"NUKE Score":round(float(r["NUKE Score"]),3)})
        st.dataframe(pd.DataFrame(top),hide_index=True,use_container_width=True)

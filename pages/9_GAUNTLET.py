import time
import pandas as pd
import streamlit as st
from nuke_nav import render_nav

from nuke_sim import prepare_slate
from nuke_football_v2 import simulate_player_matrix_v2
from nuke_validation import prepare_actuals, build_validation, validation_summary
from nuke_historical_data import load_nfldfs_2017, historical_week, starter_aware_pool
from nuke_crossseason_data import load_rotoguru_season, SOURCE_NAME
from nuke_calibration import fit_position_calibration, apply_position_calibration, summary_comparison, promotion_gate, calibration_distance

st.set_page_config(page_title="NUKE Cross-Season Gauntlet",page_icon="🧊",layout="wide")
render_nav()
st.title("🧊 NUKE V2.1 CROSS-SEASON GAUNTLET")
st.caption("Freeze calibration learned only from 2017 Weeks 1–8, then test it unchanged on later NFL seasons. Target-season results never refit the candidate.")

@st.cache_data(ttl=86400,show_spinner=False)
def get_2017(): return load_nfldfs_2017()

@st.cache_data(ttl=86400,show_spinner=False)
def get_external_season(year): return load_rotoguru_season(int(year))

def make_inputs(hist):
    salary=pd.DataFrame({"Name":hist["Name"],"Position":hist["Position"],"Team":hist["Team"],"Salary":hist["Salary"],"Game":hist["Game"],"Status":""})
    players=prepare_slate(salary)
    actuals=prepare_actuals(pd.DataFrame({"Name":hist["Name"],"Actual DKFP":hist["Actual DK Points"]}),name_col="Name",points_col="Actual DKFP")
    return players,actuals

def validate_hist(hist,params,universes,seed):
    players,actuals=make_inputs(hist); matrix=simulate_player_matrix_v2(players,int(universes),int(seed))
    return build_validation(players,matrix,actuals),build_validation(players,apply_position_calibration(players,matrix,params),actuals)

def fit_frozen_params(universes,seed):
    history=get_2017(); details=[]
    for w in range(1,9):
        hist=starter_aware_pool(historical_week(history,2017,w)); players,actuals=make_inputs(hist)
        d=build_validation(players,simulate_player_matrix_v2(players,int(universes),int(seed)+w),actuals)
        if not d.empty: details.append(d)
    if not details: raise ValueError("Could not build the 2017 calibration sample.")
    train=pd.concat(details,ignore_index=True)
    return fit_position_calibration(train),train

def final_readiness(o,c,season_df,requested,unavailable):
    base=promotion_gate(o,c); tested=set(season_df.Season.astype(int)) if not season_df.empty else set()
    checks={
        "Combined promotion gate passes":bool(base.get("pass")),
        "Every available tested season passes individually":bool(not season_df.empty and season_df["Gate Pass"].astype(bool).all()),
        "Frozen V2.1 MAE improves overall":float(c["mae"])<float(o["mae"]),
        "Absolute overall bias ≤ 0.75 DKFP":abs(float(c["bias"]))<=0.75,
        "50/80/90 coverage is close to calibration targets":calibration_distance(c)<=7.5,
        "At least four independent seasons tested":len(tested)>=4,
    }
    return {"pass":all(checks.values()),"checks":checks,"tested":sorted(tested),"unavailable":sorted(set(unavailable))}

# RotoGuru/nfldfs public DK archive is reliable through 2021. Later seasons are shown as optional probes only.
ALL_YEARS=[2018,2019,2020,2021,2022,2023,2024]
RECOMMENDED=[2018,2019,2020,2021]
c1,c2,c3=st.columns(3)
years=c1.multiselect("Independent test seasons",ALL_YEARS,default=RECOMMENDED)
universes=c2.selectbox("Universes per week",[250,500,750],index=1)
seed=c3.number_input("Base seed",1,2147483646,2026,1)
st.info(f"Independent source: {SOURCE_NAME}. The public RotoGuru/nfldfs archive is known to cover through 2021; 2022–2024 are optional probes and may be unavailable. Recommended final free-data test: 2018–2021. 2017 Weeks 1–8 remain the only fitting sample.")

if st.button("🧊 RUN CROSS-SEASON GAUNTLET",type="primary",use_container_width=True,disabled=not years):
    started=time.perf_counter()
    try:
        with st.status("Running frozen cross-season gauntlet...",expanded=True) as status:
            st.write("1/3 · Fitting frozen V2.1 parameters from 2017 Weeks 1–8 only")
            params,train=fit_frozen_params(universes,seed)
            season_rows=[]; orig_all=[]; cal_all=[]; pos_rows=[]; failures=[]; unavailable=[]
            for yi,year in enumerate(years,1):
                st.write(f"2/3 · {yi}/{len(years)} · Loading independent {year} DraftKings history")
                try:
                    season_data,load_failures=get_external_season(year)
                except Exception as e:
                    unavailable.append(int(year)); failures.append({"Season":year,"Week":"ALL","Error":str(e)})
                    st.write(f"↳ {year} unavailable from this public archive — skipped without aborting the gauntlet.")
                    continue
                failures.extend([{"Season":year,"Week":w,"Error":err} for w,err in load_failures])
                weeks=sorted(pd.to_numeric(season_data.Week,errors="coerce").dropna().astype(int).unique().tolist())
                season_orig=[]; season_cal=[]
                for w in weeks:
                    hist=starter_aware_pool(season_data[pd.to_numeric(season_data.Week,errors="coerce").eq(w)].copy())
                    if hist.empty: continue
                    o,c=validate_hist(hist,params,universes,int(seed)+year*100+w)
                    if o.empty or c.empty: continue
                    o.insert(0,"Season",year); o.insert(1,"Week",w); c.insert(0,"Season",year); c.insert(1,"Week",w)
                    season_orig.append(o); season_cal.append(c)
                if not season_orig:
                    unavailable.append(int(year)); failures.append({"Season":year,"Week":"ALL","Error":"No usable matched weeks"}); continue
                od=pd.concat(season_orig,ignore_index=True); cd=pd.concat(season_cal,ignore_index=True); orig_all.append(od); cal_all.append(cd)
                os,op=validation_summary(od); cs,cp=validation_summary(cd); gate=promotion_gate(os,cs)
                season_rows.append({"Season":year,"Players":cs["matched_players"],"V2 MAE":round(os["mae"],3),"V2.1 MAE":round(cs["mae"],3),"V2 Bias":round(os["bias"],3),"V2.1 Bias":round(cs["bias"],3),"V2 50%":round(os["inside_50"],1),"V2.1 50%":round(cs["inside_50"],1),"V2 80%":round(os["inside_80"],1),"V2.1 80%":round(cs["inside_80"],1),"V2 90%":round(os["inside_90"],1),"V2.1 90%":round(cs["inside_90"],1),"Gate Pass":bool(gate["pass"])})
                op.insert(0,"Season",year); op.insert(2,"Model","V2 Original"); cp.insert(0,"Season",year); cp.insert(2,"Model","V2.1 Frozen"); pos_rows.extend([op,cp])
            if not orig_all: raise ValueError("No independent seasons could be validated.")
            original=pd.concat(orig_all,ignore_index=True); candidate=pd.concat(cal_all,ignore_index=True)
            os,_=validation_summary(original); cs,_=validation_summary(candidate); season_df=pd.DataFrame(season_rows)
            overall_gate=promotion_gate(os,cs); readiness=final_readiness(os,cs,season_df,years,unavailable); elapsed=time.perf_counter()-started
            status.update(label=f"Cross-season gauntlet complete · {elapsed:.1f}s",state="complete")
        for k,v in {"gauntlet_params":params,"gauntlet_seasons":season_df,"gauntlet_original":original,"gauntlet_candidate":candidate,"gauntlet_orig_summary":os,"gauntlet_candidate_summary":cs,"gauntlet_position":pd.concat(pos_rows,ignore_index=True) if pos_rows else pd.DataFrame(),"gauntlet_gate":overall_gate,"gauntlet_readiness":readiness,"gauntlet_failures":pd.DataFrame(failures),"gauntlet_runtime":elapsed,"gauntlet_years":list(years)}.items(): st.session_state[k]=v
    except Exception as e: st.error(f"Cross-season gauntlet failed: {e}")

os=st.session_state.get("gauntlet_orig_summary"); cs=st.session_state.get("gauntlet_candidate_summary")
if os and cs:
    st.divider(); st.subheader("Frozen V2.1 · Independent Season Results")
    st.dataframe(summary_comparison(os,cs).replace({"V2.1 Candidate":"V2.1 Frozen"}),use_container_width=True,hide_index=True)
    c1,c2,c3,c4=st.columns(4); c1.metric("MAE",f"{os['mae']:.2f} → {cs['mae']:.2f}"); c2.metric("Bias",f"{os['bias']:+.2f} → {cs['bias']:+.2f}"); c3.metric("90% Coverage",f"{os['inside_90']:.1f}% → {cs['inside_90']:.1f}%"); c4.metric("Independent Players",f"{cs['matched_players']:,}")
    st.subheader("Player-Outcome Promotion Readiness")
    readiness=st.session_state.get("gauntlet_readiness",{})
    if readiness.get("pass"): st.success("PLAYER-OUTCOME VALIDATION PASSES across the available independent public-data era. V2.1 is eligible for live-engine promotion after review. Contest SIM ROI/ownership/duplication remains a separate validation task.")
    else: st.warning("PLAYER-OUTCOME VALIDATION IS NOT YET COMPLETE. Review the checks below.")
    st.dataframe(pd.DataFrame([{"Readiness Check":k,"Pass":bool(v)} for k,v in readiness.get("checks",{}).items()]),use_container_width=True,hide_index=True)
    if readiness.get("unavailable"): st.warning("Unavailable from this public archive: "+", ".join(map(str,readiness["unavailable"]))+". These seasons were not counted as failures and were not used to claim validation.")
    st.subheader("Season-by-Season"); st.dataframe(st.session_state.get("gauntlet_seasons"),use_container_width=True,hide_index=True)
    st.subheader("Frozen Parameters · Learned Only From 2017 Weeks 1–8"); st.dataframe(st.session_state.get("gauntlet_params"),use_container_width=True,hide_index=True)
    with st.expander("Position detail"): st.dataframe(st.session_state.get("gauntlet_position"),use_container_width=True,hide_index=True)
    failures=st.session_state.get("gauntlet_failures")
    if failures is not None and not failures.empty:
        with st.expander("Unavailable source weeks / seasons"): st.dataframe(failures,use_container_width=True,hide_index=True)
    st.caption(f"Runtime: {float(st.session_state.get('gauntlet_runtime',0)):.1f}s. The app does not pretend unavailable seasons were tested.")
else: st.caption("Recommended free-data gauntlet: 2018–2021. Later seasons can be probed, but the source may not contain them.")
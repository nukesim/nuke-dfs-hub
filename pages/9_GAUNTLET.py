import time
import pandas as pd
import streamlit as st

from nuke_sim import prepare_slate
from nuke_football_v2 import simulate_player_matrix_v2
from nuke_validation import prepare_actuals, build_validation, validation_summary
from nuke_historical_data import load_nfldfs_2017, historical_week, starter_aware_pool
from nuke_crossseason_data import load_rotoguru_season, SOURCE_NAME
from nuke_calibration import fit_position_calibration, apply_position_calibration, summary_comparison, promotion_gate

st.set_page_config(page_title="NUKE Cross-Season Gauntlet",page_icon="🧊",layout="wide")
st.title("🧊 NUKE V2.1 CROSS-SEASON GAUNTLET")
st.caption("Freeze calibration learned only from 2017 Weeks 1–8, then test it unchanged on completely different NFL seasons. Target-season results never refit the candidate.")

@st.cache_data(ttl=86400,show_spinner=False)
def get_2017():
    return load_nfldfs_2017()

@st.cache_data(ttl=86400,show_spinner=False)
def get_external_season(year):
    return load_rotoguru_season(int(year))


def make_inputs(hist):
    salary=pd.DataFrame({
        "Name":hist["Name"],"Position":hist["Position"],"Team":hist["Team"],
        "Salary":hist["Salary"],"Game":hist["Game"],"Status":""
    })
    players=prepare_slate(salary)
    actuals=prepare_actuals(pd.DataFrame({"Name":hist["Name"],"Actual DKFP":hist["Actual DK Points"]}),name_col="Name",points_col="Actual DKFP")
    return players,actuals


def validate_hist(hist,params,universes,seed):
    players,actuals=make_inputs(hist)
    matrix=simulate_player_matrix_v2(players,int(universes),int(seed))
    orig=build_validation(players,matrix,actuals)
    cal=build_validation(players,apply_position_calibration(players,matrix,params),actuals)
    return orig,cal


def fit_frozen_params(universes,seed):
    history=get_2017(); details=[]
    for w in range(1,9):
        hist=starter_aware_pool(historical_week(history,2017,w))
        players,actuals=make_inputs(hist)
        matrix=simulate_player_matrix_v2(players,int(universes),int(seed)+w)
        d=build_validation(players,matrix,actuals)
        if not d.empty: details.append(d)
    if not details:
        raise ValueError("Could not build the 2017 calibration sample.")
    train=pd.concat(details,ignore_index=True)
    return fit_position_calibration(train),train

c1,c2,c3=st.columns(3)
years=c1.multiselect("Independent test seasons",[2018,2019,2020,2021,2022,2023,2024],default=[2018,2019,2020])
universes=c2.selectbox("Universes per week",[250,500,750],index=1)
seed=c3.number_input("Base seed",1,2147483646,2026,1)

st.info(f"Data source for independent seasons: {SOURCE_NAME}. Starter-aware filtering uses salary rank only. 2017 Weeks 1–8 are the only outcomes allowed to fit the frozen V2.1 parameters.")

if st.button("🧊 RUN CROSS-SEASON GAUNTLET",type="primary",use_container_width=True,disabled=not years):
    started=time.perf_counter()
    try:
        with st.status("Running frozen cross-season gauntlet...",expanded=True) as status:
            st.write("1/3 · Fitting frozen V2.1 parameters from 2017 Weeks 1–8 only")
            params,train=fit_frozen_params(universes,seed)
            season_rows=[]; orig_all=[]; cal_all=[]; pos_rows=[]; failures=[]
            for yi,year in enumerate(years,1):
                st.write(f"2/3 · Loading independent {year} DraftKings history")
                season_data,load_failures=get_external_season(year)
                failures.extend([{"Season":year,"Week":w,"Error":err} for w,err in load_failures])
                weeks=sorted(pd.to_numeric(season_data.Week,errors="coerce").dropna().astype(int).unique().tolist())
                season_orig=[]; season_cal=[]
                for wi,w in enumerate(weeks,1):
                    hist=season_data[pd.to_numeric(season_data.Week,errors="coerce").eq(w)].copy()
                    hist=starter_aware_pool(hist)
                    if hist.empty: continue
                    o,c=validate_hist(hist,params,universes,int(seed)+year*100+w)
                    if o.empty or c.empty: continue
                    o.insert(0,"Season",year); o.insert(1,"Week",w)
                    c.insert(0,"Season",year); c.insert(1,"Week",w)
                    season_orig.append(o); season_cal.append(c)
                if not season_orig:
                    failures.append({"Season":year,"Week":"ALL","Error":"No usable matched weeks"})
                    continue
                od=pd.concat(season_orig,ignore_index=True); cd=pd.concat(season_cal,ignore_index=True)
                orig_all.append(od); cal_all.append(cd)
                os,op=validation_summary(od); cs,cp=validation_summary(cd)
                gate=promotion_gate(os,cs)
                season_rows.append({
                    "Season":year,"Players":cs["matched_players"],
                    "V2 MAE":round(os["mae"],3),"V2.1 MAE":round(cs["mae"],3),
                    "V2 Bias":round(os["bias"],3),"V2.1 Bias":round(cs["bias"],3),
                    "V2 90%":round(os["inside_90"],1),"V2.1 90%":round(cs["inside_90"],1),
                    "Gate Pass":bool(gate["pass"])
                })
                op.insert(0,"Season",year); op.insert(2,"Model","V2 Original")
                cp.insert(0,"Season",year); cp.insert(2,"Model","V2.1 Frozen")
                pos_rows.extend([op,cp])

            if not orig_all:
                raise ValueError("No independent seasons could be validated. The public historical source may be temporarily unavailable.")
            original=pd.concat(orig_all,ignore_index=True); candidate=pd.concat(cal_all,ignore_index=True)
            os,_=validation_summary(original); cs,_=validation_summary(candidate)
            overall_gate=promotion_gate(os,cs)
            elapsed=time.perf_counter()-started
            status.update(label=f"Cross-season gauntlet complete · {elapsed:.1f}s",state="complete")

        for k,v in {
            "gauntlet_params":params,"gauntlet_seasons":pd.DataFrame(season_rows),
            "gauntlet_original":original,"gauntlet_candidate":candidate,
            "gauntlet_orig_summary":os,"gauntlet_candidate_summary":cs,
            "gauntlet_position":pd.concat(pos_rows,ignore_index=True) if pos_rows else pd.DataFrame(),
            "gauntlet_gate":overall_gate,"gauntlet_failures":pd.DataFrame(failures),"gauntlet_runtime":elapsed
        }.items(): st.session_state[k]=v
    except Exception as e:
        st.error(f"Cross-season gauntlet failed: {e}")

os=st.session_state.get("gauntlet_orig_summary")
cs=st.session_state.get("gauntlet_candidate_summary")
if os and cs:
    st.divider(); st.subheader("Frozen V2.1 · Independent Season Results")
    st.dataframe(summary_comparison(os,cs).replace({"V2.1 Candidate":"V2.1 Frozen"}),use_container_width=True,hide_index=True)
    gate=st.session_state.get("gauntlet_gate",{})
    if gate.get("pass"):
        st.success("FROZEN V2.1 PASSES the combined cross-season gate. The same 2017-trained parameters improved unseen seasons without retraining.")
    else:
        st.warning("FROZEN V2.1 DOES NOT PASS the combined cross-season gate. Keep live V2 unchanged.")

    c1,c2,c3,c4=st.columns(4)
    c1.metric("MAE",f"{os['mae']:.2f} → {cs['mae']:.2f}")
    c2.metric("Bias",f"{os['bias']:+.2f} → {cs['bias']:+.2f}")
    c3.metric("90% Coverage",f"{os['inside_90']:.1f}% → {cs['inside_90']:.1f}%")
    c4.metric("Independent Players",f"{cs['matched_players']:,}")

    st.subheader("Season-by-Season")
    st.dataframe(st.session_state.get("gauntlet_seasons"),use_container_width=True,hide_index=True)
    st.subheader("Frozen Parameters · Learned Only From 2017 Weeks 1–8")
    st.dataframe(st.session_state.get("gauntlet_params"),use_container_width=True,hide_index=True)
    with st.expander("Position detail"):
        st.dataframe(st.session_state.get("gauntlet_position"),use_container_width=True,hide_index=True)
    failures=st.session_state.get("gauntlet_failures")
    if failures is not None and not failures.empty:
        with st.expander("Source weeks that could not be loaded"):
            st.dataframe(failures,use_container_width=True,hide_index=True)
    st.caption(f"Runtime: {float(st.session_state.get('gauntlet_runtime',0)):.1f}s. Passing this test still does not automatically modify the live simulator.")
else:
    st.caption("Run the gauntlet to test frozen 2017-derived V2.1 calibration on different NFL seasons.")

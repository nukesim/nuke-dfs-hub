import time
import pandas as pd
import streamlit as st

from nuke_sim import prepare_slate
from nuke_football_v2 import simulate_player_matrix_v2
from nuke_validation import prepare_actuals, build_validation, validation_summary
from nuke_historical_data import load_nfldfs_2017, available_weeks, historical_week, starter_aware_pool, SOURCE_NAME
from nuke_calibration import fit_position_calibration, apply_position_calibration, summary_comparison, promotion_gate

st.set_page_config(page_title="NUKE Calibration Lab",page_icon="🧬",layout="wide")
st.title("🧬 NUKE V2 → V2.1 CALIBRATION LAB")
st.caption("Train on one block of historical weeks, then judge the candidate only on untouched holdout weeks. The live SIM remains on Football Engine V2 unless the candidate earns promotion after broader validation.")

@st.cache_data(ttl=86400,show_spinner=False)
def get_history():
    return load_nfldfs_2017()


def make_inputs(hist):
    salary_raw=pd.DataFrame({
        "Name":hist["Name"],"Position":hist["Position"],"Team":hist["Team"],
        "Salary":hist["Salary"],"Game":hist["Game"],"Status":""
    })
    players=prepare_slate(salary_raw)
    actuals=prepare_actuals(pd.DataFrame({"Name":hist["Name"],"Actual DKFP":hist["Actual DK Points"]}),name_col="Name",points_col="Actual DKFP")
    return players,actuals


def run_original(hist, universes, seed):
    players,actuals=make_inputs(hist)
    matrix=simulate_player_matrix_v2(players,int(universes),int(seed))
    detail=build_validation(players,matrix,actuals)
    return players,actuals,matrix,detail

try:
    history=get_history()
except Exception as e:
    st.error(f"Could not load public historical data: {e}")
    st.stop()

weeks=available_weeks(history,2017)
if len(weeks)<4:
    st.error("Not enough historical weeks are available for a train/holdout split.")
    st.stop()

c1,c2,c3,c4=st.columns(4)
train_end=c1.selectbox("Calibration weeks",[6,7,8,9,10],index=2,format_func=lambda x:f"Weeks 1–{x}")
holdout_start=int(train_end)+1
c2.metric("Untouched holdout",f"Weeks {holdout_start}–{max(weeks)}")
universes=c3.selectbox("Universes per week",[250,500,750,1000],index=1)
seed=c4.number_input("Base seed",1,2147483646,2026,1)

train_weeks=[w for w in weeks if w<=int(train_end)]
holdout_weeks=[w for w in weeks if w>=holdout_start]
st.info(f"Starter-aware only. Training outcomes from Weeks 1–{train_end} may fit calibration parameters. Weeks {holdout_start}–{max(weeks)} are never used to fit them. Source: {SOURCE_NAME}.")

if st.button("🧬 RUN TRAIN / HOLDOUT CALIBRATION",type="primary",use_container_width=True):
    started=time.perf_counter()
    try:
        train_details=[]
        holdout_original=[]
        holdout_calibrated=[]
        weekly_rows=[]
        with st.status("Running protected train/holdout test...",expanded=True) as status:
            for i,w in enumerate(train_weeks,1):
                st.write(f"Training {i}/{len(train_weeks)} · Week {w}")
                hist=starter_aware_pool(historical_week(history,2017,w))
                _,_,_,detail=run_original(hist,universes,int(seed)+w)
                if not detail.empty:
                    detail.insert(0,"Week",w)
                    train_details.append(detail)
            train_detail=pd.concat(train_details,ignore_index=True) if train_details else pd.DataFrame()
            if train_detail.empty:
                raise ValueError("Training sample produced no matched players.")

            params=fit_position_calibration(train_detail)
            if params.empty:
                raise ValueError("Could not fit position calibration parameters.")

            for i,w in enumerate(holdout_weeks,1):
                st.write(f"Holdout {i}/{len(holdout_weeks)} · Week {w} · original vs candidate")
                hist=starter_aware_pool(historical_week(history,2017,w))
                players,actuals,matrix,orig=run_original(hist,universes,int(seed)+1000+w)
                calibrated_matrix=apply_position_calibration(players,matrix,params)
                cal=build_validation(players,calibrated_matrix,actuals)
                if orig.empty or cal.empty:
                    continue
                orig.insert(0,"Week",w); cal.insert(0,"Week",w)
                holdout_original.append(orig); holdout_calibrated.append(cal)
                so,_=validation_summary(orig); sc,_=validation_summary(cal)
                weekly_rows.append({
                    "Week":w,
                    "Original MAE":round(so["mae"],2),"Candidate MAE":round(sc["mae"],2),
                    "Original Bias":round(so["bias"],2),"Candidate Bias":round(sc["bias"],2),
                    "Original 90%":round(so["inside_90"],1),"Candidate 90%":round(sc["inside_90"],1),
                })

            orig_detail=pd.concat(holdout_original,ignore_index=True) if holdout_original else pd.DataFrame()
            cal_detail=pd.concat(holdout_calibrated,ignore_index=True) if holdout_calibrated else pd.DataFrame()
            if orig_detail.empty or cal_detail.empty:
                raise ValueError("Holdout sample produced no matched players.")

            train_summary,train_pos=validation_summary(train_detail)
            orig_summary,orig_pos=validation_summary(orig_detail)
            cal_summary,cal_pos=validation_summary(cal_detail)
            gate=promotion_gate(orig_summary,cal_summary)
            elapsed=time.perf_counter()-started
            status.update(label=f"Protected holdout test complete · {elapsed:.1f}s",state="complete")

        for k,v in {
            "cal_train_detail":train_detail,"cal_params":params,"cal_train_summary":train_summary,
            "cal_orig_detail":orig_detail,"cal_candidate_detail":cal_detail,
            "cal_orig_summary":orig_summary,"cal_candidate_summary":cal_summary,
            "cal_orig_pos":orig_pos,"cal_candidate_pos":cal_pos,
            "cal_weekly":pd.DataFrame(weekly_rows),"cal_gate":gate,"cal_runtime":elapsed,
            "cal_split":f"Weeks 1–{train_end} train / {holdout_start}–{max(weeks)} holdout"
        }.items(): st.session_state[k]=v
    except Exception as e:
        st.error(f"Calibration test failed: {e}")

orig_summary=st.session_state.get("cal_orig_summary")
cal_summary=st.session_state.get("cal_candidate_summary")
if orig_summary and cal_summary:
    st.divider()
    st.subheader(f"Untouched Holdout Results · {st.session_state.get('cal_split','')}")
    comparison=summary_comparison(orig_summary,cal_summary)
    st.dataframe(comparison,use_container_width=True,hide_index=True)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("MAE Change",f"{cal_summary['mae']-orig_summary['mae']:+.2f} DKFP")
    c2.metric("Bias Change",f"{cal_summary['bias']-orig_summary['bias']:+.2f} DKFP")
    c3.metric("90% Coverage",f"{orig_summary['inside_90']:.1f}% → {cal_summary['inside_90']:.1f}%")
    c4.metric("Holdout Players",f"{cal_summary['matched_players']:,}")

    gate=st.session_state.get("cal_gate",{})
    checks=gate.get("checks",{})
    if gate.get("pass"):
        st.success("V2.1 CANDIDATE PASSES this holdout gate. This is evidence to continue validating it — not permission to replace the live engine yet.")
    else:
        st.warning("V2.1 CANDIDATE DOES NOT PASS the holdout gate. Keep live V2 unchanged and revise the calibration approach before promotion.")
    if checks:
        check_df=pd.DataFrame([{"Gate Check":k,"Pass":bool(v)} for k,v in checks.items()])
        st.dataframe(check_df,use_container_width=True,hide_index=True)

    st.subheader("Parameters Learned From Training Weeks Only")
    st.dataframe(st.session_state.get("cal_params"),use_container_width=True,hide_index=True)
    st.caption("Mean Bias Correction shifts the simulated position mean down when training V2 ran high. Spread Multiplier widens or narrows player distributions. Holdout outcomes never participate in fitting these values.")

    st.subheader("Holdout Position Comparison")
    op=st.session_state.get("cal_orig_pos",pd.DataFrame()).copy(); cp=st.session_state.get("cal_candidate_pos",pd.DataFrame()).copy()
    if not op.empty and not cp.empty:
        op.insert(1,"Model","V2 Original"); cp.insert(1,"Model","V2.1 Candidate")
        st.dataframe(pd.concat([op,cp],ignore_index=True),use_container_width=True,hide_index=True)

    weekly=st.session_state.get("cal_weekly")
    if weekly is not None and not weekly.empty:
        st.subheader("Holdout Week-by-Week")
        st.dataframe(weekly,use_container_width=True,hide_index=True)

    st.caption(f"Runtime: {float(st.session_state.get('cal_runtime',0)):.1f}s. Live Football Engine V2 was not modified by this experiment.")
else:
    st.caption("Run the protected test to compare original V2 against a training-derived V2.1 candidate on untouched weeks.")

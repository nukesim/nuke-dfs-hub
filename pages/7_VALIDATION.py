import time
import pandas as pd
import streamlit as st

from nuke_sim import prepare_slate
from nuke_football_v2 import simulate_player_matrix_v2
from nuke_validation import prepare_actuals, build_validation, validation_summary

st.set_page_config(page_title="NUKE Validation Lab",page_icon="🧪",layout="wide")
st.title("🧪 NUKE HISTORICAL VALIDATION LAB")
st.caption("Backtest Football Engine V2 against completed DraftKings NFL slates. This page does not change the live SIM; it measures where the model is accurate, too high, too low, or too narrow/wide.")

with st.expander("What you need",expanded=True):
    st.markdown("""
Upload **two files from the same historical slate**:

1. **DraftKings salary CSV** from before the games started.
2. **Actual player results CSV** containing player name (or DraftKings ID) and actual DraftKings fantasy points.

The results file can use common columns such as `Name` / `Player` and `DKFP` / `FPTS` / `Fantasy Points`. If NUKE cannot recognize them, you can map the columns below.
""")

c1,c2=st.columns(2)
with c1:
    salary_file=st.file_uploader("Historical DraftKings salary CSV",type=["csv"],key="validation_salary")
with c2:
    actual_file=st.file_uploader("Actual historical player results CSV",type=["csv"],key="validation_actual")

if salary_file is None or actual_file is None:
    st.info("Upload both historical files to run a validation slate.")
    st.stop()

try:
    salary_raw=pd.read_csv(salary_file)
    actual_raw=pd.read_csv(actual_file)
    players=prepare_slate(salary_raw)
except Exception as e:
    st.error(f"Could not read the historical slate: {e}")
    st.stop()

st.subheader("Actual-results column mapping")
cols=list(actual_raw.columns)
none="— none —"
name_candidates=[c for c in ["Name","Player","Player Name","name","player"] if c in cols]
points_candidates=[c for c in ["Actual DKFP","DKFP","FPTS","Fantasy Points","FantasyPoints","Points","Actual Points","Score"] if c in cols]
id_candidates=[c for c in ["ID","Id","id","player_id","Player ID"] if c in cols]

m1,m2,m3=st.columns(3)
name_col=m1.selectbox("Player name column",[none]+cols,index=([none]+cols).index(name_candidates[0]) if name_candidates else 0)
points_col=m2.selectbox("Actual DK points column",[none]+cols,index=([none]+cols).index(points_candidates[0]) if points_candidates else 0)
id_col=m3.selectbox("DraftKings ID column (optional)",[none]+cols,index=([none]+cols).index(id_candidates[0]) if id_candidates else 0)

universes=st.slider("Validation football universes",200,3000,500,100,help="More universes give smoother distribution estimates but take longer. 500 is enough for a first calibration pass.")
seed=st.number_input("Validation seed",1,2147483646,2026,1)

if st.button("🧪 RUN HISTORICAL VALIDATION",type="primary",use_container_width=True):
    if points_col==none or (name_col==none and id_col==none):
        st.error("Choose the actual DK points column and either a player-name or DraftKings-ID column.")
        st.stop()
    try:
        actuals=prepare_actuals(actual_raw,name_col=None if name_col==none else name_col,points_col=points_col,id_col=None if id_col==none else id_col)
        started=time.perf_counter()
        with st.status("Running historical validation...",expanded=True) as status:
            st.write(f"Simulating {universes:,} projection-free football universes...")
            matrix=simulate_player_matrix_v2(players,int(universes),int(seed))
            st.write("Matching historical results and calculating calibration...")
            detail=build_validation(players,matrix,actuals)
            summary,pos=validation_summary(detail)
            elapsed=time.perf_counter()-started
            status.update(label=f"Validation complete · {elapsed:.1f}s",state="complete")
        st.session_state["validation_detail"]=detail
        st.session_state["validation_summary"]=summary
        st.session_state["validation_position"]=pos
        st.session_state["validation_runtime"]=elapsed
        st.session_state["validation_slate_name"]=salary_file.name
    except Exception as e:
        st.error(f"Validation failed: {e}")

summary=st.session_state.get("validation_summary")
detail=st.session_state.get("validation_detail")
pos=st.session_state.get("validation_position")
if summary and detail is not None and not detail.empty:
    st.divider()
    st.subheader("Calibration Scorecard")
    a,b,c,d,e,f=st.columns(6)
    a.metric("Matched Players",f"{summary['matched_players']:,}")
    b.metric("Mean Absolute Error",f"{summary['mae']:.2f} DKFP")
    c.metric("Model Bias",f"{summary['bias']:+.2f} DKFP")
    d.metric("Inside 50% Range",f"{summary['inside_50']:.1f}%",help="A well-calibrated central 50% interval should contain roughly 50% of actual outcomes over many slates.")
    e.metric("Inside 80% Range",f"{summary['inside_80']:.1f}%",help="A well-calibrated 80% interval should contain roughly 80% of actual outcomes over many slates.")
    f.metric("Inside 90% Range",f"{summary['inside_90']:.1f}%",help="A well-calibrated 90% interval should contain roughly 90% of actual outcomes over many slates.")

    bias=summary['bias']
    if abs(bias)<=1.0:
        st.success("Overall scoring bias is reasonably centered on this slate. The more important test is whether this remains true across many historical slates.")
    elif bias>1:
        st.warning(f"NUKE ran high by {bias:.2f} DKFP per matched player on average for this slate.")
    else:
        st.warning(f"NUKE ran low by {abs(bias):.2f} DKFP per matched player on average for this slate.")

    st.subheader("Position Calibration")
    st.dataframe(pos,use_container_width=True,hide_index=True)

    st.subheader("Player-Level Calibration")
    position=st.selectbox("Position",["ALL"]+sorted(detail.Position.unique().tolist()))
    view=detail if position=="ALL" else detail[detail.Position.eq(position)]
    sort_by=st.selectbox("Sort players by",["Abs Error","Mean Error","Actual Percentile","Actual DKFP","Salary"])
    ascending=sort_by=="Mean Error"
    view=view.sort_values(sort_by,ascending=ascending)
    st.dataframe(view,use_container_width=True,hide_index=True)

    st.download_button("Download validation results CSV",detail.to_csv(index=False).encode("utf-8-sig"),"nuke_historical_validation.csv","text/csv")
    st.caption(f"Validation runtime: {float(st.session_state.get('validation_runtime',0)):.1f}s · Engine: Football Engine V2 · This evaluates distribution calibration, not future predictive certainty.")

    with st.expander("How to read this"):
        st.markdown("""
**MAE** tells us how far the simulated player mean was from the actual result. Lower is better, but NFL outcomes are noisy, so this should be compared across many slates rather than judged from one Sunday.

**Bias** tells us whether NUKE systematically scores players too high or too low.

**Inside 50 / 80 / 90%** tests whether the simulated ranges are calibrated. Across a large history, roughly 50% of actual scores should land inside NUKE's central 50% range, roughly 80% inside its central 80%, and roughly 90% inside its central 90%. If actual coverage is much lower, the engine is too confident/narrow. If much higher, it may be too wide.

**Actual Percentile** shows where the real outcome landed inside that player's NUKE distribution. A healthy model should eventually produce percentiles spread across the full 0–100 range rather than clustering at one end.
""")
else:
    st.caption("Historical validation results will appear here after the first run.")

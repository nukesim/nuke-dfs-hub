import time
import pandas as pd
import streamlit as st

from nuke_sim import prepare_slate
from nuke_football_v2 import simulate_player_matrix_v2
from nuke_validation import prepare_actuals, build_validation, validation_summary
from nuke_historical_data import load_nfldfs_2017, available_seasons, available_weeks, historical_week, SOURCE_NAME

st.set_page_config(page_title="NUKE Validation Lab",page_icon="🧪",layout="wide")
st.title("🧪 NUKE HISTORICAL VALIDATION LAB")
st.caption("Backtest Football Engine V2 against completed DraftKings NFL data. No historical files are required for the built-in dataset.")

@st.cache_data(ttl=86400,show_spinner=False)
def get_public_history():
    return load_nfldfs_2017()

mode=st.radio("Historical data source",["Automatic public data","Manual files"],horizontal=True)

players=None
actuals=None
validation_label=""

if mode=="Automatic public data":
    st.info("NUKE downloads a public historical DraftKings dataset automatically and uses the pre-game DK salary plus the player's actual DK fantasy points after the game.")
    try:
        with st.spinner("Loading historical DraftKings database..."):
            history=get_public_history()
    except Exception as e:
        st.error(f"Could not load the public historical dataset: {e}")
        st.caption("You can still use Manual files below if the upstream public source is temporarily unavailable.")
        st.stop()

    seasons=available_seasons()
    c1,c2,c3,c4=st.columns(4)
    season=c1.selectbox("Season",seasons,index=len(seasons)-1)
    weeks=available_weeks(history,season)
    week=c2.selectbox("Week",weeks,index=0)
    universes=c3.selectbox("Validation universes",[250,500,750,1000],index=1)
    seed=c4.number_input("Validation seed",1,2147483646,2026,1)

    hist=historical_week(history,season,week)
    if hist.empty:
        st.error("No historical players were found for that season/week.")
        st.stop()

    # Historical source is full-week DK salary/scoring data, which is suitable for
    # player-distribution calibration. It is not treated as a reconstructed Sunday-main contest.
    salary_raw=pd.DataFrame({
        "Name":hist["Name"],"Position":hist["Position"],"Team":hist["Team"],
        "Salary":hist["Salary"],"Game":hist["Game"],"Status":""
    })
    players=prepare_slate(salary_raw)
    actual_raw=pd.DataFrame({"Name":hist["Name"],"Actual DKFP":hist["Actual DK Points"]})
    actuals=prepare_actuals(actual_raw,name_col="Name",points_col="Actual DKFP")
    validation_label=f"{season} Week {week}"

    a,b,c,d=st.columns(4)
    a.metric("Historical Players",f"{len(players):,}")
    b.metric("Teams",players.Team.nunique())
    c.metric("Games",players.Game.nunique())
    d.metric("Source","Public DK history")
    st.caption(f"Source: {SOURCE_NAME}. Current automatic library: 2017 regular season. This dataset covers the full DK week, so this page validates player outcome distributions rather than reconstructing a specific Sunday-main contest field.")

else:
    with st.expander("Manual historical files",expanded=True):
        st.markdown("Upload a historical DraftKings salary CSV and a results CSV from the same slate. The results file needs player name (or DK ID) and actual DraftKings fantasy points.")
    c1,c2=st.columns(2)
    with c1:
        salary_file=st.file_uploader("Historical DraftKings salary CSV",type=["csv"],key="validation_salary")
    with c2:
        actual_file=st.file_uploader("Actual historical player results CSV",type=["csv"],key="validation_actual")
    if salary_file is None or actual_file is None:
        st.info("Upload both files, or switch to Automatic public data.")
        st.stop()
    try:
        salary_raw=pd.read_csv(salary_file); actual_raw=pd.read_csv(actual_file); players=prepare_slate(salary_raw)
    except Exception as e:
        st.error(f"Could not read the historical slate: {e}"); st.stop()

    cols=list(actual_raw.columns); none="— none —"
    name_candidates=[c for c in ["Name","Player","Player Name","name","player"] if c in cols]
    points_candidates=[c for c in ["Actual DKFP","DKFP","FPTS","Fantasy Points","FantasyPoints","Points","Actual Points","Score"] if c in cols]
    id_candidates=[c for c in ["ID","Id","id","player_id","Player ID"] if c in cols]
    m1,m2,m3,m4=st.columns(4)
    name_col=m1.selectbox("Player name column",[none]+cols,index=([none]+cols).index(name_candidates[0]) if name_candidates else 0)
    points_col=m2.selectbox("Actual DK points column",[none]+cols,index=([none]+cols).index(points_candidates[0]) if points_candidates else 0)
    id_col=m3.selectbox("DK ID column",[none]+cols,index=([none]+cols).index(id_candidates[0]) if id_candidates else 0)
    universes=m4.selectbox("Validation universes",[250,500,750,1000],index=1)
    seed=st.number_input("Validation seed",1,2147483646,2026,1)
    if points_col==none or (name_col==none and id_col==none):
        st.warning("Map the actual DK points column and either player name or DK ID.")
        st.stop()
    actuals=prepare_actuals(actual_raw,name_col=None if name_col==none else name_col,points_col=points_col,id_col=None if id_col==none else id_col)
    validation_label=salary_file.name

if st.button("🧪 RUN HISTORICAL VALIDATION",type="primary",use_container_width=True):
    try:
        started=time.perf_counter()
        with st.status("Running historical validation...",expanded=True) as status:
            st.write(f"1/2 · Simulating {int(universes):,} Football Engine V2 universes...")
            matrix=simulate_player_matrix_v2(players,int(universes),int(seed))
            st.write("2/2 · Matching actual outcomes and calculating calibration...")
            detail=build_validation(players,matrix,actuals)
            summary,pos=validation_summary(detail)
            elapsed=time.perf_counter()-started
            status.update(label=f"Validation complete · {elapsed:.1f}s",state="complete")
        for k,v in {
            "validation_detail":detail,"validation_summary":summary,"validation_position":pos,
            "validation_runtime":elapsed,"validation_slate_name":validation_label
        }.items(): st.session_state[k]=v
    except Exception as e:
        st.error(f"Validation failed: {e}")

summary=st.session_state.get("validation_summary")
detail=st.session_state.get("validation_detail")
pos=st.session_state.get("validation_position")
if summary and detail is not None and not detail.empty:
    st.divider(); st.subheader(f"Calibration Scorecard · {st.session_state.get('validation_slate_name','Historical Slate')}")
    a,b,c,d,e,f=st.columns(6)
    a.metric("Matched Players",f"{summary['matched_players']:,}")
    b.metric("Mean Absolute Error",f"{summary['mae']:.2f} DKFP")
    c.metric("Model Bias",f"{summary['bias']:+.2f} DKFP")
    d.metric("Inside 50% Range",f"{summary['inside_50']:.1f}%")
    e.metric("Inside 80% Range",f"{summary['inside_80']:.1f}%")
    f.metric("Inside 90% Range",f"{summary['inside_90']:.1f}%")

    target_text=f"Targets over many slates: 50% range ≈ 50%, 80% range ≈ 80%, 90% range ≈ 90%. Median actual percentile should trend toward ~50%."
    st.caption(target_text)
    bias=summary['bias']
    if abs(bias)<=1.0:
        st.success("Overall scoring bias is reasonably centered for this test. We still need many weeks before treating that as meaningful calibration.")
    elif bias>1:
        st.warning(f"NUKE simulated players {bias:.2f} DKFP too high on average for this test.")
    else:
        st.warning(f"NUKE simulated players {abs(bias):.2f} DKFP too low on average for this test.")

    st.subheader("Position Calibration")
    st.dataframe(pos,use_container_width=True,hide_index=True)

    st.subheader("Player-Level Calibration")
    p1,p2=st.columns(2)
    position=p1.selectbox("Position",["ALL"]+sorted(detail.Position.unique().tolist()))
    sort_by=p2.selectbox("Sort players by",["Abs Error","Mean Error","Actual Percentile","Actual DKFP","Salary"])
    view=detail if position=="ALL" else detail[detail.Position.eq(position)]
    view=view.sort_values(sort_by,ascending=(sort_by=="Mean Error"))
    st.dataframe(view,use_container_width=True,hide_index=True)
    st.download_button("Download validation results CSV",detail.to_csv(index=False).encode("utf-8-sig"),"nuke_historical_validation.csv","text/csv")
    st.caption(f"Validation runtime: {float(st.session_state.get('validation_runtime',0)):.1f}s · Engine: Football Engine V2 · Diagnostic calibration only; this does not imply contest profitability or future certainty.")

    with st.expander("How to read this"):
        st.markdown("""
**MAE** measures how far the simulated player mean was from the actual outcome. **Bias** tells us whether the engine systematically runs high or low. **Inside 50 / 80 / 90%** tests the width of NUKE's distributions. Across a large sample, those coverages should approach their stated percentages. **Actual Percentile** shows where the real result landed inside each player's simulated distribution.

One NFL week is noisy. The goal is to repeat this across many weeks, identify persistent position-level or distribution-level misses, and only then tune Football Engine V2.
""")
else:
    st.caption("Choose a historical week and run the validation. No file hunting required in Automatic public data mode.")

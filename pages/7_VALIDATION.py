import time
import pandas as pd
import streamlit as st
from nuke_nav import render_nav

from nuke_sim import prepare_slate
from nuke_football_v2 import simulate_player_matrix_v2
from nuke_validation import prepare_actuals, build_validation, validation_summary
from nuke_historical_data import (
    load_nfldfs_2017, available_seasons, available_weeks, historical_week,
    starter_aware_pool, SOURCE_NAME
)

st.set_page_config(page_title="NUKE Validation Lab",page_icon="🧪",layout="wide")
render_nav()
st.title("🧪 NUKE HISTORICAL VALIDATION LAB")
st.caption("Backtest Football Engine V2 against completed DraftKings NFL data. The recommended starter-aware lens uses only pre-game salary structure — never actual fantasy points — to approximate the roles NUKE models live.")

@st.cache_data(ttl=86400,show_spinner=False)
def get_public_history():
    return load_nfldfs_2017()


def make_week_inputs(hist):
    salary_raw=pd.DataFrame({
        "Name":hist["Name"],"Position":hist["Position"],"Team":hist["Team"],
        "Salary":hist["Salary"],"Game":hist["Game"],"Status":""
    })
    players=prepare_slate(salary_raw)
    actual_raw=pd.DataFrame({"Name":hist["Name"],"Actual DKFP":hist["Actual DK Points"]})
    actuals=prepare_actuals(actual_raw,name_col="Name",points_col="Actual DKFP")
    return players,actuals


def run_week(hist, universes, seed, week_value):
    players,actuals=make_week_inputs(hist)
    matrix=simulate_player_matrix_v2(players,int(universes),int(seed))
    detail=build_validation(players,matrix,actuals)
    if not detail.empty:
        detail.insert(0,"Week",int(week_value))
    return detail


mode=st.radio("Historical data source",["Automatic public data","Manual files"],horizontal=True)

players=None
actuals=None
validation_label=""
run_scope="Single week"
selected_weeks=[]
history=None
season=None
lens="Starter-aware (recommended)"

if mode=="Automatic public data":
    st.info("NUKE downloads the public historical DraftKings dataset automatically. For starter-aware validation, QB is limited to each team's highest-salaried QB; RB1-3, WR1-4, TE1-2 and DST are retained. This filter uses salary only, so no post-game result leaks into the model test.")
    try:
        with st.spinner("Loading historical DraftKings database..."):
            history=get_public_history()
    except Exception as e:
        st.error(f"Could not load the public historical dataset: {e}")
        st.stop()

    seasons=available_seasons()
    c1,c2,c3,c4=st.columns(4)
    season=c1.selectbox("Season",seasons,index=len(seasons)-1)
    weeks=available_weeks(history,season)
    run_scope=c2.selectbox("Backtest scope",["Single week","Full regular season"],index=1)
    universes=c3.selectbox("Universes per week",[250,500,750,1000],index=1)
    seed=c4.number_input("Base validation seed",1,2147483646,2026,1)

    d1,d2=st.columns([1,2])
    if run_scope=="Single week":
        week=d1.selectbox("Week",weeks,index=0)
        selected_weeks=[int(week)]
    else:
        selected_weeks=[int(w) for w in weeks]
        d1.metric("Weeks queued",len(selected_weeks))

    lens=d2.radio("Validation lens",["Starter-aware (recommended)","All salaried players"],horizontal=True)
    if lens=="All salaried players":
        st.warning("All-salaried mode includes backup QBs and deep bench players. Use it as a secondary diagnostic, not the primary live-engine calibration test.")

    preview=historical_week(history,season,selected_weeks[0])
    if lens.startswith("Starter-aware"):
        preview=starter_aware_pool(preview)
    a,b,c,d=st.columns(4)
    a.metric("Preview Players",f"{len(preview):,}")
    b.metric("Preview Teams",preview.Team.nunique())
    c.metric("Weeks to Test",len(selected_weeks))
    d.metric("Lens","Starter-aware" if lens.startswith("Starter-aware") else "All salaried")
    st.caption(f"Source: {SOURCE_NAME}. Current automatic library: 2017 regular season. This validates player outcome distributions, not a reconstructed Sunday-main contest field.")

else:
    with st.expander("Manual historical files",expanded=True):
        st.markdown("Upload a historical DraftKings salary CSV and a results CSV from the same slate. Manual mode currently runs one slate at a time.")
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
        weekly_rows=[]
        details=[]
        with st.status("Running historical validation...",expanded=True) as status:
            if mode=="Automatic public data":
                total=len(selected_weeks)
                for n,w in enumerate(selected_weeks,1):
                    st.write(f"{n}/{total} · {season} Week {w} · {int(universes):,} Football Engine V2 universes")
                    hist=historical_week(history,season,w)
                    if lens.startswith("Starter-aware"):
                        hist=starter_aware_pool(hist)
                    if hist.empty:
                        continue
                    detail_w=run_week(hist,universes,int(seed)+int(w),w)
                    if detail_w.empty:
                        continue
                    details.append(detail_w)
                    s,_=validation_summary(detail_w)
                    weekly_rows.append({
                        "Week":int(w),"Players":s["matched_players"],"MAE":round(s["mae"],2),"Bias":round(s["bias"],2),
                        "Inside 50%":round(s["inside_50"],1),"Inside 80%":round(s["inside_80"],1),"Inside 90%":round(s["inside_90"],1)
                    })
                detail=pd.concat(details,ignore_index=True) if details else pd.DataFrame()
                validation_label=(f"{season} Full Regular Season" if run_scope=="Full regular season" else f"{season} Week {selected_weeks[0]}") + (" · Starter-aware" if lens.startswith("Starter-aware") else " · All salaried")
            else:
                st.write(f"Simulating {int(universes):,} Football Engine V2 universes...")
                matrix=simulate_player_matrix_v2(players,int(universes),int(seed))
                detail=build_validation(players,matrix,actuals)
                weekly_rows=[]

            summary,pos=validation_summary(detail)
            elapsed=time.perf_counter()-started
            status.update(label=f"Validation complete · {elapsed:.1f}s",state="complete")

        weekly=pd.DataFrame(weekly_rows)
        for k,v in {
            "validation_detail":detail,"validation_summary":summary,"validation_position":pos,
            "validation_weekly":weekly,"validation_runtime":elapsed,"validation_slate_name":validation_label
        }.items(): st.session_state[k]=v
    except Exception as e:
        st.error(f"Validation failed: {e}")

summary=st.session_state.get("validation_summary")
detail=st.session_state.get("validation_detail")
pos=st.session_state.get("validation_position")
weekly=st.session_state.get("validation_weekly")
if summary and detail is not None and not detail.empty:
    st.divider(); st.subheader(f"Calibration Scorecard · {st.session_state.get('validation_slate_name','Historical Slate')}")
    a,b,c,d,e,f=st.columns(6)
    a.metric("Matched Players",f"{summary['matched_players']:,}")
    b.metric("Mean Absolute Error",f"{summary['mae']:.2f} DKFP")
    c.metric("Model Bias",f"{summary['bias']:+.2f} DKFP")
    d.metric("Inside 50% Range",f"{summary['inside_50']:.1f}%")
    e.metric("Inside 80% Range",f"{summary['inside_80']:.1f}%")
    f.metric("Inside 90% Range",f"{summary['inside_90']:.1f}%")

    st.caption("Calibration targets over large samples: central 50% ≈ 50%, central 80% ≈ 80%, central 90% ≈ 90%. Bias should trend toward 0 DKFP.")
    bias=summary['bias']
    if abs(bias)<=1.0:
        st.success("Overall scoring bias is within ±1 DKFP for this sample. Position-level and interval calibration still matter before changing the live engine.")
    elif bias>1:
        st.warning(f"NUKE simulated players {bias:.2f} DKFP too high on average for this sample.")
    else:
        st.warning(f"NUKE simulated players {abs(bias):.2f} DKFP too low on average for this sample.")

    if weekly is not None and not weekly.empty and len(weekly)>1:
        st.subheader("Week-by-Week Stability")
        st.dataframe(weekly,use_container_width=True,hide_index=True)
        st.caption("This is the key protection against overreacting to one strange NFL Sunday. We care about misses that persist across weeks.")

    st.subheader("Position Calibration")
    st.dataframe(pos,use_container_width=True,hide_index=True)

    st.subheader("Player-Level Calibration")
    p1,p2=st.columns(2)
    position=p1.selectbox("Position",["ALL"]+sorted(detail.Position.unique().tolist()))
    sort_by=p2.selectbox("Sort players by",["Abs Error","Mean Error","Actual Percentile","Actual DKFP","Salary"])
    view=detail if position=="ALL" else detail[detail.Position.eq(position)]
    view=view.sort_values(sort_by,ascending=(sort_by=="Mean Error"))
    st.dataframe(view,use_container_width=True,hide_index=True)

    c1,c2=st.columns(2)
    c1.download_button("Download player validation CSV",detail.to_csv(index=False).encode("utf-8-sig"),"nuke_historical_validation.csv","text/csv",use_container_width=True)
    if weekly is not None and not weekly.empty:
        c2.download_button("Download weekly summary CSV",weekly.to_csv(index=False).encode("utf-8-sig"),"nuke_weekly_validation_summary.csv","text/csv",use_container_width=True)
    st.caption(f"Validation runtime: {float(st.session_state.get('validation_runtime',0)):.1f}s · Engine: Football Engine V2 · Diagnostic calibration only; this does not imply contest profitability or future certainty.")

    with st.expander("Why starter-aware matters"):
        st.markdown("""
The historical salary file can contain backup quarterbacks and deep bench players who were priced by DraftKings but were not expected to play meaningful snaps. Comparing NUKE's live-starter model against all of those players makes the engine look artificially high — especially at QB.

The **starter-aware** lens fixes that without cheating: it uses only each player's pre-game DK salary rank within his own team and position. It never uses the player's actual fantasy points to decide who is included. The all-salaried lens remains available as a stress test.
""")
else:
    st.caption("Choose a historical scope and run the validation. For model tuning, use Starter-aware + Full regular season.")

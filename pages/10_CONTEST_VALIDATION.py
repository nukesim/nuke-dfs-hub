import pandas as pd
import streamlit as st

from nuke_contest_validation import (
    normalize_contests, normalize_results, normalize_ownership,
    contest_structure, ownership_summary, compare_modeled_ownership,
)
from nuke_public_contests import PUBLIC_CONTESTS, load_public_contest
from nuke_historical_dk import recover_contest_draftables

st.set_page_config(page_title="NUKE Contest Validation",page_icon="🏁",layout="wide")
st.title("🏁 NUKE CONTEST VALIDATION LAB")
st.caption("Validate the contest layer against real DraftKings fields, then recover the historical salary slate for blind NUKE backtesting when the archive supports it.")

source_mode=st.radio("Historical contest source",["Built-in public archive","Upload my own CSVs"],horizontal=True)
results=pd.DataFrame(); contests=pd.DataFrame(); ownership=pd.DataFrame(); modeled_file=None; source_note=""; cfg={}

if source_mode=="Built-in public archive":
    st.info("No files required. NUKE loads preserved public DraftKings standings archives directly from GitHub.")
    labels=list(PUBLIC_CONTESTS.keys())
    label=st.selectbox("Archived contest",labels,index=0)
    if st.button("🏁 LOAD HISTORICAL CONTEST",type="primary",use_container_width=True):
        try:
            with st.spinner("Loading and parsing the archived DraftKings field..."):
                results,ownership,cfg=load_public_contest(label)
            st.session_state["cv_public_results"]=results
            st.session_state["cv_public_ownership"]=ownership
            st.session_state["cv_public_label"]=label
            st.session_state["cv_public_cfg"]=cfg
        except Exception as e:
            st.error(f"Could not load the public archive: {e}")
    if st.session_state.get("cv_public_label")==label:
        results=st.session_state.get("cv_public_results",pd.DataFrame())
        ownership=st.session_state.get("cv_public_ownership",pd.DataFrame())
        cfg=st.session_state.get("cv_public_cfg",{})
        source_note=f"Public archive · {cfg.get('name','')} · contest {cfg.get('contest_id','')} · {cfg.get('date','')} · {cfg.get('source','')}"
    modeled_file=st.file_uploader("Optional: NUKE/player modeled ownership CSV",type=["csv"],key="cv_modeled_public")
else:
    st.info("Manual mode supports contests.csv, contestResults.csv, and contestOwnership.csv.")
    c1,c2,c3=st.columns(3)
    contest_file=c1.file_uploader("contests.csv",type=["csv"],key="cv_contests")
    results_file=c2.file_uploader("contestResults.csv",type=["csv"],key="cv_results")
    own_file=c3.file_uploader("contestOwnership.csv",type=["csv"],key="cv_ownership")
    modeled_file=st.file_uploader("Optional: NUKE/player modeled ownership CSV",type=["csv"],key="cv_modeled")
    if results_file is not None:
        try:
            results=normalize_results(pd.read_csv(results_file))
            contests=normalize_contests(pd.read_csv(contest_file)) if contest_file is not None else pd.DataFrame()
            ownership=normalize_ownership(pd.read_csv(own_file)) if own_file is not None else pd.DataFrame()
        except Exception as e:
            st.error(f"Could not parse contest files: {e}")
            st.stop()

if not results.empty:
    contest_ids=sorted(results.contest_id.dropna().astype(str).unique().tolist())
    selected=contest_ids[0] if len(contest_ids)==1 else st.selectbox("Contest",contest_ids)
    r=results[results.contest_id.eq(str(selected))].copy()
    o=ownership[ownership.contest_id.eq(str(selected))].copy() if not ownership.empty else pd.DataFrame()
    meta=contests[contests.contest_id.eq(str(selected))].copy() if not contests.empty else pd.DataFrame()

    if source_note:
        st.caption(source_note)

    s=contest_structure(r)
    a,b,c1,d,e,f=st.columns(6)
    a.metric("Entries Loaded",f"{s.get('entries',0):,}")
    b.metric("Winning Score",f"{s.get('winning_score',0):.2f}")
    c1.metric("Top 1% Cut",f"{s.get('top1_score',0):.2f}")
    d.metric("20% Cut",f"{s.get('cash20_score',0):.2f}")
    e.metric("Unique Lineups",f"{s.get('unique_lineups',0):,}")
    f.metric("Duplicate Entries",f"{s.get('duplicate_lineups',0):,}")

    if s.get("entries",0)<1000:
        st.warning("This archive has fewer than 1,000 valid entries. Treat it as a parser/diagnostic contest, not primary large-field validation.")
    else:
        dup_rate=100.0*s.get("duplicate_lineups",0)/max(1,s.get("entries",0))
        st.success(f"Large-field archive loaded: {s.get('entries',0):,} valid entries. {dup_rate:.1f}% of entries are involved in duplicated lineups.")

    if cfg:
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Contest",cfg.get("name","Unknown"))
        m2.metric("Entry Fee",f"${cfg.get('entry_fee',0):,.2f}")
        m3.metric("Advertised Prizes",f"${cfg.get('advertised_prizes',0):,.0f}")
        m4.metric("Slate Type",str(cfg.get("season_type","unknown")).title())

    st.subheader("Actual Field Results")
    cols=[x for x in ["place","points","payout","lineup","roster_size"] if x in r.columns]
    st.dataframe(r.sort_values(["place","points"],ascending=[True,False])[cols].head(250),use_container_width=True,hide_index=True)

    if not o.empty:
        st.subheader("Actual DraftKings Ownership")
        st.dataframe(ownership_summary(o),use_container_width=True,hide_index=True)
        st.dataframe(o.sort_values("drafted",ascending=False)[["player","pos","drafted","points"]].head(150),use_container_width=True,hide_index=True)

        if modeled_file is not None:
            try:
                modeled=pd.read_csv(modeled_file)
                detail,summary=compare_modeled_ownership(o,modeled)
                st.subheader("Modeled vs Actual Ownership")
                if summary:
                    x1,x2,x3,x4=st.columns(4)
                    x1.metric("Matched Players",f"{summary['matched_players']:,}")
                    x2.metric("Ownership MAE",f"{summary['mae']:.2f} pts")
                    x3.metric("Ownership Bias",f"{summary['bias']:+.2f} pts")
                    x4.metric("Correlation",f"{summary['corr']:.3f}")
                    st.dataframe(detail,use_container_width=True,hide_index=True)
            except Exception as e:
                st.error(f"Could not compare modeled ownership: {e}")

    st.divider()
    st.subheader("🕰️ Historical Slate Reconstruction")
    st.write("NUKE now attempts to recover the original DraftKings draft group and salary slate directly from DraftKings' public contest/draftables API. We do not fabricate historical salaries if DraftKings no longer retains them.")

    if st.button("RECOVER ORIGINAL DK SALARY SLATE",use_container_width=True):
        with st.spinner("Querying DraftKings historical contest and draftables endpoints..."):
            slate,recovery=recover_contest_draftables(selected)
        st.session_state[f"cv_recovery_{selected}"]=recovery
        st.session_state[f"cv_slate_{selected}"]=slate

    recovery=st.session_state.get(f"cv_recovery_{selected}")
    slate=st.session_state.get(f"cv_slate_{selected}",pd.DataFrame())
    if recovery:
        if recovery.get("recovered") and not slate.empty:
            st.success(f"Recovered the original DraftKings salary slate: {len(slate):,} draftable players. Draft group {recovery.get('draft_group_id','')}.")
            st.dataframe(slate.sort_values("salary",ascending=False) if "salary" in slate.columns else slate,use_container_width=True,hide_index=True)
            st.download_button("Download recovered historical slate",slate.to_csv(index=False).encode("utf-8"),f"DKSalaries_{selected}_recovered.csv","text/csv")
        else:
            st.warning(f"Exact salary slate could not be recovered from DraftKings: {recovery.get('error','historical data unavailable')}")

    st.subheader("Blind NUKE Backtest Status")
    if cfg.get("season_type")=="preseason":
        st.warning("This 15,060-entry archive is PRESEASON (Aug. 11, 2017). It is valid for field structure, ownership, duplication and rank-distribution testing, but Football Engine V2.1 was calibrated/validated on regular-season NFL. I am deliberately NOT calling a V2.1 preseason run a valid model backtest.")
    elif not slate.empty:
        st.success("This contest is eligible for the next blind V2.1 backtest because an exact salary slate is available and the slate type is compatible.")
    else:
        st.info("Blind V2.1 ranking remains blocked until the exact pregame salary slate is recovered. No actual ownership or final fantasy points will be fed into lineup generation because that would leak the answer into the test.")

    st.caption("Current result: this archive gives NUKE a legitimate 15,060-entry real-field target. The remaining requirement for a true outcome backtest is a regular-season contest with its exact historical DK salary slate. The recovery button above tests whether DraftKings still exposes that slate without inventing missing data.")
else:
    st.caption("Choose a built-in archive and click LOAD HISTORICAL CONTEST, or switch to manual CSV upload.")

import pandas as pd
import streamlit as st

from nuke_contest_validation import (
    normalize_contests, normalize_results, normalize_ownership,
    contest_structure, ownership_summary, compare_modeled_ownership,
)
from nuke_public_contests import PUBLIC_CONTESTS, load_public_contest

st.set_page_config(page_title="NUKE Contest Validation",page_icon="🏁",layout="wide")
st.title("🏁 NUKE CONTEST VALIDATION LAB")
st.caption("Validate the contest layer against real DraftKings contest exports: field scoring, duplication, ownership, payouts, and eventually NUKE ranking/ROI. Player Engine V2.1 validation is separate and already complete.")

source_mode=st.radio("Historical contest source",["Built-in public archive","Upload my own CSVs"],horizontal=True)

results=pd.DataFrame(); contests=pd.DataFrame(); ownership=pd.DataFrame(); modeled_file=None; source_note=""

if source_mode=="Built-in public archive":
    st.info("No files required. NUKE loads preserved public DraftKings standings archives directly from GitHub. These old exports combine the full contest field and player ownership in one CSV.")
    label=st.selectbox("Archived contest",list(PUBLIC_CONTESTS.keys()),index=1)
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
        source_note=f"Public archive · contest {cfg.get('contest_id','')} · {cfg.get('source','')}"
    modeled_file=st.file_uploader("Optional: NUKE/player modeled ownership CSV",type=["csv"],key="cv_modeled_public")
else:
    st.info("Manual mode supports the three CSVs produced by the DraftKings_Scraper format: contests.csv, contestResults.csv, and contestOwnership.csv.")
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
        st.warning("This archive has fewer than 1,000 valid entries. Treat it as a parser/diagnostic contest, not as primary large-field GPP validation.")
    else:
        st.success(f"Large-field archive loaded: {s.get('entries',0):,} valid DraftKings entries. This clears the 1,000-entry minimum for contest-structure testing.")

    if not meta.empty:
        st.subheader("Contest Metadata")
        show_cols=[x for x in ["name","entries","entry_fee","total_prizes","week","year","date"] if x in meta.columns]
        st.dataframe(meta[show_cols],use_container_width=True,hide_index=True)

    st.subheader("Actual Field Results")
    cols=[x for x in ["place","points","payout","lineup","roster_size"] if x in r.columns]
    st.dataframe(r.sort_values(["place","points"],ascending=[True,False])[cols].head(250),use_container_width=True,hide_index=True)

    if not o.empty:
        st.subheader("Actual DraftKings Ownership")
        os=ownership_summary(o)
        st.dataframe(os,use_container_width=True,hide_index=True)
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
                else:
                    st.warning("No player names matched between the modeled file and actual ownership file.")
            except Exception as e:
                st.error(f"Could not compare modeled ownership: {e}")

    st.subheader("What this validates now")
    st.markdown("""
- Actual field score distribution: winner, top-1%, median, and top-20% thresholds.
- Actual lineup duplication and unique-lineup counts.
- Actual player ownership by contest and position.
- Preserved historical lineups for every entry in the archive.
- Optional ownership-model accuracy against the real DraftKings field.

**Important:** these archived combined standings files do not preserve the original payout ladder, and contest-structure validation is not the same thing as validating NUKE Sim ROI. The next layer is reconstructing the exact historical salary slate, running V2.1 blind, and testing whether NUKE Score / Contest Rank rank the historically stronger lineups higher.
""")
else:
    st.caption("Choose a built-in archive and click LOAD HISTORICAL CONTEST, or switch to manual CSV upload.")

import pandas as pd
import streamlit as st

from nuke_contest_validation import (
    normalize_contests, normalize_results, normalize_ownership,
    contest_structure, ownership_summary, compare_modeled_ownership,
)

PUBLIC_ARCHIVE_URL = "https://raw.githubusercontent.com/rogerfitz/tutorials/master/draft_kings_contests_scrape/data/contest-standings-43293784.csv"

@st.cache_data(ttl=86400, show_spinner=False)
def load_public_archive():
    raw = pd.read_csv(PUBLIC_ARCHIVE_URL)
    # This older DK export combines standings and ownership in one file.
    results = pd.DataFrame({
        "contest_id": "43293784",
        "place": raw.get("Rank"),
        "entry_id": raw.get("EntryId"),
        "points": raw.get("Points"),
        "lineup": raw.get("Lineup"),
        "payout": 0.0,
    })
    ownership = pd.DataFrame({
        "contest_id": "43293784",
        "player": raw.get("Player"),
        "pos": "",
        "drafted": raw.get("%Drafted"),
        "points": raw.get("FPTS"),
    }).dropna(subset=["player"])
    return normalize_results(results), normalize_ownership(ownership)

st.set_page_config(page_title="NUKE Contest Validation",page_icon="🏁",layout="wide")
st.title("🏁 NUKE CONTEST VALIDATION LAB")
st.caption("Validate the contest layer against real DraftKings contest exports: field scoring, duplication, ownership, payouts, and eventually NUKE ranking/ROI. Player Engine V2.1 validation is separate and already complete.")

source = st.radio("Historical contest source", ["Built-in public archive", "Upload my own files"], horizontal=True)

results = pd.DataFrame(); contests = pd.DataFrame(); ownership = pd.DataFrame(); modeled_file = None
if source == "Built-in public archive":
    st.info("Built-in starter dataset: archived DraftKings NFL contest 43293784. The source file has 589 rows and contains actual standings, lineups, player ownership, and fantasy points. This is useful for contest-layer validation, but it is smaller than the large-field GPPs NUKE ultimately needs to validate against.")
    if st.button("🏁 LOAD ARCHIVED CONTEST", type="primary"):
        try:
            with st.spinner("Loading archived DraftKings contest..."):
                results, ownership = load_public_archive()
            st.session_state["public_contest_results"] = results
            st.session_state["public_contest_ownership"] = ownership
        except Exception as e:
            st.error(f"Could not load public archive: {e}")
    results = st.session_state.get("public_contest_results", pd.DataFrame())
    ownership = st.session_state.get("public_contest_ownership", pd.DataFrame())
else:
    st.info("Manual mode supports the three CSVs produced by the public DraftKings_Scraper project: contests.csv, contestResults.csv, and contestOwnership.csv.")
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
    selected=st.selectbox("Contest",contest_ids)
    r=results[results.contest_id.eq(str(selected))].copy()
    o=ownership[ownership.contest_id.eq(str(selected))].copy() if not ownership.empty else pd.DataFrame()
    meta=contests[contests.contest_id.eq(str(selected))].copy() if not contests.empty else pd.DataFrame()

    s=contest_structure(r)
    a,b,c1,d,e,f=st.columns(6)
    a.metric("Entries Loaded",f"{s.get('entries',0):,}")
    b.metric("Winning Score",f"{s.get('winning_score',0):.2f}")
    c1.metric("Top 1% Cut",f"{s.get('top1_score',0):.2f}")
    d.metric("20% Cut",f"{s.get('cash20_score',0):.2f}")
    e.metric("Unique Lineups",f"{s.get('unique_lineups',0):,}")
    f.metric("Duplicate Entries",f"{s.get('duplicate_lineups',0):,}")

    if not meta.empty:
        st.subheader("Contest Metadata")
        show_cols=[x for x in ["name","entries","entry_fee","total_prizes","week","year","date"] if x in meta.columns]
        st.dataframe(meta[show_cols],use_container_width=True,hide_index=True)

    st.subheader("Actual Field Results")
    cols=[x for x in ["place","points","payout","lineup","roster_size"] if x in r.columns]
    st.dataframe(r.sort_values(["place","points"],ascending=[True,False])[cols].head(589),use_container_width=True,hide_index=True)

    if not o.empty:
        st.subheader("Actual DraftKings Ownership")
        os=ownership_summary(o)
        st.dataframe(os,use_container_width=True,hide_index=True)
        own_cols=[x for x in ["player","pos","drafted","points"] if x in o.columns]
        st.dataframe(o.sort_values("drafted",ascending=False)[own_cols].head(150),use_container_width=True,hide_index=True)

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

    st.warning("Do not treat this 589-row archive as proof that NUKE is calibrated for large-field GPPs. It is our first real-field contest test bed while larger historical archives are recovered.")
else:
    st.caption("Load the built-in archived contest or switch to manual upload mode.")

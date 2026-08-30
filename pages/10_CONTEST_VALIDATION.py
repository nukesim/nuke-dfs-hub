import pandas as pd
import streamlit as st

from nuke_contest_validation import (
    normalize_contests, normalize_results, normalize_ownership,
    contest_structure, ownership_summary, compare_modeled_ownership,
)

st.set_page_config(page_title="NUKE Contest Validation",page_icon="🏁",layout="wide")
st.title("🏁 NUKE CONTEST VALIDATION LAB")
st.caption("Validate the contest layer against real DraftKings contest exports: field scoring, duplication, ownership, payouts, and eventually NUKE ranking/ROI. Player Engine V2.1 validation is separate and already complete.")

st.info("Best source format: the three CSVs produced by the public DraftKings_Scraper project — contests.csv, contestResults.csv, and contestOwnership.csv. DraftKings removes public contest data quickly, so this page is designed to preserve and analyze exports you collect.")

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

    contest_ids=sorted(results.contest_id.dropna().astype(str).unique().tolist())
    selected=st.selectbox("Contest",contest_ids)
    r=results[results.contest_id.eq(str(selected))].copy()
    o=ownership[ownership.contest_id.eq(str(selected))].copy() if not ownership.empty else pd.DataFrame()
    c=contests[contests.contest_id.eq(str(selected))].copy() if not contests.empty else pd.DataFrame()

    s=contest_structure(r)
    a,b,c1,d,e,f=st.columns(6)
    a.metric("Entries Loaded",f"{s.get('entries',0):,}")
    b.metric("Winning Score",f"{s.get('winning_score',0):.2f}")
    c1.metric("Top 1% Cut",f"{s.get('top1_score',0):.2f}")
    d.metric("20% Cash Cut",f"{s.get('cash20_score',0):.2f}")
    e.metric("Unique Lineups",f"{s.get('unique_lineups',0):,}")
    f.metric("Duplicate Entries",f"{s.get('duplicate_lineups',0):,}")

    if not c.empty:
        st.subheader("Contest Metadata")
        show_cols=[x for x in ["name","entries","entry_fee","total_prizes","week","year","date"] if x in c.columns]
        st.dataframe(c[show_cols],use_container_width=True,hide_index=True)

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
- Actual field score distribution: winner, top-1%, and cash thresholds.
- Actual lineup duplication and unique-lineup counts.
- Actual player ownership by contest and position.
- Actual payout results and contest metadata when supplied.
- Optional ownership-model accuracy against the real DraftKings field.

The next build will connect these historical contest files to a reconstructed historical salary slate and run NUKE V2.1 on that exact slate. That will let us test whether **NUKE Score / Contest Rank / Sim ROI actually rank historically strong lineups above weak ones**, without using the contest outcome when generating the rankings.
""")
else:
    st.caption("Upload at least contestResults.csv to begin. Add contests.csv and contestOwnership.csv for the full validation view.")

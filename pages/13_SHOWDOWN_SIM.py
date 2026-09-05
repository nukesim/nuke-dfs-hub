import pandas as pd
import streamlit as st

from nuke_nav import render_nav
from nuke_showdown import parse_showdown_salary_csv
from nuke_showdown_sim import (
    SCRIPT_NAMES, add_lineup_labels, build_portfolio, evaluate_candidates,
    exposure_table, generate_showdown_candidates, simulate_player_outcomes,
)

st.set_page_config(page_title="NUKE Showdown Sim", page_icon="⚡", layout="wide")
render_nav()
st.title("⚡ NUKE SHOWDOWN SIM")
st.caption("Projection-free DraftKings NFL single-game simulation · game scripts · Captain outcomes · portfolio generation")

upload=st.file_uploader("Upload DraftKings NFL Showdown salary CSV",type=["csv"],key="showdown_sim_upload")
if upload is None:
    st.info("Upload the raw DraftKings Showdown salary CSV to run the single-game simulator.")
    st.stop()
try:
    players,meta=parse_showdown_salary_csv(pd.read_csv(upload))
except Exception as exc:
    st.error(f"Could not read this Showdown slate: {exc}"); st.stop()

players=players[players["Auto Include"]].reset_index(drop=True)
team_a,team_b=meta["teams"]
m1,m2,m3,m4=st.columns(4)
m1.metric("Game",f"{team_a} vs {team_b}"); m2.metric("Active Players",len(players)); m3.metric("Format","1 CPT + 5 FLEX"); m4.metric("Cap","$50,000")
st.caption(meta["game_info"])

with st.expander("Simulation Settings",expanded=True):
    c1,c2,c3,c4=st.columns(4)
    n_sims=c1.selectbox("Game simulations",[2000,5000,10000],index=1)
    candidates=c2.selectbox("Candidate lineups",[3000,6000,12000],index=1)
    min_salary=c3.slider("Minimum salary",30000,50000,42000,500)
    portfolio_n=c4.selectbox("Portfolio lineups",[5,10,20,50,100,150],index=2)
    c5,c6=st.columns(2)
    max_player=c5.slider("Max player exposure",25,100,75,5)/100
    max_cpt=c6.slider("Max Captain exposure",10,100,35,5)/100

st.markdown("#### What NUKE is simulating")
st.caption("Balanced · Shootout · Low Scoring · each team controlling the game · Passing Spike · Rushing Control · Chaos. Player outcomes use DraftKings salary/FPPG as baseline signals plus correlated game, team and role volatility — no paid projections required.")

if st.button("☢️ RUN SHOWDOWN SIM",type="primary",use_container_width=True):
    with st.spinner("Simulating single-game outcomes and evaluating Showdown constructions..."):
        sims,scripts,base=simulate_player_outcomes(players,meta["teams"],n_sims=n_sims)
        cand=generate_showdown_candidates(players,max_candidates=candidates,min_salary=min_salary)
        results=evaluate_candidates(players,cand,sims,scripts)
        portfolio=build_portfolio(results,players,count=portfolio_n,max_player_pct=max_player,max_cpt_pct=max_cpt)
        st.session_state["showdown_sim_results"]=results
        st.session_state["showdown_sim_portfolio"]=portfolio
        st.session_state["showdown_sim_players"]=players
        st.session_state["showdown_sim_scripts"]=pd.Series(scripts).value_counts().to_dict()
    st.success(f"Showdown SIM complete · {n_sims:,} game outcomes · {len(cand):,} legal candidate lineups")

results=st.session_state.get("showdown_sim_results")
portfolio=st.session_state.get("showdown_sim_portfolio")
sim_players=st.session_state.get("showdown_sim_players")
if results is None or sim_players is None or results.empty:
    st.stop()

st.subheader("Top Simulated Lineups")
labeled=add_lineup_labels(results.head(250),sim_players)
show_cols=["CPT","FLEX1","FLEX2","FLEX3","FLEX4","FLEX5","Split","Salary","NUKE Score","Mean","Ceiling","P95","Top 1% Score"]
st.dataframe(labeled[show_cols].round(2),use_container_width=True,hide_index=True,column_config={"Salary":st.column_config.NumberColumn("Salary",format="$%d")})

st.subheader("Game-Script Leaders")
script_tabs=st.tabs(SCRIPT_NAMES)
for tab,script in zip(script_tabs,SCRIPT_NAMES):
    with tab:
        x=results.nlargest(20,script)
        x=add_lineup_labels(x,sim_players)
        st.dataframe(x[["CPT","FLEX1","FLEX2","FLEX3","FLEX4","FLEX5","Split","Salary",script]].round(2),use_container_width=True,hide_index=True)

st.subheader("NUKE Showdown Portfolio")
if portfolio is None or portfolio.empty:
    st.info("No portfolio could be built with the current exposure limits.")
else:
    p=add_lineup_labels(portfolio,sim_players)
    st.dataframe(p[show_cols].round(2),use_container_width=True,hide_index=True,column_config={"Salary":st.column_config.NumberColumn("Salary",format="$%d")})
    overall,captains=exposure_table(portfolio,sim_players)
    e1,e2=st.columns(2)
    with e1:
        st.markdown("#### Player Exposure"); st.dataframe(overall,use_container_width=True,hide_index=True)
    with e2:
        st.markdown("#### Captain Exposure"); st.dataframe(captains,use_container_width=True,hide_index=True)

    split_counts=p["Split"].value_counts().rename_axis("Construction").reset_index(name="Lineups")
    st.markdown("#### Construction Mix")
    st.dataframe(split_counts,use_container_width=True,hide_index=True)

st.info("Showdown SIM V1 intentionally ranks lineups by simulated outcome quality rather than contest payout simulation. The next layer is ownership/duplication leverage once we have a reliable public ownership signal.")

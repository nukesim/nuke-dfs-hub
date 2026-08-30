import streamlit as st
import pandas as pd

from dfs_platform import get_platform
from fanduel_slate import fanduel_slate_status, load_fanduel_slate, FD_SLATE_LABEL
from nuke_sim import prepare_slate

st.set_page_config(page_title="FanDuel NFL", page_icon="🔵", layout="wide")

cfg = get_platform("FD")
st.title("🔵 FanDuel NFL")
st.caption("FanDuel Classic support inside the NUKE DFS Hub — hand build, simulate, portfolio build, contest sim, exposure tools, and FanDuel export.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Salary Cap", f"${cfg.salary_cap:,}")
c2.metric("Roster Spots", "9")
c3.metric("Reception Scoring", "0.5 PPR")
c4.metric("Yardage Bonuses", "None")

st.markdown("### FanDuel slate")
status = fanduel_slate_status()
if status["available"]:
    try:
        raw = load_fanduel_slate()
        players = prepare_slate(raw, site="FD")
        a, b, c = st.columns(3)
        a.metric("Players", len(players))
        b.metric("Teams", players.Team.nunique())
        c.metric("Games", players.Game.nunique())
        st.success(f"Repository slate loaded automatically: **{FD_SLATE_LABEL}**")
    except Exception as e:
        st.error(f"The repository FanDuel slate exists but could not be parsed: {e}")
else:
    st.info("FanDuel mode is built and waiting for the official FanDuel salary CSV. Once that file is added to the repo, this page and the SIM will auto-load it just like DraftKings.")

upload = st.file_uploader("Preview a FanDuel NFL salary CSV", type=["csv"], key="fd_preview_upload")
if upload is not None:
    try:
        raw = pd.read_csv(upload)
        players = prepare_slate(raw, site="FD")
        a, b, c, d = st.columns(4)
        a.metric("Parsed Players", len(players))
        b.metric("Teams", players.Team.nunique())
        c.metric("Games", players.Game.nunique())
        d.metric("Top Salary", f"${int(players.Salary.max()):,}" if len(players) else "$0")
        if len(players):
            st.success("FanDuel CSV parses successfully. When this file is committed as data/fanduel_nfl_current.csv, it will become the automatic weekly FanDuel slate.")
            show_cols = [c for c in ["Position", "Name", "Team", "Game", "Salary", "ID", "Status"] if c in players.columns]
            st.dataframe(players[show_cols].head(30), use_container_width=True, hide_index=True)
        else:
            st.warning("The file opened, but no valid FanDuel NFL players were found. We will map the exact FanDuel schema when the official file is supplied.")
    except Exception as e:
        st.error(f"Could not parse this FanDuel file yet: {e}")

st.markdown("### Go to FanDuel tools")
col1, col2 = st.columns(2)
with col1:
    if st.button("🔵 OPEN FANDUEL SIM", use_container_width=True, type="primary"):
        st.session_state["dfs_site"] = "FD"
        st.switch_page("pages/6_SIM.py")
with col2:
    if st.button("🧩 OPEN FANDUEL HAND BUILDER", use_container_width=True):
        st.session_state["dfs_site"] = "FD"
        st.switch_page("app.py")

st.caption("DraftKings and FanDuel remain separate slate states because salaries and player IDs are site-specific. Vegas/game-environment data is shared.")

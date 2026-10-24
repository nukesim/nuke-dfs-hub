"""NUKE DFS landing page. NFL Hand Builder permanently retired."""
import streamlit as st
from nuke_nav import render_nav

st.set_page_config(page_title="NUKE DFS Hub", page_icon="☢️", layout="wide")
render_nav()
st.title("☢️ NUKE DFS Hub")
st.caption("NFL • NBA • PGA • NHL • UFC/MMA • Showdown")
st.markdown("### 🏈 NFL NUKE Simulator")
st.write("The manual NFL Hand Builder has been retired. NFL DFS lineups are created using the NUKE simulator's player pool, correlated slate simulations, contest simulations, and tournament portfolio builder.")
st.page_link("pages/14_NUKE_SIM.py", label="Open NFL Sim", icon="☢️", use_container_width=True)
st.divider()
st.markdown("### More simulators")
p1,p2,p3=st.columns(3)
with p1:
    st.page_link("pages/20_NBA_SIM.py", label="NBA Sim", icon="🏀")
    st.page_link("pages/13_SHOWDOWN_SIM.py", label="NFL Showdown", icon="⚡")
with p2:
    st.page_link("pages/15_PGA_SIM.py", label="PGA Sim", icon="⛳")
    st.page_link("pages/16_NHL_SIM.py", label="NHL Sim", icon="🏒")
with p3:
    st.page_link("pages/17_MMA_SIM.py", label="MMA 150-Max", icon="🥊")
    st.page_link("pages/19_UFC_SINGLE_ENTRY.py", label="UFC Single Entry", icon="🎯")

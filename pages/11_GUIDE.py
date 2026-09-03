import streamlit as st
from nuke_nav import render_nav

st.set_page_config(page_title="NUKE DFS Guide", page_icon="❓", layout="wide")
render_nav()

st.title("❓ NUKE DFS GUIDE")
st.caption("A quick guide to building, simulating, saving, and managing your NFL DFS lineups.")

st.markdown("### What is NUKE?")
st.write("NUKE is a free NFL DFS research, lineup-building, and simulation toolkit for DraftKings and FanDuel. Use the Lineup Builder when you want full manual control over your portfolio, or NUKE Sim when you want to test lineups across simulated football outcomes and tournament environments.")

c1,c2=st.columns(2,gap="large")
with c1:
    with st.container(border=True):
        st.markdown("### 🏈 Lineup Builder")
        st.write("Hand-build and manage the lineups you actually plan to play.")
        st.markdown("**Typical workflow**")
        st.markdown("1. Choose DraftKings or FanDuel.\n2. Review the weekly slate and betting environment.\n3. Build your Player Pool.\n4. Set your QB Plan.\n5. Build lineups.\n6. Save completed lineups to your portfolio.\n7. Review exposure and combinations.")
        st.info("BUILD lineups are drafts. A lineup does not become part of your portfolio until you save it under SAVED LINEUPS.")
        st.page_link("app.py",label="OPEN LINEUP BUILDER",icon="🏈",use_container_width=True)

with c2:
    with st.container(border=True):
        st.markdown("### ☢️ NUKE Sim")
        st.write("Generate candidate lineups, simulate NFL outcomes and contest environments, and build a diversified tournament portfolio.")
        st.markdown("**Typical workflow**")
        st.markdown("1. Choose DraftKings or FanDuel.\n2. Confirm the current slate.\n3. Adjust the player pool and role/usage assumptions.\n4. Set contest and portfolio controls.\n5. Run NUKE Sim.\n6. Review results, paths, exposures, and portfolio intelligence.\n7. Send the portfolio to the Lineup Builder when you want to work with it there.")
        st.info("NUKE Sim is designed to model ranges of outcomes, not predict one exact future result.")
        st.page_link("pages/6_SIM.py",label="OPEN NUKE SIM",icon="☢️",use_container_width=True)

st.divider()
st.markdown("### 💾 Save your work")
st.write("Use **Save workspace** when you want to stop and continue later. Download the workspace JSON file to your computer. When you return, upload that file and choose **Restore/Load workspace**.")
st.markdown("**Lineup Builder workspace:** restores your platform, player pool, QB plan, BUILD drafts, Saved Lineups portfolio, role adjustments, and related builder settings.\n\n**NUKE Sim workspace:** restores your SIM settings, player pool, Player Takes, portfolio controls, and completed simulation results saved in that workspace.")
st.warning("A workspace is a snapshot. If weekly slate data, odds, injuries, or other live inputs change after you save it, review the current information before entering contests.")

st.divider()
st.markdown("### DraftKings & FanDuel")
st.write("Platform salaries, player IDs, roster rules, and scoring are different. Keep the correct platform selected when building, simulating, restoring workspaces, and exporting lineups.")

st.divider()
st.markdown("### Important")
st.write("NUKE DFS is an independent fantasy sports research and lineup-building tool. It is not affiliated with or endorsed by DraftKings, FanDuel, or the NFL. Simulations, projections, ownership estimates, rankings, and other model outputs are estimates and do not guarantee outcomes or winnings. Users are responsible for complying with applicable fantasy sports laws, age requirements, contest rules, and platform terms in their jurisdiction. Play responsibly.")

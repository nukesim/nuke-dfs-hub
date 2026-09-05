import streamlit as st
from nuke_nav import render_nav

st.set_page_config(page_title="NUKE DFS Guide", page_icon="❓", layout="wide")
render_nav()

st.title("❓ NUKE DFS GUIDE")
st.caption("A quick guide to building, simulating, saving, and managing your NFL DFS lineups.")

st.markdown("### What is NUKE?")
st.write("NUKE is a free NFL DFS research, lineup-building, and simulation toolkit for DraftKings and FanDuel. Use the Lineup Builder when you want full manual control over your portfolio, NUKE Sim for full-slate tournament simulation, or NFL Showdown for single-game DraftKings and FanDuel contests.")

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
st.markdown("### ⚡ NFL Showdown — DraftKings & FanDuel")
st.write("NFL Showdown is NUKE's single-game simulation environment. It uses the current single-game player pool together with sportsbook totals, spreads, team totals, line movement, player-level controls, correlated game scripts, and portfolio construction rules to evaluate thousands of possible lineups.")

s1,s2=st.columns(2,gap="large")
with s1:
    with st.container(border=True):
        st.markdown("#### DraftKings Showdown")
        st.write("DraftKings uses a **6-player lineup** with **1 Captain (CPT) + 5 FLEX**. The Captain receives **1.5× fantasy points** and costs **1.5× salary**. NUKE applies the DraftKings **$50,000 salary cap** and uses the correct CPT/FLEX player IDs when creating the export file.")
with s2:
    with st.container(border=True):
        st.markdown("#### FanDuel Single Game")
        st.write("FanDuel uses a **6-player lineup** with **1 MVP + 5 AnyFLEX**. The MVP receives **1.5× fantasy points** and uses the platform's **1.5× MVP salary**. NUKE applies the FanDuel **$60,000 salary cap** and uses the correct FanDuel player IDs when creating the export file.")

st.markdown("#### Recommended Showdown workflow")
st.markdown("1. Select **DraftKings** or **FanDuel**.\n2. Review the current game, betting total, spread, team totals, and line movement.\n3. Review the player pool and make any Boost %, Min %, or Max % adjustments.\n4. Set your desired lineup-construction mix (5-1, 4-2, 3-3), salary range, exposure limits, simulation count, candidate count, and portfolio size.\n5. Run the Showdown SIM.\n6. Review the top simulated lineups, portfolio, player exposure, CPT/MVP exposure, and construction mix.\n7. Download the platform-specific CSV when you are satisfied with the portfolio.")

st.info("**Important — portfolio size and construction settings work together.** Construction percentages are applied to the portfolio size selected when the simulation is run. If you materially change the requested portfolio size — for example, from 20 lineups to 150 — after setting a construction target such as 25% 5-1, run the Showdown SIM again. This allows NUKE to generate and evaluate a candidate pool sized for the new portfolio and gives the construction and exposure targets enough eligible lineups to be applied properly. Changes to the construction mix that keep the same portfolio size can be applied with **APPLY MIX & REBUILD PORTFOLIO** without rerunning the football simulations, provided the existing candidate results can support the requested mix.")

st.warning("Think of the completed Showdown SIM as the candidate universe for that run. Rebuilding can reorganize that existing universe, but increasing the number of lineups you want to build may require a larger candidate universe. When you change the requested portfolio size, rerun the SIM before finalizing or exporting your lineups.")

st.markdown("#### Showdown controls")
st.write("**Boost %** changes how strongly NUKE treats a player's baseline opportunity. **Min % / Max %** control portfolio exposure. **Max CPT/MVP exposure** limits how frequently a player can occupy the multiplier position. **Construction Mix** controls the desired team split across 5-1, 4-2, and 3-3 lineups. Salary controls can intentionally leave salary unused to create more differentiated constructions.")
st.write("NUKE models multiple correlated game environments — including balanced games, shootouts, low-scoring outcomes, team-control scripts, passing spikes, rushing-control outcomes, and chaos — rather than assuming the game unfolds one way.")
st.page_link("pages/13_SHOWDOWN_SIM.py",label="OPEN NFL SHOWDOWN",icon="⚡",use_container_width=True)

st.divider()
st.markdown("### 💾 Save your work")
st.write("Use **Save workspace** when you want to stop and continue later. Download the workspace JSON file to your computer. When you return, upload that file and choose **Restore/Load workspace**.")
st.markdown("**Lineup Builder workspace:** restores your platform, player pool, QB plan, BUILD drafts, Saved Lineups portfolio, role adjustments, and related builder settings.\n\n**NUKE Sim workspace:** restores your SIM settings, player pool, Player Takes, portfolio controls, and completed simulation results saved in that workspace.\n\n**Showdown workspace:** restores the selected platform, game-specific controls, simulation settings, construction preferences, and completed Showdown results for that game. DraftKings and FanDuel workspaces are kept platform-specific to prevent incompatible roster settings from being mixed.")
st.warning("A workspace is a snapshot. If weekly slate data, odds, injuries, or other live inputs change after you save it, review the current information before entering contests.")

st.divider()
st.markdown("### DraftKings & FanDuel")
st.write("Platform salaries, player IDs, roster rules, multiplier positions, salary caps, and scoring are different. Keep the correct platform selected when building, simulating, restoring workspaces, and exporting lineups. A portfolio generated for one platform should not be treated as a valid portfolio for the other.")

st.divider()
st.markdown("### Important")
st.write("NUKE DFS is an independent fantasy sports research and lineup-building tool. It is not affiliated with or endorsed by DraftKings, FanDuel, or the NFL. Simulations, projections, ownership estimates, rankings, and other model outputs are estimates and do not guarantee outcomes or winnings. Users are responsible for complying with applicable fantasy sports laws, age requirements, contest rules, and platform terms in their jurisdiction. Play responsibly.")

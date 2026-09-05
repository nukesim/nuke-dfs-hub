import streamlit as st

BUY_ME_A_COFFEE_URL = "https://buymeacoffee.com/nukedfs"
VENMO_URL = "https://account.venmo.com/u/Bryson-Anderson-1"


def _clean_player_takes(field):
    takes=dict(st.session_state.get("nuke_player_takes",{}) or {})
    cleaned={}
    for pid,pref in takes.items():
        p=dict(pref or {})
        if field=="boost":
            p["boost"]=0.0
        elif field=="min":
            p["min"]=0.0
        elif field=="max":
            p.pop("max",None)
        boost=float(p.get("boost",0.0) or 0.0)
        mn=float(p.get("min",0.0) or 0.0)
        has_max="max" in p
        if abs(boost)>1e-9 or mn>1e-9 or has_max:
            cleaned[int(pid)]={"boost":boost,"min":mn,**({"max":float(p["max"])} if has_max else {})}
    st.session_state["nuke_player_takes"]=cleaned
    st.session_state.pop("player_takes_editor",None)
    st.rerun()


def render_nav():
    # Shared public UI rule: show the whole value instead of Streamlit's default "..." truncation.
    st.markdown(
        """
        <style>
        div[data-testid="stMetricValue"],
        div[data-testid="stMetricValue"] *,
        div[data-testid="stMetricLabel"],
        div[data-testid="stMetricLabel"] * {
            max-width: none !important;
            width: auto !important;
            overflow: visible !important;
            text-overflow: clip !important;
            white-space: normal !important;
            overflow-wrap: anywhere !important;
        }
        div[data-testid="stMetric"] {
            overflow: visible !important;
            min-width: 0 !important;
        }
        div[data-testid="stMetric"] > div {
            overflow: visible !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.page_link("app.py", label="Lineup Builder", icon="🏈")
        st.page_link("pages/6_SIM.py", label="NUKE Sim", icon="☢️")
        st.page_link("pages/12_SHOWDOWN.py", label="NFL Showdown", icon="⚡")
        st.page_link("pages/11_GUIDE.py", label="Guide / About", icon="❓")

        if st.session_state.get("nuke_player_takes"):
            st.divider()
            st.markdown("### SIM Player Takes")
            st.caption("Clear every saved override in one click.")
            r1,r2,r3=st.columns(3)
            if r1.button("Boosts",key="nav_clear_boosts",use_container_width=True,help="Clear all player Boost values"):
                _clean_player_takes("boost")
            if r2.button("Min %",key="nav_clear_mins",use_container_width=True,help="Clear all player minimum exposure targets"):
                _clean_player_takes("min")
            if r3.button("Max %",key="nav_clear_maxes",use_container_width=True,help="Clear all player-specific maximums and return them to the global Max player % setting"):
                _clean_player_takes("max")

        st.divider()
        st.markdown("### ❤️ Support NUKE")
        st.caption("NUKE is completely free. If it helps your DFS process and you want to support continued development, any contribution is appreciated.")
        c1, c2 = st.columns(2)
        with c1:
            st.link_button("☕ Coffee", BUY_ME_A_COFFEE_URL, use_container_width=True)
        with c2:
            st.link_button("💸 Venmo", VENMO_URL, use_container_width=True)
        st.caption("Buy Me a Coffee supports one-time or monthly contributions.")

        st.divider()
        st.caption("NUKE DFS is an independent fantasy sports research and lineup-building tool. It is not affiliated with or endorsed by DraftKings, FanDuel, or the NFL. Simulations and model outputs are estimates and do not guarantee outcomes or winnings. Play responsibly and follow applicable laws and platform rules.")

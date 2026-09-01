import streamlit as st

BUY_ME_A_COFFEE_URL = "https://buymeacoffee.com/nukedfs"
VENMO_URL = "https://account.venmo.com/u/Bryson-Anderson-1"


def render_nav():
    with st.sidebar:
        st.page_link("app.py", label="Lineup Builder", icon="🏈")
        st.page_link("pages/6_SIM.py", label="NUKE Sim", icon="☢️")
        st.page_link("pages/7_VALIDATION.py", label="Model Performance", icon="📊")
        st.page_link("pages/8_CALIBRATION.py", label="Model Lab", icon="🧠")
        st.page_link("pages/9_GAUNTLET.py", label="Historical Testing", icon="🧪")
        st.page_link("pages/10_CONTEST_VALIDATION.py", label="Contest Testing", icon="🏆")
        st.divider()
        st.markdown("### Support NUKE")
        st.caption("NUKE is completely free. If it helps your DFS process and you want to support continued development, any contribution is appreciated.")
        c1, c2 = st.columns(2)
        with c1:
            st.link_button("☕ Coffee", BUY_ME_A_COFFEE_URL, use_container_width=True)
        with c2:
            st.link_button("💸 Venmo", VENMO_URL, use_container_width=True)
        st.caption("Buy Me a Coffee supports one-time or monthly contributions.")

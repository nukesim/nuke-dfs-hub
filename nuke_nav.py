import streamlit as st


def render_nav():
    with st.sidebar:
        st.page_link("app.py", label="Lineup Builder", icon="🏈")
        st.page_link("pages/6_SIM.py", label="NUKE Sim", icon="☢️")
        st.page_link("pages/7_VALIDATION.py", label="Model Performance", icon="📊")
        st.page_link("pages/8_CALIBRATION.py", label="Model Lab", icon="🧠")
        st.page_link("pages/9_GAUNTLET.py", label="Historical Testing", icon="🧪")
        st.page_link("pages/10_CONTEST_VALIDATION.py", label="Contest Testing", icon="🏆")
        st.divider()

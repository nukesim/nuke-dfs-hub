import streamlit as st


def apply_public_ui_fixes():
    """Small responsive UI fixes shared by public NUKE pages."""
    st.markdown(
        """
        <style>
        /* Streamlit metrics truncate long values with an ellipsis by default.
           NUKE favors readable labels/values, so let them wrap instead. */
        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] > div,
        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] > div {
            overflow: visible !important;
            text-overflow: clip !important;
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: normal !important;
        }

        /* Keep long button/tab/segmented-control text readable too. */
        .stButton button,
        .stDownloadButton button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-primary"],
        [data-testid="stSegmentedControl"] label,
        [data-baseweb="tab"] {
            white-space: normal !important;
            text-overflow: clip !important;
            overflow: visible !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

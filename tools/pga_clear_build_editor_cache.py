from pathlib import Path

# Triggered after the cache-reset workflow was added so the live PGA page is patched.
p = Path("pages/15_PGA_SIM.py")
s = p.read_text()


def replace_once(old, new, label):
    global s
    if old not in s:
        if new in s:
            return
        raise RuntimeError(f"Could not find expected PGA code for: {label}")
    s = s.replace(old, new, 1)


# Invalidate all existing PGA result/editor state so old 11K labels cannot survive
# after the salary-tier logic changed to cap at 10K.
replace_once(
    'PGA_PORTFOLIO_VERSION=6\nif st.session_state.get("pga_results_version") != PGA_PORTFOLIO_VERSION:\n    st.session_state.pop("pga_results",None)\n    st.session_state.pop("pga_run_settings",None)\n',
    'PGA_PORTFOLIO_VERSION=7\nif st.session_state.get("pga_results_version") != PGA_PORTFOLIO_VERSION:\n    st.session_state.pop("pga_results",None)\n    st.session_state.pop("pga_run_settings",None)\n    for key in list(st.session_state):\n        if key.startswith("pga_build_range_editor_"):\n            st.session_state.pop(key,None)\n',
    "portfolio version/session reset",
)

# Include the model version in the data-editor widget key so a future build-tier
# logic change cannot reuse stale row labels from an older Streamlit widget state.
replace_once(
    '            height=min(360,38+35*len(mix)),key=f"pga_build_range_editor_{seed}",\n',
    '            height=min(360,38+35*len(mix)),key=f"pga_build_range_editor_v{PGA_PORTFOLIO_VERSION}_{seed}",\n',
    "versioned build editor key",
)

p.write_text(s)

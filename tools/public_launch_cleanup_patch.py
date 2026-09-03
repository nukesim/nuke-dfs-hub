from pathlib import Path


def replace_once(path, old, new):
    p=Path(path)
    text=p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected text not found in {path}: {old[:80]!r}")
    p.write_text(text.replace(old,new,1),encoding="utf-8")

replace_once(
    "app.py",
    'st.caption("Slate Intel • Player Pool • QB Planning • Multi-Lineup Hand Building • Late Swap • Portfolio Control")',
    'st.caption("Slate Intel • Player Pool • QB Planning • Multi-Lineup Hand Building • Late Swap • Portfolio Control")\n\nwith st.expander("👋 NEW TO NUKE? QUICK START", expanded=False):\n    st.markdown("**1.** Choose your platform and review the slate  →  **2.** Build your Player Pool  →  **3.** Set your QB Plan  →  **4.** Build lineups  →  **5.** Save completed lineups  →  **6.** Review Saved Lineups / Exposure")\n    st.caption("BUILD lineups are drafts. They do not count toward your portfolio until you intentionally save them under SAVED LINEUPS. Use Save workspace in the sidebar when you want to leave and continue later.")\n    st.page_link("pages/11_GUIDE.py", label="Open the full NUKE Guide", icon="❓")'
)

replace_once(
    "pages/6_SIM.py",
    'st.caption("Workspace files contain your NUKE settings only — not account credentials or API keys.")',
    'st.caption("Workspace saves your current NUKE session, including settings, player pool, Player Takes, and completed SIM results. It never contains account credentials or API keys.")'
)

print("Public launch cleanup patch applied.")

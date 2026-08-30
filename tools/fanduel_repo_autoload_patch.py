# deployment trigger: repo-backed FanDuel slate
from pathlib import Path

p = Path("pages/6_SIM.py")
s = p.read_text()

if "from fanduel_slate import load_fanduel_slate" not in s:
    s = s.replace(
        "from dfs_platform import get_platform\n",
        "from dfs_platform import get_platform\nfrom fanduel_slate import load_fanduel_slate, has_fanduel_slate, FD_SLATE_LABEL\n",
        1,
    )

old = '''    elif site=="DK":
        raw_slate=load_default_slate()
        slate_source=SLATE_LABEL
        st.success(f"Loaded automatically: **{SLATE_LABEL}** · {len(raw_slate):,} players")
    else:
        st.info("FanDuel mode is ready. Upload the FanDuel NFL salary CSV for this slate to use exact FanDuel salaries and player IDs.")
        st.stop()'''
new = '''    elif site=="DK":
        raw_slate=load_default_slate()
        slate_source=SLATE_LABEL
        st.success(f"Loaded automatically: **{SLATE_LABEL}** · {len(raw_slate):,} players")
    elif has_fanduel_slate():
        raw_slate=load_fanduel_slate()
        slate_source=FD_SLATE_LABEL
        st.success(f"Loaded automatically: **{FD_SLATE_LABEL}** · {len(raw_slate):,} players")
    else:
        st.info("FanDuel mode is ready. Upload the FanDuel NFL salary CSV for this slate. Once we commit it as data/fanduel_nfl_current.csv, FanDuel will auto-load weekly just like DraftKings.")
        st.stop()'''
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise RuntimeError("Could not find FanDuel slate loading block")

p.write_text(s)
print("FanDuel repository autoload enabled")

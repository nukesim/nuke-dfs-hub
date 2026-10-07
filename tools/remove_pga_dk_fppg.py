from pathlib import Path

p = Path("pages/15_PGA_SIM.py")
s = p.read_text()


def replace_once(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"Could not find expected PGA code for: {label}")
    s = s.replace(old, new, 1)


# Clear cached results because the golfer model is changing materially.
replace_once("PGA_PORTFOLIO_VERSION=4", "PGA_PORTFOLIO_VERSION=5", "portfolio version")

# The PGA salary CSV only needs identifiers and salary. DraftKings' points-per-game
# field is intentionally ignored by this simulator.
replace_once(
    '    req={"Name","ID","Salary","AvgPointsPerGame"}\n',
    '    req={"Name","ID","Salary"}\n',
    "required CSV columns",
)
replace_once(
    '    d["AvgPointsPerGame"]=pd.to_numeric(d["AvgPointsPerGame"],errors="coerce").fillna(0.0)\n',
    "",
    "points-per-game parsing",
)

old_model = '''def base_projection(d):\n    f=d["AvgPointsPerGame"].to_numpy(float)\n    sal=d["Salary"].to_numpy(float)\n    fallback=np.interp(sal,[sal.min(),sal.max()],[42,78])\n    return np.where(f>0,f,fallback)\n\ndef ownership_estimate(d):\n    sal=d["Salary"].to_numpy(float)\n    form=base_projection(d)\n    z=.58*(sal-sal.mean())/(sal.std()+1e-9)+.42*(form-form.mean())/(form.std()+1e-9)\n    raw=np.exp(np.clip(z,-2.5,2.5))\n    # six roster spots across the field -> ownership sums to ~600%\n    return raw/raw.sum()*600\n'''
new_model = '''def salary_baseline(d):\n    sal=d["Salary"].to_numpy(float)\n    if not len(sal):\n        return np.array([],dtype=float)\n    lo=float(sal.min()); hi=float(sal.max())\n    if np.isclose(lo,hi):\n        return np.full(len(sal),60.0,dtype=float)\n    return np.interp(sal,[lo,hi],[42,78])\n\ndef ownership_estimate(d):\n    sal=d["Salary"].to_numpy(float)\n    z=(sal-sal.mean())/(sal.std()+1e-9)\n    raw=np.exp(np.clip(z,-2.5,2.5))\n    # six roster spots across the field -> ownership sums to ~600%\n    return raw/raw.sum()*600\n'''
replace_once(old_model, new_model, "projection and ownership model")

# Every former projection input now comes from salary only.
s = s.replace("base_projection(", "salary_baseline(")

replace_once(
    '    # salary/form-informed cut probability; missed cuts score much lower\n    strength=.55*(mu-mu.mean())/(mu.std()+1e-9)+.45*(salary-salary.mean())/(salary.std()+1e-9)\n',
    '    # Salary-tier-informed cut probability; missed cuts score much lower.\n    strength=(salary-salary.mean())/(salary.std()+1e-9)\n',
    "cut-strength model",
)

replace_once(
    'slate_key=(event,tuple(zip(golfers["ID"].astype(int),golfers["Salary"],golfers["AvgPointsPerGame"])))',
    'slate_key=(event,tuple(zip(golfers["ID"].astype(int),golfers["Salary"])))',
    "slate key",
)

replace_once(
    'st.caption("Include/exclude golfers, lock golfers, and set boosts or exposure limits. Automatic caps use salary tier, relative projection/cut strength, and estimated ownership. An explicit Max % overrides the automatic cap within the global limit; locks use 100%. In portfolios of 10+ lineups, every golfer used appears at least twice.")',
    'st.caption("Include/exclude golfers, lock golfers, and set boosts or exposure limits. Automatic caps use salary tier, simulated cut strength, and estimated ownership. An explicit Max % overrides the automatic cap within the global limit; locks use 100%. In portfolios of 10+ lineups, every golfer used appears at least twice.")',
    "golfer-pool caption",
)
replace_once(
    'editor=golfers[["ID","Name","Salary","AvgPointsPerGame","R1 Tee","R2 Tee","Wave","Weather","Weather Edge"]].copy()',
    'editor=golfers[["ID","Name","Salary","R1 Tee","R2 Tee","Wave","Weather","Weather Edge"]].copy()',
    "golfer-pool columns",
)
replace_once(
    '    disabled=["Auto Max %","ID","Name","Salary","AvgPointsPerGame","pOwn%","R1 Tee","R2 Tee","Wave","Weather","Weather Edge"],',
    '    disabled=["Auto Max %","ID","Name","Salary","pOwn%","R1 Tee","R2 Tee","Wave","Weather","Weather Edge"],',
    "disabled pool columns",
)
replace_once(
    '      "AvgPointsPerGame":st.column_config.NumberColumn("DK FPPG",format="%.1f"),\n',
    "",
    "DK points-per-game UI column",
)

# Hard guard: the live PGA page must contain no dependency on DraftKings' PPG field.
for forbidden in ("AvgPointsPerGame", "DK FPPG", "base_projection"):
    if forbidden in s:
        raise RuntimeError(f"PGA page still contains forbidden dependency: {forbidden}")

p.write_text(s)

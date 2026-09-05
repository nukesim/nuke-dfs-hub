from pathlib import Path

page = Path('pages/13_SHOWDOWN_SIM.py')
sim = Path('nuke_showdown_sim.py')
ws = Path('nuke_showdown_workspace.py')

p = page.read_text(encoding='utf-8')
old = '''    c1, c2, c3, c4 = st.columns(4)\n    n_sims = c1.selectbox("Game simulations", [2000, 5000, 10000], index=1, key="showdown_game_sims")\n    candidates = c2.selectbox("Candidate lineups", [3000, 6000, 12000], index=1, key="showdown_candidates")\n    min_salary = c3.slider("Minimum salary", 30000, 50000, 42000, 500, key="showdown_min_salary")\n    portfolio_n = c4.selectbox("Portfolio lineups", [5, 10, 20, 50, 100, 150], index=2, key="showdown_portfolio_n")\n'''
new = '''    c1, c2, c3, c4 = st.columns(4)\n    n_sims = c1.selectbox("Game simulations", [2000, 5000, 10000], index=1, key="showdown_game_sims")\n    candidates = c2.selectbox("Candidate lineups", [3000, 6000, 12000], index=1, key="showdown_candidates")\n    portfolio_n = c3.selectbox("Portfolio lineups", [5, 10, 20, 50, 100, 150], index=2, key="showdown_portfolio_n")\n    c4.caption("Salary range applies to every generated candidate lineup.")\n    s1, s2 = st.columns(2)\n    min_salary = s1.slider("Minimum salary", 30000, 50000, 42000, 500, key="showdown_min_salary")\n    max_salary = s2.slider(\n        "Maximum salary", 30000, 50000, 50000, 500, key="showdown_max_salary",\n        help="Set below $50,000 to intentionally leave salary unused and reduce duplicated Showdown constructions.",\n    )\n    if max_salary < min_salary:\n        st.warning("Maximum salary is below Minimum salary. Raise Max or lower Min before running the SIM.")\n'''
if old not in p:
    raise SystemExit('settings block not found')
p = p.replace(old, new, 1)
p = p.replace('''            max_candidates=candidates,\n            min_salary=min_salary,\n            seed=seed,\n''', '''            max_candidates=candidates,\n            min_salary=min_salary,\n            max_salary=max_salary,\n            seed=seed,\n''', 1)
page.write_text(p, encoding='utf-8')

s = sim.read_text(encoding='utf-8')
# Find function signature area by replacing the default seed argument sequence.
needle = '''def generate_showdown_candidates(players, max_candidates=6000, min_salary=42000, seed=1):'''
if needle in s:
    s = s.replace(needle, '''def generate_showdown_candidates(players, max_candidates=6000, min_salary=42000, max_salary=SHOWDOWN_SALARY_CAP, seed=1):''', 1)
else:
    # Support multiline signature if present.
    s = s.replace('''    min_salary=42000,\n    seed=1,''', '''    min_salary=42000,\n    max_salary=SHOWDOWN_SALARY_CAP,\n    seed=1,''', 1)
old_filter = '''        if salary > SHOWDOWN_SALARY_CAP or salary < int(min_salary):\n            continue'''
new_filter = '''        effective_max_salary = min(SHOWDOWN_SALARY_CAP, int(max_salary))\n        if salary > effective_max_salary or salary < int(min_salary):\n            continue'''
if old_filter not in s:
    raise SystemExit('salary filter not found')
s = s.replace(old_filter, new_filter, 1)
sim.write_text(s, encoding='utf-8')

w = ws.read_text(encoding='utf-8')
needle_ws = '    "showdown_min_salary",\n'
if '"showdown_max_salary"' not in w:
    if needle_ws not in w:
        raise SystemExit('workspace min salary key not found')
    w = w.replace(needle_ws, needle_ws + '    "showdown_max_salary",\n', 1)
ws.write_text(w, encoding='utf-8')

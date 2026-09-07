from pathlib import Path

# Engine: support players that must occupy FLEX/AnyFLEX and can never be CPT/MVP.
p = Path('nuke_showdown_sim.py')
s = p.read_text()
s = s.replace(
'def generate_showdown_candidates(players, max_candidates=12000, min_salary=42000, max_salary=SHOWDOWN_SALARY_CAP, salary_cap=SHOWDOWN_SALARY_CAP, seed=26):',
'def generate_showdown_candidates(players, max_candidates=12000, min_salary=42000, max_salary=SHOWDOWN_SALARY_CAP, salary_cap=SHOWDOWN_SALARY_CAP, seed=26, required_flex_indices=None):'
)
s = s.replace(
'    rng = np.random.default_rng(int(seed) + 7919)\n    base = np.array',
'    required_flex = tuple(sorted(set(int(i) for i in (required_flex_indices or []))))\n    if len(required_flex) > 5 or any(i < 0 or i >= n for i in required_flex):\n        return []\n\n    rng = np.random.default_rng(int(seed) + 7919)\n    base = np.array'
)
s = s.replace(
'    cpt_pool = np.argsort(-cpt_score)[:cpt_count].astype(np.int32)\n',
'    cpt_pool = np.argsort(-cpt_score)[:cpt_count].astype(np.int32)\n    if required_flex:\n        required_set = set(required_flex)\n        cpt_pool = np.asarray([i for i in cpt_pool if int(i) not in required_set], dtype=np.int32)\n        if cpt_pool.size == 0:\n            return []\n'
)
s = s.replace(
'        eligible, probs = cached[cpt]\n        flex_arr = rng.choice(eligible, size=5, replace=False, p=probs)\n',
'        eligible, probs = cached[cpt]\n        if required_flex:\n            required_arr = np.asarray(required_flex, dtype=np.int32)\n            remaining = 5 - len(required_flex)\n            if remaining:\n                mask = ~np.isin(eligible, required_arr)\n                optional = eligible[mask]\n                optional_probs = probs[mask]\n                if optional.size < remaining or optional_probs.sum() <= 0:\n                    continue\n                optional_probs = optional_probs / optional_probs.sum()\n                sampled = rng.choice(optional, size=remaining, replace=False, p=optional_probs)\n                flex_arr = np.concatenate([required_arr, sampled])\n            else:\n                flex_arr = required_arr.copy()\n        else:\n            flex_arr = rng.choice(eligible, size=5, replace=False, p=probs)\n'
)
p.write_text(s)

# UI: FanDuel-only AnyFLEX lock checkbox, validation, and pass locks to generator.
p = Path('pages/13_SHOWDOWN_SIM.py')
s = p.read_text()
s = s.replace(
'st.caption("Exclude removes a player from candidate generation entirely. Boost changes the simulated baseline for that player. Min/Max exposure are enforced in the generated portfolio. Leave 0 / 100 for no player-specific exposure rule.")',
'st.caption("Exclude removes a player from candidate generation entirely. On FanDuel, Lock AnyFLEX forces a player into an AnyFLEX spot in every generated lineup and prevents that player from being used at MVP. Boost changes the simulated baseline; Min/Max control portfolio exposure.")'
)
s = s.replace(
'                "Exclude": bool(cfg.get("exclude", False)),\n                "Boost %":',
'                "Exclude": bool(cfg.get("exclude", False)),\n                **({"Lock AnyFLEX": bool(cfg.get("lock_flex", False))} if site == "FanDuel" else {}),\n                "Boost %":'
)
s = s.replace(
'                "Exclude": st.column_config.CheckboxColumn("Exclude", width="small", help="Remove this player from all generated Showdown lineups."),\n                "Boost %":',
'                "Exclude": st.column_config.CheckboxColumn("Exclude", width="small", help="Remove this player from all generated Showdown lineups."),\n                **({"Lock AnyFLEX": st.column_config.CheckboxColumn("Lock AnyFLEX", width="small", help="FanDuel only: force this player into an AnyFLEX spot in every lineup; the player will not be used at MVP.")} if site == "FanDuel" else {}),\n                "Boost %":'
)
s = s.replace(
'            control_state[key] = {"exclude": bool(er["Exclude"]), "boost": float(er["Boost %"]), "min": mn, "max": mx}',
'            control_state[key] = {"exclude": bool(er["Exclude"]), "lock_flex": bool(er.get("Lock AnyFLEX", False)) if site == "FanDuel" else False, "boost": float(er["Boost %"]), "min": mn, "max": mx}'
)
s = s.replace(
'if len(players) < 6:\n    st.error("Fewer than 6 players remain after exclusions. Re-enable at least enough players to build a legal single-game lineup.")\n    st.stop()\n\nboosts =',
'if len(players) < 6:\n    st.error("Fewer than 6 players remain after exclusions. Re-enable at least enough players to build a legal single-game lineup.")\n    st.stop()\n\nlocked_flex_keys = {k for k, cfg in control_state.items() if site == "FanDuel" and bool((cfg or {}).get("lock_flex", False)) and k not in excluded_keys}\nlocked_flex_indices = [i for i, r in players.iterrows() if str(r["Player Key"]) in locked_flex_keys]\nif len(locked_flex_indices) > 5:\n    st.error("FanDuel lineups have only 5 AnyFLEX spots. Remove at least one AnyFLEX lock before running the SIM.")\n    st.stop()\nif locked_flex_indices:\n    locked_names = players.iloc[locked_flex_indices]["Name"].astype(str).tolist()\n    st.info("🔒 AnyFLEX lock: " + ", ".join(locked_names) + " — included at AnyFLEX in every generated FanDuel lineup and excluded from MVP.")\n\nboosts ='
)
s = s.replace(
'            salary_cap=salary_cap,\n            seed=seed,\n        )',
'            salary_cap=salary_cap,\n            seed=seed,\n            required_flex_indices=locked_flex_indices if site == "FanDuel" else None,\n        )'
)
p.write_text(s)

# Guide: document the new FanDuel lock behavior.
p = Path('pages/11_GUIDE.py')
s = p.read_text()
s = s.replace(
'**Boost %** changes how strongly NUKE treats a player\'s baseline opportunity. **Min % / Max %** control portfolio exposure.',
'**Exclude** removes a player from the candidate pool entirely. On FanDuel, **Lock AnyFLEX** forces a selected player into an AnyFLEX spot in every generated lineup and prevents that player from being used at MVP. This is useful when you want a specific RB or other player in every lineup but do not want them occupying the multiplier position. **Boost %** changes how strongly NUKE treats a player\'s baseline opportunity. **Min % / Max %** control portfolio exposure.'
)
p.write_text(s)

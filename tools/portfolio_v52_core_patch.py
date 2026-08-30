from pathlib import Path

p=Path('nuke_portfolio.py')
s=p.read_text(encoding='utf-8')
s=s.replace('PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V5.1"','PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V5.2"')

old='''    selected, path_counts, qb_counts, stack_counts = [], {}, {}, {}\n    player_counts, team_counts, game_counts, reasons = {}, {}, {}, {}\n'''
new='''    selected, path_counts, qb_counts, stack_counts = [], {}, {}, {}\n    player_counts, team_counts, game_counts, reasons = {}, {}, {}, {}\n    pair_counts, triple_counts = {}, {}\n\n    def lineup_pairs(lu):\n        return [tuple(sorted(x)) for x in itertools.combinations(sorted(set(lu)), 2)]\n\n    def lineup_triples(lu):\n        return [tuple(sorted(x)) for x in itertools.combinations(sorted(set(lu)), 3)]\n'''
if old not in s:
    raise SystemExit('selection state anchor not found')
s=s.replace(old,new,1)

old='''            concentration_penalty = 0.25 * max(0.0, qb_share - 0.20) + 0.10 * max(0.0, stack_share - 0.55)\n            redundancy_penalty = 0.10 * max(0.0, avg_overlap - 5.25) + 0.16 * max(0.0, worst_overlap - 6)\n\n            min_bonus = 0.0\n'''
new='''            concentration_penalty = 0.25 * max(0.0, qb_share - 0.20) + 0.10 * max(0.0, stack_share - 0.55)\n            redundancy_penalty = 0.10 * max(0.0, avg_overlap - 5.25) + 0.16 * max(0.0, worst_overlap - 6)\n\n            # V5.2 core diversity: individual exposures can look healthy while the same\n            # 2- and 3-player cores quietly repeat across many lineups. Penalize the\n            # marginal repetition of those cores without hard-banning strong combinations.\n            lu_pairs = lineup_pairs(lu)\n            lu_triples = lineup_triples(lu)\n            max_pair_repeat = max((pair_counts.get(core, 0) for core in lu_pairs), default=0)\n            max_triple_repeat = max((triple_counts.get(core, 0) for core in lu_triples), default=0)\n            pair_repeat_load = sum(max(0, pair_counts.get(core, 0) - 4) for core in lu_pairs)\n            triple_repeat_load = sum(max(0, triple_counts.get(core, 0) - 2) for core in lu_triples)\n            core_penalty = (\n                0.035 * pair_repeat_load\n                + 0.075 * triple_repeat_load\n                + 0.08 * max(0, max_pair_repeat - 10) ** 1.35\n                + 0.16 * max(0, max_triple_repeat - 6) ** 1.45\n            )\n\n            min_bonus = 0.0\n'''
if old not in s:
    raise SystemExit('penalty anchor not found')
s=s.replace(old,new,1)

old='''            score = float(base[i] + preference_adjustment[i] + min_bonus + path_adjustment - dominance_penalty - concentration_penalty - redundancy_penalty)\n            if score > best_score:\n                best_i, best_score = i, score\n                takes = sum(1 for pid in lu if abs(prefs.get(pid, {}).get("boost", 0.0)) > 1e-9 or prefs.get(pid, {}).get("min", 0.0) > 0)\n                best_reason = f"GPP upside | {path} | player takes {takes} | max overlap {worst_overlap}"\n'''
new='''            score = float(base[i] + preference_adjustment[i] + min_bonus + path_adjustment - dominance_penalty - concentration_penalty - redundancy_penalty - core_penalty)\n            if score > best_score:\n                best_i, best_score = i, score\n                takes = sum(1 for pid in lu if abs(prefs.get(pid, {}).get("boost", 0.0)) > 1e-9 or prefs.get(pid, {}).get("min", 0.0) > 0)\n                best_reason = f"GPP upside | {path} | player takes {takes} | max overlap {worst_overlap} | pair repeat {max_pair_repeat} | 3-core repeat {max_triple_repeat}"\n'''
if old not in s:
    raise SystemExit('score anchor not found')
s=s.replace(old,new,1)

old='''        for game in lineup_games[best_i]:\n            game_counts[game] = game_counts.get(game, 0) + 1\n        reasons[best_i] = best_reason\n'''
new='''        for game in lineup_games[best_i]:\n            game_counts[game] = game_counts.get(game, 0) + 1\n        for core in lineup_pairs(lineup_ids[best_i]):\n            pair_counts[core] = pair_counts.get(core, 0) + 1\n        for core in lineup_triples(lineup_ids[best_i]):\n            triple_counts[core] = triple_counts.get(core, 0) + 1\n        reasons[best_i] = best_reason\n'''
if old not in s:
    raise SystemExit('count update anchor not found')
s=s.replace(old,new,1)

old='''    out.attrs["path_soft_cap"] = 0.45\n    out.attrs["player_preferences"] = prefs\n'''
new='''    out.attrs["path_soft_cap"] = 0.45\n    out.attrs["player_preferences"] = prefs\n    out.attrs["max_pair_repeat"] = max(pair_counts.values(), default=0)\n    out.attrs["max_triple_repeat"] = max(triple_counts.values(), default=0)\n'''
if old not in s:
    raise SystemExit('attrs anchor not found')
s=s.replace(old,new,1)

old='''        "path_soft_cap": float(portfolio.attrs.get("path_soft_cap", 0.45)),\n    }\n'''
new='''        "path_soft_cap": float(portfolio.attrs.get("path_soft_cap", 0.45)),\n        "max_pair_repeat": int(portfolio.attrs.get("max_pair_repeat", 0)),\n        "max_triple_repeat": int(portfolio.attrs.get("max_triple_repeat", 0)),\n    }\n'''
if old not in s:
    raise SystemExit('summary stats anchor not found')
s=s.replace(old,new,1)

# Upgrade docstring wording if present.
s=s.replace('V5 keeps player takes, adds hard team/game lineup-incidence caps, and retains soft','V5.2 keeps player/team/game caps and adds soft repeated pair / 3-player core control while retaining soft')

p.write_text(s,encoding='utf-8')
print('patched nuke_portfolio.py to V5.2')

from pathlib import Path

# Portfolio engine: add nonlinear marginal penalty once a single slate path starts dominating.
p = Path('nuke_portfolio.py')
s = p.read_text(encoding='utf-8')
s = s.replace('PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V5"', 'PORTFOLIO_ENGINE_VERSION = "Portfolio Engine V5.1"')
old = '''            current_path = path_counts.get(path, 0)\n            if path in viable_paths:\n                saturation = current_path / target_per_path\n                path_adjustment = float(path_balance) * (0.55 * max(0.0, 1.0 - saturation) - 0.42 * max(0.0, saturation - 1.0) ** 2)\n            else:\n                path_adjustment = 0.0\n'''
new = '''            current_path = path_counts.get(path, 0)\n            if path in viable_paths:\n                saturation = current_path / target_per_path\n                path_adjustment = float(path_balance) * (0.55 * max(0.0, 1.0 - saturation) - 0.42 * max(0.0, saturation - 1.0) ** 2)\n            else:\n                path_adjustment = 0.0\n\n            # V5.1 marginal path-value control. This is deliberately a SOFT guard, not a\n            # forced quota: a dominant path can still earn more portfolio slots when its\n            # lineup quality is sufficiently better than alternatives. But after 45% of\n            # the portfolio, every additional lineup from that same path must overcome a\n            # rapidly increasing concentration cost.\n            next_path_share = (current_path + 1) / max(1, len(selected) + 1)\n            dominance_penalty = 0.0\n            if path in viable_paths and next_path_share > 0.45:\n                excess_units = (next_path_share - 0.45) / 0.10\n                dominance_penalty = float(path_balance) * (0.90 * excess_units + 0.50 * excess_units ** 2)\n'''
if old not in s:
    raise SystemExit('portfolio path scoring block not found')
s = s.replace(old, new, 1)
old2 = '''            score = float(base[i] + preference_adjustment[i] + min_bonus + path_adjustment - concentration_penalty - redundancy_penalty)\n'''
new2 = '''            score = float(base[i] + preference_adjustment[i] + min_bonus + path_adjustment - dominance_penalty - concentration_penalty - redundancy_penalty)\n'''
if old2 not in s:
    raise SystemExit('portfolio score line not found')
s = s.replace(old2, new2, 1)
old3 = '''    out.attrs["max_game_exposure"] = max_game_exposure\n    out.attrs["player_preferences"] = prefs\n'''
new3 = '''    out.attrs["max_game_exposure"] = max_game_exposure\n    out.attrs["path_soft_cap"] = 0.45\n    out.attrs["player_preferences"] = prefs\n'''
if old3 not in s:
    raise SystemExit('portfolio attrs block not found')
s = s.replace(old3, new3, 1)
old4 = '''    stats = {\n        "lineups": len(portfolio),\n'''
new4 = '''    dominant_path = str(path.index[0]) if len(path) else "UNKNOWN"\n    dominant_path_pct = float(100.0 * path.iloc[0] / len(portfolio)) if len(path) else 0.0\n    shares = path.to_numpy(float) / max(1, len(portfolio))\n    path_hhi = float(np.sum(shares ** 2)) if len(shares) else 0.0\n    stats = {\n        "lineups": len(portfolio),\n'''
if old4 not in s:
    raise SystemExit('portfolio summary stats block not found')
s = s.replace(old4, new4, 1)
old5 = '''        "unmet_minimums": portfolio.attrs.get("unmet_minimums", {}),\n    }\n'''
new5 = '''        "unmet_minimums": portfolio.attrs.get("unmet_minimums", {}),\n        "dominant_path": dominant_path,\n        "dominant_path_pct": dominant_path_pct,\n        "path_hhi": path_hhi,\n        "path_soft_cap": float(portfolio.attrs.get("path_soft_cap", 0.45)),\n    }\n'''
if old5 not in s:
    raise SystemExit('portfolio summary end block not found')
s = s.replace(old5, new5, 1)
p.write_text(s, encoding='utf-8')

# Streamlit: remove misleading metric deltas and show path-concentration diagnostics.
p = Path('pages/6_SIM.py')
s = p.read_text(encoding='utf-8')
old = '''        for col,p in zip(fcols,["RB","WR","TE"]):\n            col.metric(f"{p} in FLEX",f"{int(fmap.get(p,{}).get('Lineups',0)):,}",f"{float(fmap.get(p,{}).get('Exposure %',0)):.1f}%")\n'''
new = '''        for col,p in zip(fcols,["RB","WR","TE"]):\n            flex_lineups=int(fmap.get(p,{}).get("Lineups",0))\n            flex_pct=float(fmap.get(p,{}).get("Exposure %",0))\n            col.metric(f"{p} in FLEX",f"{flex_lineups:,}")\n            col.caption(f"{flex_pct:.1f}% exposure")\n'''
if old not in s:
    raise SystemExit('FLEX metric block not found')
s = s.replace(old, new, 1)
old2 = '''            st.markdown("#### Path Mix")\n            st.dataframe(portfolio_paths,use_container_width=True,hide_index=True)\n'''
new2 = '''            st.markdown("#### Path Mix")\n            dominant_path=str(portfolio_stats.get("dominant_path","UNKNOWN"))\n            dominant_pct=float(portfolio_stats.get("dominant_path_pct",0.0))\n            soft_cap_pct=100.0*float(portfolio_stats.get("path_soft_cap",0.45))\n            hhi=float(portfolio_stats.get("path_hhi",0.0))\n            pm1,pm2,pm3=st.columns(3)\n            pm1.metric("Dominant Path",dominant_path)\n            pm2.metric("Dominant Path Exposure",f"{dominant_pct:.1f}%")\n            pm3.metric("Path Concentration",f"{hhi:.3f}")\n            if dominant_pct>soft_cap_pct:\n                st.info(f"{dominant_path} is above the {soft_cap_pct:.0f}% soft concentration line. V5.1 does not hard-cap it; additional lineups must earn their slots by overcoming a rising marginal path penalty.")\n            st.dataframe(portfolio_paths,use_container_width=True,hide_index=True)\n'''
if old2 not in s:
    raise SystemExit('Path Mix block not found')
s = s.replace(old2, new2, 1)
old3 = '''**Portfolio engine:** {PORTFOLIO_ENGINE_VERSION}. Player Takes remain portfolio-only after the run. V5 adds team/game exposure caps, QB-stack exposure reporting, and Portfolio Health concentration diagnostics. Duplication is not part of portfolio selection.'''
new3 = '''**Portfolio engine:** {PORTFOLIO_ENGINE_VERSION}. Player Takes remain portfolio-only after the run. V5.1 adds marginal path-value concentration control on top of player/team/game caps, QB-stack exposure reporting, and Portfolio Health diagnostics. Path control is soft rather than a forced quota. Duplication is not part of portfolio selection.'''
if old3 in s:
    s = s.replace(old3, new3, 1)
p.write_text(s, encoding='utf-8')

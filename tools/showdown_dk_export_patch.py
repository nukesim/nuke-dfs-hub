from pathlib import Path

p = Path('pages/13_SHOWDOWN_SIM.py')
s = p.read_text(encoding='utf-8')

old_import = 'from nuke_showdown import parse_showdown_salary_csv\n'
new_import = 'from nuke_showdown import export_lineup_only_csv, parse_showdown_salary_csv\n'
if old_import not in s:
    raise SystemExit('showdown import anchor not found')
s = s.replace(old_import, new_import, 1)

anchor = '''    st.dataframe(\n        p[show_cols].round(2),\n        use_container_width=True,\n        hide_index=True,\n        column_config={"Salary": st.column_config.NumberColumn("Salary", format="$%d")},\n    )\n    overall, captains = exposure_table(portfolio, sim_players)\n'''
insert = '''    st.dataframe(\n        p[show_cols].round(2),\n        use_container_width=True,\n        hide_index=True,\n        column_config={"Salary": st.column_config.NumberColumn("Salary", format="$%d")},\n    )\n\n    st.markdown("#### 📤 DraftKings Export")\n    st.caption("Download this exact NUKE portfolio using the DraftKings CPT/FLEX player IDs from the current Showdown salary file.")\n    export_rows = []\n    export_error = None\n    sim_rows = sim_players.reset_index(drop=True)\n    try:\n        for _, lineup in portfolio.iterrows():\n            cpt_idx = int(lineup["_cpt"])\n            flex_idxs = list(map(int, lineup["_flex"]))\n            all_idxs = [cpt_idx] + flex_idxs\n            if len(all_idxs) != 6 or len(set(all_idxs)) != 6:\n                raise ValueError("A portfolio lineup does not contain 6 unique players.")\n            salary = int(lineup["Salary"])\n            if salary > 50000:\n                raise ValueError(f"A portfolio lineup exceeds the DraftKings salary cap: ${salary:,}.")\n            cpt_key = str(sim_rows.iloc[cpt_idx]["Player Key"])\n            flex_keys = [str(sim_rows.iloc[i]["Player Key"]) for i in flex_idxs]\n            export_rows.append({\n                "captain_key": cpt_key,\n                "flex_keys": flex_keys,\n                "salary": salary,\n            })\n\n        players_by_key = {\n            str(r["Player Key"]): r.to_dict()\n            for _, r in sim_rows.iterrows()\n        }\n        for rec in export_rows:\n            cpt = players_by_key.get(rec["captain_key"])\n            flex = [players_by_key.get(k) for k in rec["flex_keys"]]\n            if cpt is None or any(x is None for x in flex):\n                raise ValueError("A portfolio player could not be matched back to the current DraftKings salary file.")\n            if not str(cpt.get("CPT ID", "")).strip() or any(not str(x.get("FLEX ID", "")).strip() for x in flex):\n                raise ValueError("A DraftKings CPT/FLEX player ID is missing from the current salary file.")\n\n        dk_csv = export_lineup_only_csv(export_rows, players_by_key)\n    except Exception as exc:\n        export_error = str(exc)\n        dk_csv = None\n\n    if export_error:\n        st.error(f"DraftKings export is not ready: {export_error}")\n    else:\n        st.download_button(\n            "DOWNLOAD DK SHOWDOWN CSV",\n            data=dk_csv,\n            file_name="nuke_showdown_dk_portfolio.csv",\n            mime="text/csv",\n            type="primary",\n            use_container_width=True,\n            key="showdown_dk_export_download",\n        )\n        st.caption(f"{len(export_rows)} lineup{'s' if len(export_rows) != 1 else ''} ready for DraftKings upload.")\n\n    overall, captains = exposure_table(portfolio, sim_players)\n'''
if anchor not in s:
    raise SystemExit('portfolio display anchor not found')
s = s.replace(anchor, insert, 1)

p.write_text(s, encoding='utf-8')
print('patched DraftKings Showdown portfolio export')

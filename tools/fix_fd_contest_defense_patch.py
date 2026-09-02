from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
repls={
    'contest_roster=add_dk_roster_columns(sim_players,contest_results)': 'contest_roster=add_dk_roster_columns(sim_players,contest_results,site=site)',
    'portfolio_export=add_dk_roster_columns(sim_players,portfolio).drop(columns=["_indices"],errors="ignore")': 'portfolio_export=add_dk_roster_columns(sim_players,portfolio,site=site).drop(columns=["_indices"],errors="ignore")',
}
changed=False
for old,new in repls.items():
    if old in s:
        s=s.replace(old,new,1); changed=True
    elif new not in s:
        raise SystemExit(f'target not found: {old}')
if changed:
    p.write_text(s,encoding='utf-8')
    print('patched explicit platform roster dispatch in pages/6_SIM.py')
else:
    print('already patched')
# trigger after workflow exists

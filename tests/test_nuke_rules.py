import runpy

import numpy as np
import pandas as pd
import pytest

from nuke_rules import RuleError, compile_rules, rule_report, rule_sentence
from nuke_sim import prepare_slate, generate_lineups, _valid_lineup
from nuke_portfolio import build_portfolio
from nuke_workspace import workspace_bytes, load_workspace_bytes, apply_workspace


def rule(anchor='p0', members=None, minimum=1, maximum=1, share=100, key='r'):
    return dict(id=key, label=key, anchor_id=anchor, member_ids=members or ['p1'],
                min_count=minimum, max_count=maximum, share=share, enabled=True,
                names={'p0': 'Anchor', 'p1': 'Partner'})


def sample():
    # Four anchor lineups: three match, one misses. Four independent alternatives.
    p = pd.DataFrame([dict(ID=f'p{i}', Name=f'Player {i}', Team=f'T{i}', Game=f'G{i}',
                          Position='WR', Salary=4000) for i in range(72)])
    p.loc[0, 'Position'] = 'QB'
    lus = []
    for i in range(8):
        core = list(range(2 + 8*i, 10 + 8*i))
        if i < 3: core[0] = 1
        lus.append([0 if i < 4 else 68+i-4] + core)
    x = pd.DataFrame({'_indices': lus, 'QB': ['Anchor']*4 + [f'QB{i}' for i in range(4)],
                      'Strongest Path': ['Shootout']*4 + ['Ground']*4, 'Stack': ['QB+1']*8})
    for col in ['Sim ROI %', '1st %', 'Top 0.1%', 'Top 1%', 'Ceiling 95', 'NUKE Score', 'Path Score']:
        x[col] = np.arange(8., 0., -1)
    return p, x


def select(p, x, rules, **kwargs):
    defaults = dict(size=4, max_overlap=8, max_player_exposure=1, max_qb_exposure=1,
                    max_team_exposure=1, max_game_exposure=1, players=p,
                    player_preferences={0: {'min': 1, 'max': 1}}, lineup_rules=rules)
    defaults.update(kwargs)
    return build_portfolio(x, **defaults)


def test_anchor_is_separate_and_share_uses_conditional_denominator():
    p, x = sample()
    r = rule(share=75)
    report = rule_report(p, x._indices, [r]).iloc[0]
    assert report['Applies to'] == 4 and report['Match'] == 3 and report['Needed'] == 3
    assert report['Actual %'] == 75 and report.Status == 'Met'
    compiled = compile_rules(p, [r])[0]
    assert compiled.counts([0, 2]) == (True, False)
    assert compiled.counts([2, 3]) == (False, False)
    assert 'other player' in rule_sentence(r)


def test_exact_portfolio_share_and_exposure_are_both_enforced():
    p, x = sample()
    out = select(p, x, [rule(share=75)])
    assert len(out) == 4
    audit = rule_report(p, out._indices, [rule(share=75)]).iloc[0]
    assert audit['Match'] == 3 and audit['Applies to'] == 4
    assert out.attrs['rules_verified']
    with pytest.raises(RuleError, match='cannot fill'):
        select(p, x, [rule(share=100)])


def test_global_group_max_and_small_portfolio_rounding():
    p, x = sample()
    global_rule = rule(None, ['p0', 'p1'], 0, 1)
    out = select(p, x, [global_rule], size=4, player_preferences={})
    assert rule_report(p, out._indices, [global_rule]).iloc[0].Status == 'Met'
    # At least 75% of 3 means 3, not 2.
    report = rule_report(p, x._indices.iloc[[0, 1, 3]], [rule(share=75)]).iloc[0]
    assert report.Needed == 3 and report.Status == 'Unmet'


def test_ids_survive_row_reordering_and_exclusions_do_not_retarget():
    p, _ = sample()
    reordered = p.iloc[::-1].reset_index(drop=True)
    c = compile_rules(reordered, [rule()])[0]
    assert reordered.iloc[c.anchor].ID == 'p0'
    assert {reordered.iloc[i].ID for i in c.members} == {'p1'}
    with pytest.raises(RuleError, match='anchor is not'):
        compile_rules(p[p.ID.ne('p0')], [rule()])
    with pytest.raises(RuleError, match='only 0'):
        compile_rules(p[p.ID.ne('p1')], [rule()])
    with pytest.raises(RuleError, match='separate'):
        compile_rules(p, [rule(members=['p0'])])
    with pytest.raises(RuleError, match='conflicts'):
        compile_rules(p, [rule(minimum=0, maximum=0), rule(key='r2')])


def test_paused_rules_and_unused_anchor_are_explicit():
    p, x = sample()
    r = rule(); r['enabled'] = False
    assert compile_rules(p, [r]) == []
    report = rule_report(p, x._indices.iloc[4:], [rule()]).iloc[0]
    assert report.Status == 'Not used' and pd.isna(report['Actual %'])


def test_workspace_preserves_platform_rulebooks_and_old_workspace_clears_them():
    state = {'dfs_site': 'DK', 'nuke_lineup_rules_DK': [rule()], 'nuke_lineup_rules_FD': [rule(share=75)]}
    target = {}
    apply_workspace(target, load_workspace_bytes(workspace_bytes(state, 'Week 8')))
    assert target['nuke_lineup_rules_DK'] == state['nuke_lineup_rules_DK']
    assert target['nuke_lineup_rules_FD'][0]['share'] == 75
    apply_workspace(target, {'product': 'NUKE SIM', 'workspace_version': 2})
    assert target['nuke_lineup_rules_DK'] == [] and target['nuke_lineup_rules_FD'] == []


def test_rules_cannot_silently_relax_overlap_or_shrink_portfolio():
    p, x = sample()
    with pytest.raises(RuleError, match='Not enough'):
        select(p, x, [rule(share=75)], size=10)
    # Duplicate rosters may never occupy separate slots, even at max overlap 8.
    repeated = pd.concat([x.iloc[[0]]]*4, ignore_index=True)
    with pytest.raises(RuleError):
        select(p, repeated, [rule()], size=4)


@pytest.mark.parametrize('site,minimum,flex', [('DK', 47000, 'ANY'), ('FD', 50000, 'RB')])
def test_constructive_candidates_keep_rules_locks_salary_and_roster(site, minimum, flex):
    make = runpy.run_path('tests/test_nuke_sim_smoke.py')['_synthetic_slate']
    p = prepare_slate(make(), site=site)
    anchor = p[p.Position.eq('QB')].iloc[0]
    members = p[p.Team.eq(anchor.Team) & p.Position.isin(['WR', 'TE'])].head(4)
    r = rule(str(anchor.ID), members.ID.astype(str).tolist(), 1, 1)
    lineups = generate_lineups(p, n_lineups=30, min_salary=minimum, seed=26, site=site,
                              flex_position=flex, locked_indices=[int(anchor.name)], lineup_rules=[r])
    assert len(lineups) == 30
    assert rule_report(p, lineups, [r]).iloc[0].Status == 'Met'
    for lu in lineups:
        assert _valid_lineup(lu, p, minimum, site=site)
        assert int(anchor.name) in lu
        if flex == 'RB': assert int(p.iloc[lu].Position.eq('RB').sum()) == 3

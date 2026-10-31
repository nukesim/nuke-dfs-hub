from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from default_slate import load_default_slate
from fanduel_slate import load_fanduel_slate
from nuke_sim import prepare_slate
from nuke_workspace import RESULT_KEYS


ROOT = str(Path(__file__).resolve().parents[1])
APP = '''
import sys, types, runpy
sys.path.insert(0, ROOT)
nav = types.ModuleType('nuke_nav')
nav.render_nav = lambda: None
previous_nav = sys.modules.get('nuke_nav')
sys.modules['nuke_nav'] = nav
try:
    runpy.run_path(ROOT + '/pages/14_NUKE_SIM.py', run_name='__main__')
finally:
    if previous_nav is None: sys.modules.pop('nuke_nav', None)
    else: sys.modules['nuke_nav'] = previous_nav
'''.replace('ROOT', repr(ROOT))


@pytest.mark.parametrize('site', ['DK', 'FD'])
@pytest.mark.parametrize('position', ['QB', 'RB', 'WR', 'TE', 'DST'])
def test_position_bulk_buttons_remove_only_that_position_and_restore(site, position):
    raw = load_default_slate() if site == 'DK' else load_fanduel_slate()
    players = prepare_slate(raw, site=site)
    target_id = str(players.loc[players.Position.eq(position), 'ID'].iloc[0])
    other_id = str(players.loc[~players.Position.eq(position), 'ID'].iloc[0])
    target_pref = {'include': True, 'role': 'AUTO', 'usage': 1.35, 'lock': True}
    other_pref = {'include': False, 'role': 'BACKUP', 'usage': 0.8, 'lock': False}
    at = AppTest.from_string(APP, default_timeout=30)
    at.session_state['dfs_site'] = site
    at.session_state['nuke_pregame_pool'] = {target_id: target_pref, other_id: other_pref}
    at.run()
    assert not at.exception
    for key in RESULT_KEYS:
        at.session_state[key] = 'stale'

    next(b for b in at.button if b.label == f'🚫 REMOVE ALL {position}').click().run()
    assert not at.exception
    state = at.session_state['nuke_pregame_pool']
    ids = set(players.loc[players.Position.eq(position), 'ID'].astype(str))
    assert ids.issubset(state)
    assert all(not state[pid]['include'] and not state[pid]['lock'] for pid in ids)
    assert state[target_id]['usage'] == 1.35
    assert state[target_id]['role'] == 'AUTO'
    assert state[other_id] == other_pref
    assert set(state) == ids | {other_id}
    assert all(key not in at.session_state for key in RESULT_KEYS)
    editor = next(e for e in at.dataframe if e.key == f'current_pool_editor_{position}_1')
    assert len(editor.value) == len(ids)
    assert not editor.value['Include'].any()
    assert not editor.value['Locked'].any()

    # Re-add one player through the existing checkbox workflow after bulk removal.
    at.session_state[editor.key] = {
        'edited_rows': {0: {'Include': True}}, 'added_rows': [], 'deleted_rows': []
    }
    next(b for b in at.button if b.label == f'APPLY {position} PLAYER POOL').click().run()
    assert not at.exception
    assert sum(at.session_state['nuke_pregame_pool'][pid]['include'] for pid in ids) == 1

    next(b for b in at.button if b.label == f'✅ INCLUDE ALL {position}').click().run()
    assert not at.exception
    state = at.session_state['nuke_pregame_pool']
    assert all(state[pid]['include'] and not state[pid]['lock'] for pid in ids)
    assert state[target_id]['usage'] == 1.35
    assert state[other_id] == other_pref

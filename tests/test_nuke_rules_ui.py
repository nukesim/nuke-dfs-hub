from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = str(Path(__file__).resolve().parents[1])
APP = '''
import sys
sys.path.insert(0, ROOT)
from default_slate import load_default_slate
from nuke_sim import prepare_slate
from nuke_rules_ui import render_strategy_studio
import streamlit as st
st.set_page_config(layout='wide')
render_strategy_studio(prepare_slate(load_default_slate()), 'DK', 'Week 8')
'''.replace('ROOT', repr(ROOT))


def test_rule_builder_save_pause_edit_remove_and_plain_language():
    at = AppTest.from_string(APP, default_timeout=30).run()
    assert not at.exception
    assert 'Strategy Studio' in str([m.value for m in at.markdown]) or 'STRATEGY STUDIO' in str([m.value for m in at.markdown])
    # Choose a player group through the same table state emitted by the checkbox editor.
    editor = next(e for e in at.dataframe if 'Use' in e.value)
    key = editor.key
    at.session_state[key] = {'edited_rows': {0: {'Use': True}, 1: {'Use': True}}, 'added_rows': [], 'deleted_rows': []}
    at.run()
    assert not at.exception
    next(b for b in at.button if b.label == 'Save rule').click().run()
    assert not at.exception
    assert len(at.session_state['nuke_lineup_rules_DK']) == 1
    saved = at.session_state['nuke_lineup_rules_DK'][0]
    assert len(saved['member_ids']) == 2 and saved['share'] == 100
    next(b for b in at.button if b.label == 'Pause').click().run()
    assert not at.session_state['nuke_lineup_rules_DK'][0]['enabled']
    next(b for b in at.button if b.label == 'Edit').click().run()
    assert not at.exception
    next(b for b in at.button if b.label == 'Remove').click().run()
    assert not at.exception
    assert at.session_state['nuke_lineup_rules_DK'] == []


def test_quick_stack_template_is_editable_and_anchor_is_not_counted():
    at = AppTest.from_string(APP, default_timeout=30).run()
    next(b for b in at.button if b.label == 'QB + receiver').click().run()
    assert not at.exception
    draft = at.session_state['nr_draft_DK']
    assert draft['anchor_id'] and draft['member_ids']
    assert draft['anchor_id'] not in draft['member_ids']
    next(b for b in at.button if b.label == 'Save rule').click().run()
    assert not at.exception
    assert at.session_state['nuke_lineup_rules_DK'][0]['anchor_id'] == draft['anchor_id']


def test_full_nfl_page_runs_and_applies_rulebook_to_existing_candidates():
    app = '''
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
    at = AppTest.from_string(app, default_timeout=90).run()
    assert not at.exception
    next(b for b in at.button if b.label == 'QB + receiver').click().run()
    next(b for b in at.button if b.label == 'Save rule').click().run()
    assert not at.exception
    for widget in at.number_input:
        if widget.label == 'Candidate lineups': widget.set_value(100)
        elif widget.label == 'Football universes': widget.set_value(250)
        elif widget.label == 'Contest iterations': widget.set_value(50)
        elif widget.label == 'Portfolio size': widget.set_value(6)
    for widget in at.slider:
        if widget.label in ['Max player exposure %', 'Max QB exposure %', 'Max team exposure %', 'Max game exposure %']:
            widget.set_value(100)
    at.run()
    next(b for b in at.button if b.label == '☢️ RUN NUKE SIM').click().run(timeout=90)
    assert not at.exception
    assert len(at.session_state['nuke_portfolio']) == 6
    assert at.session_state['nuke_portfolio'].attrs['rules_verified']
    next(b for b in at.button if b.label == 'Pause').click().run()
    assert 'nuke_portfolio' not in at.session_state
    next(b for b in at.button if b.label == 'APPLY RULEBOOK TO PORTFOLIO').click().run(timeout=90)
    assert not at.exception
    assert len(at.session_state['nuke_portfolio']) == 6


def test_empty_search_and_scope_count_changes_do_not_crash():
    at = AppTest.from_string(APP, default_timeout=30).run()
    next(t for t in at.text_input if t.label == 'Player search').set_value('no-such-player-XYZ').run()
    assert not at.exception
    next(n for n in at.number_input if n.label == 'Maximum group players').set_value(9).run()
    control = next(c for c in at.get('segmented_control') if c.label == 'Rule scope')
    control.set_value('With a player').run()
    anchor = next(w for w in at.selectbox if 'Anchor player' in w.label)
    anchor.select_index(1).run()
    assert not at.exception

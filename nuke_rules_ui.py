"""NFL Strategy Studio: readable rule cards, a player board, and honest audits."""
import copy
import hashlib
import html
import math
from uuid import uuid4

import pandas as pd
import streamlit as st

from nuke_rules import RuleError, active_rules, compile_rules, rule_report, rule_sentence


def _clear_portfolio():
    for key in ['nuke_portfolio', 'nuke_portfolio_paths', 'nuke_portfolio_stats',
                'nuke_path_exposure', '_nuke_workspace_export_cache']:
        st.session_state.pop(key, None)


def _save_book(site, rules):
    st.session_state[f'nuke_lineup_rules_{site}'] = copy.deepcopy(rules)
    _clear_portfolio()
    st.session_state[f'nr_notice_{site}'] = 'Rulebook updated. Apply it to existing candidates below, or run a new simulation to create more matching lineups.'


def _new_draft(site, value=None):
    st.session_state[f'nr_draft_{site}'] = copy.deepcopy(value or {
        'id': uuid4().hex, 'anchor_id': None, 'member_ids': [], 'min_count': 1,
        'max_count': 1, 'share': 100, 'enabled': True, 'names': {},
    })
    st.session_state[f'nr_version_{site}'] = st.session_state.get(f'nr_version_{site}', 0) + 1


def _names(players):
    return {str(r.ID): str(r.Name) for r in players.itertuples()}


def _card(rule, lookup):
    e = html.escape
    share = float(rule.get('share', 100))
    badge = 'EVERY · 100%' if share == 100 else f'AT LEAST {share:g}%'
    if not rule.get('enabled', True): badge = 'PAUSED'
    anchor = rule.get('anchor_id')
    context = f"WITH {rule.get('names', {}).get(str(anchor), str(anchor))}" if anchor else 'ALL LINEUPS'
    chips = []
    for pid in rule.get('member_ids', []):
        row = lookup.get(str(pid))
        text = f'{row.Name} · {row.Position} · ${int(row.Salary):,}' if row is not None else rule.get('names', {}).get(str(pid), str(pid)) + ' · outside pool'
        chips.append(f'<span class="nr-chip">{e(text)}</span>')
    return f'''<div class="nr-card"><div class="nr-eyebrow">{e(context)}<span class="nr-badge">{badge}</span></div>
        <div class="nr-card-title">{e(str(rule.get('label') or 'Player group'))}</div>
        <div class="nr-sentence">{e(rule_sentence(rule))}</div><div class="nr-chips">{''.join(chips)}</div></div>'''


def game_map_svg(players, rules, portfolio=None):
    """Show only saved-rule links; node area encodes measured portfolio exposure."""
    e = html.escape
    teams = sorted(set(players.Team.astype(str)))
    focus = {str(x) for r in active_rules(rules) for x in [r.get('anchor_id'), *r.get('member_ids', [])] if x}
    # Exposures are joined by stable player ID by the caller, never by current row order.
    actual = players.get('_portfolio_pct', pd.Series(0., index=players.index)).to_dict()
    nodes = {}; circles = []; edges = []; headings = []; shown = []
    for j, team in enumerate(teams[:2]):
        group = players[players.Team.eq(team)].copy()
        group['_focus'] = group.ID.astype(str).isin(focus)
        group = group.sort_values(['_focus', 'Salary'], ascending=[False, False]).head(10)
        x = 200 if j == 0 else 610
        color = '#57c8ff' if j == 0 else '#b298ff'
        headings.append(f'<text x="{x}" y="38" text-anchor="middle" fill="{color}" font-size="18" font-weight="750">{e(team)}</text>')
        for k, (idx, row) in enumerate(group.iterrows()):
            y = 87 + k * 56
            pct = float(actual.get(idx, 0))
            r = 13 + 15 * math.sqrt(max(0, pct) / 100) if portfolio is not None else 18
            nodes[str(row.ID)] = (x, y)
            anchor = any(str(rule.get('anchor_id')) == str(row.ID) for rule in active_rules(rules))
            stroke = '#ffbc73' if anchor else color
            label_x = x - 40 if j == 0 else x + 40
            align = 'end' if j == 0 else 'start'
            shown.append(str(row.ID))
            tooltip = f'{row.Name} · {row.Position} · ${int(row.Salary):,}' + (f' · {pct:.1f}% of portfolio' if portfolio is not None else '')
            circles.append(f'<g><title>{e(tooltip)}</title><circle cx="{x}" cy="{y}" r="{r:.1f}" fill="{color}" fill-opacity=".18" stroke="{stroke}" stroke-width="2"/><text x="{x}" y="{y+4}" text-anchor="middle" fill="#f1f5ff" font-size="10" font-weight="700">{e(str(row.Position))}</text><text x="{label_x}" y="{y-3}" text-anchor="{align}" fill="#f1f5ff" font-size="12" font-weight="600">{e(str(row.Name))}</text><text x="{label_x}" y="{y+14}" text-anchor="{align}" fill="#9cabc2" font-size="10">${int(row.Salary):,} {f' · {pct:.1f}%' if portfolio is not None else ''}</text></g>')
    for rule in active_rules(rules):
        group = [str(pid) for pid in rule.get('member_ids', []) if str(pid) in nodes]
        anchor = str(rule.get('anchor_id') or '')
        pairs = [(anchor, pid) for pid in group] if anchor in nodes else [(group[i], group[i+1]) for i in range(len(group)-1)] if not anchor else []
        for a, b in pairs:
            x1, y1 = nodes[a]; x2, y2 = nodes[b]
            if x1 == x2:
                path = f'M {x1} {y1} Q {x1 + (95 if x1 < 400 else -95)} {(y1+y2)/2} {x2} {y2}'
            else:
                path = f'M {x1} {y1} C 375 {y1}, 435 {y2}, {x2} {y2}'
            dash = 'stroke-dasharray="5 5"' if float(rule.get('share', 100)) < 100 else ''
            edges.append(f'<path d="{path}" fill="none" stroke="#ffbc73" stroke-opacity=".45" stroke-width="1.5" {dash}><title>{e(rule_sentence(rule))}</title></path>')
    height = max(300, 115 + 56 * min(10, max([sum(players.Team.eq(t)) for t in teams[:2]], default=1)))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 810 {height}" style="width:100%;max-height:680px" role="img" aria-label="Player groups and saved rule connections"><rect width="810" height="{height}" rx="16" fill="#101827"/><line x1="405" y1="65" x2="405" y2="{height-25}" stroke="#243249" stroke-dasharray="3 7"/>{"".join(headings + edges + circles)}</svg>'
    return svg, max(0, len(players) - len(shown))


def render_strategy_studio(players, site, slate_label):
    key = f'nuke_lineup_rules_{site}'
    rules = copy.deepcopy(st.session_state.get(key, []))
    st.markdown('''<style>
    .nr-hero {background:linear-gradient(110deg,#101c2e,#16283b);border:1px solid #29435b;border-radius:16px;padding:24px 26px;margin:16px 0;color:#eff7ff}
    .nr-kicker {font-size:11px;letter-spacing:.18em;font-weight:800;color:#77ddcc;margin-bottom:7px}
    .nr-hero h2 {font-size:28px;margin:0 0 8px;color:#eff7ff;letter-spacing:-.025em}
    .nr-hero p {color:#bccbdc;font-size:14px;margin:0;line-height:1.6;max-width:850px}
    .nr-card {background:#111d2e;border:1px solid #304158;border-radius:13px;padding:19px 20px;margin:5px 0 9px;color:#edf5ff;min-height:190px}
    .nr-eyebrow {font-size:10px;letter-spacing:.1em;color:#b9cbdd;display:flex;gap:12px;justify-content:space-between;align-items:center}
    .nr-badge {background:#203b3d;color:#9ee9d9;border:1px solid #315957;border-radius:20px;padding:4px 8px;letter-spacing:.02em;white-space:nowrap}
    .nr-card-title {font-size:18px;font-weight:750;margin:13px 0 10px;color:#f3f7ff}
    .nr-sentence {font-size:14px;line-height:1.7;color:#dbe7f6}
    .nr-chips {display:flex;gap:6px;flex-wrap:wrap;margin-top:15px}
    .nr-chip {font-size:11px;background:#1b2c43;border:1px solid #354a66;color:#c9d8ec;padding:5px 8px;border-radius:6px}
    </style><div class="nr-hero"><div class="nr-kicker">NFL · STRATEGY STUDIO</div><h2>Build the story behind your lineups.</h2><p>Pair players. Choose your bring-backs. Limit combinations. Turn your ideas into clear rules, then see exactly how your portfolio follows them.</p></div>''', unsafe_allow_html=True)
    a, b, c = st.columns(3)
    a.metric('Active rules', len(active_rules(rules)))
    b.metric('Every-lineup rules', sum(float(r.get('share', 100)) == 100 for r in active_rules(rules)))
    c.metric('Percentage rules', sum(float(r.get('share', 100)) < 100 for r in active_rules(rules)))
    if st.session_state.get(f'nr_notice_{site}'):
        st.info(st.session_state[f'nr_notice_{site}'])
    if players.empty:
        st.info('Include players in the pool above to build rules. Your saved rules are kept.')
        return rules
    names = _names(players)
    lookup = {str(r.ID): r for r in players.itertuples()}
    games = sorted(players.Game.astype(str).unique())
    game = st.pills('Focus game', games, format_func=lambda g: g.split()[0].replace('@', ' @ '),
                    default=games[0], key=f'nr_game_{site}') or games[0]
    book_tab, map_tab, audit_tab = st.tabs(['Rulebook', 'Game map', 'Portfolio check'])
    with book_tab:
        with st.expander('＋ Create or edit a rule', expanded=not bool(rules) or st.session_state.get(f'nr_editor_open_{site}', False)):
            if f'nr_draft_{site}' not in st.session_state:
                _new_draft(site)
            t1, t2, t3 = st.columns(3)
            qbs = players[players.Game.eq(game) & players.Position.eq('QB') & players.auto_qb_eligible].sort_values('Salary', ascending=False)
            template = None
            if t1.button('QB + receiver', key=f'nr_template_stack_{site}', use_container_width=True, disabled=qbs.empty): template = 'stack'
            if t2.button('QB + bring-back', key=f'nr_template_back_{site}', use_container_width=True, disabled=qbs.empty): template = 'back'
            if t3.button('Limit a combination', key=f'nr_template_limit_{site}', use_container_width=True): template = 'limit'
            if template:
                d = {'id': uuid4().hex, 'enabled': True, 'share': 100, 'names': names,
                     'anchor_id': None, 'member_ids': [], 'min_count': 0, 'max_count': 1}
                if template != 'limit':
                    qb = qbs.iloc[0]
                    group = players[players.Game.eq(game) & players.Position.isin(['WR', 'TE'] if template == 'stack' else ['RB', 'WR', 'TE'])]
                    group = group[group.Team.eq(qb.Team) if template == 'stack' else group.Team.ne(qb.Team)].sort_values('Salary', ascending=False).head(3)
                    d.update(anchor_id=str(qb.ID), member_ids=group.ID.astype(str).tolist(), min_count=1,
                             label=f"{qb.Name} + {'receiver' if template == 'stack' else 'bring-back'}")
                _new_draft(site, d); st.rerun()
            st.caption('Templates create an editable draft using the focus game. Review the players and counts before saving.')
            draft = copy.deepcopy(st.session_state[f'nr_draft_{site}'])
            version = st.session_state.get(f'nr_version_{site}', 0)
            prefix = f'nr_build_{site}_{version}'
            st.markdown('**1 · When should this rule apply?**')
            scope = st.segmented_control('Rule scope', ['With a player', 'All lineups'],
                                        default='With a player' if draft.get('anchor_id') else 'All lineups', key=prefix+'_scope') or 'All lineups'
            anchor = None
            if scope == 'With a player':
                options = [str(r.ID) for r in players.sort_values(['Game', 'Salary'], ascending=[True, False]).itertuples()]
                current = str(draft.get('anchor_id') or '')
                anchor = st.selectbox('Anchor player · type a name to search', [None] + options,
                                      index=options.index(current)+1 if current in options else 0,
                                      format_func=lambda pid: 'Choose an anchor…' if pid is None else f'{lookup[pid].Name} · {lookup[pid].Team} {lookup[pid].Position} · ${int(lookup[pid].Salary):,}', key=prefix+'_anchor')
                st.caption('The anchor is a condition, not a lock. Its exposure still comes from your portfolio settings.')
            st.markdown('**2 · Pick the group**')
            st.caption('Check players in the table. The anchor does not count toward the group. Switch games or search the whole slate to build cross-game groups.')
            f1, f2, f3 = st.columns([1.2, 1.2, 1])
            whole_slate = f1.toggle('Search whole slate', key=prefix+'_all')
            search = f2.text_input('Player search', key=prefix+'_search', placeholder='Name or team')
            depth = f3.toggle('Show depth players', key=prefix+'_depth')
            board = players.copy()
            if not whole_slate: board = board[board.Game.eq(game)]
            selected = set(map(str, draft.get('member_ids', []))) - {anchor}
            if not depth and 'team_depth_rank' in board:
                board = board[(board.team_depth_rank <= 3) | board.ID.astype(str).isin(selected)]
            if search:
                board = board[board.Name.str.contains(search, case=False, regex=False) | board.Team.str.contains(search, case=False, regex=False)]
            board = board[board.ID.astype(str).ne(str(anchor))].sort_values(['Team', 'Position', 'Salary'], ascending=[True, True, False])
            signature = hashlib.sha1(f'{game}|{whole_slate}|{search}|{depth}|{anchor}|{tuple(board.ID)}'.encode()).hexdigest()[:12]
            table_key = prefix + '_members_' + signature
            base_key = table_key + '_base'
            if base_key not in st.session_state:
                st.session_state[base_key] = pd.DataFrame([
                    {'Use': str(r.ID) in selected, 'Player': str(r.Name), 'Team': str(r.Team),
                     'Pos': str(r.Position), 'Salary': int(r.Salary), '_id': str(r.ID)} for r in board.itertuples()
                ], columns=['Use', 'Player', 'Team', 'Pos', 'Salary', '_id']).set_index('_id')
            table = st.session_state[base_key]
            edited = st.data_editor(table, hide_index=True, use_container_width=True, height=320,
                                    disabled=['Player', 'Team', 'Pos', 'Salary'], key=table_key,
                                    column_config={'Use': st.column_config.CheckboxColumn('Use', width='small'),
                                                   'Salary': st.column_config.NumberColumn('Salary', format='$%d')})
            selected.difference_update(table.index.astype(str))
            selected.update(edited.index[edited.Use.astype(bool)].astype(str))
            selected.discard(anchor)
            if selected:
                st.caption('Selected: ' + ' · '.join(names.get(pid, draft.get('names', {}).get(pid, pid)) for pid in sorted(selected)))
            if st.button('Clear group', key=prefix+'_clear'):
                draft['member_ids'] = []
                _new_draft(site, draft); st.rerun()
            st.markdown('**3 · How many, and how often?**')
            v1, v2, v3 = st.columns([1, 1, 1.5])
            for field in ('min', 'max'):
                widget_key = prefix + '_' + field
                if st.session_state.get(widget_key, 0) > (8 if anchor else 9):
                    st.session_state[widget_key] = 8 if anchor else 9
            lo = v1.number_input('Minimum group players', 0, 8 if anchor else 9, min(8 if anchor else 9, int(draft.get('min_count', 1))), 1, key=prefix+'_min')
            hi = v2.number_input('Maximum group players', 0, 8 if anchor else 9, min(8 if anchor else 9, int(draft.get('max_count', 1))), 1, key=prefix+'_max')
            share_mode = v3.segmented_control('Apply to', ['Every', 'Most', 'Custom'], default='Every' if float(draft.get('share', 100)) == 100 else 'Most' if float(draft.get('share', 100)) == 75 else 'Custom', key=prefix+'_share_mode') or 'Every'
            share = 100 if share_mode == 'Every' else 75 if share_mode == 'Most' else st.slider('Minimum share of matching lineups', 1, 100, int(draft.get('share', 75)), key=prefix+'_share')
            st.caption('Every = 100%. Most = at least 75%. Percentages apply only to lineups containing the anchor, or the whole portfolio when there is no anchor. Both minimum and maximum counts define a match.')
            label = st.text_input('Rule name (optional)', value=str(draft.get('label', '')), placeholder='e.g. Allen with one Buffalo receiver', key=prefix+'_label')
            draft.update(anchor_id=anchor, member_ids=sorted(selected), min_count=int(lo), max_count=int(hi),
                         share=int(share), label=label, names={**draft.get('names', {}), **names})
            st.session_state[f'nr_draft_{site}'] = draft
            if selected:
                st.info(rule_sentence(draft))
            if st.button('Save rule', type='primary', use_container_width=True, key=prefix+'_save'):
                try:
                    if scope == 'With a player' and not anchor:
                        raise RuleError('Choose an anchor first.')
                    draft['label'] = label.strip() or (f'{names.get(anchor, "Portfolio")} group')
                    draft['enabled'] = True
                    refs = set(draft['member_ids']) | ({anchor} if anchor else set())
                    draft['names'] = {pid: names.get(pid, draft.get('names', {}).get(pid, pid)) for pid in refs}
                    new = [r for r in rules if r.get('id') != draft['id']] + [draft]
                    compile_rules(players, new)
                    _save_book(site, new); _new_draft(site)
                    st.session_state[f'nr_editor_open_{site}'] = False
                    st.rerun()
                except RuleError as exc:
                    st.error(str(exc))
        if not rules:
            st.caption('Try: Allen → exactly 1 Buffalo pass catcher, on Every lineup. Or Flowers + Henry → at most 1, across All lineups.')
        cols = st.columns(2)
        for i, rule in enumerate(rules):
            with cols[i % 2]:
                st.markdown(_card(rule, lookup), unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                if c1.button('Edit', key=f'nr_edit_{site}_{rule["id"]}', use_container_width=True):
                    _new_draft(site, rule)
                    st.session_state[f'nr_editor_open_{site}'] = True
                    st.session_state[f'nr_notice_{site}'] = 'Editing draft above. Save rule to apply your changes.'
                    st.rerun()
                if c2.button('Pause' if rule.get('enabled', True) else 'Enable', key=f'nr_pause_{site}_{rule["id"]}', use_container_width=True):
                    rule['enabled'] = not rule.get('enabled', True)
                    _save_book(site, rules); st.rerun()
                if c3.button('Remove', key=f'nr_delete_{site}_{rule["id"]}', use_container_width=True):
                    _save_book(site, [r for r in rules if r['id'] != rule['id']]); st.rerun()
        try:
            compile_rules(players, rules)
        except RuleError as exc:
            st.error(str(exc))
        st.caption('Rules are saved with your workspace. DraftKings and FanDuel keep separate rulebooks. New slates require reviewing rules with unavailable player IDs.')
    with map_tab:
        gp = players[players.Game.eq(game)].copy()
        portfolio = st.session_state.get('nuke_portfolio')
        sim_players = st.session_state.get('nuke_sim_players')
        if portfolio is not None and not portfolio.empty and sim_players is not None:
            counts = {}
            for lu in portfolio['_indices']:
                for i in set(map(int, lu)):
                    pid = str(sim_players.iloc[i].ID); counts[pid] = counts.get(pid, 0) + 1
            gp['_portfolio_pct'] = gp.ID.astype(str).map(lambda pid: 100 * counts.get(pid, 0) / len(portfolio))
        else:
            portfolio = None
        svg, hidden = game_map_svg(gp, rules, portfolio)
        st.html(svg)
        st.caption('Links show saved rules, not estimated correlations. Orange border = anchor. Dashed link = percentage rule. ' + ('Bubble size grows with actual portfolio exposure.' if portfolio is not None else 'Bubbles have equal size until a portfolio is built.'))
        if hidden: st.caption(f'{hidden} additional pool players are outside this compact map; the full player board remains available above.')
        ids = set(gp.ID.astype(str))
        related = [r for r in rules if ids.intersection([str(r.get('anchor_id')), *map(str, r.get('member_ids', []))])]
        for rule in related: st.markdown(_card(rule, lookup), unsafe_allow_html=True)
    with audit_tab:
        portfolio = st.session_state.get('nuke_portfolio')
        sp = st.session_state.get('nuke_sim_players')
        candidates = st.session_state.get('nuke_contest_results')
        if portfolio is not None and not portfolio.empty and sp is not None:
            try:
                report = rule_report(sp, portfolio['_indices'], rules)
                if report.empty: st.info('Save a rule to see portfolio compliance here.')
                else:
                    if report.Status.eq('Unmet').any(): st.error('Some rules are unmet. Apply the rulebook again before exporting.')
                    else: st.success('Every triggered rule meets its target in the selected portfolio.')
                    st.dataframe(report, hide_index=True, use_container_width=True,
                                 column_config={'Actual %': st.column_config.NumberColumn(format='%.1f%%'), 'Target %': st.column_config.NumberColumn(format='%.1f%%')})
                    st.caption('Not used means no selected lineup contained the anchor. It does not mean the rule forced that player into your portfolio.')
            except RuleError as exc: st.error(str(exc))
        else:
            st.info('Build or apply a portfolio to see actual counts, conditional percentages, and unmet rules.')
        if candidates is not None and sp is not None and not candidates.empty and active_rules(rules):
            try:
                support = rule_report(sp, candidates['_indices'], rules)
                with st.expander('Candidate support · are there enough matching options?'):
                    st.dataframe(support.drop(columns=['Status']), hide_index=True, use_container_width=True)
                    st.caption('Candidate counts are diagnostic. Percentage targets are enforced in the selected portfolio.')
            except RuleError as exc: st.error(str(exc))
    return rules

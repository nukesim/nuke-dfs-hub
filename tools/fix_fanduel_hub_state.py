from pathlib import Path

p=Path('app.py')
s=p.read_text()

# Make FanDuel repository slate available to the Hub.
if 'from fanduel_slate import load_fanduel_slate, FD_SLATE_LABEL' not in s:
    s=s.replace('from dfs_platform import get_platform\n', 'from dfs_platform import get_platform\nfrom fanduel_slate import load_fanduel_slate, FD_SLATE_LABEL\n',1)

# Fix saved_lineups type when switching platform.
s=s.replace('st.session_state["saved_lineups"]=[]','st.session_state["saved_lineups"]={}')

old='''    st.subheader("Slate")
    up=st.file_uploader("Optional: override current weekly DK slate",type="csv",help="Leave empty to use the same built-in weekly slate as NUKE SIM.")
    try:
        source_name=up.name if up is not None else SLATE_LABEL
        should_load=(st.session_state.slate is None or st.session_state.slate_name!=source_name)
        if should_load:
            raw=pd.read_csv(up) if up is not None else load_default_slate()
            sl=normalize(raw)
            st.session_state.slate=sl
            st.session_state.slate_name=source_name
            valid_ids=set(sl["Name + ID"])
            st.session_state.pool_ids={x for x in st.session_state.pool_ids if x in valid_ids}
            st.session_state.pending_pool_ids={x for x in st.session_state.pending_pool_ids if x in valid_ids}
            for lu in st.session_state.lineups:
                for slot_name in SLOTS:
                    if lu.get(slot_name) not in valid_ids:
                        lu[slot_name]=None
            if not st.session_state.pending_pool_ids and st.session_state.pool_ids:
                st.session_state.pending_pool_ids=set(st.session_state.pool_ids)
        if up is None:
            st.success(f"Auto-loaded {SLATE_LABEL} · {len(st.session_state.slate):,} players")
        else:
            st.info(f"Using uploaded override: {up.name} · {len(st.session_state.slate):,} players")
    except Exception as e:
        st.error(f"Could not load slate: {e}")
    st.caption(st.session_state.slate_name)
'''

new='''    st.subheader("Slate")
    cfg=get_platform(SITE)
    default_label=SLATE_LABEL if SITE=="DK" else FD_SLATE_LABEL
    up=st.file_uploader(
        f"Optional: override current weekly {cfg.name} slate",
        type="csv",
        key=f"hub_slate_upload_{SITE}",
        help=f"Leave empty to use the repository-backed {cfg.name} weekly slate."
    )
    try:
        source_name=up.name if up is not None else default_label
        should_load=(st.session_state.slate is None or st.session_state.slate_name!=source_name)
        if should_load:
            if up is not None:
                raw=pd.read_csv(up)
            elif SITE=="DK":
                raw=load_default_slate()
            else:
                raw=load_fanduel_slate()
            sl=normalize(raw)
            st.session_state.slate=sl
            st.session_state.slate_name=source_name
            valid_ids=set(sl["Name + ID"])
            st.session_state.pool_ids={x for x in st.session_state.pool_ids if x in valid_ids}
            st.session_state.pending_pool_ids={x for x in st.session_state.pending_pool_ids if x in valid_ids}
            for lu in st.session_state.lineups:
                for slot_name in SLOTS:
                    if lu.get(slot_name) not in valid_ids:
                        lu[slot_name]=None
            if not st.session_state.pending_pool_ids and st.session_state.pool_ids:
                st.session_state.pending_pool_ids=set(st.session_state.pool_ids)
        if up is None:
            st.success(f"Auto-loaded {default_label} · {len(st.session_state.slate):,} players")
        else:
            st.info(f"Using uploaded {cfg.name} override: {up.name} · {len(st.session_state.slate):,} players")
    except Exception as e:
        st.error(f"Could not load {cfg.name} slate: {e}")
    st.caption(st.session_state.slate_name)
'''

if old not in s:
    if new not in s:
        raise RuntimeError('Hub slate block not found')
else:
    s=s.replace(old,new,1)

# Make public-facing copy platform-neutral.
s=s.replace('Make sure both pages are using the same DraftKings slate.', 'Make sure both pages are using the same platform slate.')
s=s.replace('Games on DK slate','Games on selected slate')
s=s.replace('Teams on DK slate','Teams on selected slate')
s=s.replace('uploaded DraftKings slate','selected platform slate')

p.write_text(s)
print('FanDuel Hub state/autoload fix applied')

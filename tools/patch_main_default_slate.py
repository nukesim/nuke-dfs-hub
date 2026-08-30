from pathlib import Path

p = Path("app.py")
s = p.read_text(encoding="utf-8")

if "from default_slate import load_default_slate, SLATE_LABEL" not in s:
    s = s.replace(
        "from pathlib import Path\n",
        "from pathlib import Path\nfrom default_slate import load_default_slate, SLATE_LABEL\n",
        1,
    )

s = s.replace(
    'cg=f("Game Info","GameInfo")\n    ct=f("TeamAbbrev","Team Abbrev","Team")',
    'cg=f("Game Info","GameInfo","game_id","Game","game")\n    co=f("Opponent","Opp","opponent","opp")\n    ct=f("TeamAbbrev","Team Abbrev","Team")',
    1,
)
s = s.replace(
    'o["Opp"]=[opp_from_game(t,g) for t,g in zip(o["Team"],o["Game Info"])]',
    'o["Opp"]=df[co].fillna("").astype(str).str.upper().str.strip().values if co else [opp_from_game(t,g) for t,g in zip(o["Team"],o["Game Info"])]',
    1,
)

old = '''    st.subheader("Slate")
    up=st.file_uploader("DraftKings salary CSV",type="csv")
    if up is not None:
        # only re-parse when the upload filename changes or no slate exists
        if st.session_state.slate is None or st.session_state.slate_name!=up.name:
            try:
                sl=normalize(pd.read_csv(up))
                st.session_state.slate=sl;st.session_state.slate_name=up.name
                valid_ids=set(sl["Name + ID"])
                st.session_state.pool_ids={x for x in st.session_state.pool_ids if x in valid_ids}
                st.session_state.pending_pool_ids={x for x in st.session_state.pending_pool_ids if x in valid_ids}
                for lu in st.session_state.lineups:
                    for s in SLOTS:
                        if lu.get(s) not in valid_ids:lu[s]=None
                if not st.session_state.pending_pool_ids and st.session_state.pool_ids:
                    st.session_state.pending_pool_ids=set(st.session_state.pool_ids)
                st.success(f"{len(sl)} players loaded")
            except Exception as e:st.error(str(e))
    st.caption(st.session_state.slate_name)
'''
new = '''    st.subheader("Slate")
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
if old not in s:
    raise SystemExit("Could not find main Hub slate uploader block")
s = s.replace(old, new, 1)
s = s.replace(
    'st.info("Upload your DraftKings NFL salary CSV in the sidebar.")',
    'st.info("The built-in weekly slate could not be loaded. Use the optional sidebar override.")',
    1,
)
s = s.replace(
    'Click **LOAD / REFRESH MODEL** once after uploading the DraftKings slate.',
    'Click **LOAD / REFRESH MODEL** once after the weekly slate loads.',
    1,
)
p.write_text(s, encoding="utf-8")
print("Patched app.py")

from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
old='''    with st.expander("Advanced settings"):\n        fixed_seed=st.checkbox("Use reproducible seed",value=False,help="Off by default: every RUN NUKE SIM click gets a fresh random simulation. Turn this on only when you want to reproduce a specific run.")\n        manual_seed=st.number_input("Random seed",1,2147483646,26,1,disabled=not fixed_seed)'''
new='''    with st.expander("Advanced settings"):\n        fixed_seed=st.checkbox("Use reproducible seed",value=False,help="Off by default: every RUN NUKE SIM click gets a fresh random simulation. Turn this on only when you want to reproduce a specific run.")\n        if "nuke_manual_seed" not in st.session_state:\n            st.session_state["nuke_manual_seed"]=int(np.random.default_rng().integers(1,2147483647))\n        manual_seed=st.number_input("Random seed",1,2147483646,step=1,disabled=not fixed_seed,key="nuke_manual_seed")'''
if old not in s:
    if 'key="nuke_manual_seed"' in s:
        print('already patched')
        raise SystemExit(0)
    raise SystemExit('target block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('patched pages/6_SIM.py')

from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()
old='''if not flagged.empty:\n    st.subheader("🚑 Injuries & Availability")\n    st.caption("OUT/inactive players default to excluded. Questionable/doubtful players stay available but are flagged for review.")\n    flagged["NUKE Action"]=flagged["Auto Exclude"].map(lambda x: "🔴 EXCLUDED" if bool(x) else "🟡 INCLUDED / REVIEW")\n    cols=[c for c in ["Name","Team","Position","Availability","Availability Detail","NUKE Action"] if c in flagged.columns]\n    show=flagged[cols].copy()\n    rename={"Name":"Player","Position":"Pos","Availability":"Status","Availability Detail":"Detail"}\n    show=show.rename(columns=rename)\n    st.dataframe(show,use_container_width=True,hide_index=True)\n'''
new='''if not flagged.empty:\n    with st.expander(f"🚑 Injuries & Availability · {len(flagged)} flagged", expanded=True):\n        st.caption("OUT/inactive players default to excluded. Questionable/doubtful players stay available but are flagged for review.")\n        flagged["NUKE Action"]=flagged["Auto Exclude"].map(lambda x: "🔴 EXCLUDED" if bool(x) else "🟡 INCLUDED / REVIEW")\n        cols=[c for c in ["Name","Team","Position","Availability","Availability Detail","NUKE Action"] if c in flagged.columns]\n        show=flagged[cols].copy()\n        rename={"Name":"Player","Position":"Pos","Availability":"Status","Availability Detail":"Detail"}\n        show=show.rename(columns=rename)\n        show=show.fillna("")\n        st.dataframe(show,use_container_width=True,hide_index=True)\n'''
if old not in s:
    raise RuntimeError('injury dashboard block not found')
s=s.replace(old,new,1)
p.write_text(s)
print('made injury dashboard collapsible')

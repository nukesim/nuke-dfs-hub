from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()
anchor='''else:\n    st.info("🚑 Player Availability feed not connected yet — no automatic injury exclusions are being applied.")\n\nc1,c2,c3,c4,c5=st.columns(5)\n'''
insert='''else:\n    st.info("🚑 Player Availability feed not connected yet — no automatic injury exclusions are being applied.")\n\n# One-stop injury review so users do not have to hunt through every game.\nflagged=players[players["Availability"].astype(str).str.lower().ne("available")].copy() if "Availability" in players.columns else players.iloc[0:0].copy()\nif not flagged.empty:\n    st.subheader("🚑 Injuries & Availability")\n    st.caption("OUT/inactive players default to excluded. Questionable/doubtful players stay available but are flagged for review.")\n    flagged["NUKE Action"]=flagged["Auto Exclude"].map(lambda x: "🔴 EXCLUDED" if bool(x) else "🟡 INCLUDED / REVIEW")\n    cols=[c for c in ["Name","Team","Position","Availability","Availability Detail","NUKE Action"] if c in flagged.columns]\n    show=flagged[cols].copy()\n    rename={"Name":"Player","Position":"Pos","Availability":"Status","Availability Detail":"Detail"}\n    show=show.rename(columns=rename)\n    st.dataframe(show,use_container_width=True,hide_index=True)\nelse:\n    if availability_meta.get("loaded"):\n        st.caption("🚑 Injuries & Availability · No flagged players on the current slate.")\n\nc1,c2,c3,c4,c5=st.columns(5)\n'''
if 'st.subheader("🚑 Injuries & Availability")' not in s:
    if anchor not in s:
        raise RuntimeError('injury dashboard anchor not found')
    s=s.replace(anchor,insert,1)
p.write_text(s)
print('patched injury dashboard')

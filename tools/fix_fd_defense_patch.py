from pathlib import Path

p=Path('nuke_sim.py')
s=p.read_text(encoding='utf-8')
old='''    out.Name=out.Name.fillna("").astype(str).str.replace(r"\\s*\\(\\d+\\)\\s*$","",regex=True); out.Position=out.Position.map(_norm_pos); out.Salary=pd.to_numeric(out.Salary,errors="coerce").fillna(0).astype(int); out.Team=out.Team.fillna("").astype(str).str.upper().str.strip(); out.Game=out.Game.fillna("").astype(str).str.strip(); out.ID=out.ID.fillna("").astype(str); out.Status=out.Status.fillna("").astype(str).str.upper().str.strip().replace({"O":"OUT"}).replace({"O":"OUT"})'''
new='''    out.Name=out.Name.fillna("").astype(str).str.replace(r"\\s*\\(\\d+\\)\\s*$","",regex=True); out.Position=out.Position.map(_norm_pos); out.Salary=pd.to_numeric(out.Salary,errors="coerce").fillna(0).astype(int); out.Team=out.Team.fillna("").astype(str).str.upper().str.strip(); out.Game=out.Game.fillna("").astype(str).str.strip(); out.ID=out.ID.fillna("").astype(str).str.strip(); out.Status=out.Status.fillna("").astype(str).str.upper().str.strip().replace({"O":"OUT"}).replace({"O":"OUT"})\n    # FanDuel defense rows can have an empty Nickname even though Team/Id are present.\n    # Give every defense a stable visible name while preserving FanDuel's real player ID for export.\n    dst_blank=out.Position.eq("DST") & ~out.Name.astype(str).str.strip().ne("")\n    if dst_blank.any():\n        out.loc[dst_blank,"Name"]=out.loc[dst_blank,"Team"].astype(str).str.strip()+" D/ST"'''
if old not in s:
    if 'dst_blank=out.Position.eq("DST")' in s:
        print('already patched')
        raise SystemExit(0)
    raise SystemExit('prepare_slate normalization target not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('patched FanDuel defense names in nuke_sim.py')
# trigger after workflow exists

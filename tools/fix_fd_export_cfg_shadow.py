from pathlib import Path

p = Path('pages/6_SIM.py')
s = p.read_text()

old = '''    with tab7:\n        st.subheader(f"📤 {cfg.name} Lineup Export")\n'''
new = '''    with tab7:\n        export_platform_name = "FanDuel" if site == "FD" else "DraftKings"\n        st.subheader(f"📤 {export_platform_name} Lineup Export")\n'''
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise RuntimeError('Export tab header anchor not found')

repls = {
    'st.download_button(f"Download {cfg.name} lineup-only CSV",lineup_only,f"nuke_{short_site}_lineups.csv","text/csv")':
        'st.download_button(f"Download {export_platform_name} lineup-only CSV",lineup_only,f"nuke_{short_site}_lineups.csv","text/csv")',
    'entries_upload=st.file_uploader(f"Upload your {cfg.name} Entries CSV",type=["csv"],key=f"entries_upload_{site}")':
        'entries_upload=st.file_uploader(f"Upload your {export_platform_name} Entries CSV",type=["csv"],key=f"entries_upload_{site}")',
    'st.success(f"Filled {info[\'entries_filled\']} {cfg.name} entries.")':
        'st.success(f"Filled {info[\'entries_filled\']} {export_platform_name} entries.")',
    'st.download_button(f"⬇️ Download {cfg.name} Upload CSV",filled,f"nuke_{short_site}_upload.csv","text/csv",type="primary")':
        'st.download_button(f"⬇️ Download {export_platform_name} Upload CSV",filled,f"nuke_{short_site}_upload.csv","text/csv",type="primary")',
    'st.error(f"Could not build {cfg.name} upload file: {e}")':
        'st.error(f"Could not build {export_platform_name} upload file: {e}")',
}
for a,b in repls.items():
    s = s.replace(a,b)

p.write_text(s)
print('Fixed export platform label shadowing')

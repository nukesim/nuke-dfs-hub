from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()

# Ensure FD helpers are imported.
imp='from fd_export import lineup_to_fd_slots, ANALYSIS_ROSTER_HEADERS\n'
anchor='from fanduel_slate import load_fanduel_slate, has_fanduel_slate, FD_SLATE_LABEL\n'
if imp not in s and anchor in s:
    s=s.replace(anchor, anchor+imp, 1)

# Platform-aware result tabs.
s=s.replace('"📤 DK EXPORT"', 'f"📤 {\'FD\' if site==\'FD\' else \'DK\'} EXPORT"')

# Replace old Contest SIM export button with an ID-only FD download.
old='st.download_button("Download Contest SIM + DK Lineups CSV",contest_show.to_csv(index=False).encode("utf-8-sig"),"nuke_contest_sim_dk_lineups.csv","text/csv")'
new='''contest_download=contest_show.copy()\n            if site=="FD":\n                fd_id_slots=pd.DataFrame([lineup_to_fd_slots(sim_players,lu,ids_only=True) for lu in contest_results["_indices"]],columns=ANALYSIS_ROSTER_HEADERS)\n                for c in ANALYSIS_ROSTER_HEADERS:\n                    if c in contest_download.columns:\n                        contest_download[c]=fd_id_slots[c].values\n                st.download_button("Download Contest SIM + FanDuel IDs CSV",contest_download.to_csv(index=False).encode("utf-8-sig"),"nuke_contest_sim_fanduel_ids.csv","text/csv")\n            else:\n                st.download_button("Download Contest SIM + DraftKings Lineups CSV",contest_download.to_csv(index=False).encode("utf-8-sig"),"nuke_contest_sim_draftkings_lineups.csv","text/csv")'''
if old in s:
    s=s.replace(old,new,1)

# Make main export tab truly platform-aware.
s=s.replace('st.subheader("📤 DraftKings Lineup Export")','st.subheader(f"📤 {cfg.name} Lineup Export")')
s=s.replace('key="dk_export_source"','key=f"export_source_{site}"')
s=s.replace('key="dk_export_count"','key=f"export_count_{site}"')
s=s.replace('lineup_only=build_lineup_only_csv(sim_players,export_results,int(export_count))','lineup_only=build_lineup_only_csv(sim_players,export_results,int(export_count),site=site)')
s=s.replace('st.download_button("Download DK lineup-only CSV",lineup_only,"nuke_dk_lineups.csv","text/csv")','st.download_button(f"Download {cfg.name} lineup-only CSV",lineup_only,("nuke_fd_ids.csv" if site=="FD" else "nuke_dk_lineups.csv"),"text/csv")')
s=s.replace('st.file_uploader("Upload your {cfg.name} Entries CSV",type=["csv"],key="dk_entries_upload")','st.file_uploader(f"Upload your {cfg.name} Entries CSV",type=["csv"],key=f"entries_upload_{site}")')
s=s.replace('fill_entries_csv(entries_upload.getvalue(),sim_players,export_results,int(export_count))','fill_entries_csv(entries_upload.getvalue(),sim_players,export_results,int(export_count),site=site)')
s=s.replace('st.success(f"Filled {info[\'entries_filled\']} DraftKings entries.")','st.success(f"Filled {info[\'entries_filled\']} {cfg.name} entries.")')
s=s.replace('st.download_button("⬇️ Download DraftKings Upload CSV",filled,"nuke_draftkings_upload.csv","text/csv",type="primary")','st.download_button(f"⬇️ Download {cfg.name} Upload CSV",filled,("nuke_fanduel_upload.csv" if site=="FD" else "nuke_draftkings_upload.csv"),"text/csv",type="primary")')

p.write_text(s)
print('Applied FanDuel ID-only export and platform labels')

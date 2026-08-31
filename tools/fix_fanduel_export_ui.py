from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()

# Need FanDuel ID-only roster slots for upload-safe contest CSV downloads.
imp='from fd_export import lineup_to_fd_slots, ANALYSIS_ROSTER_HEADERS\n'
if imp not in s:
    anchor='from fanduel_slate import load_fanduel_slate, has_fanduel_slate, FD_SLATE_LABEL\n'
    if anchor not in s:
        raise RuntimeError('FanDuel slate import anchor not found')
    s=s.replace(anchor, anchor+imp, 1)

# Platform-aware export tab label.
s=s.replace('"📤 DK EXPORT"', 'f"📤 {\'FD\' if site==\'FD\' else \'DK\'} EXPORT"')

old='''            contest_dk=add_dk_roster_columns(sim_players,contest_results)
            left=["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DST","FLEX Pos","Stack"]
            stats=["Contest Rank","Sim ROI %","1st %","Top 0.1%","Top 1%","Cash %","Avg Finish","Expected Duplicates","Avg Payout","Strongest Path","Path Score","Lineup Thesis","NUKE Score","Ceiling 95","Salary"]
            contest_show=contest_dk[[c for c in left+stats if c in contest_dk.columns]].copy()
            st.dataframe(contest_show,use_container_width=True,hide_index=True)
            st.download_button("Download Contest SIM + DK Lineups CSV",contest_show.to_csv(index=False).encode("utf-8-sig"),"nuke_contest_sim_dk_lineups.csv","text/csv")
'''
new='''            contest_roster=add_dk_roster_columns(sim_players,contest_results)
            defense_col="D" if site=="FD" else "DST"
            left=["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX",defense_col,"FLEX Pos","Stack"]
            stats=["Contest Rank","Sim ROI %","1st %","Top 0.1%","Top 1%","Cash %","Avg Finish","Expected Duplicates","Avg Payout","Strongest Path","Path Score","Lineup Thesis","NUKE Score","Ceiling 95","Salary"]
            contest_show=contest_roster[[c for c in left+stats if c in contest_roster.columns]].copy()
            st.dataframe(contest_show,use_container_width=True,hide_index=True)

            # FanDuel's edit-entries CSV validates player IDs, not display strings like
            # "Player Name (133104-12345)". Keep names on-screen, but make the downloaded
            # FanDuel contest CSV copy/paste safe by writing raw FanDuel IDs in roster cells.
            contest_download=contest_show.copy()
            if site=="FD":
                fd_slots=pd.DataFrame(
                    [lineup_to_fd_slots(sim_players,lu,ids_only=True) for lu in contest_results["_indices"]],
                    columns=ANALYSIS_ROSTER_HEADERS,
                )
                for col in ANALYSIS_ROSTER_HEADERS:
                    if col in contest_download.columns and col in fd_slots.columns:
                        contest_download[col]=fd_slots[col].values
                contest_label="Download Contest SIM + FanDuel Lineups CSV"
                contest_filename="nuke_contest_sim_fanduel_lineups.csv"
            else:
                contest_label="Download Contest SIM + DraftKings Lineups CSV"
                contest_filename="nuke_contest_sim_draftkings_lineups.csv"
            st.download_button(contest_label,contest_download.to_csv(index=False).encode("utf-8-sig"),contest_filename,"text/csv")
'''
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise RuntimeError('Contest export block not found')

old2='''    with tab7:
        st.subheader("📤 DraftKings Lineup Export")
        source_options=["Portfolio","Contest-ranked","NUKEM-ranked"]
        export_source=st.selectbox("Lineup source",source_options,index=0,key="dk_export_source")
        export_results=portfolio if export_source=="Portfolio" and portfolio is not None and not portfolio.empty else contest_results if export_source=="Contest-ranked" and contest_results is not None and not contest_results.empty else results
        max_export=min(150,len(export_results))
        export_count=st.number_input("Lineups to export",1,max_export,min(150,max_export),1,key="dk_export_count")
        lineup_only=build_lineup_only_csv(sim_players,export_results,int(export_count))
        st.download_button("Download DK lineup-only CSV",lineup_only,"nuke_dk_lineups.csv","text/csv")
        entries_upload=st.file_uploader("Upload your {cfg.name} Entries CSV",type=["csv"],key="dk_entries_upload")
        if entries_upload is not None:
            try:
                filled,info=fill_entries_csv(entries_upload.getvalue(),sim_players,export_results,int(export_count))
                st.success(f"Filled {info['entries_filled']} DraftKings entries.")
                st.download_button("⬇️ Download DraftKings Upload CSV",filled,"nuke_draftkings_upload.csv","text/csv",type="primary")
            except Exception as e:
                st.error(f"Could not build {cfg.name} upload file: {e}")
'''
new2='''    with tab7:
        st.subheader(f"📤 {cfg.name} Lineup Export")
        source_options=["Portfolio","Contest-ranked","NUKEM-ranked"]
        export_source=st.selectbox("Lineup source",source_options,index=0,key=f"export_source_{site}")
        export_results=portfolio if export_source=="Portfolio" and portfolio is not None and not portfolio.empty else contest_results if export_source=="Contest-ranked" and contest_results is not None and not contest_results.empty else results
        max_export=min(150,len(export_results))
        export_count=st.number_input("Lineups to export",1,max_export,min(150,max_export),1,key=f"export_count_{site}")
        lineup_only=build_lineup_only_csv(sim_players,export_results,int(export_count),site=site)
        short_site="fd" if site=="FD" else "dk"
        st.download_button(f"Download {cfg.name} lineup-only CSV",lineup_only,f"nuke_{short_site}_lineups.csv","text/csv")
        entries_upload=st.file_uploader(f"Upload your {cfg.name} Entries CSV",type=["csv"],key=f"entries_upload_{site}")
        if entries_upload is not None:
            try:
                filled,info=fill_entries_csv(entries_upload.getvalue(),sim_players,export_results,int(export_count),site=site)
                st.success(f"Filled {info['entries_filled']} {cfg.name} entries.")
                st.download_button(f"⬇️ Download {cfg.name} Upload CSV",filled,f"nuke_{short_site}_upload.csv","text/csv",type="primary")
            except Exception as e:
                st.error(f"Could not build {cfg.name} upload file: {e}")
'''
if old2 in s:
    s=s.replace(old2,new2,1)
elif new2 not in s:
    raise RuntimeError('Main export tab block not found')

p.write_text(s)
print('FanDuel export UI and ID-only contest CSV patch applied')

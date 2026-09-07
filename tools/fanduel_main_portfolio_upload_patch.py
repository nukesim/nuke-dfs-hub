from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
s=s.replace('from fd_export import lineup_to_fd_slots, ANALYSIS_ROSTER_HEADERS','from fd_export import lineup_to_fd_slots, ANALYSIS_ROSTER_HEADERS, build_fd_lineup_only_csv')
old='''            st.dataframe(portfolio_export,use_container_width=True,hide_index=True)\n            st.download_button("⬇️ Download Portfolio + Stats CSV",portfolio_export.to_csv(index=False).encode("utf-8-sig"),"nuke_portfolio_with_stats.csv","text/csv",type="primary",use_container_width=True,key="download_portfolio_stats")\n'''
new='''            st.dataframe(portfolio_export,use_container_width=True,hide_index=True)\n            if site=="FD":\n                st.caption("Review file keeps player names + stats. FanDuel upload file uses player IDs only in roster columns.")\n                d1,d2=st.columns(2)\n                with d1:\n                    st.download_button("⬇️ Download Portfolio + Stats CSV",portfolio_export.to_csv(index=False).encode("utf-8-sig"),"nuke_portfolio_with_stats.csv","text/csv",type="primary",use_container_width=True,key="download_portfolio_stats")\n                with d2:\n                    st.download_button("⬇️ Download FanDuel Upload CSV",build_fd_lineup_only_csv(sim_players,portfolio),"nuke_fanduel_portfolio_upload.csv","text/csv",type="primary",use_container_width=True,key="download_fd_portfolio_upload")\n            else:\n                st.download_button("⬇️ Download Portfolio + Stats CSV",portfolio_export.to_csv(index=False).encode("utf-8-sig"),"nuke_portfolio_with_stats.csv","text/csv",type="primary",use_container_width=True,key="download_portfolio_stats")\n'''
if old not in s:
    raise SystemExit('portfolio export block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

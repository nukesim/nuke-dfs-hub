from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
needle='''            st.download_button("⬇️ Download Portfolio + Stats CSV",portfolio_export.to_csv(index=False).encode("utf-8-sig"),"nuke_portfolio_with_stats.csv","text/csv",type="primary",use_container_width=True,key="download_portfolio_stats")\n'''
replacement='''            st.markdown("""\n            <style id="portfolio-download-green">\n            div[data-testid="stDownloadButton"] button[kind="primary"] {\n                background: #16a34a !important;\n                border-color: #16a34a !important;\n                color: white !important;\n            }\n            div[data-testid="stDownloadButton"] button[kind="primary"]:hover {\n                background: #15803d !important;\n                border-color: #15803d !important;\n                color: white !important;\n            }\n            </style>\n            """,unsafe_allow_html=True)\n            st.download_button("⬇️ Download Portfolio + Stats CSV",portfolio_export.to_csv(index=False).encode("utf-8-sig"),"nuke_portfolio_with_stats.csv","text/csv",type="primary",use_container_width=True,key="download_portfolio_stats")\n'''
if 'portfolio-download-green' not in s:
    if needle not in s:
        raise SystemExit('download button target not found')
    s=s.replace(needle,replacement,1)
p.write_text(s,encoding='utf-8')

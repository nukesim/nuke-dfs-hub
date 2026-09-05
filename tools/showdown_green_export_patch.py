from pathlib import Path
p=Path('pages/13_SHOWDOWN_SIM.py')
s=p.read_text(encoding='utf-8')
needle='''    st.markdown("#### 📤 DraftKings Export")\n'''
css='''    st.markdown("""\n    <style id="showdown-dk-export-green">\n    div[data-testid="stDownloadButton"] button[kind="primary"] {\n        background: #16a34a !important;\n        border-color: #16a34a !important;\n        color: white !important;\n    }\n    div[data-testid="stDownloadButton"] button[kind="primary"]:hover {\n        background: #15803d !important;\n        border-color: #15803d !important;\n        color: white !important;\n    }\n    </style>\n    """, unsafe_allow_html=True)\n    st.markdown("#### 📤 DraftKings Export")\n'''
if needle not in s: raise SystemExit('export heading not found')
s=s.replace(needle,css,1)
p.write_text(s,encoding='utf-8')

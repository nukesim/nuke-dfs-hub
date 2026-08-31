from pathlib import Path

files = [
    Path('app.py'),
    Path('pages/6_SIM.py'),
    Path('pages/7_VALIDATION.py'),
    Path('pages/8_CALIBRATION.py'),
    Path('pages/9_GAUNTLET.py'),
    Path('pages/10_CONTEST_VALIDATION.py'),
]

for p in files:
    s = p.read_text()
    imp = 'from nuke_nav import render_nav\n'
    if imp not in s:
        anchor = 'import streamlit as st\n'
        if anchor not in s:
            raise RuntimeError(f'streamlit import not found in {p}')
        s = s.replace(anchor, anchor + imp, 1)

    if 'render_nav()' not in s:
        marker = 'st.set_page_config('
        idx = s.find(marker)
        if idx < 0:
            raise RuntimeError(f'set_page_config not found in {p}')
        start = idx
        depth = 0
        end = None
        for i in range(start, len(s)):
            ch = s[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and i > start:
                    end = i + 1
                    break
        if end is None:
            raise RuntimeError(f'could not parse set_page_config in {p}')
        s = s[:end] + '\nrender_nav()' + s[end:]

    p.write_text(s)
    print(f'patched {p}')

# deploy trigger

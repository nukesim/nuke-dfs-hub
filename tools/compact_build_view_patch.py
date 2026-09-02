from pathlib import Path

p=Path('app.py')
s=p.read_text(encoding='utf-8')
anchor='.active-select button{font-weight:900!important}\n'
css='''\n/* Keep build-view slot labels compact in 3/4-lineup layouts. */\ndiv[data-testid="stButton"] button{\n  min-height:32px!important;\n  padding:.22rem .38rem!important;\n}\ndiv[data-testid="stButton"] button p{\n  white-space:nowrap!important;\n  word-break:keep-all!important;\n  overflow-wrap:normal!important;\n  font-size:.72rem!important;\n  line-height:1!important;\n}\n'''
if css.strip() in s:
    print('already patched')
elif anchor not in s:
    raise SystemExit('CSS anchor not found')
else:
    s=s.replace(anchor,anchor+css,1)
    p.write_text(s,encoding='utf-8')
    print('patched compact build button labels')
# workflow trigger

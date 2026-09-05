from pathlib import Path

p = Path('pages/13_SHOWDOWN_SIM.py')
s = p.read_text(encoding='utf-8')
old1 = 'min_salary = s1.slider("Minimum salary", 30000, 50000, 42000, 500, key="showdown_min_salary")'
new1 = 'min_salary = s1.slider("Minimum salary", 30000, 50000, 42000, 100, key="showdown_min_salary")'
old2 = '"Maximum salary", 30000, 50000, 50000, 500, key="showdown_max_salary",'
new2 = '"Maximum salary", 30000, 50000, 50000, 100, key="showdown_max_salary",'
if old1 not in s or old2 not in s:
    raise SystemExit('salary slider anchors not found')
s = s.replace(old1, new1, 1).replace(old2, new2, 1)
p.write_text(s, encoding='utf-8')
print('updated Showdown salary sliders to $100 increments')

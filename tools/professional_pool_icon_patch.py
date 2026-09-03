from pathlib import Path

path = Path("pages/6_SIM.py")
text = path.read_text(encoding="utf-8")
old = 'st.subheader("🎮 Game-by-Game Player Pool")'
new = 'st.subheader("📊 Game-by-Game Player Pool")'
if old not in text:
    raise SystemExit("Target Game-by-Game Player Pool header not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Replaced game controller icon with analytics icon")

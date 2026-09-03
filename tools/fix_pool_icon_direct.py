from pathlib import Path

path = Path("pages/6_SIM.py")
text = path.read_text(encoding="utf-8")
old = 'st.subheader("🎮 Game-by-Game Player Pool")'
new = 'st.subheader("📊 Game-by-Game Player Pool")'
if old not in text:
    raise SystemExit("Expected Game-by-Game Player Pool controller heading not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("Replaced controller icon with analytics icon")

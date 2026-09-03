from pathlib import Path

TARGETS = [Path("app.py"), Path("pages/6_SIM.py"), Path("pages/11_GUIDE.py")]

for path in TARGETS:
    text = path.read_text(encoding="utf-8")
    if "from nuke_ui import apply_public_ui_fixes" not in text:
        marker = "import streamlit as st\n"
        if marker not in text:
            raise SystemExit(f"Could not find Streamlit import in {path}")
        text = text.replace(marker, marker + "from nuke_ui import apply_public_ui_fixes\n", 1)

    if "apply_public_ui_fixes()" not in text:
        marker = "st.set_page_config("
        idx = text.find(marker)
        if idx < 0:
            raise SystemExit(f"Could not find set_page_config in {path}")
        line_end = text.find("\n", idx)
        if line_end < 0:
            raise SystemExit(f"Could not find end of set_page_config line in {path}")
        text = text[: line_end + 1] + "apply_public_ui_fixes()\n" + text[line_end + 1 :]

    path.write_text(text, encoding="utf-8")
    print(f"updated {path}")

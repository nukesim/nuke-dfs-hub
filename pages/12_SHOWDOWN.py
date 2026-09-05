import pandas as pd
import streamlit as st

from nuke_nav import render_nav
from nuke_showdown import (
    SHOWDOWN_SALARY_CAP,
    exposure_tables,
    export_lineup_only_csv,
    lineup_identity,
    lineup_record,
    lineup_salary,
    parse_showdown_salary_csv,
    saved_lineups_table,
    validate_lineup,
)

st.set_page_config(page_title="NUKE Showdown", page_icon="⚡", layout="wide")
render_nav()

st.title("⚡ NUKE SHOWDOWN")
st.caption("DraftKings NFL single-game lineup builder · 1 CPT + 5 FLEX · $50,000 salary cap")

upload = st.file_uploader(
    "Upload DraftKings NFL Showdown salary CSV",
    type=["csv"],
    key="showdown_salary_upload",
    help="Use the raw DraftKings Showdown salary file. NUKE pairs each player's CPT and FLEX rows automatically.",
)

if upload is None:
    st.info("Upload a DraftKings NFL Showdown salary CSV to begin.")
    st.stop()

try:
    raw = pd.read_csv(upload)
    players, meta = parse_showdown_salary_csv(raw)
except Exception as exc:
    st.error(f"Could not read this Showdown slate: {exc}")
    st.stop()

slate_sig = f"{meta['game_info']}|{len(players)}"
if st.session_state.get("showdown_slate_sig") != slate_sig:
    st.session_state["showdown_slate_sig"] = slate_sig
    st.session_state["showdown_saved_lineups"] = []
    st.session_state["showdown_pool"] = {
        row["Player Key"]: bool(row["Auto Include"]) for _, row in players.iterrows()
    }
    for key in ["showdown_cpt", "showdown_f1", "showdown_f2", "showdown_f3", "showdown_f4", "showdown_f5"]:
        st.session_state.pop(key, None)

team_a, team_b = meta["teams"]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Game", f"{team_a} vs {team_b}")
m2.metric("Players", meta["player_count"])
m3.metric("Roster", "1 CPT + 5 FLEX")
m4.metric("Salary Cap", f"${SHOWDOWN_SALARY_CAP:,}")
st.caption(meta["game_info"])

st.subheader("Player Pool")
st.caption("OUT/IR players default to excluded. Questionable players stay available for review.")

pool_state = dict(st.session_state.get("showdown_pool", {}))
pool_df = players[["Player Key", "Name", "Team", "Pos", "FLEX Salary", "CPT Salary", "Status", "Avg FPPG"]].copy()
pool_df.insert(0, "Include", pool_df["Player Key"].map(lambda k: bool(pool_state.get(k, True))))
pool_df["Status"] = pool_df["Status"].replace("", "Available")

edited_pool = st.data_editor(
    pool_df.drop(columns=["Player Key"]),
    use_container_width=True,
    hide_index=True,
    disabled=["Name", "Team", "Pos", "FLEX Salary", "CPT Salary", "Status", "Avg FPPG"],
    column_config={
        "Include": st.column_config.CheckboxColumn("Include", width="small"),
        "Name": st.column_config.TextColumn("Player", width="medium"),
        "Team": st.column_config.TextColumn("Team", width="small"),
        "Pos": st.column_config.TextColumn("Pos", width="small"),
        "FLEX Salary": st.column_config.NumberColumn("FLEX", format="$%d", width="small"),
        "CPT Salary": st.column_config.NumberColumn("CPT", format="$%d", width="small"),
        "Status": st.column_config.TextColumn("Status", width="small"),
        "Avg FPPG": st.column_config.NumberColumn("DK FPPG", format="%.1f", width="small"),
    },
    key="showdown_pool_editor",
)

for idx, row in players.iterrows():
    pool_state[row["Player Key"]] = bool(edited_pool.iloc[idx]["Include"])
st.session_state["showdown_pool"] = pool_state

active = players[players["Player Key"].map(lambda k: bool(pool_state.get(k, True)))].copy()
if active.empty:
    st.warning("No active players remain in the Showdown pool.")
    st.stop()

records = {row["Player Key"]: row.to_dict() for _, row in active.iterrows()}
keys = active["Player Key"].tolist()
blank = ""
options = [blank] + keys


def player_label(key, slot):
    if not key:
        return "— Select player —"
    p = records.get(key)
    if not p:
        return key
    salary = p["CPT Salary"] if slot == "CPT" else p["FLEX Salary"]
    status = f" · {p['Status']}" if p.get("Status") else ""
    return f"{p['Name']} · {p['Team']} {p['Pos']} · ${int(salary):,}{status}"


st.subheader("Build Lineup")
left, right = st.columns([1, 1])

with left:
    st.markdown("#### CPT")
    captain = st.selectbox(
        "Captain",
        options,
        format_func=lambda k: player_label(k, "CPT"),
        key="showdown_cpt",
        label_visibility="collapsed",
    )
    if captain:
        p = records[captain]
        st.caption(f"1.5× fantasy points · 1.5× salary · ${int(p['CPT Salary']):,}")

with right:
    st.markdown("#### FLEX")
    flex_keys = []
    for i in range(1, 6):
        key = st.selectbox(
            f"FLEX {i}",
            options,
            format_func=lambda k: player_label(k, "FLEX"),
            key=f"showdown_f{i}",
            label_visibility="collapsed",
        )
        flex_keys.append(key)

salary = lineup_salary(records, captain, flex_keys) if captain else 0
remaining = SHOWDOWN_SALARY_CAP - salary
selected = [x for x in [captain] + flex_keys if x]
teams_selected = [records[k]["Team"] for k in selected if k in records]
team_counts = {t: teams_selected.count(t) for t in meta["teams"]}
construction = "-".join(str(x) for x in sorted([x for x in team_counts.values() if x], reverse=True)) if selected else "—"

s1, s2, s3, s4 = st.columns(4)
s1.metric("Salary Used", f"${salary:,}")
s2.metric("Remaining", f"${remaining:,}")
s3.metric("Players", f"{len(selected)}/6")
s4.metric("Team Split", construction)

legal, message = validate_lineup(records, captain, flex_keys)
if legal:
    st.success(message)
else:
    st.info(message)

save_col, clear_col = st.columns([3, 1])
with save_col:
    save_clicked = st.button("SAVE LINEUP", type="primary", use_container_width=True, disabled=not legal)
with clear_col:
    if st.button("CLEAR", use_container_width=True):
        for key in ["showdown_cpt", "showdown_f1", "showdown_f2", "showdown_f3", "showdown_f4", "showdown_f5"]:
            st.session_state.pop(key, None)
        st.rerun()

if save_clicked:
    rec = lineup_record(records, captain, flex_keys)
    saved = list(st.session_state.get("showdown_saved_lineups", []))
    ident = lineup_identity(rec)
    if any(lineup_identity(x) == ident for x in saved):
        st.warning("That exact CPT/FLEX lineup is already saved.")
    else:
        saved.append(rec)
        st.session_state["showdown_saved_lineups"] = saved
        st.success(f"Saved lineup #{len(saved)}")

saved = list(st.session_state.get("showdown_saved_lineups", []))

st.subheader("Saved Showdown Lineups")
if not saved:
    st.info("No saved Showdown lineups yet.")
else:
    table = saved_lineups_table(saved, records)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Salary": st.column_config.NumberColumn("Salary", format="$%d"),
        },
    )

    a, b = st.columns([1, 1])
    with a:
        if st.button("DELETE LAST LINEUP", use_container_width=True):
            saved.pop()
            st.session_state["showdown_saved_lineups"] = saved
            st.rerun()
    with b:
        st.download_button(
            "DOWNLOAD DK LINEUPS CSV",
            data=export_lineup_only_csv(saved, records),
            file_name="nuke_showdown_lineups.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.subheader("Exposure")
    player_exp, captain_exp = exposure_tables(saved, records)
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("#### Overall Player Exposure")
        st.dataframe(player_exp, use_container_width=True, hide_index=True)
    with e2:
        st.markdown("#### Captain Exposure")
        st.dataframe(captain_exp, use_container_width=True, hide_index=True)

st.divider()
st.caption("Showdown V1 is the lineup-building foundation. Next: game-script simulation, Captain leverage, lineup duplication logic, and Showdown portfolio generation.")

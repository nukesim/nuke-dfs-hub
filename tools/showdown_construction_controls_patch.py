from pathlib import Path

page = Path('pages/13_SHOWDOWN_SIM.py')
engine = Path('nuke_showdown_sim.py')
workspace = Path('nuke_showdown_workspace.py')

# ---------- Engine ----------
s = engine.read_text(encoding='utf-8')
start = s.index('def add_lineup_labels(')
end = s.index('\ndef exposure_table(', start)
replacement = '''def _construction_label(cpt, flex, players):
    rows = players.reset_index(drop=True)
    inds = [int(cpt)] + list(map(int, flex))
    counts = Counter(rows.iloc[inds]["Team"].astype(str))
    ordered = counts.most_common()
    if not ordered:
        return "Unknown"
    if len(ordered) == 2 and ordered[0][1] == ordered[1][1]:
        return "3-3 Even"
    major_team, major_count = ordered[0]
    minor_count = ordered[1][1] if len(ordered) > 1 else 0
    return f"{major_team} {major_count}-{minor_count}"


def add_lineup_labels(results, players):
    if results.empty:
        return results
    rows = players.reset_index(drop=True)
    out = results.copy()
    out.insert(0, "CPT", [rows.iloc[i]["Name"] for i in out["_cpt"]])
    for k in range(5):
        out.insert(k + 1, f"FLEX{k+1}", [rows.iloc[list(x)[k]]["Name"] for x in out["_flex"]])
    constructions = [
        _construction_label(r["_cpt"], r["_flex"], rows)
        for _, r in out.iterrows()
    ]
    out.insert(6, "Construction", constructions)
    return out


def build_portfolio(
    results,
    players,
    count=20,
    max_player_pct=.75,
    max_cpt_pct=.35,
    player_mins=None,
    player_maxes=None,
    construction_mins=None,
    construction_maxes=None,
):
    if results.empty:
        return results
    target = max(1, int(count))
    player_mins = player_mins or {}
    player_maxes = player_maxes or {}
    construction_mins = construction_mins or {}
    construction_maxes = construction_maxes or {}

    global_player_max = max(1, int(np.floor(target * float(max_player_pct) + 1e-9)))
    global_cpt_max = max(1, int(np.floor(target * float(max_cpt_pct) + 1e-9)))
    min_counts = {
        i: int(np.ceil(target * max(0.0, min(1.0, float(player_mins.get(i, 0.0))))))
        for i in range(len(players))
    }
    max_counts = {}
    for i in range(len(players)):
        personal = max(0.0, min(1.0, float(player_maxes.get(i, 1.0))))
        personal_count = int(np.floor(target * personal + 1e-9))
        max_counts[i] = min(global_player_max, personal_count)

    construction_min_counts = {
        str(k): int(np.ceil(target * max(0.0, min(1.0, float(v)))))
        for k, v in construction_mins.items()
    }
    construction_max_counts = {
        str(k): int(np.floor(target * max(0.0, min(1.0, float(v))) + 1e-9))
        for k, v in construction_maxes.items()
    }

    player_counts = Counter()
    cpt_counts = Counter()
    construction_counts = Counter()
    chosen = []
    used = set()
    band = results.head(min(len(results), 6000)).reset_index(drop=True)

    for _ in range(target):
        best_idx = None
        best_value = None
        for ridx, r in band.iterrows():
            if ridx in used:
                continue
            cpt = int(r["_cpt"])
            inds = [cpt] + list(map(int, r["_flex"]))
            construction = _construction_label(cpt, r["_flex"], players)
            if cpt_counts[cpt] >= global_cpt_max:
                continue
            if any(player_counts[i] >= max_counts.get(i, global_player_max) for i in inds):
                continue
            if construction in construction_max_counts and construction_counts[construction] >= construction_max_counts[construction]:
                continue

            deficit_bonus = 0.0
            for i in inds:
                need = max(0, min_counts.get(i, 0) - player_counts[i])
                deficit_bonus += need * 1000.0
            construction_need = max(
                0,
                construction_min_counts.get(construction, 0) - construction_counts[construction],
            )
            deficit_bonus += construction_need * 1500.0
            value = deficit_bonus + float(r.get("NUKE Score", 0.0))
            if best_value is None or value > best_value:
                best_value = value
                best_idx = ridx

        if best_idx is None:
            break
        r = band.iloc[best_idx]
        cpt = int(r["_cpt"])
        inds = [cpt] + list(map(int, r["_flex"]))
        construction = _construction_label(cpt, r["_flex"], players)
        chosen.append(r)
        used.add(best_idx)
        cpt_counts[cpt] += 1
        player_counts.update(inds)
        construction_counts[construction] += 1

    return pd.DataFrame(chosen).reset_index(drop=True) if chosen else results.iloc[0:0].copy()
'''
s = s[:start] + replacement + s[end:]
engine.write_text(s, encoding='utf-8')

# ---------- Workspace ----------
s = workspace.read_text(encoding='utf-8')
needle = '    "showdown_manual_seed",\n]'
if needle not in s:
    raise SystemExit('workspace control anchor missing')
s = s.replace(needle, '    "showdown_manual_seed",\n    "showdown_construction_controls",\n]', 1)
workspace.write_text(s, encoding='utf-8')

# ---------- Page ----------
s = page.read_text(encoding='utf-8')

# Add construction controls before Simulation Settings.
anchor = 'with st.expander("Simulation Settings", expanded=True):\n'
if anchor not in s:
    raise SystemExit('simulation settings anchor missing')
insert = '''st.subheader("🧱 Construction Limits")
st.caption("Control the team build mix in the final portfolio. 3-3 is even; team-specific 4-2 and 5-1 builds show which team supplies the majority of the lineup.")
construction_styles = [f"{team_a} 5-1", f"{team_b} 5-1", f"{team_a} 4-2", f"{team_b} 4-2", "3-3 Even"]
construction_state = dict(st.session_state.get("showdown_construction_controls", {}) or {})
construction_rows = []
for style in construction_styles:
    cfg = construction_state.get(style, {})
    construction_rows.append({
        "Construction": style,
        "Min %": int(cfg.get("min", 0)),
        "Max %": int(cfg.get("max", 100)),
    })
construction_editor = st.data_editor(
    pd.DataFrame(construction_rows),
    use_container_width=True,
    hide_index=True,
    disabled=["Construction"],
    column_config={
        "Construction": st.column_config.TextColumn("Construction", width="medium"),
        "Min %": st.column_config.NumberColumn("Min %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),
        "Max %": st.column_config.NumberColumn("Max %", min_value=0, max_value=100, step=5, format="%d%%", width="small"),
    },
    key="showdown_construction_editor",
)
construction_state = {}
for _, row in construction_editor.iterrows():
    mn = int(row["Min %"]); mx = int(row["Max %"])
    if mn > mx:
        mn = mx
    construction_state[str(row["Construction"])] = {"min": mn, "max": mx}
st.session_state["showdown_construction_controls"] = construction_state
construction_mins = {k: float(v["min"]) / 100.0 for k, v in construction_state.items()}
construction_maxes = {k: float(v["max"]) / 100.0 for k, v in construction_state.items()}
if sum(v["min"] for v in construction_state.values()) > 100:
    st.warning("Construction minimums add up to more than 100%. Lower the Min % values before running the SIM.")

'''
s = s.replace(anchor, insert + anchor, 1)

# Pass construction constraints to portfolio builder.
old = '''            player_mins=player_mins, player_maxes=player_maxes,
        )'''
new = '''            player_mins=player_mins, player_maxes=player_maxes,
            construction_mins=construction_mins, construction_maxes=construction_maxes,
        )'''
if old not in s:
    raise SystemExit('portfolio call anchor missing')
s = s.replace(old, new, 1)

# Rename lineup table column.
s = s.replace('"CPT", "FLEX1", "FLEX2", "FLEX3", "FLEX4", "FLEX5", "Split", "Salary",',
              '"CPT", "FLEX1", "FLEX2", "FLEX3", "FLEX4", "FLEX5", "Construction", "Salary",')

# Remove Game-Script Leaders block.
start_marker = 'st.subheader("Game-Script Leaders")\n'
end_marker = 'st.subheader("NUKE Showdown Portfolio")\n'
if start_marker not in s or end_marker not in s:
    raise SystemExit('game script section anchors missing')
a = s.index(start_marker)
b = s.index(end_marker, a)
s = s[:a] + s[b:]

# Replace final construction mix table with team-aware exposure table.
old = '''    split_counts = p["Split"].value_counts().rename_axis("Construction").reset_index(name="Lineups")
    st.markdown("#### Construction Mix")
    st.dataframe(split_counts, use_container_width=True, hide_index=True)
'''
new = '''    construction_counts = p["Construction"].value_counts().reindex(construction_styles, fill_value=0)
    construction_mix = construction_counts.rename_axis("Construction").reset_index(name="Lineups")
    construction_mix["Construction %"] = (100.0 * construction_mix["Lineups"] / max(1, len(p))).round(1)
    construction_mix["Min %"] = construction_mix["Construction"].map(lambda x: construction_state.get(x, {}).get("min", 0))
    construction_mix["Max %"] = construction_mix["Construction"].map(lambda x: construction_state.get(x, {}).get("max", 100))
    st.markdown("#### Construction Mix")
    st.dataframe(construction_mix, use_container_width=True, hide_index=True)
'''
if old not in s:
    raise SystemExit('construction mix anchor missing')
s = s.replace(old, new, 1)

page.write_text(s, encoding='utf-8')
print('patched team-aware Showdown construction controls')

from pathlib import Path
import re


def rep(text, old, new, label):
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"Missing anchor: {label}")


# ---------- nuke_sim.py ----------
p = Path("nuke_sim.py")
s = p.read_text()
if "from dfs_platform import get_platform, player_name_series" not in s:
    s = s.replace("import pandas as pd\n", "import pandas as pd\nfrom dfs_platform import get_platform, player_name_series\n", 1)
s = s.replace("def prepare_slate(df):", "def prepare_slate(df,site=\"DK\"):", 1)
s = s.replace('"Name":["Name","name","Player","player","Name + ID"]', '"Name":["Name","name","Nickname","nickname","Player","player","Name + ID"]', 1)
s = s.replace('"Status":["Status","status","Injury Status","injury_status"]', '"Status":["Status","status","Injury Status","injury_status","Injury Indicator"]', 1)
anchor = '    for t,opts in aliases.items():\n        c=next((c for c in opts if c in df.columns),None); out[t]=df[c] if c else ""\n'
if anchor in s and "player_name_series(df)" not in s:
    s = s.replace(anchor, anchor + '    if not out["Name"].astype(str).str.strip().ne("").any():\n        names=player_name_series(df)\n        if names is not None: out["Name"]=names\n', 1)
s = s.replace('out.ID=out.ID.fillna("").astype(str); out.Status=out.Status.fillna("").astype(str).str.upper().str.strip()', 'out.ID=out.ID.fillna("").astype(str); out.Status=out.Status.fillna("").astype(str).str.upper().str.strip().replace({"O":"OUT"})', 1)
old_return = '    return _attach_auto_roles(out).reset_index(drop=True)\n'
new_return = '    out=_attach_auto_roles(out).reset_index(drop=True)\n    out.attrs["site"]=get_platform(site).code\n    return out\n'
if old_return in s:
    s = s.replace(old_return, new_return, 1)
s = s.replace('def _valid_lineup(indices,p,min_salary,max_salary=50000):', 'def _valid_lineup(indices,p,min_salary,max_salary=None,site="DK"):\n    if max_salary is None: max_salary=get_platform(site).salary_cap', 1)
s = s.replace('def generate_lineups(players,n_lineups=600,min_salary=49400,seed=26):', 'def generate_lineups(players,n_lineups=600,min_salary=None,seed=26,site="DK"):', 1)
s = s.replace('    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)\n    if p.empty:return []\n    min_salary=max(49400,int(min_salary)); n_lineups=int(n_lineups)', '    rng=np.random.default_rng(seed); p=players.reset_index(drop=True)\n    if p.empty:return []\n    cfg=get_platform(site); salary_cap=int(cfg.salary_cap); min_salary=int(cfg.default_min_salary if min_salary is None else min_salary); n_lineups=int(n_lineups)', 1)
s = s.replace('max_flex_salary=50000-partial', 'max_flex_salary=salary_cap-partial')
s = s.replace('lo=min_salary-partial; hi=50000-partial', 'lo=min_salary-partial; hi=salary_cap-partial')
p.write_text(s)

# ---------- nuke_football_v2.py ----------
p = Path("nuke_football_v2.py")
s = p.read_text()
if "from dfs_platform import get_platform" not in s:
    s = s.replace("import numpy as np\n", "import numpy as np\nfrom dfs_platform import get_platform\n", 1)
s = s.replace('def simulate_player_matrix_v2(players,n_sims=1500,seed=26,game_environment=None):', 'def simulate_player_matrix_v2(players,n_sims=1500,seed=26,game_environment=None,site="DK"):\n    cfg=get_platform(site)', 1)
s = s.replace('            pts=rec+.1*(rec_y+rush_y)+6*tds[:,js]+3*(rec_y>=100)+3*(rush_y>=100)', '            pts=cfg.reception_points*rec+.1*(rec_y+rush_y)+6*tds[:,js]\n            if cfg.yardage_bonuses: pts=pts+3*(rec_y>=100)+3*(rush_y>=100)', 1)
s = s.replace('                pts=.04*py+4*pass_td-ints+.1*ry+6*rtd+3*(py>=300)', '                pts=.04*py+4*pass_td-ints+.1*ry+6*rtd\n                if cfg.yardage_bonuses: pts=pts+3*(py>=300)', 1)
p.write_text(s)

# ---------- nuke_football_v21.py ----------
p = Path("nuke_football_v21.py")
s = p.read_text()
if "from dfs_platform import normalize_site" not in s:
    s = s.replace("import numpy as np\n", "import numpy as np\nfrom dfs_platform import normalize_site\n", 1)
if "def engine_version" not in s:
    s = s.replace('ENGINE_VERSION = "Football Engine V2.1 + Live Game Environment"\n', 'ENGINE_VERSION = "Football Engine V2.1 + Live Game Environment"\n\ndef engine_version(site="DK"):\n    return ENGINE_VERSION if normalize_site(site)=="DK" else "Football Engine V2 + FanDuel Scoring + Live Game Environment"\n', 1)
s = s.replace('def simulate_player_matrix_v21(players, n_sims=1500, seed=26, game_environment=None):', 'def simulate_player_matrix_v21(players, n_sims=1500, seed=26, game_environment=None, site="DK"):', 1)
s = s.replace('        game_environment=env,\n    )\n    return apply_v21_calibration(players, original)', '        game_environment=env,\n        site=site,\n    )\n    # V2.1 calibration was validated on DraftKings scoring. FanDuel uses the same\n    # generative football outcomes with FanDuel scoring, without applying DK-only calibration.\n    return apply_v21_calibration(players, original) if normalize_site(site)=="DK" else original', 1)
p.write_text(s)

# ---------- pages/6_SIM.py ----------
p = Path("pages/6_SIM.py")
s = p.read_text()
s = s.replace('from dk_export import build_lineup_only_csv, fill_entries_csv, add_dk_roster_columns', 'from dfs_export import build_lineup_only_csv, fill_entries_csv, add_dk_roster_columns', 1)
s = s.replace('from nuke_football_v21 import simulate_player_matrix_v21, ENGINE_VERSION', 'from nuke_football_v21 import simulate_player_matrix_v21, ENGINE_VERSION, engine_version', 1)
if "from dfs_platform import get_platform" not in s:
    s = s.replace('from nuke_bridge import sync_hub_pool_to_sim, portfolio_to_hub_rows\n', 'from nuke_bridge import sync_hub_pool_to_sim, portfolio_to_hub_rows\nfrom dfs_platform import get_platform\n', 1)
s = s.replace('st.caption(f"Projection-free NFL DFS outcome + contest simulation inside the NUKE DFS Hub · {ENGINE_VERSION}.")', 'st.caption("Projection-free NFL DFS outcome + contest simulation for DraftKings and FanDuel.")', 1)
old = '    st.header("SIM CONTROL ROOM")\n    preset=st.selectbox("Preset",["QUICK","STANDARD","DEEP"],index=0)'
new = '    st.header("SIM CONTROL ROOM")\n    site=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="dfs_site") or "DK"\n    cfg=get_platform(site)\n    st.caption(f"{cfg.name} · ${cfg.salary_cap:,} cap · {\'1.0 PPR + yardage bonuses\' if site==\'DK\' else \'0.5 PPR · no 100/300-yard bonuses\'}")\n    preset=st.selectbox("Preset",["QUICK","STANDARD","DEEP"],index=0)'
s = rep(s, old, new, "SIM platform selector")
s = s.replace('    min_salary=st.number_input("Minimum salary",45000,50000,49400,100)', '    min_salary=st.number_input("Minimum salary",cfg.min_salary_input,cfg.max_salary_input,cfg.default_min_salary,100,key=f"min_salary_{site}")', 1)
old_upload = 'salary_upload=st.file_uploader("Optional: upload a different DraftKings NFL salary CSV",type=["csv"],help="Leave this empty to use the built-in current weekly slate.")\ntry:\n    if salary_upload is not None:\n        raw_slate=pd.read_csv(salary_upload)\n        slate_source=f"Uploaded override: {salary_upload.name}"\n        st.info(f"Using uploaded slate: **{salary_upload.name}**")\n    else:\n        raw_slate=load_default_slate()\n        slate_source=SLATE_LABEL\n        st.success(f"Loaded automatically: **{SLATE_LABEL}** · {len(raw_slate):,} players")'
new_upload = 'salary_upload=st.file_uploader(f"{\'Optional: upload a different DraftKings NFL salary CSV\' if site==\'DK\' else \'Upload FanDuel NFL salary CSV\'}",type=["csv"],key=f"salary_upload_{site}",help="DraftKings can use the built-in weekly slate. FanDuel currently uses the official FanDuel salary CSV so its player IDs and $60K salaries are exact.")\ntry:\n    if salary_upload is not None:\n        raw_slate=pd.read_csv(salary_upload)\n        slate_source=f"{cfg.name} upload: {salary_upload.name}"\n        st.info(f"Using {cfg.name} slate: **{salary_upload.name}**")\n    elif site=="DK":\n        raw_slate=load_default_slate()\n        slate_source=SLATE_LABEL\n        st.success(f"Loaded automatically: **{SLATE_LABEL}** · {len(raw_slate):,} players")\n    else:\n        st.info("FanDuel mode is ready. Upload the FanDuel NFL salary CSV for this slate to use exact FanDuel salaries and player IDs.")\n        st.stop()'
s = rep(s, old_upload, new_upload, "SIM salary upload")
s = s.replace('payout_upload=st.file_uploader("Optional: upload DraftKings payout CSV / Excel",type=["csv","xlsx","xls"],key="dk_payout_upload")', 'payout_upload=st.file_uploader(f"Optional: upload {cfg.name} payout CSV / Excel",type=["csv","xlsx","xls"],key=f"payout_upload_{site}")', 1)
s = s.replace('players=prepare_slate(raw_slate)', 'players=prepare_slate(raw_slate,site=site)', 1)
s = s.replace('st.caption("Sportsbook lines are not loaded yet, so NUKE is temporarily using its DK salary-market estimates. Rank 1 = strongest on the slate.")', 'st.caption(f"Sportsbook lines are not loaded yet, so NUKE is temporarily using its {cfg.name} salary-market estimates. Rank 1 = strongest on the slate.")', 1)
# Add site=site to candidate and football-engine calls, preserving existing positional args.
s = re.sub(r'generate_lineups\(([^\n()]*)\)', lambda m: m.group(0) if 'site=' in m.group(1) else 'generate_lineups('+m.group(1)+',site=site)', s)
s = re.sub(r'simulate_player_matrix_v21\(([^\n()]*)\)', lambda m: m.group(0) if 'site=' in m.group(1) else 'simulate_player_matrix_v21('+m.group(1)+',site=site)', s)
s = s.replace('{ENGINE_VERSION}', '{engine_version(site)}')
s = s.replace('DraftKings Entries CSV', '{cfg.name} Entries CSV')
s = s.replace('DraftKings CSV', '{cfg.name} CSV')
s = s.replace('DraftKings upload', '{cfg.name} upload')
p.write_text(s)

# ---------- app.py: hand-builder platform cap + platform switch ----------
p = Path("app.py")
s = p.read_text()
if "from dfs_platform import get_platform" not in s:
    s = s.replace('from nuke_bridge import portable_to_hub_lineup\n', 'from nuke_bridge import portable_to_hub_lineup\nfrom dfs_platform import get_platform\n', 1)
s = s.replace('CAP = 50000\nMAX_LU = 50', 'SITE = st.session_state.get("dfs_site","DK")\nCAP = get_platform(SITE).salary_cap\nMAX_LU = 50', 1)
# Insert a simple platform switch immediately after init() is called if we can find that call.
if 'key="hub_platform"' not in s:
    marker = 'init()\n'
    insert = 'init()\n\n_platform=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="hub_platform") or "DK"\nif _platform!=st.session_state.get("dfs_site","DK"):\n    st.session_state["dfs_site"]=_platform\n    # Platform salaries and IDs are not interchangeable; clear weekly lineup state on switch.\n    st.session_state["slate"]=None\n    st.session_state["slate_name"]="No slate loaded"\n    st.session_state["pool_ids"]=set()\n    st.session_state["saved_lineups"]=[]\n    st.session_state["lineups"]=[empty_lu() for _ in range(MAX_LU)]\n    st.rerun()\nSITE=st.session_state.get("dfs_site","DK")\nCAP=get_platform(SITE).salary_cap\nst.caption(f"{get_platform(SITE).name} Classic · ${CAP:,} salary cap")\n'
    s = s.replace(marker, insert, 1)
# Make common slate copy platform-neutral and allow FanDuel nickname column in existing loader logic.
s = s.replace('DraftKings', '{get_platform(SITE).name}') if False else s
p.write_text(s)

print("FanDuel parity patch applied")

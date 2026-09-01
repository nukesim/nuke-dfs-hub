import streamlit as st
from nuke_nav import render_nav
import pandas as pd
import numpy as np
import time
from collections import Counter
from itertools import combinations
from nuke_sim import prepare_slate, simulate_player_matrix, generate_lineups, evaluate_lineups, exposure_table, position_exposure_table, flex_exposure_table
from nuke_contest import simulate_contest
from nuke_paths import attach_path_labels, path_exposure
from nuke_portfolio import build_portfolio, portfolio_summary, portfolio_player_exposure, portfolio_qb_exposure, portfolio_team_game_exposure, portfolio_stack_exposure, portfolio_health, PORTFOLIO_ENGINE_VERSION
from dk_contest_import import parse_payout_upload
from dfs_export import build_lineup_only_csv, fill_entries_csv, add_dk_roster_columns
from default_slate import load_default_slate, SLATE_LABEL
from nuke_football_v21 import simulate_player_matrix_v21, ENGINE_VERSION, engine_version, engine_version
from nuke_combos import combo_exposure_table
from nuke_game_pool import game_environment, style_environment
from nuke_odds import load_current_odds, load_odds_history, odds_status, movement_for_game
from nuke_portfolio_story import portfolio_story
from nuke_bridge import sync_hub_pool_to_sim, portfolio_to_hub_rows
from dfs_platform import get_platform
from fanduel_slate import load_fanduel_slate, has_fanduel_slate, FD_SLATE_LABEL
from nuke_availability import availability_status
from fd_export import lineup_to_fd_slots, ANALYSIS_ROSTER_HEADERS

def candidate_diagnostics(players,lineups,requested,min_salary):
    if not lineups:
        return {}
    lus=[tuple(map(int,lu)) for lu in lineups]
    n=len(lus)
    pair_counts=Counter()
    triple_counts=Counter()
    qb_names=set()
    games=set()
    salaries=[]
    for lu in lus:
        sorted_lu=tuple(sorted(lu))
        pair_counts.update(combinations(sorted_lu,2))
        triple_counts.update(combinations(sorted_lu,3))
        salary=0
        for pid in lu:
            if pid<0 or pid>=len(players):
                continue
            r=players.iloc[pid]
            salary+=int(r.Salary)
            if str(r.Position)=="QB":
                qb_names.add(str(r.Name))
            game=str(getattr(r,"Game",""))
            if game and game.lower()!="nan":
                games.add(game)
        salaries.append(salary)
    sample=lus if n<=300 else lus[:300]
    overlap_vals=[]
    for i in range(len(sample)):
        a=set(sample[i])
        for j in range(i+1,len(sample)):
            overlap_vals.append(len(a & set(sample[j])))
    avg_overlap=float(sum(overlap_vals)/len(overlap_vals)) if overlap_vals else 0.0
    median_overlap=float(np.median(overlap_vals)) if overlap_vals else 0.0
    p95_overlap=float(np.percentile(overlap_vals,95)) if overlap_vals else 0.0
    max_overlap_seen=int(max(overlap_vals)) if overlap_vals else 0
    max_pair=max(pair_counts.values()) if pair_counts else 0
    max_triple=max(triple_counts.values()) if triple_counts else 0
    max_pair_pct=100.0*max_pair/max(1,n)
    max_triple_pct=100.0*max_triple/max(1,n)
    avg_salary=float(sum(salaries)/max(1,len(salaries)))
    fill_pct=100.0*n/max(1,int(requested))
    checks=[fill_pct>=95.0,len(qb_names)>=6,len(games)>=6,avg_overlap<=5.5,max_pair_pct<=35.0,max_triple_pct<=20.0]
    score=100.0*sum(checks)/len(checks)
    grade="A" if score>=90 else "B" if score>=80 else "C" if score>=65 else "D" if score>=50 else "F"
    return {"grade":grade,"score":score,"generated":n,"requested":int(requested),"fill_pct":fill_pct,"unique_qbs":len(qb_names),"games":len(games),"avg_overlap":avg_overlap,"median_overlap":median_overlap,"p95_overlap":p95_overlap,"max_overlap_seen":max_overlap_seen,"max_pair_repeat":max_pair,"max_pair_pct":max_pair_pct,"max_triple_repeat":max_triple,"max_triple_pct":max_triple_pct,"avg_salary":avg_salary,"min_salary":int(min_salary)}

st.set_page_config(page_title="NUKE SIM",page_icon="☢️",layout="wide")
render_nav()
st.title("☢️ NUKE SIM")
st.caption("Projection-free NFL DFS outcome + contest simulation for DraftKings and FanDuel.")

with st.sidebar:
    st.header("SIM CONTROL ROOM")
    previous_site=st.session_state.get("nuke_sim_active_site")
    site=st.segmented_control("Platform",options=["DK","FD"],format_func=lambda x: "DraftKings" if x=="DK" else "FanDuel",default=st.session_state.get("dfs_site","DK"),key="dfs_site") or "DK"
    if previous_site is not None and previous_site != site:
        for key in [
            "nuke_sim_results","nuke_sim_players","nuke_sim_exposure","nuke_path_exposure",
            "nuke_contest_results","nuke_contest_summary","nuke_portfolio","nuke_portfolio_paths",
            "nuke_portfolio_stats","nuke_sim_runtime","nuke_stage_times","nuke_candidate_diagnostics",
            "nuke_player_takes","nuke_shared_portfolio_rows","nuke_shared_portfolio_version",
            "nuke_pregame_pool","nuke_pool_editor_version"
        ]:
            st.session_state.pop(key,None)
    st.session_state["nuke_sim_active_site"]=site
    cfg=get_platform(site)
    st.caption(f"{cfg.name} · ${cfg.salary_cap:,} cap · {'1.0 PPR + yardage bonuses' if site=='DK' else '0.5 PPR · no 100/300-yard bonuses'}")
    preset=st.selectbox("Preset",["QUICK","STANDARD","DEEP"],index=0)
    presets={"QUICK":(250,350,50,200),"STANDARD":(400,750,75,350),"DEEP":(700,1200,100,500)}
    candidates,sims,exposure_n,contest_iters=presets[preset]
    min_salary=st.number_input("Minimum salary",cfg.min_salary_input,cfg.max_salary_input,cfg.default_min_salary,100,key=f"min_salary_{site}")
    candidates=st.number_input("Candidate lineups",100,5000,candidates,100)
    sims=st.number_input("Football universes",250,10000,sims,250)
    exposure_n=st.number_input("Exposure sample",10,150,exposure_n,10)
    with st.expander("Advanced settings"):
        fixed_seed=st.checkbox("Use reproducible seed",value=False,help="Off by default: every RUN NUKE SIM click gets a fresh random simulation. Turn this on only when you want to reproduce a specific run.")
        if "nuke_manual_seed" not in st.session_state:
            st.session_state["nuke_manual_seed"]=int(np.random.default_rng().integers(1,2147483647))
        manual_seed=st.number_input("Random seed",1,2147483646,step=1,disabled=not fixed_seed,key="nuke_manual_seed")
    st.divider()
    st.subheader("Contest")
    field_size=st.number_input("Field size",2,100000,2222,1)
    entry_fee=st.number_input("Entry fee ($)",.25,10000.,100.,1.)
    first_prize=st.number_input("1st prize ($)",1.,10000000.,50000.,100.)
    st.caption("Every generated candidate lineup is contest-simmed automatically.")
    contest_iters=st.number_input("Contest iterations",50,5000,contest_iters,50)
    st.divider()
    st.subheader("Portfolio")
    portfolio_size=st.number_input("Portfolio size",1,150,150,1)
    max_overlap=st.slider("Max player overlap",4,8,7,1)
    path_balance=st.slider("Path diversification",0.,3.,1.25,.25)
    max_player_exp=st.slider("Max player exposure %",10,100,45,5)
    max_qb_exp=st.slider("Max QB exposure %",5,100,30,5)
    max_team_exp=st.slider("Max team exposure %",10,100,80,5)
    max_game_exp=st.slider("Max game exposure %",10,100,70,5)
    st.caption(f"{PORTFOLIO_ENGINE_VERSION}: tournament upside + player/team/game concentration controls. Duplication is not used to select your portfolio.")

st.subheader("🏈 Current Slate")
salary_upload=st.file_uploader(f"{'Optional: upload a different DraftKings NFL salary CSV' if site=='DK' else 'Upload FanDuel NFL salary CSV'}",type=["csv"],key=f"salary_upload_{site}",help="DraftKings can use the built-in weekly slate. FanDuel currently uses the official FanDuel salary CSV so its player IDs and $60K salaries are exact.")
try:
    if salary_upload is not None:
        raw_slate=pd.read_csv(salary_upload)
        slate_source=f"{cfg.name} upload: {salary_upload.name}"
        st.info(f"Using {cfg.name} slate: **{salary_upload.name}**")
    elif site=="DK":
        raw_slate=load_default_slate()
        slate_source=SLATE_LABEL
        st.success(f"Loaded automatically: **{SLATE_LABEL}** · {len(raw_slate):,} players")
    elif has_fanduel_slate():
        raw_slate=load_fanduel_slate()
        slate_source=FD_SLATE_LABEL
        st.success(f"Loaded automatically: **{FD_SLATE_LABEL}** · {len(raw_slate):,} players")
    else:
        st.info("FanDuel mode is ready. Upload the FanDuel NFL salary CSV for this slate. Once we commit it as data/fanduel_nfl_current.csv, FanDuel will auto-load weekly just like DraftKings.")
        st.stop()
except Exception as e:
    st.error(f"Could not load slate: {e}")
    st.stop()

st.subheader("🏆 Contest Payouts")
payout_upload=st.file_uploader(f"Optional: upload {cfg.name} payout CSV / Excel",type=["csv","xlsx","xls"],key=f"payout_upload_{site}")
payouts_override=None
if payout_upload is not None:
    try:
        payouts_override,payout_info=parse_payout_upload(payout_upload)
        a,b,c=st.columns(3)
        a.metric("Imported Paid Places",f"{int(payout_info['paid_places']):,}")
        b.metric("Imported 1st",f"${float(payout_info['first_prize']):,.0f}")
        c.metric("Imported Prize Pool",f"${float(payout_info['listed_prize_pool']):,.0f}")
        st.success("Real payout ladder loaded.")
    except Exception as e:
        st.error(f"Could not parse payout file: {e}")
        st.stop()
else:
    st.caption("No payout file uploaded — NUKE will use the modeled GPP payout curve.")

try:
    players=prepare_slate(raw_slate,site=site)
except Exception as e:
    st.error(f"Could not read this slate: {e}")
    st.stop()

# Automated player availability protection. The scheduled feed is joined before the pool editor.
players,availability_meta=availability_status(players)
if availability_meta.get("loaded"):
    red=int(availability_meta.get("red",0)); yellow=int(availability_meta.get("yellow",0))
    updated=availability_meta.get("updated","")
    if red:
        st.warning(f"🚑 Player Availability · {red} OUT/inactive auto-excluded · {yellow} questionable/doubtful kept in pool" + (f" · Updated {updated}" if updated else ""))
    else:
        st.success(f"🚑 Player Availability ✓ · 0 OUT/inactive · {yellow} questionable/doubtful" + (f" · Updated {updated}" if updated else ""))
    for warning in availability_meta.get("qb_warnings",[]):
        st.warning(f"⚠️ Starting QB alert: {warning}")
else:
    st.info("🚑 Player Availability feed not connected yet — no automatic injury exclusions are being applied.")

# One-stop injury review so users do not have to hunt through every game.
flagged=players[players["Availability"].astype(str).str.lower().ne("available")].copy() if "Availability" in players.columns else players.iloc[0:0].copy()
if not flagged.empty:
    with st.expander(f"🚑 Injuries & Availability · {len(flagged)} flagged", expanded=True):
        st.caption("OUT/inactive players default to excluded. Questionable/doubtful players stay available but are flagged for review.")
        flagged["NUKE Action"]=flagged["Auto Exclude"].map(lambda x: "🔴 EXCLUDED" if bool(x) else "🟡 INCLUDED / REVIEW")
        cols=[c for c in ["Name","Team","Position","Availability","Availability Detail","NUKE Action"] if c in flagged.columns]
        show=flagged[cols].copy()
        rename={"Name":"Player","Position":"Pos","Availability":"Status","Availability Detail":"Detail"}
        show=show.rename(columns=rename)
        show=show.fillna("")
        st.dataframe(show,use_container_width=True,hide_index=True)
else:
    if availability_meta.get("loaded"):
        st.caption("🚑 Injuries & Availability · No flagged players on the current slate.")

c1,c2,c3,c4,c5=st.columns(5)
c1.metric("Players",len(players))
c2.metric("Teams",players.Team.nunique())
c3.metric("Games",players.Game.nunique())
c4.metric("Salary Floor",f"${int(min_salary):,}")
c5.metric("Slate",slate_source)

st.subheader("🎮 Game-by-Game Player Pool")
st.caption("Work the slate one game at a time. Include/remove players, adjust role if needed, then apply the game once.")
current_odds=load_current_odds()
odds_history=load_odds_history()
odds_meta=odds_status(current_odds)
env=game_environment(players,current_odds)
if not env.empty:
    sportsbook_games=int(env[env["Source"].eq("Sportsbook Consensus")]["Game"].nunique()) if "Source" in env.columns else 0
    if sportsbook_games:
        rem=odds_meta.get("credits_remaining")
        rem_text=f" · {rem} free API credits remaining" if rem is not None else ""
        st.caption(f"Sportsbook consensus is live for {sportsbook_games} slate games. Team totals are implied from consensus spread + game total. Auto-updated throughout the week{rem_text}. Rank 1 = strongest on the slate.")
    else:
        st.caption(f"Sportsbook lines are not loaded yet, so NUKE is temporarily using its {cfg.name} salary-market estimates. Rank 1 = strongest on the slate.")

pool_state=st.session_state.get("nuke_pregame_pool",{})
editor_version=int(st.session_state.get("nuke_pool_editor_version",0))

# Hub and SIM share Streamlit session state. Pull the committed Hub pool and role adjustments
# only when those Hub inputs change; later SIM-only edits remain intact until the Hub changes again.
hub_pool=list(st.session_state.get("pool_ids",[]) or [])
hub_adjust=dict(st.session_state.get("projection_overrides",{}) or {})
hub_signature=(tuple(sorted(map(str,hub_pool))),tuple(sorted((str(k),float(v)) for k,v in hub_adjust.items())))
last_hub_signature=st.session_state.get("nuke_sim_hub_signature")
if (hub_pool or hub_adjust) and hub_signature!=last_hub_signature:
    pool_state=sync_hub_pool_to_sim(players,pool_state,hub_pool,hub_adjust)
    st.session_state["nuke_pregame_pool"]=pool_state
    st.session_state["nuke_sim_hub_signature"]=hub_signature
    st.session_state["nuke_pool_editor_version"]=editor_version+1
    editor_version+=1
    st.success(f"Synced from Hub · {len(hub_pool) if hub_pool else 'all'} players in committed pool · {len(hub_adjust)} role adjustments")

for _,row in players.iterrows():
    key=str(row.ID) if str(row.ID) else f"{row.Name}|{row.Team}|{row.Position}|{int(row.Salary)}"
    auto_exclude=bool(row.get("Auto Exclude",False))
    pool_state.setdefault(key,{"include":not auto_exclude,"role":"AUTO","usage":1.0})

updated_state=dict(pool_state)
needs_rerun=False

game_values=players.Game.drop_duplicates().tolist()
game_labels={}
for game in game_values:
    gp0=players[players.Game.eq(game)]
    teams0=list(dict.fromkeys(gp0.Team.astype(str).tolist()))
    game_labels[game]=" vs ".join(teams0[:2]) if len(teams0)>=2 else str(game)

selected_game=st.selectbox(
    "Open game",game_values,
    format_func=lambda g: f"🏈 {game_labels.get(g,str(g))}",
    key="nuke_active_pool_game",
    help="Only the selected game is rendered. This keeps the SIM page fast even on large slates."
) if game_values else None

if selected_game is not None:
    game=selected_game
    gp=players[players.Game.eq(game)].copy()
    teams=list(dict.fromkeys(gp.Team.astype(str).tolist()))
    label=game_labels.get(game,str(game))
    ge=env[env.Game.eq(str(game))].copy() if not env.empty else pd.DataFrame()
    st.markdown(f"### 🏈 {label}")
    if not ge.empty:
        env_cols=["Team","Opponent","Spread","Team Total","Team Total Rank","Game Total","Game Total Rank","Books","Source"]
        env_show=ge[[c for c in env_cols if c in ge.columns]]
        st.dataframe(style_environment(env_show),use_container_width=True,hide_index=True)
        book_rows=ge[ge["Source"].eq("Sportsbook Consensus")] if "Source" in ge.columns else pd.DataFrame()
        if not book_rows.empty:
            last_update=str(book_rows.iloc[0].get("Last Update",""))
            st.caption(f"Consensus across {int(book_rows['Books'].max()) if 'Books' in book_rows.columns else 0} US sportsbooks · Last odds snapshot: {last_update}")
            movement=movement_for_game(odds_history,teams)
            if not movement.empty:
                with st.expander("📈 Odds movement this week",expanded=False):
                    chart_cols=[c for c in ["Game Total",f"{teams[0]} Team Total",f"{teams[1]} Team Total"] if c in movement.columns]
                    if chart_cols:
                        chart_df=movement[["Timestamp"]+chart_cols].copy().set_index("Timestamp")
                        st.line_chart(chart_df,use_container_width=True)
                    first,last=movement.iloc[0],movement.iloc[-1]
                    m1,m2,m3=st.columns(3)
                    gt0=float(first.get("Game Total",0)); gt1=float(last.get("Game Total",0))
                    a_col=f"{teams[0]} Team Total"; b_col=f"{teams[1]} Team Total"
                    a0=float(first.get(a_col,0)); a1=float(last.get(a_col,0)); b0=float(first.get(b_col,0)); b1=float(last.get(b_col,0))
                    m1.metric("Game Total",f"{gt1:.1f}",delta=f"{gt1-gt0:+.1f} vs first snapshot")
                    m2.metric(f"{teams[0]} Team Total",f"{a1:.1f}",delta=f"{a1-a0:+.1f}")
                    m3.metric(f"{teams[1]} Team Total",f"{b1:.1f}",delta=f"{b1-b0:+.1f}")
                    spread_cols=[c for c in [f"{teams[0]} Spread",f"{teams[1]} Spread"] if c in movement.columns]
                    if spread_cols:
                        st.caption("Spread movement")
                        st.line_chart(movement[["Timestamp"]+spread_cols].set_index("Timestamp"),use_container_width=True)
    st.caption("Only this game's controls are loaded. Make as many changes as you want, then click Apply changes once.")
    with st.form(key=f"pool_form_{str(game)}_{editor_version}",clear_on_submit=False):
        game_action=st.selectbox("Game bulk action",["No bulk change","✅ Include entire game","🚫 Exclude entire game"],key=f"game_bulk_{str(game)}_{editor_version}")
        visible_teams=teams[:2]
        team_cols=st.columns(len(visible_teams)) if visible_teams else [st.container()]
        pending_by_team={}
        team_actions={}
        for team_col,team in zip(team_cols,visible_teams):
            tp=gp[gp.Team.eq(team)].copy()
            pos_order={"QB":0,"RB":1,"WR":2,"TE":3,"DST":4}
            tp["_pos_order"]=tp.Position.map(pos_order).fillna(9)
            tp=tp.sort_values(["_pos_order","Salary"],ascending=[True,False])
            trow=ge[ge.Team.eq(team)].iloc[0] if not ge.empty and ge.Team.eq(team).any() else None
            with team_col:
                if trow is not None:
                    st.markdown(f"### {team} · {float(trow['Team Total']):.1f} · Rank #{int(trow['Team Total Rank'])}")
                else:
                    st.markdown(f"### {team}")
                team_actions[team]=st.selectbox(f"{team} bulk action",["No bulk change","✅ Include all","🚫 Exclude all"],key=f"team_bulk_{str(game)}_{team}_{editor_version}",label_visibility="collapsed")
                rows=[]
                for idx,row in tp.iterrows():
                    key=str(row.ID) if str(row.ID) else f"{row.Name}|{row.Team}|{row.Position}|{int(row.Salary)}"
                    cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})
                    rows.append({"_row":int(idx),"_key":key,"Include":bool(cfg.get("include",True)),"Pos":row.Position,"Player":row.Name,"Status":str(row.get("Availability","Available")),"Salary":int(row.Salary),"Auto Role":row.auto_role,"Role":str(cfg.get("role","AUTO")),"Usage x":float(cfg.get("usage",1.0))})
                edit_df=pd.DataFrame(rows).set_index("_row")
                edited_team=st.data_editor(
                    edit_df.drop(columns=["_key"]),use_container_width=True,hide_index=True,
                    disabled=["Pos","Player","Status","Salary","Auto Role"],
                    column_order=["Include","Pos","Player","Status","Salary","Auto Role","Role","Usage x"],
                    column_config={
                        "Include":st.column_config.CheckboxColumn("Include",width="small"),
                        "Pos":st.column_config.TextColumn("Pos",width="small"),
                        "Player":st.column_config.TextColumn("Player",width="medium"),
                        "Status":st.column_config.TextColumn("Status",width="small",help="Automated injury/availability status. OUT/inactive players default to excluded; questionable players remain available."),
                        "Salary":st.column_config.NumberColumn("Salary",format="$%d",width="small"),
                        "Auto Role":st.column_config.TextColumn("Auto Role",width="small"),
                        "Role":st.column_config.SelectboxColumn("Role",options=["AUTO","QB1","RB1","RB2","RB3","WR1","WR2","WR3","TE1","BACKUP"],width="small"),
                        "Usage x":st.column_config.NumberColumn("Usage x",min_value=.25,max_value=2.25,step=.05,format="%.2f",width="small",help="Changes the football simulation itself. Leave at 1.00 unless you believe actual usage changes."),
                    },key=f"game_pool_{str(game)}_{team}_{editor_version}"
                )
                pending_by_team[team]=(edit_df,edited_team)
                excluded_count=sum(not bool(updated_state.get(str(r.ID) if str(r.ID) else f"{r.Name}|{r.Team}|{r.Position}|{int(r.Salary)}",{}).get("include",True)) for _,r in tp.iterrows())
                if excluded_count:
                    st.caption(f"🚫 Currently excluded: {excluded_count}")
        apply_changes=st.form_submit_button(f"Apply changes for {label}",type="primary",use_container_width=True)
    if apply_changes:
        for team,(edit_df,edited_team) in pending_by_team.items():
            action=team_actions.get(team,"No bulk change")
            for idx,erow in edited_team.iterrows():
                key=str(edit_df.loc[idx,"_key"])
                include=bool(erow["Include"])
                if action=="✅ Include all": include=True
                elif action=="🚫 Exclude all": include=False
                if game_action=="✅ Include entire game": include=True
                elif game_action=="🚫 Exclude entire game": include=False
                updated_state[key]={"include":include,"role":str(erow["Role"]),"usage":float(erow["Usage x"])}
        st.session_state["nuke_pregame_pool"]=updated_state
        st.session_state["nuke_pool_editor_version"]=editor_version+1
        st.rerun()

st.session_state["nuke_pregame_pool"]=updated_state
active_rows=[]
for _,row in players.iterrows():
    key=str(row.ID) if str(row.ID) else f"{row.Name}|{row.Team}|{row.Position}|{int(row.Salary)}"
    cfg=updated_state.get(key,{"include":True,"role":"AUTO","usage":1.0})
    if cfg.get("include",True):
        r=row.copy()
        r["role_override"]=str(cfg.get("role","AUTO")).upper()
        r["usage_multiplier"]=float(cfg.get("usage",1.0))
        active_rows.append(r)
players=pd.DataFrame(active_rows).reset_index(drop=True) if active_rows else players.iloc[0:0].copy()
if not players.empty:
    st.caption(f"Active pool: {len(players):,} players")

if st.button("☢️ RUN NUKE SIM",type="primary",use_container_width=True):
    run_started=time.perf_counter()
    stage_times={}
    seed=int(manual_seed) if fixed_seed else int.from_bytes(__import__("secrets").token_bytes(4), "big") % 2147483646 + 1
    if len(players)<9:
        st.error("Not enough active players.")
        st.stop()
    with st.status("NUKE SIM is running...",expanded=True) as status:
        stage=time.perf_counter()
        st.write(f"1/5 · Generating correlated {get_platform(site).name} candidates...")
        lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed),site=site)
        stage_times["Candidate Generation"]=time.perf_counter()-stage
        st.write(f"Candidate generation: {stage_times['Candidate Generation']:.1f}s")
        if not lineups:
            status.update(label="No legal lineups found",state="error")
            st.stop()
        st.write(f"Generated {len(lineups):,} unique candidates.")
        candidate_diag=candidate_diagnostics(players,lineups,int(candidates),int(min_salary))
        st.write(f"Candidate Pool Health: {candidate_diag.get('grade','?')} · {candidate_diag.get('score',0):.0f}/100")
        stage=time.perf_counter()
        st.write(f"2/5 · Simulating {int(sims):,} correlated football universes with {engine_version(site)}...")
        matrix=simulate_player_matrix_v21(players,int(sims),int(seed))
        stage_times["Football Simulation"]=time.perf_counter()-stage
        st.write(f"Football simulation: {stage_times['Football Simulation']:.1f}s")
        stage=time.perf_counter()
        st.write("3/5 · Ranking outcomes and assigning paths...")
        results=attach_path_labels(players,evaluate_lineups(players,lineups,matrix))
        exposure=exposure_table(players,results,int(exposure_n))
        stage_times["Ranking + Paths"]=time.perf_counter()-stage
        st.write(f"Ranking + paths: {stage_times['Ranking + Paths']:.1f}s")
        stage=time.perf_counter()
        st.write(f"4/5 · Contest-simming all {len(results):,} candidates...")
        contest_results,contest_summary=simulate_contest(results=results,player_matrix=matrix,field_size=int(field_size),entry_fee=float(entry_fee),first_prize=float(first_prize),iterations=int(contest_iters),seed=int(seed)+97,payouts_override=payouts_override,players=players)
        stage_times["Contest Simulation"]=time.perf_counter()-stage
        st.write(f"Contest simulation: {stage_times['Contest Simulation']:.1f}s")
        stage=time.perf_counter()
        st.write(f"5/5 · Building {PORTFOLIO_ENGINE_VERSION} portfolio...")
        portfolio=build_portfolio(contest_results,size=int(portfolio_size),max_overlap=int(max_overlap),path_balance=float(path_balance),max_player_exposure=float(max_player_exp)/100.0,max_qb_exposure=float(max_qb_exp)/100.0,players=players,max_team_exposure=float(max_team_exp)/100.0,max_game_exposure=float(max_game_exp)/100.0)
        portfolio_paths,portfolio_stats=portfolio_summary(portfolio)
        pexposure=path_exposure(portfolio,len(portfolio))
        stage_times["Portfolio Build"]=time.perf_counter()-stage
        st.write(f"Portfolio build: {stage_times['Portfolio Build']:.1f}s")
        run_seconds=time.perf_counter()-run_started
        stage_times["Other / UI Overhead"]=max(0.0,run_seconds-sum(stage_times.values()))
        initial_takes={}
        st.session_state["nuke_shared_portfolio_rows"]=portfolio_to_hub_rows(players,portfolio)
        st.session_state["nuke_shared_portfolio_version"]=int(st.session_state.get("nuke_shared_portfolio_version",0))+1
        for k,v in {"nuke_sim_results":results,"nuke_sim_players":players.copy(),"nuke_sim_exposure":exposure,"nuke_path_exposure":pexposure,"nuke_contest_results":contest_results,"nuke_contest_summary":contest_summary,"nuke_portfolio":portfolio,"nuke_portfolio_paths":portfolio_paths,"nuke_portfolio_stats":portfolio_stats,"nuke_sim_runtime":run_seconds,"nuke_stage_times":stage_times,"nuke_candidate_diagnostics":candidate_diag,"nuke_player_takes":initial_takes}.items():
            st.session_state[k]=v
        status.update(label=f"NUKE SIM complete · {run_seconds:.1f}s",state="complete")
    st.success(f"Total run time: {run_seconds:.1f} seconds")

results=st.session_state.get("nuke_sim_results")
sim_players=st.session_state.get("nuke_sim_players")
exposure=st.session_state.get("nuke_sim_exposure")
pexposure=st.session_state.get("nuke_path_exposure")
contest_results=st.session_state.get("nuke_contest_results")
contest_summary=st.session_state.get("nuke_contest_summary",{})
portfolio=st.session_state.get("nuke_portfolio")
portfolio_paths=st.session_state.get("nuke_portfolio_paths")
portfolio_stats=st.session_state.get("nuke_portfolio_stats",{})
candidate_diag=st.session_state.get("nuke_candidate_diagnostics",{})
stage_times=st.session_state.get("nuke_stage_times",{})

if stage_times:
    st.subheader("⏱️ Run Performance")
    total=float(st.session_state.get("nuke_sim_runtime",0.0))
    timing_cols=st.columns(len(stage_times))
    for col,(name,secs) in zip(timing_cols,stage_times.items()):
        col.metric(name,f"{float(secs):.1f}s")
    if total>0:
        slow_name,slow_secs=max(stage_times.items(),key=lambda kv:kv[1])
        st.caption(f"Total {total:.1f}s · Bottleneck: {slow_name} ({float(slow_secs):.1f}s, {100.0*float(slow_secs)/total:.0f}% of run).")

if candidate_diag:
    st.subheader("🩺 Candidate Pool Health")
    d1,d2,d3,d4,d5,d6=st.columns(6)
    d1.metric("Grade",str(candidate_diag.get("grade","?")))
    d2.metric("Candidates",f"{int(candidate_diag.get('generated',0)):,}")
    d3.metric("Unique QBs",f"{int(candidate_diag.get('unique_qbs',0)):,}")
    d4.metric("Avg Shared Players",f"{float(candidate_diag.get('avg_overlap',0)):.2f}",help="Average number of identical players shared by two candidate lineups. This is calculated across candidate-lineup pairs, not against one reference lineup.")
    d5.metric("Max Pair Repeat",f"{float(candidate_diag.get('max_pair_pct',0)):.1f}%")
    d6.metric("Max 3-Core Repeat",f"{float(candidate_diag.get('max_triple_pct',0)):.1f}%")
    st.caption(f"Generated {float(candidate_diag.get('fill_pct',0)):.1f}% of requested candidates · {int(candidate_diag.get('games',0))} games represented · Avg salary ${float(candidate_diag.get('avg_salary',0)):,.0f} · Shared-player overlap: median {float(candidate_diag.get('median_overlap',0)):.1f}, 95th percentile {float(candidate_diag.get('p95_overlap',0)):.1f}, max {int(candidate_diag.get('max_overlap_seen',0))}.")

if results is not None and not results.empty:
    tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8=st.tabs(["🏆 CONTEST SIM","🧬 PORTFOLIO","☢️ NUKEM LINEUPS","🧭 PATHS","👤 EXPOSURE","🔗 COMBOS",f"📤 {'FD' if site=='FD' else 'DK'} EXPORT","🧠 MODEL NOTES"])
    with tab1:
        if contest_results is not None and not contest_results.empty:
            m1,m2,m3,m4,m5,m6=st.columns(6)
            m1.metric("Field",f"{int(contest_summary.get('field_size',0)):,}")
            m2.metric("Entry",f"${float(contest_summary.get('entry_fee',0)):,.2f}")
            m3.metric("Paid Places",f"{int(contest_summary.get('paid_places',0)):,}")
            m4.metric("Contest Sims",f"{int(contest_summary.get('iterations',0)):,}")
            m5.metric("Lineups Simmed",f"{len(contest_results):,}")
            m6.metric("Field Model",str(contest_summary.get("field_model","")))
            contest_roster=add_dk_roster_columns(sim_players,contest_results)
            defense_col="D" if site=="FD" else "DST"
            left=["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX",defense_col,"FLEX Pos","Stack"]
            stats=["Contest Rank","Sim ROI %","1st %","Top 0.1%","Top 1%","Cash %","Avg Finish","Expected Duplicates","Avg Payout","Strongest Path","Path Score","Lineup Thesis","NUKE Score","Ceiling 95","Salary"]
            contest_show=contest_roster[[c for c in left+stats if c in contest_roster.columns]].copy()
            st.dataframe(contest_show,use_container_width=True,hide_index=True)

            contest_download=contest_show.copy()
            if site=="FD":
                fd_slots=pd.DataFrame(
                    [lineup_to_fd_slots(sim_players,lu,ids_only=True) for lu in contest_results["_indices"]],
                    columns=ANALYSIS_ROSTER_HEADERS,
                )
                for col in ANALYSIS_ROSTER_HEADERS:
                    if col in contest_download.columns and col in fd_slots.columns:
                        contest_download[col]=fd_slots[col].values
                contest_label="Download Contest SIM + FanDuel IDs CSV"
                contest_filename="nuke_contest_sim_fanduel_ids.csv"
            else:
                contest_label="Download Contest SIM + DraftKings Lineups CSV"
                contest_filename="nuke_contest_sim_draftkings_lineups.csv"
            st.download_button(contest_label,contest_download.to_csv(index=False).encode("utf-8-sig"),contest_filename,"text/csv")
    with tab2:
        if portfolio is not None and not portfolio.empty:
            st.subheader("Portfolio Manager")
            st.caption("Change these controls and rebuild instantly from the existing contest-simmed candidate pool — no football re-simulation required.")

            story=portfolio_story(sim_players,portfolio)
            sm=story.get("metrics",{})
            st.markdown("### 🧠 Portfolio Story")
            st.caption("What this portfolio is betting on, where it is different from the modeled field, and where concentration risk lives.")
            s1,s2,s3,s4,s5,s6=st.columns(6)
            s1.metric("Lineups",f"{int(sm.get('lineups',len(portfolio))):,}")
            s2.metric("Elite Ceiling",f"{int(sm.get('elite_lineups',0)):,}")
            s3.metric("Low-Dup Leverage",f"{int(sm.get('leverage_lineups',0)):,}")
            s4.metric("Top Scenario",str(sm.get('dominant_scenario','UNKNOWN')),delta=f"{float(sm.get('dominant_scenario_pct',0)):.1f}% of portfolio")
            s5.metric("Top QB",str(sm.get('dominant_qb','UNKNOWN')),delta=f"{float(sm.get('dominant_qb_pct',0)):.1f}% exposure")
            s6.metric("Top Game",str(sm.get('dominant_game','UNKNOWN')),delta=f"{float(sm.get('dominant_game_pct',0)):.1f}% exposure")

            story_left,story_right=st.columns(2)
            with story_left:
                st.markdown("#### Scenario Bets")
                scenario_df=story.get("scenario_df",pd.DataFrame())
                if scenario_df is not None and not scenario_df.empty:
                    st.dataframe(scenario_df.head(12),use_container_width=True,hide_index=True,height=330)
                else:
                    st.caption("No scenario labels are available for this portfolio yet.")
            with story_right:
                st.markdown("#### Why Lineups Made It")
                reason_df=story.get("reason_df",pd.DataFrame())
                if reason_df is not None and not reason_df.empty:
                    st.dataframe(reason_df,use_container_width=True,hide_index=True,height=330)
                else:
                    st.caption("No portfolio-reason labels are available yet.")

            leverage_df=story.get("leverage_df",pd.DataFrame())
            if leverage_df is not None and not leverage_df.empty:
                st.markdown("#### ⚡ Portfolio vs Modeled Field")
                st.caption("Positive leverage = NUKE is using the player more than the projection-free Field Engine ownership prior. Negative leverage = portfolio fade. This is a portfolio stance, not a live ownership projection.")
                lev1,lev2=st.columns(2)
                with lev1:
                    st.markdown("**Largest Overweights**")
                    st.dataframe(leverage_df.head(12),use_container_width=True,hide_index=True,height=390)
                with lev2:
                    st.markdown("**Largest Underweights / Fades**")
                    st.dataframe(leverage_df.sort_values("Leverage +/-",ascending=True).head(12),use_container_width=True,hide_index=True,height=390)

            story_flags=story.get("flags",[])
            st.markdown("#### 🚨 Portfolio Risk Check")
            if story_flags:
                for flag in story_flags:
                    st.warning(flag)
            else:
                st.success("No major player, team, game, or 3-player-core concentration flags detected.")
            st.divider()
            pc1,pc2,pc3,pc4,pc5,pc6,pc7=st.columns(7)
            manage_size=pc1.number_input("Portfolio lineups",1,min(150,len(contest_results)),min(int(portfolio_stats.get("requested_lineups",len(portfolio))),min(150,len(contest_results))),1,key="manage_portfolio_size")
            manage_overlap=pc2.slider("Max overlap",4,8,int(max_overlap),1,key="manage_overlap")
            manage_player=pc3.slider("Max player %",10,100,int(round(100*float(portfolio_stats.get("max_player_exposure",.45)))),5,key="manage_player_exp")
            manage_qb=pc4.slider("Max QB %",5,100,int(round(100*float(portfolio_stats.get("max_qb_exposure",.30)))),5,key="manage_qb_exp")
            manage_path=pc5.slider("Path diversity",0.0,3.0,float(path_balance),0.25,key="manage_path_balance")
            manage_team=pc6.slider("Max team %",10,100,int(round(100*float(portfolio_stats.get("max_team_exposure",.80)))),5,key="manage_team_exp")
            manage_game=pc7.slider("Max game %",10,100,int(round(100*float(portfolio_stats.get("max_game_exposure",.70)))),5,key="manage_game_exp")

            st.markdown("#### 🎚️ Player Takes")
            st.caption("Boost changes only portfolio selection — it does NOT change the player's simulated fantasy points. +1/+2/+3 = Like/Love/Flag Plant; negatives reduce exposure. Min/Max are hard portfolio targets when the candidate pool can support them.")
            saved_takes=st.session_state.get("nuke_player_takes",{})
            current_counts={}
            for lu in portfolio["_indices"]:
                for pid in lu:
                    current_counts[int(pid)]=current_counts.get(int(pid),0)+1
            candidate_ids=sorted({int(pid) for lu in contest_results["_indices"] for pid in lu})
            take_rows=[]
            for pid in candidate_ids:
                p=sim_players.iloc[pid]
                pref=saved_takes.get(pid,{})
                take_rows.append({"Player ID":pid,"Player":p.Name,"Pos":p.Position,"Team":p.Team,"Salary":int(p.Salary),"Current %":round(100*current_counts.get(pid,0)/max(1,len(portfolio)),1),"Boost":float(pref.get("boost",0.0)),"Min %":float(100*pref.get("min",0.0)),"Max %":float(100*pref.get("max",float(manage_player)/100.0))})
            take_df=pd.DataFrame(take_rows).set_index("Player ID")
            take_filter=st.multiselect("Positions",["QB","RB","WR","TE","DST"],default=["QB","RB","WR","TE","DST"],key="take_pos_filter")
            edit_base=take_df[take_df.Pos.isin(take_filter)].copy()
            take_edit=st.data_editor(edit_base,use_container_width=True,hide_index=True,height=430,disabled=["Player","Pos","Team","Salary","Current %"],column_config={"Boost":st.column_config.NumberColumn("Boost",min_value=-3.0,max_value=3.0,step=1.0,format="%.0f"),"Min %":st.column_config.NumberColumn("Min %",min_value=0.0,max_value=100.0,step=5.0,format="%.0f%%"),"Max %":st.column_config.NumberColumn("Max %",min_value=0.0,max_value=100.0,step=5.0,format="%.0f%%")},key="player_takes_editor")

            if st.button("🧬 REBUILD PORTFOLIO",type="primary",use_container_width=True,key="rebuild_portfolio"):
                preferences=dict(saved_takes)
                invalid=[]
                for pid,row in take_edit.iterrows():
                    mn=float(row["Min %"])/100.0
                    mx=float(row["Max %"])/100.0
                    boost=float(row["Boost"])
                    if mn>mx:
                        invalid.append(str(row["Player"]))
                        continue
                    if abs(boost)>1e-9 or mn>0 or abs(mx-float(manage_player)/100.0)>1e-9:
                        preferences[int(pid)]={"boost":boost,"min":mn,"max":mx}
                    else:
                        preferences.pop(int(pid),None)
                if invalid:
                    st.error("Min % cannot be greater than Max % for: "+", ".join(invalid))
                    st.stop()
                new_portfolio=build_portfolio(contest_results,size=int(manage_size),max_overlap=int(manage_overlap),path_balance=float(manage_path),max_player_exposure=float(manage_player)/100.0,max_qb_exposure=float(manage_qb)/100.0,player_preferences=preferences,players=sim_players,max_team_exposure=float(manage_team)/100.0,max_game_exposure=float(manage_game)/100.0)
                new_paths,new_stats=portfolio_summary(new_portfolio)
                st.session_state["nuke_player_takes"]=preferences
                st.session_state["nuke_portfolio"]=new_portfolio
                st.session_state["nuke_portfolio_paths"]=new_paths
                st.session_state["nuke_portfolio_stats"]=new_stats
                st.session_state["nuke_shared_portfolio_rows"]=portfolio_to_hub_rows(sim_players,new_portfolio)
                st.session_state["nuke_shared_portfolio_version"]=int(st.session_state.get("nuke_shared_portfolio_version",0))+1
                st.session_state["nuke_path_exposure"]=path_exposure(new_portfolio,len(new_portfolio))
                st.rerun()

            requested=int(portfolio_stats.get("requested_lineups",len(portfolio)))
            if len(portfolio)<requested:
                st.warning(f"Exposure/overlap constraints allowed only {len(portfolio)} of {requested} requested lineups. Raise a cap or overlap limit to fill the portfolio.")
            unmet=portfolio_stats.get("unmet_minimums",{})
            if unmet:
                names=[]
                for pid,v in unmet.items():
                    name=sim_players.iloc[int(pid)].Name if int(pid)<len(sim_players) else str(pid)
                    names.append(f"{name}: {v['actual']}/{v['requested']}")
                st.warning("Candidate pool could not satisfy these minimum exposures: "+" · ".join(names))
            p1,p2,p3,p4=st.columns(4)
            p1.metric("Lineups",int(portfolio_stats.get("lineups",0)))
            p2.metric("Paths Covered",int(portfolio_stats.get("paths",0)))
            p3.metric("QBs Used",int(portfolio_stats.get("qbs",0)))
            p4.metric("Avg Sim ROI",f"{float(portfolio_stats.get('avg_roi',0)):.1f}%")
            st.caption(str(portfolio_stats.get("engine",PORTFOLIO_ENGINE_VERSION)))
            st.markdown("#### Portfolio Exposure")
            pe=portfolio_player_exposure(sim_players,portfolio)
            qe=portfolio_qb_exposure(portfolio)
            ec1,ec2=st.columns([2,1])
            ec1.dataframe(pe,use_container_width=True,hide_index=True,height=420)
            ec2.dataframe(qe,use_container_width=True,hide_index=True,height=420)
            st.markdown("#### Team / Game Exposure")
            team_e,game_e=portfolio_team_game_exposure(sim_players,portfolio)
            tg1,tg2=st.columns(2)
            tg1.dataframe(team_e,use_container_width=True,hide_index=True,height=360)
            tg2.dataframe(game_e,use_container_width=True,hide_index=True,height=360)
            st.markdown("#### QB Stack Exposure")
            st.dataframe(portfolio_stack_exposure(portfolio),use_container_width=True,hide_index=True,height=320)
            st.markdown("#### Portfolio Health")
            health=portfolio_health(sim_players,portfolio)
            if health.get("flags"):
                for flag in health["flags"]:
                    st.warning(flag)
            else:
                st.success("No major concentration flags detected under the current portfolio-health thresholds.")
            st.caption(f"Tracked {int(health.get('core_count',0)):,} distinct 3-player cores across the portfolio.")
            core_df=health.get("top_core")
            if core_df is not None and not core_df.empty:
                st.dataframe(core_df.head(20),use_container_width=True,hide_index=True,height=340)
            st.markdown("#### Path Mix")
            dominant_path=str(portfolio_stats.get("dominant_path","UNKNOWN"))
            dominant_pct=float(portfolio_stats.get("dominant_path_pct",0.0))
            soft_cap_pct=100.0*float(portfolio_stats.get("path_soft_cap",0.45))
            hhi=float(portfolio_stats.get("path_hhi",0.0))
            pm1,pm2,pm3=st.columns(3)
            pm1.metric("Dominant Path",dominant_path)
            pm2.metric("Dominant Path Exposure",f"{dominant_pct:.1f}%")
            pm3.metric("Path Concentration",f"{hhi:.3f}")
            if dominant_pct>soft_cap_pct:
                st.info(f"{dominant_path} is above the {soft_cap_pct:.0f}% soft concentration line. V5.1 does not hard-cap it; additional lineups must earn their slots by overcoming a rising marginal path penalty.")
            st.dataframe(portfolio_paths,use_container_width=True,hide_index=True)
            st.markdown("#### Selected Lineups")
            portfolio_export=add_dk_roster_columns(sim_players,portfolio).drop(columns=["_indices"],errors="ignore")
            preferred=["Portfolio Slot","QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DST","FLEX Pos","Stack","Contest Rank","Sim ROI %","1st %","Top 0.1%","Top 1%","Cash %","Avg Finish","Avg Payout","Strongest Path","Secondary Path","Path Score","Lineup Thesis","NUKE Score","Median","Ceiling 95","Salary","Portfolio Reason"]
            portfolio_export=portfolio_export[[c for c in preferred if c in portfolio_export.columns]+[c for c in portfolio_export.columns if c not in preferred]]
            st.dataframe(portfolio_export,use_container_width=True,hide_index=True)
            st.download_button("⬇️ Download Portfolio + Stats CSV",portfolio_export.to_csv(index=False).encode("utf-8-sig"),"nuke_portfolio_with_stats.csv","text/csv",type="primary",use_container_width=True,key="download_portfolio_stats")
    with tab3:
        show=results.drop(columns=["_indices"],errors="ignore")
        st.dataframe(show.head(150),use_container_width=True,hide_index=True)
        st.download_button("Download NUKEM lineup results CSV",show.to_csv(index=False).encode("utf-8-sig"),"nuke_sim_results.csv","text/csv")
    with tab4:
        st.subheader("Path Coverage")
        path_scope=portfolio if portfolio is not None and not portfolio.empty else results.head(min(150,len(results)))
        current_paths=path_exposure(path_scope,len(path_scope))
        st.caption(f"Showing path stats for the full selected portfolio: {len(path_scope):,} lineups.")
        st.dataframe(current_paths,use_container_width=True,hide_index=True)
        cols=[c for c in ["Portfolio Slot","Contest Rank","Rank","Strongest Path","Secondary Path","Path Score","Lineup Thesis","Stack","Salary","QB"] if c in path_scope.columns]
        st.dataframe(path_scope[cols],use_container_width=True,hide_index=True)
    with tab5:
        st.subheader("Exposure Insights")
        scope=st.radio("Exposure scope",["Portfolio", "All contest-simmed lineups",f"Top {int(exposure_n)} NUKEM lineups"],horizontal=True)
        er=portfolio if scope=="Portfolio" and portfolio is not None and not portfolio.empty else contest_results if scope.startswith("All") and contest_results is not None else results.head(int(exposure_n))
        flex_table=flex_exposure_table(sim_players,er)
        pos_table=position_exposure_table(sim_players,er)
        fcols=st.columns(3)
        fmap={str(r["FLEX Position"]):r for _,r in flex_table.iterrows()}
        for col,p in zip(fcols,["RB","WR","TE"]):
            flex_lineups=int(fmap.get(p,{}).get("Lineups",0))
            flex_pct=float(fmap.get(p,{}).get("Exposure %",0))
            col.metric(f"{p} in FLEX",f"{flex_lineups:,}")
            col.caption(f"{flex_pct:.1f}% exposure")
        st.dataframe(flex_table,use_container_width=True,hide_index=True)
        pos_filter=st.selectbox("Position exposure",["ALL","QB","RB","WR","TE","DST"])
        pshow=pos_table if pos_filter=="ALL" else pos_table[pos_table.Position.eq(pos_filter)]
        st.dataframe(pshow,use_container_width=True,hide_index=True)
        st.markdown("**Top-player exposure detail**")
        st.dataframe(exposure,use_container_width=True,hide_index=True)
    with tab6:
        st.subheader("Player Combo Exposure")
        combo_scope=portfolio if portfolio is not None and not portfolio.empty else contest_results
        if combo_scope is not None and not combo_scope.empty:
            pairs,qb_pairs=combo_exposure_table(sim_players,combo_scope)
            st.caption(f"Calculated across {len(combo_scope):,} portfolio lineups." if portfolio is not None and not portfolio.empty else f"Calculated across {len(combo_scope):,} contest-simmed lineups.")
            if not pairs.empty:
                c1,c2,c3=st.columns(3)
                top=pairs.iloc[0]
                c1.metric("Highest Combo",f"{top['Player 1']} + {top['Player 2']}")
                c2.metric("Highest Combo %",f"{float(top['Portfolio Combo %']):.1f}%")
                c3.metric("Combo Lineups",int(top['Combo Lineups']))
                st.markdown("#### Highest Overall Player Pairs")
                relation=st.multiselect("Show relationships",["Same Team","Same Game","Non-Stacked"],default=["Same Team","Same Game","Non-Stacked"],key="combo_relation")
                pair_show=pairs[pairs["Relationship"].isin(relation)].head(75)
                st.dataframe(pair_show,use_container_width=True,hide_index=True)
            if not qb_pairs.empty:
                st.markdown("#### QB-Anchored Combos")
                st.caption("% of QB Lineups answers: when this QB is used, how often is the other player paired with him?")
                qb_filter=st.selectbox("QB anchor",["All QBs"]+sorted(qb_pairs.QB.unique().tolist()),key="combo_qb")
                qshow=qb_pairs if qb_filter=="All QBs" else qb_pairs[qb_pairs.QB.eq(qb_filter)]
                st.dataframe(qshow.head(100),use_container_width=True,hide_index=True)
    with tab7:
        export_platform_name="FanDuel" if site=="FD" else "DraftKings"
        st.subheader(f"📤 {export_platform_name} Lineup Export")
        source_options=["Portfolio","Contest-ranked","NUKEM-ranked"]
        export_source=st.selectbox("Lineup source",source_options,index=0,key=f"export_source_{site}")
        export_results=portfolio if export_source=="Portfolio" and portfolio is not None and not portfolio.empty else contest_results if export_source=="Contest-ranked" and contest_results is not None and not contest_results.empty else results
        max_export=min(150,len(export_results))
        export_count=st.number_input("Lineups to export",1,max_export,min(150,max_export),1,key=f"export_count_{site}")
        lineup_only=build_lineup_only_csv(sim_players,export_results,int(export_count),site=site)
        short_site="fd" if site=="FD" else "dk"
        st.download_button(f"Download {export_platform_name} lineup-only CSV",lineup_only,f"nuke_{short_site}_lineups.csv","text/csv")
        entries_upload=st.file_uploader(f"Upload your {export_platform_name} Entries CSV",type=["csv"],key=f"entries_upload_{site}")
        if entries_upload is not None:
            try:
                filled,info=fill_entries_csv(entries_upload.getvalue(),sim_players,export_results,int(export_count),site=site)
                st.success(f"Filled {info['entries_filled']} {export_platform_name} entries.")
                st.download_button(f"⬇️ Download {export_platform_name} Upload CSV",filled,f"nuke_{short_site}_upload.csv","text/csv",type="primary")
            except Exception as e:
                st.error(f"Could not build {export_platform_name} upload file: {e}")
    with tab8:
        st.markdown(f"""**Football engine:** {engine_version(site)}.\n\n**Pre-sim player takes:** Game-by-game Include/Boost controls shape candidate generation before the sim. Boost does not alter simulated fantasy points; Usage x does.\n\n**Portfolio engine:** {PORTFOLIO_ENGINE_VERSION}. Player Takes remain portfolio-only after the run. V5.1 adds marginal path-value concentration control on top of player/team/game caps, QB-stack exposure reporting, and Portfolio Health diagnostics. Path control is soft rather than a forced quota. Duplication is not part of portfolio selection.\n\n**Correlation:** NUKE generates a tournament mixture of QB+1, QB+1/1, QB+2, QB+2/1 and QB+2/2 structures.\n\n**Field:** opponent ownership remains modeled until real regular-season contest data is available for calibration.""")

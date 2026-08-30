import streamlit as st
import pandas as pd
import time
from nuke_sim import prepare_slate, simulate_player_matrix, generate_lineups, evaluate_lineups, exposure_table, position_exposure_table, flex_exposure_table
from nuke_contest import simulate_contest
from nuke_paths import attach_path_labels, path_exposure
from nuke_portfolio import build_portfolio, portfolio_summary, portfolio_player_exposure, portfolio_qb_exposure, PORTFOLIO_ENGINE_VERSION
from dk_contest_import import parse_payout_upload
from dk_export import build_lineup_only_csv, fill_entries_csv, add_dk_roster_columns
from default_slate import load_default_slate, SLATE_LABEL
from nuke_football_v21 import simulate_player_matrix_v21, ENGINE_VERSION
from nuke_combos import combo_exposure_table

st.set_page_config(page_title="NUKE SIM",page_icon="☢️",layout="wide"); st.title("☢️ NUKE SIM"); st.caption(f"Projection-free NFL DFS outcome + contest simulation inside the NUKE DFS Hub · {ENGINE_VERSION}.")
with st.sidebar:
    st.header("SIM CONTROL ROOM"); preset=st.selectbox("Preset",["QUICK","STANDARD","DEEP"],index=0); presets={"QUICK":(250,350,50,200),"STANDARD":(400,750,75,350),"DEEP":(700,1200,100,500)}; candidates,sims,exposure_n,contest_iters=presets[preset]
    min_salary=st.number_input("Minimum salary",45000,50000,49400,100); candidates=st.number_input("Candidate lineups",100,5000,candidates,100); sims=st.number_input("Football universes",250,10000,sims,250); exposure_n=st.number_input("Exposure sample",10,150,exposure_n,10)
    with st.expander("Advanced settings"):
        fixed_seed=st.checkbox("Use reproducible seed",value=False,help="Off by default: every RUN NUKE SIM click gets a fresh random simulation. Turn this on only when you want to reproduce a specific run.")
        manual_seed=st.number_input("Random seed",1,2147483646,26,1,disabled=not fixed_seed)
    st.divider(); st.subheader("Contest"); field_size=st.number_input("Field size",2,100000,2222,1); entry_fee=st.number_input("Entry fee ($)",.25,10000.,100.,1.); first_prize=st.number_input("1st prize ($)",1.,10000000.,50000.,100.); st.caption("Every generated candidate lineup is contest-simmed automatically."); contest_iters=st.number_input("Contest iterations",50,5000,contest_iters,50)
    st.divider(); st.subheader("Portfolio"); portfolio_size=st.number_input("Portfolio size",1,150,150,1); max_overlap=st.slider("Max player overlap",4,8,7,1); path_balance=st.slider("Path diversification",0.,3.,1.25,.25); max_player_exp=st.slider("Max player exposure %",10,100,45,5); max_qb_exp=st.slider("Max QB exposure %",5,100,30,5); st.caption(f"{PORTFOLIO_ENGINE_VERSION}: tournament upside + controlled concentration. Duplication is not used to select your portfolio.")

st.subheader("🏈 Current Slate")
salary_upload=st.file_uploader("Optional: upload a different DraftKings NFL salary CSV",type=["csv"],help="Leave this empty to use the built-in current weekly slate.")
try:
    if salary_upload is not None:
        raw_slate=pd.read_csv(salary_upload); slate_source=f"Uploaded override: {salary_upload.name}"; st.info(f"Using uploaded slate: **{salary_upload.name}**")
    else:
        raw_slate=load_default_slate(); slate_source=SLATE_LABEL; st.success(f"Loaded automatically: **{SLATE_LABEL}** · {len(raw_slate):,} players")
except Exception as e: st.error(f"Could not load slate: {e}"); st.stop()

st.subheader("🏆 Contest Payouts"); payout_upload=st.file_uploader("Optional: upload DraftKings payout CSV / Excel",type=["csv","xlsx","xls"],key="dk_payout_upload"); payouts_override=None
if payout_upload is not None:
    try:
        payouts_override,payout_info=parse_payout_upload(payout_upload); a,b,c=st.columns(3); a.metric("Imported Paid Places",f"{int(payout_info['paid_places']):,}"); b.metric("Imported 1st",f"${float(payout_info['first_prize']):,.0f}"); c.metric("Imported Prize Pool",f"${float(payout_info['listed_prize_pool']):,.0f}"); st.success("Real payout ladder loaded.")
    except Exception as e: st.error(f"Could not parse payout file: {e}"); st.stop()
else: st.caption("No payout file uploaded — NUKE will use the modeled GPP payout curve.")
try: players=prepare_slate(raw_slate)
except Exception as e: st.error(f"Could not read this slate: {e}"); st.stop()
c1,c2,c3,c4,c5=st.columns(5); c1.metric("Players",len(players)); c2.metric("Teams",players.Team.nunique()); c3.metric("Games",players.Game.nunique()); c4.metric("Salary Floor",f"${int(min_salary):,}"); c5.metric("Slate",slate_source)
st.subheader("Player / Injury / Role Overrides"); st.caption("NUKE automatically infers depth roles. Manual controls are optional emergency overrides.")
editor=players[["Name","Position","Team","Salary","Game"]].copy(); editor.insert(0,"Active",True); editor["Role"]="AUTO"; editor["Usage x"]=1.0
edited=st.data_editor(editor,use_container_width=True,hide_index=True,disabled=["Name","Position","Team","Salary","Game"],column_config={"Role":st.column_config.SelectboxColumn("Role",options=["AUTO","QB1","RB1","RB2","RB3","WR1","WR2","WR3","TE1","BACKUP"]),"Usage x":st.column_config.NumberColumn("Usage x",min_value=.25,max_value=2.25,step=.05,format="%.2f")})
mask=edited.Active.fillna(False).astype(bool).to_numpy(); players=players.loc[mask].copy().reset_index(drop=True); ae=edited.loc[mask].reset_index(drop=True); players["role_override"]=ae.Role.fillna("AUTO").astype(str).str.upper().values; players["usage_multiplier"]=pd.to_numeric(ae["Usage x"],errors="coerce").fillna(1).clip(.25,2.25).values
if st.button("☢️ RUN NUKE SIM",type="primary",use_container_width=True):
    run_started=time.perf_counter(); seed=int(manual_seed) if fixed_seed else int.from_bytes(__import__("secrets").token_bytes(4), "big") % 2147483646 + 1
    if len(players)<9: st.error("Not enough active players."); st.stop()
    with st.status("NUKE SIM is running...",expanded=True) as status:
        stage=time.perf_counter(); st.write("1/5 · Generating correlated DraftKings candidates..."); lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed)); st.write(f"Candidate generation: {time.perf_counter()-stage:.1f}s")
        if not lineups: status.update(label="No legal lineups found",state="error"); st.stop()
        st.write(f"Generated {len(lineups):,} unique candidates."); stage=time.perf_counter(); st.write(f"2/5 · Simulating {int(sims):,} correlated football universes with {ENGINE_VERSION}..."); matrix=simulate_player_matrix_v21(players,int(sims),int(seed)); st.write(f"Football simulation: {time.perf_counter()-stage:.1f}s")
        stage=time.perf_counter(); st.write("3/5 · Ranking outcomes and assigning paths..."); results=attach_path_labels(players,evaluate_lineups(players,lineups,matrix)); exposure=exposure_table(players,results,int(exposure_n)); st.write(f"Ranking + paths: {time.perf_counter()-stage:.1f}s")
        stage=time.perf_counter(); st.write(f"4/5 · Contest-simming all {len(results):,} candidates..."); contest_results,contest_summary=simulate_contest(results=results,player_matrix=matrix,field_size=int(field_size),entry_fee=float(entry_fee),first_prize=float(first_prize),iterations=int(contest_iters),seed=int(seed)+97,payouts_override=payouts_override,players=players); st.write(f"Contest simulation: {time.perf_counter()-stage:.1f}s")
        stage=time.perf_counter(); st.write(f"5/5 · Building {PORTFOLIO_ENGINE_VERSION} portfolio..."); portfolio=build_portfolio(contest_results,size=int(portfolio_size),max_overlap=int(max_overlap),path_balance=float(path_balance),max_player_exposure=float(max_player_exp)/100.0,max_qb_exposure=float(max_qb_exp)/100.0); portfolio_paths,portfolio_stats=portfolio_summary(portfolio); pexposure=path_exposure(portfolio,len(portfolio)); st.write(f"Portfolio build: {time.perf_counter()-stage:.1f}s")
        run_seconds=time.perf_counter()-run_started
        for k,v in {"nuke_sim_results":results,"nuke_sim_players":players.copy(),"nuke_sim_exposure":exposure,"nuke_path_exposure":pexposure,"nuke_contest_results":contest_results,"nuke_contest_summary":contest_summary,"nuke_portfolio":portfolio,"nuke_portfolio_paths":portfolio_paths,"nuke_portfolio_stats":portfolio_stats,"nuke_sim_runtime":run_seconds}.items(): st.session_state[k]=v
        status.update(label=f"NUKE SIM complete · {run_seconds:.1f}s",state="complete")
    st.success(f"Total run time: {run_seconds:.1f} seconds")
results=st.session_state.get("nuke_sim_results"); sim_players=st.session_state.get("nuke_sim_players"); exposure=st.session_state.get("nuke_sim_exposure"); pexposure=st.session_state.get("nuke_path_exposure"); contest_results=st.session_state.get("nuke_contest_results"); contest_summary=st.session_state.get("nuke_contest_summary",{}); portfolio=st.session_state.get("nuke_portfolio"); portfolio_paths=st.session_state.get("nuke_portfolio_paths"); portfolio_stats=st.session_state.get("nuke_portfolio_stats",{})
if results is not None and not results.empty:
    tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8=st.tabs(["🏆 CONTEST SIM","🧬 PORTFOLIO","☢️ NUKEM LINEUPS","🧭 PATHS","👤 EXPOSURE","🔗 COMBOS","📤 DK EXPORT","🧠 MODEL NOTES"])
    with tab1:
        if contest_results is not None and not contest_results.empty:
            m1,m2,m3,m4,m5,m6=st.columns(6); m1.metric("Field",f"{int(contest_summary.get('field_size',0)):,}"); m2.metric("Entry",f"${float(contest_summary.get('entry_fee',0)):,.2f}"); m3.metric("Paid Places",f"{int(contest_summary.get('paid_places',0)):,}"); m4.metric("Contest Sims",f"{int(contest_summary.get('iterations',0)):,}"); m5.metric("Lineups Simmed",f"{len(contest_results):,}"); m6.metric("Field Model",str(contest_summary.get("field_model","")))
            contest_dk=add_dk_roster_columns(sim_players,contest_results); left=["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DST","FLEX Pos","Stack"]; stats=["Contest Rank","Sim ROI %","1st %","Top 0.1%","Top 1%","Cash %","Avg Finish","Expected Duplicates","Avg Payout","Strongest Path","Path Score","Lineup Thesis","NUKE Score","Ceiling 95","Salary"]
            contest_show=contest_dk[[c for c in left+stats if c in contest_dk.columns]].copy(); st.dataframe(contest_show,use_container_width=True,hide_index=True); st.download_button("Download Contest SIM + DK Lineups CSV",contest_show.to_csv(index=False).encode("utf-8-sig"),"nuke_contest_sim_dk_lineups.csv","text/csv")
    with tab2:
        if portfolio is not None and not portfolio.empty:
            st.subheader("Portfolio Manager")
            st.caption("Change these controls and rebuild the portfolio instantly from the existing contest-simmed candidate pool — no football re-simulation required.")
            pc1,pc2,pc3,pc4,pc5=st.columns(5)
            manage_size=pc1.number_input("Portfolio lineups",1,min(150,len(contest_results)),min(int(portfolio_stats.get("requested_lineups",len(portfolio))),min(150,len(contest_results))),1,key="manage_portfolio_size")
            manage_overlap=pc2.slider("Max overlap",4,8,int(max_overlap),1,key="manage_overlap")
            manage_player=pc3.slider("Max player %",10,100,int(round(100*float(portfolio_stats.get("max_player_exposure",.45)))),5,key="manage_player_exp")
            manage_qb=pc4.slider("Max QB %",5,100,int(round(100*float(portfolio_stats.get("max_qb_exposure",.30)))),5,key="manage_qb_exp")
            manage_path=pc5.slider("Path diversity",0.0,3.0,float(path_balance),0.25,key="manage_path_balance")
            if st.button("🧬 REBUILD PORTFOLIO",type="primary",use_container_width=True,key="rebuild_portfolio"):
                new_portfolio=build_portfolio(contest_results,size=int(manage_size),max_overlap=int(manage_overlap),path_balance=float(manage_path),max_player_exposure=float(manage_player)/100.0,max_qb_exposure=float(manage_qb)/100.0)
                new_paths,new_stats=portfolio_summary(new_portfolio)
                st.session_state["nuke_portfolio"]=new_portfolio; st.session_state["nuke_portfolio_paths"]=new_paths; st.session_state["nuke_portfolio_stats"]=new_stats; st.session_state["nuke_path_exposure"]=path_exposure(new_portfolio,len(new_portfolio)); st.rerun()

            requested=int(portfolio_stats.get("requested_lineups",len(portfolio)))
            if len(portfolio)<requested: st.warning(f"Exposure/overlap constraints allowed only {len(portfolio)} of {requested} requested lineups. Raise a cap or overlap limit to fill the portfolio.")
            p1,p2,p3,p4=st.columns(4); p1.metric("Lineups",int(portfolio_stats.get("lineups",0))); p2.metric("Paths Covered",int(portfolio_stats.get("paths",0))); p3.metric("QBs Used",int(portfolio_stats.get("qbs",0))); p4.metric("Avg Sim ROI",f"{float(portfolio_stats.get('avg_roi',0)):.1f}%"); st.caption(str(portfolio_stats.get("engine",PORTFOLIO_ENGINE_VERSION)))
            st.markdown("#### Portfolio Exposure")
            pe=portfolio_player_exposure(sim_players,portfolio); qe=portfolio_qb_exposure(portfolio); ec1,ec2=st.columns([2,1]); ec1.dataframe(pe,use_container_width=True,hide_index=True,height=420); ec2.dataframe(qe,use_container_width=True,hide_index=True,height=420)
            st.markdown("#### Path Mix"); st.dataframe(portfolio_paths,use_container_width=True,hide_index=True)
            st.markdown("#### Selected Lineups"); st.dataframe(portfolio.drop(columns=["_indices"],errors="ignore"),use_container_width=True,hide_index=True)
    with tab3:
        show=results.drop(columns=["_indices"],errors="ignore"); st.dataframe(show.head(150),use_container_width=True,hide_index=True); st.download_button("Download NUKEM lineup results CSV",show.to_csv(index=False).encode("utf-8-sig"),"nuke_sim_results.csv","text/csv")
    with tab4:
        st.subheader("Path Coverage"); path_scope=portfolio if portfolio is not None and not portfolio.empty else results.head(min(150,len(results))); current_paths=path_exposure(path_scope,len(path_scope)); st.caption(f"Showing path stats for the full selected portfolio: {len(path_scope):,} lineups."); st.dataframe(current_paths,use_container_width=True,hide_index=True); cols=[c for c in ["Portfolio Slot","Contest Rank","Rank","Strongest Path","Secondary Path","Path Score","Lineup Thesis","Stack","Salary","QB"] if c in path_scope.columns]; st.dataframe(path_scope[cols],use_container_width=True,hide_index=True)
    with tab5:
        st.subheader("Exposure Insights"); scope=st.radio("Exposure scope",["Portfolio", "All contest-simmed lineups",f"Top {int(exposure_n)} NUKEM lineups"],horizontal=True); er=portfolio if scope=="Portfolio" and portfolio is not None and not portfolio.empty else contest_results if scope.startswith("All") and contest_results is not None else results.head(int(exposure_n)); flex_table=flex_exposure_table(sim_players,er); pos_table=position_exposure_table(sim_players,er)
        fcols=st.columns(3); fmap={str(r["FLEX Position"]):r for _,r in flex_table.iterrows()}
        for col,p in zip(fcols,["RB","WR","TE"]): col.metric(f"{p} in FLEX",f"{int(fmap.get(p,{}).get('Lineups',0)):,}",f"{float(fmap.get(p,{}).get('Exposure %',0)):.1f}%")
        st.dataframe(flex_table,use_container_width=True,hide_index=True); pos_filter=st.selectbox("Position exposure",["ALL","QB","RB","WR","TE","DST"]); pshow=pos_table if pos_filter=="ALL" else pos_table[pos_table.Position.eq(pos_filter)]; st.dataframe(pshow,use_container_width=True,hide_index=True); st.markdown("**Top-player exposure detail**"); st.dataframe(exposure,use_container_width=True,hide_index=True)
    with tab6:
        st.subheader("Player Combo Exposure"); combo_scope=portfolio if portfolio is not None and not portfolio.empty else contest_results
        if combo_scope is not None and not combo_scope.empty:
            pairs,qb_pairs=combo_exposure_table(sim_players,combo_scope); st.caption(f"Calculated across {len(combo_scope):,} portfolio lineups." if portfolio is not None and not portfolio.empty else f"Calculated across {len(combo_scope):,} contest-simmed lineups.")
            if not pairs.empty:
                c1,c2,c3=st.columns(3); top=pairs.iloc[0]; c1.metric("Highest Combo",f"{top['Player 1']} + {top['Player 2']}"); c2.metric("Highest Combo %",f"{float(top['Portfolio Combo %']):.1f}%"); c3.metric("Combo Lineups",int(top['Combo Lineups'])); st.markdown("#### Highest Overall Player Pairs"); relation=st.multiselect("Show relationships",["Same Team","Same Game","Non-Stacked"],default=["Same Team","Same Game","Non-Stacked"],key="combo_relation"); pair_show=pairs[pairs["Relationship"].isin(relation)].head(75); st.dataframe(pair_show,use_container_width=True,hide_index=True)
            if not qb_pairs.empty:
                st.markdown("#### QB-Anchored Combos"); st.caption("% of QB Lineups answers: when this QB is used, how often is the other player paired with him?"); qb_filter=st.selectbox("QB anchor",["All QBs"]+sorted(qb_pairs.QB.unique().tolist()),key="combo_qb"); qshow=qb_pairs if qb_filter=="All QBs" else qb_pairs[qb_pairs.QB.eq(qb_filter)]; st.dataframe(qshow.head(100),use_container_width=True,hide_index=True)
    with tab7:
        st.subheader("📤 DraftKings Lineup Export"); source_options=["Portfolio","Contest-ranked","NUKEM-ranked"]; export_source=st.selectbox("Lineup source",source_options,index=0,key="dk_export_source"); export_results=portfolio if export_source=="Portfolio" and portfolio is not None and not portfolio.empty else contest_results if export_source=="Contest-ranked" and contest_results is not None and not contest_results.empty else results; max_export=min(150,len(export_results)); export_count=st.number_input("Lineups to export",1,max_export,min(150,max_export),1,key="dk_export_count"); lineup_only=build_lineup_only_csv(sim_players,export_results,int(export_count)); st.download_button("Download DK lineup-only CSV",lineup_only,"nuke_dk_lineups.csv","text/csv")
        entries_upload=st.file_uploader("Upload your DraftKings Entries CSV",type=["csv"],key="dk_entries_upload")
        if entries_upload is not None:
            try:
                filled,info=fill_entries_csv(entries_upload.getvalue(),sim_players,export_results,int(export_count)); st.success(f"Filled {info['entries_filled']} DraftKings entries."); st.download_button("⬇️ Download DraftKings Upload CSV",filled,"nuke_draftkings_upload.csv","text/csv",type="primary")
            except Exception as e: st.error(f"Could not build DraftKings upload file: {e}")
    with tab8:
        st.markdown(f"""**Football engine:** {ENGINE_VERSION}.\n\n**Portfolio engine:** {PORTFOLIO_ENGINE_VERSION}. Portfolio selection emphasizes tournament upside, ceiling, correlation, path diversity and controlled concentration. Predicted duplication is not part of portfolio selection. Player/QB exposure caps can be adjusted after a SIM without rerunning the football engine.\n\n**Correlation:** NUKE generates a tournament mixture of QB+1, QB+1/1, QB+2, QB+2/1 and QB+2/2 structures.\n\n**Field:** opponent ownership remains modeled until real regular-season contest data is available for calibration.""")

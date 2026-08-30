import streamlit as st
import pandas as pd
from nuke_sim import prepare_slate, simulate_player_matrix, generate_lineups, evaluate_lineups, exposure_table, position_exposure_table, flex_exposure_table
from nuke_contest import simulate_contest
from nuke_paths import attach_path_labels, path_exposure
from nuke_portfolio import build_portfolio, portfolio_summary
from dk_contest_import import parse_payout_upload
from dk_export import build_lineup_only_csv, fill_entries_csv, add_dk_roster_columns
from default_slate import load_default_slate, SLATE_LABEL
from nuke_football_v2 import simulate_player_matrix_v2

st.set_page_config(page_title="NUKE SIM",page_icon="☢️",layout="wide"); st.title("☢️ NUKE SIM"); st.caption("Projection-free NFL DFS outcome + contest simulation inside the NUKE DFS Hub.")
with st.sidebar:
    st.header("SIM CONTROL ROOM"); preset=st.selectbox("Preset",["QUICK","STANDARD","DEEP"],index=1); presets={"QUICK":(300,500,50,300),"STANDARD":(700,1500,75,750),"DEEP":(1400,3000,100,1500)}; candidates,sims,exposure_n,contest_iters=presets[preset]
    min_salary=st.number_input("Minimum salary",45000,50000,49400,100); candidates=st.number_input("Candidate lineups",100,5000,candidates,100); sims=st.number_input("Football universes",250,10000,sims,250); exposure_n=st.number_input("Exposure sample",10,150,exposure_n,10)
    with st.expander("Advanced settings"):
        fixed_seed=st.checkbox("Use reproducible seed",value=False,help="Off by default: every RUN NUKE SIM click gets a fresh random simulation. Turn this on only when you want to reproduce a specific run.")
        manual_seed=st.number_input("Random seed",1,2147483646,26,1,disabled=not fixed_seed)
    st.divider(); st.subheader("Contest"); field_size=st.number_input("Field size",2,100000,2222,1); entry_fee=st.number_input("Entry fee ($)",.25,10000.,100.,1.); first_prize=st.number_input("1st prize ($)",1.,10000000.,50000.,100.); st.caption("Every generated candidate lineup is contest-simmed automatically."); contest_iters=st.number_input("Contest iterations",50,5000,contest_iters,50)
    st.divider(); st.subheader("Portfolio"); portfolio_size=st.number_input("Portfolio size",1,150,150,1); max_overlap=st.slider("Max player overlap",4,8,7,1); path_balance=st.slider("Path diversification",0.,3.,1.25,.25)

st.subheader("🏈 Current Slate")
salary_upload=st.file_uploader("Optional: upload a different DraftKings NFL salary CSV",type=["csv"],help="Leave this empty to use the built-in current weekly slate.")
try:
    if salary_upload is not None:
        raw_slate=pd.read_csv(salary_upload); slate_source=f"Uploaded override: {salary_upload.name}"
        st.info(f"Using uploaded slate: **{salary_upload.name}**")
    else:
        raw_slate=load_default_slate(); slate_source=SLATE_LABEL
        st.success(f"Loaded automatically: **{SLATE_LABEL}** · {len(raw_slate):,} players")
except Exception as e:
    st.error(f"Could not load slate: {e}"); st.stop()

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
    # Public-safe default: each click gets a fresh seed, so identical users do not all receive the same portfolio.
    seed=int(manual_seed) if fixed_seed else int.from_bytes(__import__("secrets").token_bytes(4), "big") % 2147483646 + 1
    if len(players)<9: st.error("Not enough active players."); st.stop()
    with st.status("NUKE SIM is running...",expanded=True) as status:
        st.write("1/5 · Generating correlated DraftKings candidates..."); lineups=generate_lineups(players,int(candidates),int(min_salary),int(seed))
        if not lineups: status.update(label="No legal lineups found",state="error"); st.stop()
        st.write(f"Generated {len(lineups):,} unique candidates."); st.write(f"2/5 · Simulating {int(sims):,} correlated football universes..."); matrix=simulate_player_matrix_v2(players,int(sims),int(seed))
        st.write("3/5 · Ranking outcomes and assigning paths..."); results=attach_path_labels(players,evaluate_lineups(players,lineups,matrix)); exposure=exposure_table(players,results,int(exposure_n)); pexposure=path_exposure(results,int(exposure_n))
        st.write(f"4/5 · Contest-simming all {len(results):,} candidates..."); contest_results,contest_summary=simulate_contest(results=results,player_matrix=matrix,field_size=int(field_size),entry_fee=float(entry_fee),first_prize=float(first_prize),iterations=int(contest_iters),seed=int(seed)+97,payouts_override=payouts_override)
        st.write("5/5 · Building path-diversified portfolio..."); portfolio=build_portfolio(contest_results,size=int(portfolio_size),max_overlap=int(max_overlap),path_balance=float(path_balance)); portfolio_paths,portfolio_stats=portfolio_summary(portfolio)
        for k,v in {"nuke_sim_results":results,"nuke_sim_players":players.copy(),"nuke_sim_exposure":exposure,"nuke_path_exposure":pexposure,"nuke_contest_results":contest_results,"nuke_contest_summary":contest_summary,"nuke_portfolio":portfolio,"nuke_portfolio_paths":portfolio_paths,"nuke_portfolio_stats":portfolio_stats}.items(): st.session_state[k]=v
        status.update(label="NUKE SIM complete",state="complete")
results=st.session_state.get("nuke_sim_results"); sim_players=st.session_state.get("nuke_sim_players"); exposure=st.session_state.get("nuke_sim_exposure"); pexposure=st.session_state.get("nuke_path_exposure"); contest_results=st.session_state.get("nuke_contest_results"); contest_summary=st.session_state.get("nuke_contest_summary",{}); portfolio=st.session_state.get("nuke_portfolio"); portfolio_paths=st.session_state.get("nuke_portfolio_paths"); portfolio_stats=st.session_state.get("nuke_portfolio_stats",{})
if results is not None and not results.empty:
    tab1,tab2,tab3,tab4,tab5,tab6,tab7=st.tabs(["🏆 CONTEST SIM","🧬 PORTFOLIO","☢️ NUKEM LINEUPS","🧭 PATHS","👤 EXPOSURE","📤 DK EXPORT","🧠 MODEL NOTES"])
    with tab1:
        if contest_results is not None and not contest_results.empty:
            m1,m2,m3,m4,m5,m6=st.columns(6); m1.metric("Field",f"{int(contest_summary.get('field_size',0)):,}"); m2.metric("Entry",f"${float(contest_summary.get('entry_fee',0)):,.2f}"); m3.metric("Paid Places",f"{int(contest_summary.get('paid_places',0)):,}"); m4.metric("Contest Sims",f"{int(contest_summary.get('iterations',0)):,}"); m5.metric("Lineups Simmed",f"{len(contest_results):,}"); m6.metric("Payout Model",str(contest_summary.get("payout_model","")))
            contest_dk=add_dk_roster_columns(sim_players,contest_results)
            left=["QB","RB1","RB2","WR1","WR2","WR3","TE","FLEX","DST","FLEX Pos","Stack"]
            stats=["Contest Rank","Sim ROI %","1st %","Top 0.1%","Top 1%","Cash %","Avg Finish","Expected Duplicates","Avg Payout","Strongest Path","Path Score","Lineup Thesis","NUKE Score","Ceiling 95","Salary"]
            contest_show=contest_dk[[c for c in left+stats if c in contest_dk.columns]].copy(); st.dataframe(contest_show,use_container_width=True,hide_index=True)
            st.download_button("Download Contest SIM + DK Lineups CSV",contest_show.to_csv(index=False).encode("utf-8-sig"),"nuke_contest_sim_dk_lineups.csv","text/csv")
    with tab2:
        if portfolio is not None and not portfolio.empty:
            p1,p2,p3,p4=st.columns(4); p1.metric("Lineups",int(portfolio_stats.get("lineups",0))); p2.metric("Paths Covered",int(portfolio_stats.get("paths",0))); p3.metric("Avg Sim ROI",f"{float(portfolio_stats.get('avg_roi',0)):.1f}%"); p4.metric("Avg Duplicates",f"{float(portfolio_stats.get('avg_dup',0)):.2f}"); st.dataframe(portfolio_paths,use_container_width=True,hide_index=True); st.dataframe(portfolio.drop(columns=["_indices"],errors="ignore"),use_container_width=True,hide_index=True)
    with tab3:
        show=results.drop(columns=["_indices"],errors="ignore"); st.dataframe(show.head(150),use_container_width=True,hide_index=True); st.download_button("Download NUKEM lineup results CSV",show.to_csv(index=False).encode("utf-8-sig"),"nuke_sim_results.csv","text/csv")
    with tab4:
        st.subheader("Path Coverage"); st.dataframe(pexposure,use_container_width=True,hide_index=True); cols=[c for c in ["Rank","Strongest Path","Secondary Path","Path Score","Lineup Thesis","Stack","Salary","QB"] if c in results.columns]; st.dataframe(results[cols].head(int(exposure_n)),use_container_width=True,hide_index=True)
    with tab5:
        st.subheader("Exposure Insights"); scope=st.radio("Exposure scope",["All contest-simmed lineups",f"Top {int(exposure_n)} NUKEM lineups"],horizontal=True)
        er=contest_results if scope.startswith("All") and contest_results is not None else results.head(int(exposure_n)); flex_table=flex_exposure_table(sim_players,er); pos_table=position_exposure_table(sim_players,er)
        fcols=st.columns(3); fmap={str(r["FLEX Position"]):r for _,r in flex_table.iterrows()}
        for col,p in zip(fcols,["RB","WR","TE"]): col.metric(f"{p} in FLEX",f"{int(fmap.get(p,{}).get('Lineups',0)):,}",f"{float(fmap.get(p,{}).get('Exposure %',0)):.1f}%")
        st.dataframe(flex_table,use_container_width=True,hide_index=True); pos_filter=st.selectbox("Position exposure",["ALL","QB","RB","WR","TE","DST"]); pshow=pos_table if pos_filter=="ALL" else pos_table[pos_table.Position.eq(pos_filter)]; st.dataframe(pshow,use_container_width=True,hide_index=True)
        st.markdown("**Top-player exposure detail**"); st.dataframe(exposure,use_container_width=True,hide_index=True)
    with tab6:
        st.subheader("📤 DraftKings Lineup Export"); source_options=["Portfolio","Contest-ranked","NUKEM-ranked"]; export_source=st.selectbox("Lineup source",source_options,index=1,key="dk_export_source"); export_results=portfolio if export_source=="Portfolio" and portfolio is not None and not portfolio.empty else contest_results if export_source=="Contest-ranked" and contest_results is not None and not contest_results.empty else results; max_export=min(150,len(export_results)); export_count=st.number_input("Lineups to export",1,max_export,min(20,max_export),1,key="dk_export_count")
        lineup_only=build_lineup_only_csv(sim_players,export_results,int(export_count)); st.download_button("Download DK lineup-only CSV",lineup_only,"nuke_dk_lineups.csv","text/csv")
        entries_upload=st.file_uploader("Upload your DraftKings Entries CSV",type=["csv"],key="dk_entries_upload")
        if entries_upload is not None:
            try:
                filled,info=fill_entries_csv(entries_upload.getvalue(),sim_players,export_results,int(export_count)); st.success(f"Filled {info['entries_filled']} DraftKings entries."); st.download_button("⬇️ Download DraftKings Upload CSV",filled,"nuke_draftkings_upload.csv","text/csv",type="primary")
            except Exception as e: st.error(f"Could not build DraftKings upload file: {e}")
    with tab7:
        st.markdown("""**Weekly slate:** NUKE auto-loads the built-in current Sunday main slate. Upload a CSV only when you want to override it.\n\n**Correlation upgrade:** NUKE generates a tournament mixture of QB+1, QB+1/1, QB+2, QB+2/1 and QB+2/2 structures.\n\n**Exposure:** FLEX construction and player exposure can be inspected by position.\n\n**Contest CSV:** roster slots are placed before the simulation statistics and use DraftKings `Name (ID)` values for copy/paste analysis.\n\nOpponent ownership remains modeled until Projection/Hybrid input is added.""")

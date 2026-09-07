from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
old='''            story_left,story_right=st.columns(2)\n            with story_left:\n                st.markdown("#### Scenario Bets")\n                scenario_df=story.get("scenario_df",pd.DataFrame())\n                if scenario_df is not None and not scenario_df.empty:\n                    st.dataframe(scenario_df.head(12),use_container_width=True,hide_index=True,height=330)\n                else:\n                    st.caption("No scenario labels are available for this portfolio yet.")\n            with story_right:\n                st.markdown("#### Why Lineups Made It")\n                reason_df=story.get("reason_df",pd.DataFrame())\n                if reason_df is not None and not reason_df.empty:\n                    st.dataframe(reason_df,use_container_width=True,hide_index=True,height=330)\n                else:\n                    st.caption("No portfolio-reason labels are available yet.")\n\n'''
if old not in s:
    raise SystemExit('target block not found')
s=s.replace(old,'',1)
p.write_text(s,encoding='utf-8')
# trigger v2

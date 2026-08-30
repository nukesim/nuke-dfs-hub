import numpy as np
import pandas as pd

from nuke_field import projection_free_player_ownership
from nuke_portfolio import portfolio_player_exposure, portfolio_qb_exposure, portfolio_team_game_exposure, portfolio_health


def _reason_bucket(value):
    s=str(value or "")
    for label in ["Elite Ceiling","Low-Dup Leverage","Scenario Diversifier","Contrarian QB Path","GPP Upside"]:
        if label.lower() in s.lower():
            return label
    return "Other"


def portfolio_story(players, portfolio):
    """Summarize what the portfolio is betting on and where its main risks/leverage live."""
    if players is None or portfolio is None or portfolio.empty:
        return {
            "metrics":{},"scenario_df":pd.DataFrame(),"reason_df":pd.DataFrame(),"leverage_df":pd.DataFrame(),
            "qb_df":pd.DataFrame(),"game_df":pd.DataFrame(),"flags":[]
        }

    n=max(1,len(portfolio))
    scenario_col="Portfolio Scenario" if "Portfolio Scenario" in portfolio.columns else "Strongest Path"
    scenarios=portfolio.get(scenario_col,pd.Series(["UNKNOWN"]*len(portfolio))).fillna("UNKNOWN").astype(str).value_counts()
    scenario_df=pd.DataFrame({"Scenario":scenarios.index,"Lineups":scenarios.values})
    scenario_df["Portfolio %"]=np.round(100.0*scenario_df["Lineups"]/n,1)

    reasons=portfolio.get("Portfolio Reason",pd.Series(["Other"]*len(portfolio))).map(_reason_bucket).value_counts()
    reason_df=pd.DataFrame({"Reason":reasons.index,"Lineups":reasons.values})
    reason_df["Portfolio %"]=np.round(100.0*reason_df["Lineups"]/n,1)

    pexp=portfolio_player_exposure(players,portfolio)
    field=projection_free_player_ownership(players)
    leverage_df=pd.DataFrame()
    if pexp is not None and not pexp.empty and field is not None and not field.empty:
        left=pexp.copy(); right=field.copy()
        left["Player"]=left["Player"].astype(str); left["Pos"]=left["Pos"].astype(str); left["Team"]=left["Team"].astype(str)
        right["Player"]=right["Player"].astype(str); right["Position"]=right["Position"].astype(str); right["Team"]=right["Team"].astype(str)
        leverage_df=left.merge(right[["Player","Position","Team","Field Ownership %"]],left_on=["Player","Pos","Team"],right_on=["Player","Position","Team"],how="left")
        leverage_df["Field Ownership %"]=pd.to_numeric(leverage_df["Field Ownership %"],errors="coerce").fillna(0.0)
        leverage_df["Leverage +/-"]=np.round(pd.to_numeric(leverage_df["Exposure %"],errors="coerce").fillna(0.0)-leverage_df["Field Ownership %"],1)
        leverage_df=leverage_df[["Player","Pos","Team","Salary","Exposure %","Field Ownership %","Leverage +/-"]].sort_values("Leverage +/-",ascending=False).reset_index(drop=True)

    qb_df=portfolio_qb_exposure(portfolio)
    _,game_df=portfolio_team_game_exposure(players,portfolio)
    health=portfolio_health(players,portfolio)
    flags=list(health.get("flags",[]))

    dup=pd.to_numeric(portfolio.get("Duplication Pressure",pd.Series(dtype=float)),errors="coerce").dropna()
    elite=int(reason_df.loc[reason_df["Reason"].eq("Elite Ceiling"),"Lineups"].sum()) if not reason_df.empty else 0
    leverage_count=int(reason_df.loc[reason_df["Reason"].eq("Low-Dup Leverage"),"Lineups"].sum()) if not reason_df.empty else 0
    dominant_scenario=str(scenario_df.iloc[0]["Scenario"]) if not scenario_df.empty else "UNKNOWN"
    dominant_scenario_pct=float(scenario_df.iloc[0]["Portfolio %"]) if not scenario_df.empty else 0.0
    dominant_qb=str(qb_df.iloc[0]["QB"]) if qb_df is not None and not qb_df.empty else "UNKNOWN"
    dominant_qb_pct=float(qb_df.iloc[0]["Exposure %"]) if qb_df is not None and not qb_df.empty else 0.0
    dominant_game=str(game_df.iloc[0]["Game"]) if game_df is not None and not game_df.empty else "UNKNOWN"
    dominant_game_pct=float(game_df.iloc[0]["Exposure %"]) if game_df is not None and not game_df.empty else 0.0

    metrics={
        "lineups":len(portfolio),
        "elite_lineups":elite,
        "leverage_lineups":leverage_count,
        "dominant_scenario":dominant_scenario,
        "dominant_scenario_pct":dominant_scenario_pct,
        "dominant_qb":dominant_qb,
        "dominant_qb_pct":dominant_qb_pct,
        "dominant_game":dominant_game,
        "dominant_game_pct":dominant_game_pct,
        "median_dup_pressure":float(dup.median()) if len(dup) else np.nan,
    }
    return {"metrics":metrics,"scenario_df":scenario_df,"reason_df":reason_df,"leverage_df":leverage_df,"qb_df":qb_df,"game_df":game_df,"flags":flags}

"""Refresh the current card's verified moneylines, preserving matchup identity."""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from check_mma_live import ROOT, scope

if __name__ == "__main__":
    pd = scope["pd"]
    fighters = scope["load_csv"](ROOT / "data/mma_current.csv")
    rows = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {}
        for _, fight in fighters.groupby("Fight"):
            if len(fight) != 2:
                continue
            a, b = fight["Name"].tolist()
            futures[executor.submit(scope["fetch_fight_market"], a, b)] = fight
        for future in as_completed(futures):
            fight = futures[future]
            market = future.result()
            timestamp = pd.Timestamp.now(tz="UTC").isoformat()
            for _, fighter in fight.iterrows():
                values = market.get(scope["_norm_name"](fighter["Name"]), {})
                print(f"{fighter['Name']}: {values}", flush=True)
                if values:
                    rows.append({"Name": fighter["Name"], "Opp": fighter["Opp"],
                                 "Fight": fighter["Fight"], "Game Info": fighter["Game Info"],
                                 **values, "Odds Updated": timestamp})
    if "--save" in sys.argv and rows:
        pd.DataFrame(rows).sort_values("Name").to_csv(ROOT / "data/mma_market.csv", index=False)
    print(f"Verified moneylines: {len(rows)}/{len(fighters)}", flush=True)

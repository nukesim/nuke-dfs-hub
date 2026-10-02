import ast
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "pages/17_MMA_SIM.py"
tree = ast.parse(source.read_text())
# Import functions without executing the Streamlit UI or its network calls.
nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))
         and not (isinstance(n, ast.ImportFrom) and n.module == "nuke_nav")]
for n in nodes:
    if isinstance(n, ast.FunctionDef): n.decorator_list = []
scope = {"__file__": str(source)}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)

if __name__ == "__main__":
    pd = scope["pd"]
    names = pd.read_csv(ROOT / "data/mma_current.csv")["Name"].tolist()
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(scope["fetch_ufcstats"], n): n for n in names}
        for f in as_completed(futures):
            row = {"Name": futures[f], **f.result()}
            print(json.dumps(row), flush=True)
            if "SLpM" in row and "SApM" in row:
                row["Stats Updated"] = pd.Timestamp.now(tz="UTC").isoformat()
                rows.append(row)
    if "--save" in sys.argv:
        pd.DataFrame(rows).sort_values("Name").to_csv(ROOT / "data/mma_fighter_stats.csv", index=False)
    print(f"Verified stats: {len(rows)}/{len(names)}", flush=True)

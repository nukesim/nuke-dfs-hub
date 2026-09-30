import ast
from collections import Counter
from itertools import combinations
from pathlib import Path
import time
import unittest

import numpy as np
import pandas as pd

from nuke_pga_portfolio import (PortfolioError, automatic_exposure_caps,
    generate_pga_candidates, select_pga_portfolio, wave_lineup_targets)


def page_functions():
    """Load pure page helpers without executing Streamlit or remote context calls."""
    source = ast.parse((Path(__file__).resolve().parents[1]/"pages/15_PGA_SIM.py").read_text())
    names = {"load_csv", "base_projection", "ownership_estimate", "simulate_golfers",
             "evaluate", "simulate_contest_metrics", "_norm_name", "_bank_utah_2026_pairings", "export_csv"}
    nodes = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = {"np": np, "pd": pd, "re": __import__("re")}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "pga_helpers", "exec"), env)
    return env


class PGAPortfolioTests(unittest.TestCase):
    def test_solver_repairs_greedy_dead_end(self):
        golfers = pd.DataFrame({"ID": range(14), "Name": [f"G{i}" for i in range(14)]})
        cands = [{"idx": np.array(idx)} for idx in
                 [range(6), [0, 1, 6, 7, 8, 9], [2, 3, 10, 11, 12, 13]]]
        results = pd.DataFrame({"_candidate": [0, 1, 2], "NUKE Score": [100., 90., 80.]})
        portfolio = select_pga_portfolio(results, cands, golfers, 2, 50, 100, 100, {}, {}, np.full(14, 100))
        self.assertEqual(set(portfolio["_candidate"]), {1, 2})

    def test_automatic_caps_protect_salary_tiers(self):
        salary = [6000, 6900, 7000, 7900, 8000, 8900, 9000, 11000]
        caps = automatic_exposure_caps(salary, range(8), np.linspace(.2, .9, 8), np.full(8, 20))
        self.assertTrue(np.all(caps[:2] <= 18))
        self.assertTrue(np.all(caps[2:4] <= 25))
        self.assertTrue(np.all(caps[4:6] <= 35))

    def test_reported_slate_complete_portfolio(self):
        env = page_functions()
        golfers = env["load_csv"](Path(__file__).resolve().parents[1]/"tests/fixtures/pga_bank_utah_2026.csv")
        tee = env["_bank_utah_2026_pairings"]()
        golfers["Wave"] = ["AM" if pd.Timestamp(tee[env["_norm_name"](name)][1]).tz_convert("America/Denver").hour < 12 else "PM" for name in golfers["Name"]]
        own = env["ownership_estimate"](golfers)
        projection = env["base_projection"](golfers)
        quotas = wave_lineup_targets(150, {6: 0, 5: 20, 4: 40, 3: 20, 2: 20, 1: 0, 0: 0})
        for seed in [1932402642, 42, 9876]:
            with self.subTest(seed=seed):
                start = time.monotonic()
                cands = generate_pga_candidates(golfers["ID"], golfers["Salary"], projection, own,
                    5000, 49600, seed, waves=golfers["Wave"], wave_targets=quotas)
                self.assertEqual(len(cands), 5000)
                sims, cut = env["simulate_golfers"](golfers, 3000 if seed == 1932402642 else 250, seed)
                results = env["evaluate"](cands, sims, own)
                results = env["simulate_contest_metrics"](results, cands, sims, cut, 2378, 3, 600, seed)
                caps = automatic_exposure_caps(golfers["Salary"], projection, cut, own)
                portfolio = select_pga_portfolio(results, cands, golfers, 150, 40, 30, 25, {}, {}, caps, wave_targets=quotas)
                self.assertEqual(len(portfolio), 150)
                counts, pairs, triples, waves, unique = Counter(), Counter(), Counter(), Counter(), set()
                for _, row in portfolio.iterrows():
                    cand = cands[int(row["_candidate"])]
                    key = tuple(sorted(golfers.iloc[cand["idx"]]["ID"].astype(int)))
                    self.assertEqual(len(set(key)), 6)
                    self.assertTrue(49600 <= cand["salary"] <= 50000)
                    unique.add(key); counts.update(key)
                    pairs.update(combinations(key, 2)); triples.update(combinations(key, 3))
                    waves[int(np.sum(golfers.iloc[cand["idx"]]["Wave"] == "AM"))] += 1
                self.assertEqual(len(unique), 150)
                self.assertTrue(all(ct >= 2 for ct in counts.values()))
                self.assertTrue(all(ct <= portfolio.attrs["exposure_caps"][pid] for pid, ct in counts.items()))
                self.assertLessEqual(max(pairs.values()), 45)
                self.assertLessEqual(max(triples.values()), 37)
                self.assertEqual(dict(waves), {k: v for k, v in quotas.items() if v})
                blair = int(golfers.loc[golfers["Name"] == "Zac Blair", "ID"].iloc[0])
                self.assertLessEqual(counts[blair], 37)
                exported = env["export_csv"](portfolio, cands, golfers)
                self.assertEqual(len(pd.read_csv(__import__("io").BytesIO(exported))), 150)
                print(f"seed={seed} candidates={len(cands)} portfolio=150 min_used={min(counts.values())} Zac_Blair={counts[blair]}/150 seconds={time.monotonic()-start:.1f}", flush=True)

    def test_minimum_lock_and_zero_max(self):
        golfers = pd.DataFrame({"ID": range(12), "Name": [f"G{i}" for i in range(12)]})
        cands = [{"idx": np.array(c)} for c in combinations(range(12), 6)]
        results = pd.DataFrame({"_candidate": range(len(cands)), "NUKE Score": np.linspace(10, 0, len(cands))})
        p = select_pga_portfolio(results, cands, golfers, 20, 60, 100, 100,
                                 {1: 50}, {2: 0}, np.full(12, 100), {0})
        counts = Counter(pid for j in p["_candidate"] for pid in cands[int(j)]["idx"])
        self.assertEqual(counts[0], 20)
        self.assertGreaterEqual(counts[1], 10)
        self.assertEqual(counts[2], 0)
        self.assertTrue(all(ct >= 2 for ct in counts.values()))
        with self.assertRaisesRegex(PortfolioError, "minimum/lock"):
            select_pga_portfolio(results, cands, golfers, 20, 60, 100, 100, {1: 80}, {}, np.full(12, 100))

    def test_pair_and_triple_caps_are_hard_limits(self):
        golfers = pd.DataFrame({"ID": range(12), "Name": [f"G{i}" for i in range(12)]})
        cands = [{"idx": np.array(c)} for c in combinations(range(12), 6)]
        results = pd.DataFrame({"_candidate": range(len(cands)), "NUKE Score": np.linspace(10, 0, len(cands))})
        p = select_pga_portfolio(results, cands, golfers, 20, 80, 35, 15, {}, {}, np.full(12, 100))
        pairs, triples = Counter(), Counter()
        for j in p["_candidate"]:
            key = tuple(cands[int(j)]["idx"])
            pairs.update(combinations(key, 2)); triples.update(combinations(key, 3))
        self.assertLessEqual(max(pairs.values()), 7)
        self.assertLessEqual(max(triples.values()), 3)

    def test_failure_does_not_return_partial(self):
        golfers = pd.DataFrame({"ID": range(6), "Name": list("ABCDEF")})
        cands = [{"idx": np.arange(6)}]
        results = pd.DataFrame({"_candidate": [0], "NUKE Score": [1.]})
        with self.assertRaisesRegex(PortfolioError, "only 1"):
            select_pga_portfolio(results, cands, golfers, 150, 40, 30, 25, {}, {}, np.full(6, 100))
        p = select_pga_portfolio(results, cands, golfers, 1, 40, 30, 25, {}, {}, np.full(6, 100))
        self.assertEqual(len(p), 1)
        with self.assertRaisesRegex(PortfolioError, "total 100"):
            wave_lineup_targets(150, {3: 95})


if __name__ == "__main__":
    unittest.main()

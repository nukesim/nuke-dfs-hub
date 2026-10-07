import ast
from collections import Counter
from itertools import combinations
from pathlib import Path
import time
import unittest

import numpy as np
import pandas as pd

from nuke_pga_portfolio import (PortfolioError, automatic_exposure_caps,
    generate_pga_candidates, select_pga_portfolio, wave_lineup_targets,
    wave_lineup_bounds, salary_build_type, build_type_summary)


def page_functions():
    """Load pure page helpers without executing Streamlit or remote context calls."""
    source = ast.parse((Path(__file__).resolve().parents[1]/"pages/15_PGA_SIM.py").read_text())
    names = {"load_csv", "salary_baseline", "ownership_estimate", "simulate_golfers",
             "evaluate", "simulate_contest_metrics", "_norm_name", "_bank_utah_2026_pairings", "export_csv",
             "_baycurrent_2026_context", "attach_tee_weather", "weather_severity", "weather_dot"}
    nodes = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = {"np": np, "pd": pd, "re": __import__("re"), "salary_build_type": salary_build_type}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "pga_helpers", "exec"), env)
    return env


class PGAPortfolioTests(unittest.TestCase):
    def test_salary_build_type_caps_10k_and_above(self):
        self.assertEqual(salary_build_type([11000, 10700, 9900, 8800, 7500, 6100]), "10/10/9/8/7/6")
        self.assertEqual(salary_build_type([12500, 10000, 9999, 9000, 8000, 7000]), "10/10/9/9/8/7")

    def test_baycurrent_field_japan_times_and_no_cut(self):
        env=page_functions()
        golfers=env["load_csv"](Path(__file__).resolve().parents[1]/"tests/fixtures/pga_baycurrent_2026.csv")
        ctx=env["_baycurrent_2026_context"]()
        self.assertEqual(len(golfers),72)
        self.assertTrue(golfers["Game Info"].eq("Baycurrent Classic").all())
        self.assertEqual(set(map(env["_norm_name"],golfers["Name"])),set(ctx["tee_times"]))
        hours=pd.date_range("2026-10-08",periods=48,freq="h")
        weather=pd.DataFrame({"time":hours,"wind_speed_10m":np.where(hours.hour<10,6,12),
                              "wind_gusts_10m":15,"precipitation_probability":0,"precipitation":0,"temperature_2m":70})
        enriched=env["attach_tee_weather"](golfers,ctx,weather)
        self.assertTrue(enriched["Wave"].eq("AM").all())
        self.assertTrue(enriched["R1 Tee"].ne("—").all())
        self.assertTrue(enriched["R2 Tee"].ne("—").all())
        self.assertTrue(enriched["Weather"].ne("⚪ TBD").all())
        self.assertTrue(np.isfinite(enriched["Weather Edge"]).all())
        self.assertAlmostEqual(enriched["Weather Edge"].mean(),0)
        byname=enriched.set_index("Name")
        self.assertEqual(byname.loc["Xander Schauffele","R1 Tee"],"9:29 AM")
        self.assertEqual(byname.loc["Xander Schauffele","R2 Tee"],"10:35 AM")
        self.assertEqual(byname.loc["Beau Hossler","R1 Tee"],"8:45 AM")
        self.assertEqual(byname.loc["Doug Ghim","R2 Tee"],"9:40 AM")
        for rec in ctx["tee_times"].values():
            for rnd,date in [(1,"2026-10-08"),(2,"2026-10-09")]:
                stamp=pd.Timestamp(rec[rnd])
                self.assertEqual(str(stamp.date()),date)
                self.assertEqual(stamp.utcoffset().total_seconds(),9*3600)
        _,cut=env["simulate_golfers"](enriched,250,107)
        np.testing.assert_array_equal(cut,np.ones(72))
        legacy=enriched.copy();legacy.attrs["has_cut"]=True
        _,legacy_cut=env["simulate_golfers"](legacy,250,107)
        self.assertTrue((legacy_cut<1).all())
        neutral=env["attach_tee_weather"](golfers,ctx,pd.DataFrame())
        self.assertTrue(neutral["Weather Edge"].eq(0).all())
        self.assertTrue(neutral["Wave"].eq("AM").all())

    def test_baycurrent_complete_150_single_wave_portfolio(self):
        env=page_functions()
        golfers=env["attach_tee_weather"](
            env["load_csv"](Path(__file__).resolve().parents[1]/"tests/fixtures/pga_baycurrent_2026.csv"),
            env["_baycurrent_2026_context"](),pd.DataFrame())
        own=env["ownership_estimate"](golfers);projection=env["salary_baseline"](golfers)
        bounds=wave_lineup_bounds(150,{am:(0,100) for am in range(7)})
        cands=generate_pga_candidates(golfers["ID"],golfers["Salary"],projection,own,5000,49600,107,
                                      waves=golfers["Wave"],wave_bounds=bounds)
        sims,cut=env["simulate_golfers"](golfers,250,107)
        results=env["simulate_contest_metrics"](env["evaluate"](cands,sims,own),cands,sims,cut,2378,3,600,107)
        self.assertTrue(results["6/6 %"].eq(100).all())
        caps=automatic_exposure_caps(golfers["Salary"],projection,cut,own)
        selected=select_pga_portfolio(results,cands,golfers,150,60,30,20,{}, {},caps,wave_bounds=bounds)
        self.assertEqual(len(selected),150)
        self.assertEqual(selected["_candidate"].nunique(),150)
        for j in selected["_candidate"]:
            cand=cands[int(j)]
            self.assertTrue(49600<=cand["salary"]<=50000)
            self.assertTrue(golfers.iloc[cand["idx"]]["Wave"].eq("AM").all())

    def test_salary_build_bands_and_rounding(self):
        self.assertEqual(salary_build_type([6999,7000,7999,8999,9999,10999]), "10/9/8/7/7/6")
        self.assertEqual(salary_build_type([11000,9000,8000,7000,6000,5000]), "10/9/8/7/6/5")
        bounds = wave_lineup_bounds(150, {4:(20,45),3:(10,60),0:(0,0)})
        self.assertEqual(bounds[4], (30,67))
        self.assertEqual(bounds[3], (15,90))
        self.assertEqual(bounds[0], (0,0))
        self.assertEqual(bounds[6], (0,150))
        with self.assertRaisesRegex(PortfolioError, "no whole lineup"):
            wave_lineup_bounds(3, {3:(20,25)})
        with self.assertRaisesRegex(PortfolioError, "minimums"):
            wave_lineup_bounds(20, {3:(60,100),4:(60,100)})
        with self.assertRaisesRegex(PortfolioError, "maximums"):
            wave_lineup_bounds(20, {am:(0,0) for am in range(7)})
        with self.assertRaisesRegex(PortfolioError, "Min %"):
            wave_lineup_bounds(20, {3:(90,20)})

    def test_rebuild_joint_wave_and_build_ranges(self):
        golfers=pd.DataFrame({"ID":range(14),"Name":[f"G{i}" for i in range(14)],
            "Salary":[10000]*3+[9000]*3+[8000]*3+[7000]*3+[6000]*2,
            "Wave":["AM","PM"]*7})
        cands=[{"idx":np.array(c),"salary":int(golfers.iloc[list(c)]["Salary"].sum())}
               for c in combinations(range(14),6) if 46000 <= golfers.iloc[list(c)]["Salary"].sum() <= 50000]
        kinds=[salary_build_type(golfers.iloc[c["idx"]]["Salary"]) for c in cands]
        a,b=[kind for kind,_ in Counter(kinds).most_common(2)]
        results=pd.DataFrame({"_candidate":range(len(cands)),"NUKE Score":[100. if kind==a else 0. for kind in kinds]})
        unchanged=results.copy(deep=True)
        args=(results,cands,golfers,20,100,100,100,{}, {},np.full(14,100))
        original=select_pga_portfolio(*args)
        before=build_type_summary(results,cands,golfers,original).set_index("Build Type")
        bounds=wave_lineup_bounds(20,{0:(0,0),1:(0,0),2:(10,40),3:(20,70),4:(10,50),5:(0,0),6:(0,0)})
        rebuilt=select_pga_portfolio(*args,wave_bounds=bounds,build_ranges={a:(0,30),b:(40,70)})
        summary=build_type_summary(results,cands,golfers,rebuilt).set_index("Build Type")
        self.assertLessEqual(summary.loc[a,"Lineups"],6)
        self.assertGreaterEqual(summary.loc[b,"Lineups"],8)
        self.assertGreater(summary.loc[b,"Lineups"],before.loc[b,"Lineups"])
        wave_counts=Counter(int(np.sum(golfers.iloc[cands[int(j)]["idx"]]["Wave"]=="AM")) for j in rebuilt["_candidate"])
        for am,(lo,hi) in bounds.items():
            self.assertTrue(lo <= wave_counts[am] <= hi)
        uses=Counter(pid for j in rebuilt["_candidate"] for pid in cands[int(j)]["idx"])
        self.assertTrue(all(ct>=2 for ct in uses.values()))
        self.assertEqual(rebuilt["_candidate"].nunique(),20)
        self.assertIn("Build Type",rebuilt)
        pd.testing.assert_frame_equal(results,unchanged)
        with self.assertRaisesRegex(PortfolioError,"only 0 simulated candidates"):
            select_pga_portfolio(*args,build_ranges={"15/14/13/12/11/10":(10,100)})
        self.assertEqual(len(original),20)

    def test_real_slate_flexible_150_and_post_sim_rebuild(self):
        env=page_functions()
        golfers=env["load_csv"](Path(__file__).resolve().parents[1]/"tests/fixtures/pga_bank_utah_2026.csv")
        tee=env["_bank_utah_2026_pairings"]()
        golfers["Wave"]=["AM" if pd.Timestamp(tee[env["_norm_name"](name)][1]).tz_convert("America/Denver").hour<12 else "PM" for name in golfers["Name"]]
        own=env["ownership_estimate"](golfers);projection=env["salary_baseline"](golfers)
        ranges={6:(0,0),5:(5,35),4:(20,55),3:(10,45),2:(5,35),1:(0,0),0:(0,0)}
        bounds=wave_lineup_bounds(150,ranges)
        cands=generate_pga_candidates(golfers["ID"],golfers["Salary"],projection,own,5000,49600,930,
                                      waves=golfers["Wave"],wave_bounds=bounds)
        self.assertEqual(len(cands),5000)
        sims,cut=env["simulate_golfers"](golfers,250,930)
        results=env["evaluate"](cands,sims,own)
        results=env["simulate_contest_metrics"](results,cands,sims,cut,2378,3,600,930)
        caps=automatic_exposure_caps(golfers["Salary"],projection,cut,own)
        args=(results,cands,golfers,150,40,30,25,{}, {},caps)
        portfolio=select_pga_portfolio(*args,wave_bounds=bounds)
        mix=build_type_summary(results,cands,golfers,portfolio)
        kind=mix.sort_values("Candidates",ascending=False).iloc[0]["Build Type"]
        rebuilt=select_pga_portfolio(*args,wave_bounds=bounds,build_ranges={kind:(20,60)})
        self.assertEqual(len(rebuilt),150)
        uses=Counter(int(golfers.iloc[ix]["ID"]) for j in rebuilt["_candidate"] for ix in cands[int(j)]["idx"])
        self.assertTrue(all(ct>=2 and ct<=rebuilt.attrs["exposure_caps"][pid] for pid,ct in uses.items()))
        wave_counts=Counter(int(np.sum(golfers.iloc[cands[int(j)]["idx"]]["Wave"]=="AM")) for j in rebuilt["_candidate"])
        for am,(lo,hi) in bounds.items():
            self.assertTrue(lo<=wave_counts[am]<=hi)
        self.assertTrue(30 <= rebuilt["Build Type"].eq(kind).sum() <= 90)
        exported=pd.read_csv(__import__("io").BytesIO(env["export_csv"](rebuilt,cands,golfers)))
        self.assertEqual(len(exported),150)
        self.assertEqual(list(exported["Build Type"]),list(rebuilt["Build Type"]))
        self.assertIn("Wave Build",exported)

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
        projection = env["salary_baseline"](golfers)
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

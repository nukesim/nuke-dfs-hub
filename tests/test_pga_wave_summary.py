"""Wave summaries must stay visible and never turn missing waves into PM."""
import unittest

import numpy as np
import pandas as pd

from nuke_pga_portfolio import wave_stack_summary


class WaveSummaryTests(unittest.TestCase):
    def test_known_and_unknown_stacks_reconcile_to_portfolio(self):
        golfers = pd.DataFrame({"Wave": ["AM"]*4 + ["PM"]*3 + ["TBD"]})
        cands = [{"idx": np.array(ix)} for ix in
                 [[0,1,2,3,4,5], [0,1,2,4,5,6], [0,1,2,3,4,7]]]
        results = pd.DataFrame({"_candidate": [0,1,2]})
        portfolio = pd.DataFrame({"_candidate": [0,2]})
        summary = wave_stack_summary(results,cands,golfers,portfolio,{4:(20,60)})
        rows = summary.set_index("Wave Stack")
        self.assertEqual(rows.loc["4 AM / 2 PM","Lineups"],1)
        self.assertEqual(rows.loc["4 AM / 2 PM","Candidates"],1)
        self.assertEqual(rows.loc["3 AM / 3 PM","Candidates"],1)
        self.assertEqual(rows.loc["TBD","Lineups"],1)
        self.assertEqual(rows.loc["TBD","Portfolio %"],50)
        self.assertEqual(rows.loc["4 AM / 2 PM","Min %"],20)
        self.assertEqual(rows.loc["4 AM / 2 PM","Max %"],60)
        self.assertEqual(summary["Lineups"].sum(),len(portfolio))
        self.assertEqual(summary["Candidates"].sum(),len(results))
        self.assertEqual(summary["Portfolio %"].sum(),100)

    def test_no_tee_times_keeps_all_seven_types_and_tbd_row(self):
        cands = [{"idx": np.arange(6)}]
        results = pd.DataFrame({"_candidate": [0]})
        summary = wave_stack_summary(results,cands,pd.DataFrame(index=range(6)),results)
        self.assertEqual(len(summary),8)
        self.assertEqual(summary.iloc[-1]["Wave Stack"],"TBD")
        self.assertEqual(summary.iloc[-1]["Portfolio %"],100)
        self.assertEqual(summary.iloc[:-1]["Lineups"].sum(),0)

    def test_known_single_wave_is_not_tbd(self):
        cands = [{"idx": np.arange(6)}]
        results = pd.DataFrame({"_candidate": [0]})
        summary = wave_stack_summary(results,cands,pd.DataFrame({"Wave":["AM"]*6}),results)
        self.assertEqual(len(summary),7)
        self.assertEqual(summary.iloc[0]["Wave Stack"],"6 AM / 0 PM")
        self.assertEqual(summary.iloc[0]["Lineups"],1)


if __name__ == "__main__":
    unittest.main()

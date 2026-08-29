import pandas as pd
from dk_contest_import import parse_payout_dataframe


def test_parse_rank_ranges_and_money():
    df = pd.DataFrame({
        "Place": ["1", "2", "3", "4-5", "6th - 10th"],
        "Prize": ["$1,000", "$500", "$250", "$100", "$50"],
    })
    payouts, info = parse_payout_dataframe(df)
    assert len(payouts) == 10
    assert payouts.tolist() == [1000, 500, 250, 100, 100, 50, 50, 50, 50, 50]
    assert info["paid_places"] == 10
    assert info["first_prize"] == 1000
    assert info["listed_prize_pool"] == 2200

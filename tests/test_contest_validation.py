import pandas as pd
from nuke_contest_validation import parse_dk_lineup, normalize_results, normalize_ownership, contest_structure


def test_parse_dk_lineup():
    s='QB Josh Allen RB James Cook RB Breece Hall WR Stefon Diggs WR CeeDee Lamb WR Nico Collins TE Travis Kelce FLEX Deebo Samuel DST Bills'
    x=parse_dk_lineup(s)
    assert len(x)==9
    assert x[0]==('QB','Josh Allen')
    assert x[-1]==('DST','Bills')


def test_normalize_and_structure():
    df=pd.DataFrame({
        'contest_id':[1,1], 'place':[1,2], 'points':[220.5,210.0],
        'lineup':['QB A RB B RB C WR D WR E WR F TE G FLEX H DST I','QB J RB K RB L WR M WR N WR O TE P FLEX Q DST R'],
        'payout':[1000,500]
    })
    r=normalize_results(df)
    s=contest_structure(r)
    assert s['entries']==2
    assert s['winning_score']==220.5
    assert s['unique_lineups']==2


def test_ownership_fraction_to_percent():
    o=normalize_ownership(pd.DataFrame({
        'contest_id':[1,1], 'player':['A','B'], 'pos':['QB','RB'],
        'drafted':[0.20,0.10], 'points':[20,15]
    }))
    assert round(float(o.loc[0,'drafted']),1)==20.0

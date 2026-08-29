import pandas as pd

from nuke_sim import prepare_slate, generate_lineups, simulate_player_matrix, evaluate_lineups
from nuke_paths import attach_path_labels
from nuke_contest import simulate_contest
from nuke_portfolio import build_portfolio


def _synthetic_slate():
    rows = []
    teams = [
        ("BUF", "HOU"), ("DET", "NO"), ("CIN", "TB"), ("BAL", "IND"),
        ("PHI", "WAS"), ("GB", "MIN"), ("LAC", "ARI"), ("ATL", "PIT"),
    ]
    idx = 1
    for a, b in teams:
        game = f"{a}@{b}"
        for team, opp in [(a, b), (b, a)]:
            rows.append({"name": f"{team} QB", "id": idx, "position": "QB", "team": team, "opponent": opp, "salary": 6100, "game_id": game, "status": ""}); idx += 1
            for j, sal in enumerate([7600, 6200, 4800]):
                rows.append({"name": f"{team} RB{j+1}", "id": idx, "position": "RB", "team": team, "opponent": opp, "salary": sal, "game_id": game, "status": ""}); idx += 1
            for j, sal in enumerate([7200, 6100, 5200, 4300, 3500]):
                rows.append({"name": f"{team} WR{j+1}", "id": idx, "position": "WR", "team": team, "opponent": opp, "salary": sal, "game_id": game, "status": ""}); idx += 1
            for j, sal in enumerate([5600, 3900]):
                rows.append({"name": f"{team} TE{j+1}", "id": idx, "position": "TE", "team": team, "opponent": opp, "salary": sal, "game_id": game, "status": ""}); idx += 1
            rows.append({"name": f"{team} DST", "id": idx, "position": "DST", "team": team, "opponent": opp, "salary": 3200, "game_id": game, "status": ""}); idx += 1
    # Verify inactive filtering too.
    rows.append({"name": "OUT TEST", "id": idx, "position": "WR", "team": "BUF", "opponent": "HOU", "salary": 5000, "game_id": "BUF@HOU", "status": "OUT"})
    return pd.DataFrame(rows)


def test_full_nuke_sim_pipeline():
    players = prepare_slate(_synthetic_slate())
    assert players.Game.nunique() == 8
    assert "OUT TEST" not in set(players.Name)

    lineups = generate_lineups(players, n_lineups=40, min_salary=47000, seed=26)
    assert len(lineups) >= 20

    # Every generated lineup should have at least QB + 1 pass catcher.
    for lu in lineups:
        r = players.iloc[lu]
        qb = r[r.Position.eq("QB")].iloc[0]
        mates = r[(r.Team.eq(qb.Team)) & (r.Position.isin(["WR", "TE"]))]
        assert len(mates) >= 1
        assert 47000 <= int(r.Salary.sum()) <= 50000

    matrix = simulate_player_matrix(players, n_sims=80, seed=26)
    results = evaluate_lineups(players, lineups, matrix)
    results = attach_path_labels(players, results)
    assert not results.empty
    assert "Strongest Path" in results.columns
    assert "Lineup Thesis" in results.columns

    contest, summary = simulate_contest(
        results, matrix, field_size=50, entry_fee=5.0, first_prize=50.0,
        user_lineups=min(15, len(results)), iterations=60, seed=123,
    )
    assert not contest.empty
    for col in ["Sim ROI %", "1st %", "Top 1%", "Cash %", "Expected Duplicates"]:
        assert col in contest.columns
    assert summary["field_size"] == 50

    portfolio = build_portfolio(contest, size=min(8, len(contest)), max_overlap=7, path_balance=1.25)
    assert not portfolio.empty
    assert "Portfolio Slot" in portfolio.columns

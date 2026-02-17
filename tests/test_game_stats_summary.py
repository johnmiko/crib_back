from app import GameSession


def test_build_game_stats_includes_requested_fields_for_both_players():
    session = GameSession(game_id="stats-shape", opponent_type="random")
    session.total_rounds_completed = 4

    session.total_points_pegged_human = 12
    session.total_points_pegged_computer = 8
    session.high_points_pegged_human = 5
    session.high_points_pegged_computer = 4

    session.total_hand_score_human = 28
    session.total_hand_score_computer = 24
    session.human_hands_count = 4
    session.computer_hands_count = 4
    session.high_hand_score_human = 12
    session.high_hand_score_computer = 10

    session.total_crib_score_human = 10
    session.total_crib_score_computer = 6
    session.human_dealer_count = 2
    session.computer_dealer_count = 2
    session.high_crib_score_human = 7
    session.high_crib_score_computer = 4

    session.total_cut_score_human = 2
    session.total_cut_score_computer = 0

    stats = session._build_game_stats()

    assert stats["rounds_played"] == 4
    assert stats["avg_pegging_diff"] == 1.0
    assert stats["you"]["pegging_average"] == 3.0
    assert stats["you"]["pegging_high"] == 5
    assert stats["you"]["pegging_total"] == 12
    assert stats["you"]["hand_average"] == 7.0
    assert stats["you"]["hand_high"] == 12
    assert stats["you"]["hand_total"] == 28
    assert stats["you"]["crib_average"] == 5.0
    assert stats["you"]["crib_high"] == 7
    assert stats["you"]["crib_total"] == 10
    assert stats["you"]["cut_total"] == 2

    assert stats["computer"]["pegging_average"] == 2.0
    assert stats["computer"]["pegging_high"] == 4
    assert stats["computer"]["pegging_total"] == 8
    assert stats["computer"]["hand_average"] == 6.0
    assert stats["computer"]["hand_high"] == 10
    assert stats["computer"]["hand_total"] == 24
    assert stats["computer"]["crib_average"] == 3.0
    assert stats["computer"]["crib_high"] == 4
    assert stats["computer"]["crib_total"] == 6
    assert stats["computer"]["cut_total"] == 0

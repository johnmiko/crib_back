"""Pegging and scoring tests (pairs, fifteens, last card, count)."""

import logging
from app import GameSession, ResumableRound
from cribbage.cribbagegame import CribbageRound, CribbageGame
from cribbage.player import RandomPlayer
from cribbage.playingcards import Deck, Card
from cribbage.models import ActionType


def _make_card(rank: str, suit: str) -> Card:
    return Card(rank=Deck.RANKS[rank], suit=Deck.SUITS[suit])


def test_player_goes_computer_plays_and_scores_1_point():
    """Player says go at 24; computer plays ace to 25 and earns last-card point."""
    session = GameSession("test-go")

    session.game.board.pegs[session.human]['front'] = 1
    session.game.board.pegs[session.human]['rear'] = 0
    session.game.board.pegs[session.computer]['front'] = 2
    session.game.board.pegs[session.computer]['rear'] = 1

    round_obj = ResumableRound(game=session.game, dealer=session.computer)
    session.current_round = round_obj

    nine_hearts = _make_card('nine', 'hearts')
    ace_hearts = _make_card('ace', 'hearts')
    table_cards = [
        _make_card('ten', 'spades'),
        _make_card('ten', 'clubs'),
        _make_card('four', 'diamonds'),
    ]

    round_obj.phase = 'play'
    round_obj.sequence_start_idx = 0
    round_obj.active_players = [session.human, session.computer]
    round_obj.round.hands = {
        session.human: [nine_hearts],
        session.computer: [ace_hearts],
    }
    round_obj.round.table = [
        {'player': session.human, 'card': table_cards[0]},
        {'player': session.human, 'card': table_cards[1]},
        {'player': session.human, 'card': table_cards[2]},
    ]
    round_obj.round.starter = _make_card('five', 'hearts')
    round_obj.round.crib = []

    session.waiting_for = ActionType.SELECT_CARD_TO_PLAY
    session.last_cards = [nine_hearts]
    session.last_n_cards = 1
    session.message = "Play a card"

    state = session.submit_action([])

    assert state.scores['computer'] == 3
    assert state.scores['you'] == 1
    assert state.table_value == 0


def test_table_value_count_with_aces_and_twos():
    """Count should progress 1,3,6,... when alternating aces (1) and twos (2)."""
    session = GameSession("test-count")
    round_obj = ResumableRound(game=session.game, dealer=session.computer)
    session.current_round = round_obj

    ace_diamonds = _make_card('ace', 'diamonds')
    ace_hearts = _make_card('ace', 'hearts')
    ace_spades = _make_card('ace', 'spades')
    ace_clubs = _make_card('ace', 'clubs')
    two_diamonds = _make_card('two', 'diamonds')
    two_hearts = _make_card('two', 'hearts')
    two_spades = _make_card('two', 'spades')
    two_clubs = _make_card('two', 'clubs')

    round_obj.phase = 'play'
    round_obj.sequence_start_idx = 0
    round_obj.active_players = [session.human, session.computer]
    round_obj.round.hands = {
        session.human: [ace_diamonds, ace_hearts, ace_spades, ace_clubs],
        session.computer: [two_diamonds, two_hearts, two_spades, two_clubs],
    }
    round_obj.round.table = []
    round_obj.round.starter = _make_card('five', 'hearts')
    round_obj.round.crib = []

    session.waiting_for = ActionType.SELECT_CARD_TO_PLAY
    session.last_cards = [ace_diamonds, ace_hearts, ace_spades, ace_clubs]
    session.last_n_cards = 1
    session.message = "Play a card"

    state = session.submit_action([0])

    logging.debug("After player plays ace: table_len=%s, table_value=%s",
                  len(state.table_cards), state.table_value)
    assert len(state.table_cards) == 2
    assert state.table_cards[0].rank == 'ace'
    assert state.table_cards[1].rank == 'two'
    assert state.table_value == 3

    state = session.submit_action([0])

    logging.debug("After second ace: table_len=%s, table_value=%s",
                  len(state.table_cards), state.table_value)
    assert len(state.table_cards) == 4
    assert state.table_value == 6


def test_scoring_pairs_and_fifteens(deterministic_computer):
    """Deterministic test: 15 scores 2; pair scores 2."""
    # Scenario 1: 5 then 10 => 15
    session = GameSession("test-scoring-15")
    round_obj = ResumableRound(game=session.game, dealer=session.computer)
    session.current_round = round_obj

    five_d = _make_card('five', 'diamonds')
    ten_d = _make_card('ten', 'diamonds')
    ten_h = _make_card('ten', 'hearts')
    ten_c = _make_card('ten', 'clubs')
    ten_s = _make_card('ten', 'spades')
    five_h = _make_card('five', 'hearts')
    five_s = _make_card('five', 'spades')
    five_c = _make_card('five', 'clubs')

    round_obj.phase = 'play'
    round_obj.sequence_start_idx = 0
    round_obj.active_players = [session.human, session.computer]
    round_obj.round.hands = {
        session.human: [five_d, ten_d, ten_h, ten_c],
        session.computer: [ten_s, five_h, five_s, five_c],
    }
    round_obj.round.table = []
    round_obj.round.starter = _make_card('ace', 'hearts')
    round_obj.round.crib = []

    session.game.board.pegs[session.human]['front'] = 0
    session.game.board.pegs[session.human]['rear'] = 0
    session.game.board.pegs[session.computer]['front'] = 0
    session.game.board.pegs[session.computer]['rear'] = 0

    session.waiting_for = ActionType.SELECT_CARD_TO_PLAY
    session.last_cards = [five_d, ten_d, ten_h, ten_c]
    session.last_n_cards = 1
    session.message = "Play a card"

    state = session.submit_action([0])  # play 5♦, computer should play 10♠ to make 15
    assert state.table_value == 15
    assert state.scores['computer'] == 2

    # Scenario 2: 10 then 10 => pair
    session2 = GameSession("test-scoring-pair")
    round_obj2 = ResumableRound(game=session2.game, dealer=session2.computer)
    session2.current_round = round_obj2

    ten_d2 = _make_card('ten', 'diamonds')
    ten_h2 = _make_card('ten', 'hearts')
    ten_s2 = _make_card('ten', 'spades')
    five_d2 = _make_card('five', 'diamonds')
    five_h2 = _make_card('five', 'hearts')

    round_obj2.phase = 'play'
    round_obj2.sequence_start_idx = 0
    round_obj2.active_players = [session2.human, session2.computer]
    round_obj2.round.hands = {
        session2.human: [ten_d2, five_h2],
        session2.computer: [ten_s2, ten_h2],
    }
    round_obj2.round.table = []
    round_obj2.round.starter = _make_card('ace', 'hearts')
    round_obj2.round.crib = []

    session2.game.board.pegs[session2.human]['front'] = 0
    session2.game.board.pegs[session2.human]['rear'] = 0
    session2.game.board.pegs[session2.computer]['front'] = 0
    session2.game.board.pegs[session2.computer]['rear'] = 0

    session2.waiting_for = ActionType.SELECT_CARD_TO_PLAY
    session2.last_cards = [ten_d2, five_h2]
    session2.last_n_cards = 1
    session2.message = "Play a card"

    state2 = session2.submit_action([0])  # play 10♦, computer should play 10♠ for a pair
    assert state2.table_value == 20
    assert state2.scores['computer'] == 2

    logging.info("Deterministic scoring verified: 15 and pair both score 2 points")


def test_reaching_31_awards_two_points_total():
    """Reaching exactly 31 should peg 1 (for 31) + 1 (for last card)."""
    game = CribbageGame(players=[RandomPlayer("human"), RandomPlayer("computer")])
    round_obj = CribbageRound(game=game, dealer=game.players[1])

    human = game.players[0]

    two_d = _make_card('two', 'diamonds')  # Will be played to reach 31
    table_cards = [
        {'player': human, 'card': _make_card('ten', 'hearts')},
        {'player': game.players[1], 'card': _make_card('nine', 'clubs')},
        {'player': human, 'card': _make_card('ten', 'spades')},
        {'player': human, 'card': two_d},  # makes 31
    ]

    round_obj.table = table_cards
    round_obj.hands = {human: [], game.players[1]: []}

    # Reset scores to zero for clarity
    game.board.pegs[human]['front'] = 0
    game.board.pegs[human]['rear'] = 0
    game.board.pegs[game.players[1]]['front'] = 0
    game.board.pegs[game.players[1]]['rear'] = 0

    # Score reaching 31
    points_for_31 = round_obj._score_play([move['card'] for move in table_cards])
    if points_for_31:
        game.board.peg(human, points_for_31)

    # Both players are out of cards; last card point should be added
    round_obj.go_or_31_reached(active_players=[])

    assert game.board.get_score(human) == 2
    assert game.board.get_score(game.players[1]) == 0


def test_runs_out_of_order_scoring():
    """Unit-score runs during play: 1,3,2 -> 3; then +4 with 4; then +3 with 3."""
    game = CribbageGame(players=[RandomPlayer("human"), RandomPlayer("computer")])
    r = CribbageRound(game=game, dealer=game.players[1])

    a_h = _make_card('ace', 'hearts')
    two_d = _make_card('two', 'diamonds')
    three_s = _make_card('three', 'spades')
    four_c = _make_card('four', 'clubs')

    assert r._score_play([a_h, three_s, two_d]) == 3
    assert r._score_play([a_h, three_s, two_d, four_c]) == 4
    # Adding another 3 should form a new 3-run among the last 3 distinct ranks
    assert r._score_play([a_h, three_s, two_d, four_c, _make_card('three', 'hearts')]) == 3


def test_three_of_a_kind_scores_six():
    """Unit-score: on third same-rank card, score 6 for the play."""
    game = CribbageGame(players=[RandomPlayer("human"), RandomPlayer("computer")])
    r = CribbageRound(game=game, dealer=game.players[1])

    seven_h = _make_card('seven', 'hearts')
    seven_d = _make_card('seven', 'diamonds')
    seven_s = _make_card('seven', 'spades')

    assert r._score_play([seven_h, seven_d, seven_s]) == 6


def test_four_of_a_kind_scores_twelve():
    """Unit-score: on fourth same-rank card, score 12 for the play."""
    game = CribbageGame(players=[RandomPlayer("human"), RandomPlayer("computer")])
    r = CribbageRound(game=game, dealer=game.players[1])

    nine_h = _make_card('nine', 'hearts')
    nine_d = _make_card('nine', 'diamonds')
    nine_s = _make_card('nine', 'spades')
    nine_c = _make_card('nine', 'clubs')

    assert r._score_play([nine_h, nine_d, nine_s, nine_c]) == 12

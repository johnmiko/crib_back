"""Pegging and scoring tests (pairs, fifteens, last card, count)."""

import logging
from app import GameSession, ResumableRound
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

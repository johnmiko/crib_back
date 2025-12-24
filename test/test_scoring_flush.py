import pytest

from cribbage.cribbagegame import CribbageGame, CribbageRound
from cribbage.playingcards import Card, Deck
from cribbage.player import RandomPlayer

def make_card(rank: str, suit: str) -> Card:
    return Card(rank=Deck.RANKS[rank], suit=Deck.SUITS[suit])


def make_round() -> CribbageRound:
    game = CribbageGame(players=[RandomPlayer("player1"), RandomPlayer("player2")])
    return CribbageRound(game, dealer=game.players[0])


def make_flush_cards(starter_suit: str):
    """Four heart hand cards plus a starter in the requested suit."""
    return [
        make_card("eight", "hearts"),
        make_card("nine", "hearts"),
        make_card("queen", "hearts"),
        make_card("king", "hearts"),
        make_card("three", starter_suit),
    ]


def test_hand_flush_scores_four_without_starter_match():
    round_inst = make_round()
    cards = make_flush_cards(starter_suit="clubs")

    score = round_inst._score_hand(cards, is_crib=False)

    assert score == 4


def test_hand_flush_scores_five_with_starter_match():
    round_inst = make_round()
    cards = make_flush_cards(starter_suit="hearts")

    score = round_inst._score_hand(cards, is_crib=False)

    assert score == 5


def test_crib_flush_requires_all_five_cards_match():
    round_inst = make_round()
    non_matching = make_flush_cards(starter_suit="clubs")
    matching = make_flush_cards(starter_suit="hearts")

    no_flush_score = round_inst._score_hand(non_matching, is_crib=True)
    flush_score = round_inst._score_hand(matching, is_crib=True)

    assert no_flush_score == 0
    assert flush_score == 5

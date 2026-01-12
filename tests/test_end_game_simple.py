"""Simplified end-of-game tests to verify game ends correctly when reaching 121.

This test suite focuses on the critical bug: verifying that the game ends 
IMMEDIATELY when a player reaches 121 points, not allowing further play.
"""
import pytest
from app import GameSession, ResumableRound
from cribbage.players.play_first_card_player import PlayFirstCardPlayer
from cribbage.playingcards import Card, build_hand
from logging import getLogger

logger = getLogger(__name__)


def create_test_session() -> GameSession:
    """Create a test session with automated players."""
    session = GameSession(game_id="test-game", opponent_type="random")
    # Replace the APIPlayer with PlayFirstCardPlayer for automated testing
    session.human = PlayFirstCardPlayer(name="human")
    session.game.players = [session.human, session.computer]
    # Re-initialize board with new player references
    session.game.board.players = session.game.players
    return session


def test_human_wins_by_pegging_15_from_119():
    """Test that human wins by scoring 15 for 2 points, going from 119 to 121.
    
    This validates the primary bug: game should end immediately when 121 is reached.
    """
    session = create_test_session()
    game = session.game
    
    # Set both players to 119
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Human is dealer, so computer (nondealer) plays first
    # Computer plays 10, human plays 5 to make 15 and win
    dealer = session.human
    session.current_round = ResumableRound(game=game, dealer=dealer)
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['5h', '5d', '5c', '5s']),
        "computer": build_hand(['10h', '10d', '10c', '10s'])
    }
    session.current_round.phase = 'play'
    
    session.current_round.run()
    
    human_score = game.board.get_score(session.human)
    computer_score = game.board.get_score(session.computer)
    
    assert human_score == 121, f"Expected human to win with 121, got {human_score}"
    assert session.current_round.game_winner is not None, "Game should have a winner"
    assert session.current_round.game_winner.name == "human", "Human should be the winner"
    assert computer_score == 119, f"Computer score should remain 119, got {computer_score}"


def test_computer_wins_by_pegging_15_from_119():
    """Test that computer wins by scoring 15 for 2 points from 119 to 121."""
    session = create_test_session()
    game = session.game
    
    # Human at 118, computer at 119
    game.board.pegs["human"]['front'] = 118
    game.board.pegs["human"]['rear'] = 118
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Computer is dealer, so human (nondealer) plays first
    # Human plays 10, computer plays 5 to make 15 and win
    dealer = session.computer
    session.current_round = ResumableRound(game=game, dealer=dealer)
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['10h', '10d', '10c', '10s']),
        "computer": build_hand(['5h', '5d', '5c', '5s'])
    }
    session.current_round.phase = 'play'
    
    session.current_round.run()
    
    human_score = game.board.get_score(session.human)
    computer_score = game.board.get_score(session.computer)
    
    assert computer_score == 121, f"Expected computer to win with 121, got {computer_score}"
    assert session.current_round.game_winner is not None, "Game should have a winner"
    assert session.current_round.game_winner.name == "computer", "Computer should be the winner"
    assert human_score == 118, f"Human score should remain 118, got {human_score}"


def test_game_stops_immediately_at_121_during_pegging():
    """CRITICAL TEST: Verify game stops immediately when 121 is reached during pegging.
    
    This is the primary bug report - when you won by pegging, the game should have
    ended immediately and not allowed the opponent to continue playing.
    """
    session = create_test_session()
    game = session.game
    
    # Both players at 119 - whoever scores first wins
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Human is dealer, computer plays first
    dealer = session.human
    session.current_round = ResumableRound(game=game, dealer=dealer)
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['5h', 'ah', '2h', '3h']),
        "computer": build_hand(['10h', '10d', '10c', '10s'])
    }
    session.current_round.phase = 'play'
    
    session.current_round.run()
    
    human_score = game.board.get_score(session.human)
    computer_score = game.board.get_score(session.computer)
    
    # Computer plays 10, human plays 5 for 15 -> human scores 2 and reaches 121
    assert human_score == 121, f"Expected human to reach 121, got {human_score}"
    assert session.current_round.game_winner.name == "human", "Human should be winner"
    
    # CRITICAL ASSERTION: Computer should NOT have scored after human won
    assert computer_score == 119, (
        f"CRITICAL BUG: Computer should still be at 119, but got {computer_score}. "
        "Game continued after human reached 121!"
    )


def test_human_wins_by_pair_from_119():
    """Test that human wins by pegging a pair for 2 points."""
    session = create_test_session()
    game = session.game
    
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 100
    game.board.pegs["computer"]['rear'] = 100
    
    # Human is dealer, computer plays first
    dealer = session.human
    session.current_round = ResumableRound(game=game, dealer=dealer)
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['5h', '5d', '5c', '5s']),
        "computer": build_hand(['5c', '10d', '10c', '10s'])
    }
    session.current_round.phase = 'play'
    
    session.current_round.run()
    
    human_score = game.board.get_score(session.human)
    
    # Computer plays 5c, human plays 5h (pair for 2 points) -> 121
    assert human_score >= 121, f"Expected human to win with at least 121, got {human_score}"
    assert session.current_round.game_winner is not None, "Game should have a winner"
    assert session.current_round.game_winner.name == "human", "Human should be the winner"

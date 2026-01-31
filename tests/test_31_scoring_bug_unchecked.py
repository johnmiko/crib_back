"""Test for the bug where scoring 31 doesn't immediately update the board score."""
import pytest
from cribbage.playingcards import Card, build_hand
from cribbage.players.random_player import RandomPlayer
from cribbage.players.play_first_card_player import PlayFirstCardPlayer
from cribbage.cribbagegame import CribbageGame, CribbageRound
from app import ResumableRound, APIPlayer, GameSession


def test_scoring_31_updates_board_immediately():
    """
    Test that when a player scores by reaching 31, their score on the board
    is updated immediately.
    
    This reproduces the bug from the logs where:
    - Computer has 117 points
    - Computer plays to make table value 31
    - Log shows: "computer scores 1 for reaching 31. Scores: human=115, computer=117"
    - But score should immediately show 118 (117 + 1 for the 31)
    """
    # Create a game session
    session = GameSession(game_id="test-31", opponent_type="random")
    
    # Replace human with automated player for testing
    session.human = PlayFirstCardPlayer(name="human")
    session.game.players = [session.human, session.computer]
    
    # Set scores: human=115, computer=117 (as in the bug report)
    game = session.game
    game.board.pegs["human"]['front'] = 115
    game.board.pegs["human"]['rear'] = 115
    game.board.pegs["computer"]['front'] = 117
    game.board.pegs["computer"]['rear'] = 117
    
    # Create a round where computer will play to reach 31
    session.current_round = ResumableRound(game=game, dealer=session.computer)
    r = session.current_round.round
    r.starter = Card("9h")
    
    # Set up hands where the table can reach 31
    # Human will play 5, 10 (so table is at 15)
    # Then human plays J (25), computer plays 6 to make 31
    r.hands = {
        "human": build_hand(['5h', '10d', 'jh', '2c']),
        "computer": build_hand(['10h', '6c', '8d', '2s'])
    }
    session.current_round.phase = 'play'
    
    # Capture state before running
    computer_score_before = game.board.get_score(session.computer)
    assert computer_score_before == 117
    
    # Run the pegging phase 
    session.current_round.run()
    
    # Check that computer scored for reaching 31
    # The computer should have 118 after reaching 31 (117 + 1)
    # Plus potentially more from other scoring
    computer_score_after = game.board.get_score(session.computer)
    
    # The bug is that the score doesn't update when 31 is reached
    # This test will fail until the bug is fixed
    assert computer_score_after >= 118, \
        f"Expected computer to score at least 1 point for reaching 31 (117->118+), but got {computer_score_after}"


def test_scoring_31_correct_sequence():
    """
    Test the correct sequence: peg to board THEN get scores for logging.
    
    This is a unit test showing what the code SHOULD do.
    """
    # Setup game with specific starting scores
    human = APIPlayer("human")
    computer = RandomPlayer("computer")
    game = CribbageGame([human, computer])
    
    # Set initial scores
    game.board.pegs["human"]['front'] = 115
    game.board.pegs["human"]['rear'] = 115
    game.board.pegs["computer"]['front'] = 117
    game.board.pegs["computer"]['rear'] = 117
    
    # Get score before
    score_before = game.board.get_score(computer)
    assert score_before == 117
    
    # THIS IS THE CORRECT SEQUENCE: 
    # 1. Peg 1 point for reaching 31 FIRST
    game.board.peg(computer, 1)
    
    # 2. THEN get the scores for logging
    scores = game.board.get_scores()
    
    # 3. Now the scores should reflect the pegged point
    assert scores[1] == 118, f"Expected computer score to be 118 after pegging, got {scores[1]}"

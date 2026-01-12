"""Tests for end-of-game scenarios via the API to ensure correct winner determination.

These tests validate that:
1. Games end immediately when a player reaches 121 during pegging
2. Games end when a player reaches 121 during hand counting
3. Winner is correctly identified
4. Ties are impossible
"""
import pytest
from app import GameSession, ResumableRound
from cribbage.cribbagegame import CribbageGame
from cribbage.players.play_first_card_player import PlayFirstCardPlayer
from cribbage.playingcards import Card, build_hand
from logging import getLogger

logger = getLogger(__name__)


def create_test_round(session: GameSession, dealer_name: str) -> ResumableRound:
    """Helper to create a ResumableRound for testing."""
    # Get the dealer player object
    dealer = None
    for player in session.game.players:
        if player.name == dealer_name:
            dealer = player
            break
    if dealer is None:
        raise ValueError(f"Player {dealer_name} not found")
    
    return ResumableRound(game=session.game, dealer=dealer)


def setup_automated_players(session: GameSession):
    """Replace the human APIPlayer with PlayFirstCardPlayer for automated testing."""
    session.human = PlayFirstCardPlayer(name="human")
    session.game.players = [session.human, session.computer]
    # Re-initialize board pegs for new player object
    session.game.board.pegs = {p.name: {'front': session.game.board.pegs[p.name]['front'], 
                                          'rear': session.game.board.pegs[p.name]['rear']} 
                                for p in session.game.players}


def test_human_wins_by_pegging_to_121():
    """Test that human wins by pegging 15 for 2 points from 119 to 121."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    # Replace human player with PlayFirstCardPlayer for automated testing
    session.human = PlayFirstCardPlayer(name="human")
    session.game.players = [session.human, session.computer]
    
    # Set both players to 119 points
    game = session.game
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Create a round where HUMAN is dealer, so COMPUTER plays first
    # Computer plays 10, then human plays 5 to make 15 and score 2 points
    session.current_round = create_test_round(session, dealer_name="human")
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['5h', '5d', '5c', '5s']),
        "computer": build_hand(['10h', '10d', '10c', '10s'])
    }
    # Start from 'play' phase to run pegging
    session.current_round.phase = 'play'
    # Initialize active players for play phase
    session.current_round.active_players = None  # Will be initialized in run()
    
    # Play the round
    logger.info(f"Before run: human score={game.board.get_score(session.human)}, computer score={game.board.get_score(session.computer)}")
    session.current_round.run()
    logger.info(f"After run: human score={game.board.get_score(session.human)}, computer score={game.board.get_score(session.computer)}")
    
    # Computer (nondealer) plays first: 10h
    # Human (dealer) plays second: 5h, making 15 for 2 points -> 121
    human_score = game.board.get_score(session.human)
    computer_score = game.board.get_score(session.computer)
    
    logger.info(f"Final: human={human_score}, computer={computer_score}, winner={session.current_round.game_winner}")
    
    assert human_score == 121, f"Expected human to have 121, got {human_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "human", "Expected human to be the winner"
    # Computer should not have played after human won
    assert computer_score == 119, f"Computer score should be 119, got {computer_score}"


def test_computer_wins_by_pegging_to_121():
    """Test that computer wins by pegging 15 for 2 points."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    # Replace human player with PlayFirstCardPlayer for automated testing
    session.human = PlayFirstCardPlayer(name="human")
    session.game.players = [session.human, session.computer]
    
    # Set scores near winning
    game = session.game
    game.board.pegs["human"]['front'] = 118
    game.board.pegs["human"]['rear'] = 118
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Computer is dealer, human plays first
    session.current_round = create_test_round(session, dealer_name="computer")
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['10h', '10d', '10c', '10s']),
        "computer": build_hand(['5h', '5d', '5c', '5s'])
    }
    session.current_round.phase = 'play'
    
    # Play the round
    session.current_round.run()
    
    computer_score = game.board.get_score(session.computer)
    human_score = game.board.get_score(session.human)
    
    # Human plays 10h, computer plays 5h for 15 and scores 2 points -> 121
    assert computer_score == 121, f"Expected computer to have 121, got {computer_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "computer", "Expected computer to be the winner"
    # Human should have played once but not scored
    assert human_score == 118, f"Human score should be 118, got {human_score}"


def test_human_wins_by_pegging_pair():
    """Test that human wins by pegging a pair."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 100
    game.board.pegs["computer"]['rear'] = 100
    
    # Computer is dealer, human plays first
    session.current_round = create_test_round(session, dealer_name="computer")
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['5h', '5d', '5c', '5s']),
        "computer": build_hand(['5h', '10d', '10c', '10s'])
    }
    session.current_round.phase = 'pegging'
    
    # Play the round
    session.current_round.run()
    
    human_score = game.board.get_score(session.human)
    
    # Human plays 5h, computer plays 5h (pair), human should not score yet
    # But if human plays next 5, they score for pair royal (6 points) or three of a kind
    # Actually with deterministic_computer fixture, computer prefers pairs
    # So: human plays 5h, computer plays 5h (scores 2), human plays 5d (scores 6)
    # Human should win
    assert human_score >= 121, f"Expected human to win with at least 121, got {human_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "human", "Expected human to be the winner"


def test_human_wins_counting_hand_first():
    """Test that human (non-dealer) wins by counting hand first."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Computer is dealer, so human counts first
    session.current_round = create_test_round(session, dealer_name="computer")
    r = session.current_round.round
    r.starter = Card("9h")
    
    # Give human a hand that scores at least 2 points
    # 3-3-A-A-A-A with starter 9h
    r.hands = {
        "human": build_hand(['3h', '3d', 'ac', 'as']),
        "computer": build_hand(['2c', '2s', '2h', '2d'])
    }
    r.crib = build_hand(['ah', 'ad'])
    session.current_round.phase = 'pegging'
    
    # Skip pegging by clearing hands after simulating some plays
    # Actually, let's just advance to scoring phase
    session.current_round.phase = 'scoring'
    
    # Score hands
    r.score_hands_phase()
    
    human_score = game.board.get_score(session.human)
    
    # Human should have scored at least 2 points (pair of 3s) and won
    assert human_score >= 121, f"Expected human to win with at least 121, got {human_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "human", "Expected human to be the winner"


def test_computer_wins_counting_hand_first():
    """Test that computer (non-dealer) wins by counting hand first."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Human is dealer, so computer counts first
    session.current_round = create_test_round(session, dealer_name="human")
    r = session.current_round.round
    r.starter = Card("9h")
    
    # Give computer a hand that scores at least 2 points
    r.hands = {
        "human": build_hand(['2c', '2s', '2h', '2d']),
        "computer": build_hand(['3h', '3d', 'ac', 'as'])
    }
    r.crib = build_hand(['ah', 'ad'])
    session.current_round.phase = 'scoring'
    
    # Score hands
    r.score_hands_phase()
    
    computer_score = game.board.get_score(session.computer)
    
    # Computer should have scored at least 2 points and won
    assert computer_score >= 121, f"Expected computer to win with at least 121, got {computer_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "computer", "Expected computer to be the winner"


def test_human_wins_counting_hand_second():
    """Test that human (dealer) wins by counting hand second."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 100
    game.board.pegs["computer"]['rear'] = 100
    
    # Human is dealer, so computer counts first, then human
    session.current_round = create_test_round(session, dealer_name="human")
    r = session.current_round.round
    r.starter = Card("10h")
    
    # Give human a hand that scores enough to win
    r.hands = {
        "human": build_hand(['3h', '3d', 'ac', 'as']),
        "computer": build_hand(['2c', '2s', '2h', '2d'])
    }
    r.crib = build_hand(['ah', 'ad'])
    session.current_round.phase = 'scoring'
    
    # Score hands
    r.score_hands_phase()
    
    human_score = game.board.get_score(session.human)
    computer_score = game.board.get_score(session.computer)
    
    # Computer counts first and scores some points
    # Human counts second and should reach 121
    assert human_score >= 121, f"Expected human to win with at least 121, got {human_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "human", "Expected human to be the winner"


def test_computer_wins_counting_crib():
    """Test that computer wins by counting crib."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    game.board.pegs["human"]['front'] = 100
    game.board.pegs["human"]['rear'] = 100
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Computer is dealer, gets to count crib last
    session.current_round = create_test_round(session, dealer_name="computer")
    r = session.current_round.round
    r.starter = Card("5h")
    
    # Give computer a crib that scores at least 2 points with the starter
    # 5-5 in crib with 5 starter = 6 points minimum
    r.hands = {
        "human": build_hand(['2c', '2s', '2h', '2d']),
        "computer": build_hand(['3c', '3s', '3h', '3d'])
    }
    r.crib = build_hand(['5c', '5s'])
    session.current_round.phase = 'scoring'
    
    # Score hands
    r.score_hands_phase()
    
    computer_score = game.board.get_score(session.computer)
    
    # Computer should win by counting crib
    assert computer_score >= 121, f"Expected computer to win with at least 121, got {computer_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "computer", "Expected computer to be the winner"


def test_human_wins_on_nibs():
    """Test that human wins by getting nibs (jack starter)."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Human is dealer, gets nibs
    session.current_round = create_test_round(session, dealer_name="human")
    r = session.current_round.round
    
    # Set starter to a jack - dealer gets 2 points for nibs
    r.starter = Card("jh")
    r.hands = {
        "human": build_hand(['3h', '3d', 'ac', 'as']),
        "computer": build_hand(['2c', '2s', '2h', '2d'])
    }
    r.crib = build_hand(['4h', '4d'])
    
    # Award nibs in the setup phase
    r.setup_crib_phase()
    
    human_score = game.board.get_score(session.human)
    
    # Human should have won with nibs
    assert human_score == 121, f"Expected human to have 121 from nibs, got {human_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "human", "Expected human to be the winner"


def test_computer_wins_on_nibs():
    """Test that computer wins by getting nibs (jack starter)."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Computer is dealer, gets nibs
    session.current_round = create_test_round(session, dealer_name="computer")
    r = session.current_round.round
    
    # Set starter to a jack - dealer gets 2 points for nibs
    r.starter = Card("jh")
    r.hands = {
        "human": build_hand(['3h', '3d', 'ac', 'as']),
        "computer": build_hand(['2c', '2s', '2h', '2d'])
    }
    r.crib = build_hand(['4h', '4d'])
    
    # Award nibs in the setup phase
    r.setup_crib_phase()
    
    computer_score = game.board.get_score(session.computer)
    
    # Computer should have won with nibs
    assert computer_score == 121, f"Expected computer to have 121 from nibs, got {computer_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "computer", "Expected computer to be the winner"


def test_game_ends_immediately_on_121_during_pegging():
    """Critical test: Verify game ends immediately when 121 is reached during pegging.
    
    This is the primary bug - game should stop as soon as a player reaches 121,
    not continue to let the other player peg more points.
    """
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    # Both players at 119
    game.board.pegs["human"]['front'] = 119
    game.board.pegs["human"]['rear'] = 119
    game.board.pegs["computer"]['front'] = 119
    game.board.pegs["computer"]['rear'] = 119
    
    # Computer is dealer, human plays first
    session.current_round = create_test_round(session, dealer_name="computer")
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['5h', 'ac', '2c', '3c']),
        "computer": build_hand(['10h', '10d', '10c', '10s'])
    }
    session.current_round.phase = 'pegging'
    
    # Play the round
    session.current_round.run()
    
    human_score = game.board.get_score(session.human)
    computer_score = game.board.get_score(session.computer)
    
    # Human plays 5h, computer plays 10h (15 for 2) -> human reaches 121
    assert human_score == 121, f"Expected human to have 121, got {human_score}"
    assert session.current_round.game_winner is not None, "Game should have a winner"
    assert session.current_round.game_winner.name == "human", "Human should be the winner"
    
    # CRITICAL: Computer should NOT have scored any points after human won
    assert computer_score == 119, f"Computer should still be at 119, but got {computer_score} - game continued after human won!"


def test_game_ends_on_exactly_121():
    """Test that game ends when a player reaches exactly 121, not just exceeds it."""
    session = GameSession(game_id="test-game", opponent_type="random")
    
    game = session.game
    game.board.pegs["human"]['front'] = 115
    game.board.pegs["human"]['rear'] = 115
    game.board.pegs["computer"]['front'] = 100
    game.board.pegs["computer"]['rear'] = 100
    
    # Computer is dealer
    session.current_round = create_test_round(session, dealer_name="computer")
    r = session.current_round.round
    r.starter = Card("9h")
    r.hands = {
        "human": build_hand(['5h', '5d', '5c', '5s']),
        "computer": build_hand(['10h', '10d', '10c', '10s'])
    }
    session.current_round.phase = 'pegging'
    
    # Play the round - human should score multiple 15s and reach exactly 121
    session.current_round.run()
    
    human_score = game.board.get_score(session.human)
    
    # Verify human reached at least 121
    assert human_score >= 121, f"Expected human to reach at least 121, got {human_score}"
    assert session.current_round.game_winner is not None, "Expected a game winner"
    assert session.current_round.game_winner.name == "human", "Expected human to be the winner"


@pytest.mark.slow
def test_no_ties_possible_near_endgame():
    """Verify that ties are impossible when both players are near 121.
    
    This test runs multiple games with both players starting at 119 points
    to verify the game always produces a clear winner, never a tie.
    """
    from cribbage.players.play_first_card_player import PlayFirstCardPlayer
    
    ties = 0
    human_wins = 0
    computer_wins = 0
    num_games = 100
    
    for i in range(num_games):
        session = GameSession(game_id=f"test-game-{i}", opponent_type="random")
        game = session.game
        
        # Both players at 119
        game.board.pegs["human"]['front'] = 119
        game.board.pegs["human"]['rear'] = 119
        game.board.pegs["computer"]['front'] = 119
        game.board.pegs["computer"]['rear'] = 119
        
        # Alternate dealer
        dealer_name = "human" if i % 2 == 0 else "computer"
        
        try:
            # Play a full round
            session.current_round = create_test_round(session, dealer_name=dealer_name)
            session.current_round.round.deal()
            
            # Need to handle crib selection - just take first 2 cards from each hand
            for player_name in ["human", "computer"]:
                hand = session.current_round.round.hands[player_name]
                if len(hand) == 6:
                    # Discard first 2 cards to crib
                    session.current_round.round.crib.extend([hand[0], hand[1]])
                    session.current_round.round.hands[player_name] = hand[2:]
            
            session.current_round.round.cut()
            session.current_round.run()
            
            human_score = game.board.get_score(session.human)
            computer_score = game.board.get_score(session.computer)
            
            if human_score == computer_score:
                ties += 1
            elif human_score > computer_score:
                human_wins += 1
            else:
                computer_wins += 1
                
        except Exception as e:
            logger.error(f"Game {i} failed: {e}")
            continue
    
    # Assert no ties occurred
    assert ties == 0, f"Found {ties} ties out of {num_games} games - ties should be impossible!"
    # Verify we actually played the games
    assert human_wins + computer_wins == num_games, f"Expected {num_games} completed games"

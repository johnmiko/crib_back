"""Test that hand scores are shown correctly when game ends during scoring phase."""

from fastapi.testclient import TestClient
from app import app
from cribbage.playingcards import Card, build_hand
from unittest.mock import patch
import pytest
import logging

logger = logging.getLogger(__name__)


def test_hand_scores_shown_when_game_ends_during_scoring():
    """When game ends during scoring phase, round summary should show actual hand scores, not 0."""
    client = TestClient(app)
    
    # Setup hands: human has pair of 5s (2 points), computer will win by counting their hand
    human_hand = build_hand(['5h', '5s', '7c', '9h', 'qd', 'kc'])  # Keep 5,5,7,9
    computer_hand = build_hand(['4s', '6d', '9c', 'jh', 'kd', 'kh'])  # Keep j,4,9,6
    
    def mock_deal(self):
        self.hands = {
            self.game.players[0].name: list(human_hand),
            self.game.players[1].name: list(computer_hand),
        }
        self.player_hand_after_discard = {
            self.game.players[0].name: [],
            self.game.players[1].name: [],
        }
        self.starter = Card('2s')  # 2 of spades as starter
    
    with patch('cribbage.cribbageround.CribbageRound._deal', mock_deal):
        # Start game at high scores
        response = client.post("/game/new", json={
            "opponent_type": "medium",
            "dealer": "computer",
            "initial_scores": {"you": 115, "computer": 115}
        })
        game_id = response.json()["game_id"]
        
        # Discard to crib (human discards Q, K; computer discards K, K)
        response = client.post(f"/game/{game_id}/action", json={
            "card_indices": [4, 5]  # Discard Q, K
        })
        
        # Play out the pegging phase
        # After pegging, scores should be: human=115, computer=117 (or similar)
        while True:
            state = client.get(f"/game/{game_id}").json()
            if state['action_required'] != 'select_card_to_play':
                break
            
            # Play first valid card
            if state['valid_card_indices']:
                response = client.post(f"/game/{game_id}/action", json={
                    "card_indices": [state['valid_card_indices'][0]]
                })
            else:
                # Say go
                response = client.post(f"/game/{game_id}/action", json={
                    "card_indices": []
                })
        
        # Get round summary
        state = client.get(f"/game/{game_id}").json()
        assert state['action_required'] == 'round_complete'
        
        # Check that round summary shows actual hand scores, not all 0s
        summary = state['round_summary']
        
        # Human has 5, 5, 7, 9 with 2 starter → pair of 5s = 2 points
        assert summary['points']['you'] == 2, f"Expected human to score 2 points (pair of 5s), got {summary['points']['you']}"
        assert len(summary['breakdowns']['you']) > 0, "Expected non-empty breakdown for human hand"
        
        # Verify human scored 2 points (pair of 5s)
        assert summary['points']['you'] == 2, f"Expected human to score 2 points, got {summary['points']['you']}"
        
        # Verify computer also scored points (pair of Ks)
        assert summary['points']['computer'] == 2, f"Expected computer to score 2 points, got {summary['points']['computer']}"
        
        # Verify final scores reflect the hand scoring
        assert state['scores']['you'] == 117, "Human should have 117 after scoring hand"
        assert state['scores']['computer'] == 121, "Computer should have 121 and won"



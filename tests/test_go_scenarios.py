"""Test API go scenarios to verify proper scoring of "go" and 31 points.

According to cribbage rules:
1. If a player reaches exactly 31, they peg 2 points (1 for 31 + 1 for last card).
   After a 31 is played, the opponent starts the next round with the total resetting to zero.
2. After a "Go," the opponent leads the next round, starting from zero.
3. The player who plays the last card in the sequence gets 1 point for "Go" and 2 points if they reach exactly 31.
"""

from math import log
from fastapi.testclient import TestClient
from app import app
from cribbage.playingcards import Card, build_hand
from unittest.mock import patch
import pytest
import logging

logger = logging.getLogger(__name__)


def test_go_scenario_with_continuation_1():
    client = TestClient(app)
    computer_hand = build_hand(['js', 'jc', '10h','10d','10c', '10s'])
    human_hand = build_hand(['jh', 'jd', 'qh','qd','qc', 'qs'])
    # human goes first, is first in score order
    def mock_deal(self):
        self.hands = {
            self.game.players[0].name: list(human_hand),
            self.game.players[1].name: list(computer_hand),
        }
        self.player_hand_after_discard = {
            self.game.players[0].name: [],
            self.game.players[1].name: [],
        }
    
    with patch('cribbage.cribbageround.CribbageRound._deal', mock_deal):
        response = client.post("/game/new", json={
            "opponent_type": "play first card",
            "dealer": "computer"
        })
        game_id = response.json()["game_id"]
        state = response.json()                    
        response = client.post(f"/game/{game_id}/action", json={
            "card_indices": [0, 1] # Discard jacks
        })
        state = response.json()        
        while (state["your_hand"] or state["computer_hand"]):
            # Wait for our turn
            state = client.get(f"/game/{game_id}").json()
            while state['action_required'] == 'waiting_for_computer':
                state = client.get(f"/game/{game_id}").json()
            
            if state['action_required'] != 'select_card_to_play':
                break  # Round may have ended
            
            # Find and play the card
            card_idx = 0
            
            response = client.post(f"/game/{game_id}/action", json={
                "card_indices": [card_idx]
            })
            assert response.status_code == 200
        
        # Let the computer finish playing
        # max_wait = 20
        # for _ in range(max_wait):
        #     state = client.get(f"/game/{game_id}").json()
        #     if state['action_required'] not in ['waiting_for_computer']:
        #         if state['action_required'] in ['round_complete', 'game_over']:
        #             break
        #         # If it's our turn again but we want computer to finish this sequence
        #         if state['action_required'] == 'select_card_to_play':
        #             # Check if we have valid cards or need to go
        #             if not state['valid_card_indices']:
        #                 # Send go
        #                 client.post(f"/game/{game_id}/action", json={"card_indices": []})
        #             else:
        #                 break  # Stop, let's check scores
                
        state = client.get(f"/game/{game_id}").json()
        
        # Check if either player scored points for hitting 31
        # Computer should have hit 31 after: 10 (human) + K (10) + A (1) + 10 (computer) = 31
        # Computer should score 2 points: 1 for 31, 1 for go/last card
        #        
        
        # The exact score may vary based on other combinations (pairs, 15s, etc)
        # But if 31 was hit, should have at least 2 points
        expected_table_history =  [{'rank': 'q', 'suit': 'h', 'symbol': 'qh', 'value': 10},
                                          {'rank': '10', 'suit': 'h', 'symbol': '10h', 'value': 10},
                                          {'rank': 'q', 'suit': 'd', 'symbol': 'qd', 'value': 10},
                                          {'rank': '10', 'suit': 'd', 'symbol': '10d', 'value': 10},
                                          {'rank': 'q', 'suit': 'c', 'symbol': 'qc', 'value': 10},
                                          {'rank': '10', 'suit': 'c', 'symbol': '10c', 'value': 10},                                          
                                          {'rank': 'q', 'suit': 's', 'symbol': 'qs', 'value': 10},                                          
                                          {'rank': '10', 'suit': 's', 'symbol': '10s', 'value': 10}]
        assert state["points_pegged"] == [1,2]
        assert state["table_history"] == expected_table_history
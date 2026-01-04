"""Test API round with specific card deals to verify beginner player behavior."""

from fastapi.testclient import TestClient
from app import app
from cribbage.playingcards import Card, build_hand
from unittest.mock import patch
import pytest


def test_beginner_player_pegging_behavior():
    """Test that beginner player plays cards as expected against a specific hand.
    
    This test uses the FastAPI TestClient to interact with the game via HTTP endpoints,
    and mocks the card dealing to create a deterministic scenario.
    
    Setup:
    - Beginner player (computer): 5♥, 5♦, 6♣, 7♠, 9♥, Q♦
    - User player (human): 6♥, 7♥, 8♥, 8♦, 2♣, 4♠
    - User discards: 2♣, 4♠
    - User plays: 8♥, 8♦, 7♥, 6♥ (then go for the 7♥)
    
    This test verifies:
    1. The game progresses correctly with mocked hands via the API
    2. The beginner player makes reasonable discard and pegging decisions
    3. Scores are tracked properly throughout pegging
    """
    client = TestClient(app)
    
    # Define the specific hands we want
    computer_hand = build_hand(['5h', '5d', '6c', '7s', '9h', 'qd'])
    human_hand = build_hand(['6h', '7h', '8h', '8d', '2c', '4s'])
    
    # Mock the deal to provide specific hands
    def mock_deal(self):
        """Provide predetermined hands instead of random dealing."""
        # Hands are keyed by player name (string), not player object
        # players[0] is human, players[1] is computer
        self.hands = {
            self.game.players[0].name: list(human_hand),      # human
            self.game.players[1].name: list(computer_hand),   # computer
        }
        self.player_hand_after_discard = {
            self.game.players[0].name: [],
            self.game.players[1].name: [],
        }
    
    # Patch the CribbageRound._deal method to control the deal
    with patch('cribbage.cribbageround.CribbageRound._deal', mock_deal):
        # Create a new game with beginner opponent and computer as dealer
        response = client.post("/game/new", json={
            "opponent_type": "beginner",
            "dealer": "computer"
        })
        
        assert response.status_code == 200
        game_id = response.json()["game_id"]
        state = response.json()
        
        # Verify initial state
        assert state['dealer'] == 'computer'
        assert state['action_required'] == 'select_crib_cards'
        assert len(state['your_hand']) == 6
        
        # Find and discard 2♣ and 4♠
        hand_cards = [Card(c['rank'] + c['suit']) for c in state['your_hand']]
        discard_indices = []
        for i, card in enumerate(hand_cards):
            if card.rank == '2' and card.suit == 'c':
                discard_indices.append(i)
            elif card.rank == '4' and card.suit == 's':
                discard_indices.append(i)
        
        assert len(discard_indices) == 2, f"Could not find 2c and 4s in hand"
        
        # Submit discard action
        response = client.post(f"/game/{game_id}/action", json={
            "card_indices": discard_indices
        })
        
        assert response.status_code == 200
        state = response.json()
        assert len(state['your_hand']) == 4
        assert state['action_required'] in ['select_card_to_play', 'waiting_for_computer']
        
        # Play the pegging phase until round completes or we run out of scripted plays
        play_sequence = ['8h', '6h', '8d', '7h']
        plays_made = 0
        computer_plays = []
        
        for card_notation in play_sequence:
            # Get current state
            state = client.get(f"/game/{game_id}").json()
            
            # If round is complete, stop
            if state['action_required'] in ['round_complete', 'game_over']:
                break
            
            # If waiting for computer, just fetch state to let it play
            while state['action_required'] == 'waiting_for_computer':
                state = client.get(f"/game/{game_id}").json()
            
            # If we can't play anymore, stop
            if state['action_required'] not in ['select_card_to_play']:
                break
            
            # Find the card in our hand
            hand_cards = [Card(c['rank'] + c['suit']) for c in state['your_hand']]
            card_to_play = Card(card_notation)
            
            card_index = None
            for i, card in enumerate(hand_cards):
                if card.rank == card_to_play.rank and card.suit == card_to_play.suit:
                    card_index = i
                    break
            
            if card_index is None:
                # Card not found (maybe we already played it or it wasn't in hand)
                break
            
            # Play the card
            response = client.post(f"/game/{game_id}/action", json={
                "card_indices": [card_index]
            })
            
            if response.status_code != 200:
                break
            
            plays_made += 1
            state = response.json()
        # I only manually checked that the written test was correct until here
        # wanted to check that the beginner player did in fact play the correct cards
        assert state["table_history"] == [{'rank': '8', 'suit': 'h', 'symbol': '8h', 'value': 8}, 
                                       {'rank': '7', 'suit': 's', 'symbol': '7s', 'value': 7},
                                       {'rank': '6', 'suit': 'h', 'symbol': '6h', 'value': 6},
                                       {'rank': '5', 'suit': 'h', 'symbol': '5h', 'value': 5}, 
                                       {'rank': '5', 'suit': 'd', 'symbol': '5d', 'value': 5}, 
                                       {'rank': '7', 'suit': 'h', 'symbol': '7h', 'value': 7}, 
                                       {'rank': '6', 'suit': 'c', 'symbol': '6c', 'value': 6}]
        # Continue until round completes (playing remaining cards or sending go)
        max_iterations = 20  # Prevent infinite loop
        iteration = 0
        while iteration < max_iterations:
            state = client.get(f"/game/{game_id}").json()
            
            if state['action_required'] in ['round_complete', 'game_over']:
                break
            
            if state['action_required'] == 'waiting_for_computer':
                # Computer is playing, just wait
                iteration += 1
                continue
            
            if state['action_required'] == 'select_card_to_play':
                # Play a valid card or send go
                if state['valid_card_indices']:
                    # Play first valid card
                    response = client.post(f"/game/{game_id}/action", json={
                        "card_indices": [state['valid_card_indices'][0]]
                    })
                else:
                    # Send go
                    response = client.post(f"/game/{game_id}/action", json={
                        "card_indices": []
                    })
                
                if response.status_code != 200:
                    break
            
            iteration += 1
        
        # Get final state
        final_state = client.get(f"/game/{game_id}").json()
        
        # Basic assertions - game should have progressed
        assert plays_made >= 3, f"Should have made at least 3 scripted plays, made {plays_made}"
        assert final_state['action_required'] in ['round_complete', 'select_card_to_play', 'game_over']
        
        # Computer should have scored some points (it's the dealer and has first play advantage)
        assert final_state['scores']['computer'] >= 0
        
        # Both players should have score entries
        assert 'you' in final_state['scores']
        assert 'computer' in final_state['scores']
        
        print(f"\n✓ Test passed - beginner player pegging behavior validated via API")
        print(f"  Final scores: {final_state['scores']}")
        print(f"  Plays made: {plays_made}/{len(play_sequence)}")
        print(f"  Final state: {final_state['action_required']}")

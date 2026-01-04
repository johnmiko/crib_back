from fastapi.testclient import TestClient
from app import app
from cribbage.playingcards import build_hand
from unittest.mock import patch
import json

client = TestClient(app)

computer_hand = build_hand(['js', 'jc', '10h','10d','10c', '10s'])
human_hand = build_hand(['jh', 'jd', 'qh','qd','qc', 'qs'])

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
    response = client.post('/game/new', json={'opponent_type': 'beginner', 'dealer': 'computer'})
    game_id = response.json()['game_id']
    
    # Discard jacks
    response = client.post(f'/game/{game_id}/action', json={'card_indices': [0, 1]})
    state = response.json()
    
    # Play all 4 queens
    for i in range(4):
        state = client.get(f'/game/{game_id}').json()
        while state['action_required'] == 'waiting_for_computer':
            state = client.get(f'/game/{game_id}').json()
        
        if state['action_required'] != 'select_card_to_play':
            break
        
        response = client.post(f'/game/{game_id}/action', json={'card_indices': [0]})
    
    # Wait for round to complete
    max_wait = 20
    for _ in range(max_wait):
        state = client.get(f'/game/{game_id}').json()
        if state['action_required'] not in ['waiting_for_computer']:
            if state['action_required'] in ['round_complete', 'game_over']:
                break
            if state['action_required'] == 'select_card_to_play':
                if not state['valid_card_indices']:
                    client.post(f'/game/{game_id}/action', json={"card_indices": []})
                else:
                    break
    
    state = client.get(f'/game/{game_id}').json()
    print('Actual table_history:')
    print(json.dumps(state['table_history'], indent=2))

"""Simple test script for the Cribbage API."""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_api():
    print("Testing Cribbage API...\n")
    
    # 1. Create a new game
    print("1. Creating new game...")
    response = requests.post(f"{BASE_URL}/game/new")
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    game_state = response.json()
    game_id = game_state["game_id"]
    print(f"   Game ID: {game_id}")
    print(f"   Action required: {game_state['action_required']}")
    print(f"   Message: {game_state['message']}")
    print(f"   Your hand: {[c['symbol'] for c in game_state['your_hand']]}")
    print(f"   Dealer: {game_state['dealer']}")
    print(f"   Scores: {game_state['scores']}\n")
    
    # 2. Submit crib cards (select first 2 cards)
    if game_state['action_required'] == 'select_crib_cards':
        print("2. Submitting crib cards (indices 0 and 1)...")
        response = requests.post(
            f"{BASE_URL}/game/{game_id}/action",
            json={"card_indices": [0, 1]}
        )
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(response.text)
            return
        
        game_state = response.json()
        print(f"   Action required: {game_state['action_required']}")
        print(f"   Message: {game_state['message']}")
        print(f"   Your hand: {[c['symbol'] for c in game_state['your_hand']]}")
        print(f"   Starter card: {game_state['starter_card']['symbol'] if game_state['starter_card'] else 'None'}")
        print(f"   Table value: {game_state['table_value']}")
        print(f"   Scores: {game_state['scores']}\n")
    
    # 3. Play a card if it's our turn
    if game_state['action_required'] == 'select_card_to_play':
        valid_indices = game_state['valid_card_indices']
        print(f"3. Playing a card...")
        print(f"   Valid card indices: {valid_indices}")
        
        if valid_indices:
            card_to_play = valid_indices[0]
            print(f"   Playing card at index {card_to_play}")
            response = requests.post(
                f"{BASE_URL}/game/{game_id}/action",
                json={"card_indices": [card_to_play]}
            )
            
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                print(response.text)
                return
            
            game_state = response.json()
            print(f"   Message: {game_state['message']}")
            print(f"   Table cards: {[c['symbol'] for c in game_state['table_cards']]}")
            print(f"   Table value: {game_state['table_value']}")
            print(f"   Your hand: {[c['symbol'] for c in game_state['your_hand']]}")
            print(f"   Scores: {game_state['scores']}\n")
    
    # 4. Get final state
    print("4. Getting game state...")
    response = requests.get(f"{BASE_URL}/game/{game_id}")
    game_state = response.json()
    print(f"   Action required: {game_state['action_required']}")
    print(f"   Message: {game_state['message']}")
    print(f"   Scores: {game_state['scores']}")
    print(f"   Game over: {game_state['game_over']}\n")
    
    print("✓ Test completed successfully!")

if __name__ == "__main__":
    try:
        test_api()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API.")
        print("Make sure the server is running with: python app.py")
    except Exception as e:
        print(f"Error: {e}")

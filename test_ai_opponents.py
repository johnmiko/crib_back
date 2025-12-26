"""Test script to verify AI opponents are working."""
import requests
import json

BASE_URL = "http://localhost:8001"

print("Testing AI Opponents Integration")
print("=" * 50)

# Test 1: Get available opponents
print("\n1. Getting available opponents...")
try:
    response = requests.get(f"{BASE_URL}/opponents")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Found {len(data['opponents'])} opponents:")
        for opp in data['opponents']:
            print(f"  - {opp['name']} (id: {opp['id']})")
    else:
        print(f"✗ Error: {response.status_code}")
except Exception as e:
    print(f"✗ Exception: {e}")

# Test 2: Create games with each AI opponent
print("\n2. Creating games with AI opponents...")
ai_opponents = ['linearb', 'deeppeg', 'myrmidon', 'bestai']

# Test 3: Directly test bestai model loads and API
print("\n3. Testing bestai model loads and fits API...")
try:
    from cribbage.bestai_opponent import BestAIOpponent
    from cribbage.playingcards import Card
    # Build a dummy hand of 6 cards
    hand = [Card({'name': 'five', 'symbol': '5', 'value': 5, 'rank': 5, 'unicode_flag': '5'}, {'name': 'spades', 'symbol': '♠', 'unicode_flag': 'A'}) for _ in range(6)]
    opp = BestAIOpponent()
    crib_cards = opp.select_crib_cards(hand)
    assert isinstance(crib_cards, list) and len(crib_cards) == 2, "select_crib_cards should return 2 cards"
    # Test play_pegging API
    table = hand[:2]
    table_value = 10
    card = opp.select_card_to_play(hand, table, table_value)
    assert (card is None or hasattr(card, 'get_value')), "select_card_to_play should return a Card or None"
    print("    ✓ bestai model loads and API works")
except Exception as e:
    print(f"    ✗ Exception: {e}")

for opponent_id in ai_opponents:
    print(f"\n  Testing {opponent_id}...")
    try:
        response = requests.post(
            f"{BASE_URL}/game/new",
            json={"opponent_type": opponent_id}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"    ✓ Game created successfully (id: {data['game_id'][:8]}...)")
            print(f"    ✓ Message: {data['message']}")
            # Clean up
            requests.delete(f"{BASE_URL}/game/{data['game_id']}")
        else:
            print(f"    ✗ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"    ✗ Exception: {e}")

print("\n" + "=" * 50)
print("Testing complete!")

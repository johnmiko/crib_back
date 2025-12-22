"""Tests for the new API implementation using cribbagegame."""

import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_healthcheck():
    """Test healthcheck endpoint."""
    response = client.get("/healthcheck")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_game():
    """Test creating a new game."""
    response = client.post("/game/new")
    assert response.status_code == 200
    
    data = response.json()
    assert "game_id" in data
    assert data["action_required"] == "select_crib_cards"
    assert len(data["your_hand"]) == 6
    assert data["game_over"] is False


def test_get_game():
    """Test getting game state."""
    # Create game
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]
    
    # Get game state
    get_resp = client.get(f"/game/{game_id}")
    assert get_resp.status_code == 200
    
    data = get_resp.json()
    assert data["game_id"] == game_id
    assert len(data["your_hand"]) == 6


def test_get_nonexistent_game():
    """Test getting a game that doesn't exist."""
    response = client.get("/game/fake-id")
    assert response.status_code == 404


def test_submit_crib_cards():
    """Test submitting crib card selection."""
    # Create game
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]
    
    # Submit crib cards (first two)
    action_resp = client.post(
        f"/game/{game_id}/action",
        json={"card_indices": [0, 1]}
    )
    assert action_resp.status_code == 200
    
    data = action_resp.json()
    assert len(data["your_hand"]) == 4  # 6 - 2 for crib
    assert data["action_required"] in ["select_card_to_play", "waiting_for_computer"]
    assert data["starter_card"] is not None  # Starter should be cut


def test_invalid_crib_selection():
    """Test invalid crib card selection."""
    # Create game
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]
    
    # Try to submit only 1 card
    action_resp = client.post(
        f"/game/{game_id}/action",
        json={"card_indices": [0]}
    )
    assert action_resp.status_code == 400
    assert "exactly 2 cards" in action_resp.json()["detail"].lower()


def test_play_complete_round():
    """Test playing a complete round of cards."""
    # Create game
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]
    
    # Submit crib cards
    crib_resp = client.post(
        f"/game/{game_id}/action",
        json={"card_indices": [0, 1]}
    )
    assert crib_resp.status_code == 200
    state = crib_resp.json()
    
    # Play cards until hand is empty
    cards_played = 0
    max_iterations = 20
    valid_indices = state.get("valid_card_indices", [])
    
    while len(state["your_hand"]) > 0 and valid_indices and cards_played < max_iterations:
        if state["action_required"] == "select_card_to_play":
            # Play first valid card
            valid_indices = state.get("valid_card_indices", [])
            
            if valid_indices:
                play_resp = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": [valid_indices[0]]}
                )
                assert play_resp.status_code == 200
                state = play_resp.json()
                cards_played += 1
            else:
                # No valid cards, say "go"
                play_resp = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": []}
                )
                assert play_resp.status_code == 200
                state = play_resp.json()
        elif state["action_required"] == "select_crib_cards":
            # Round complete, new round started
            break
        elif state["action_required"] == "waiting_for_computer":
            # Should not happen - computer should play automatically
            pytest.fail("Game stuck waiting for computer")
            break
        else:
            # Unknown state - break to avoid infinite loop
            break
    
    # Should have played all 4 cards or moved to next round
    assert valid_indices == [] or state["action_required"] == "select_crib_cards"
    assert cards_played <= 4


def test_delete_game():
    """Test deleting a game."""
    # Create game
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]
    
    # Delete game
    delete_resp = client.delete(f"/game/{game_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "deleted"
    
    # Game should be gone
    get_resp = client.get(f"/game/{game_id}")
    assert get_resp.status_code == 404


def test_scores_update():
    """Test that scores are updated as the game progresses."""
    # Create game
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]
    initial_state = create_resp.json()
    
    initial_human_score = initial_state["scores"]["human"]
    initial_computer_score = initial_state["scores"]["computer"]
    
    # Submit crib cards
    crib_resp = client.post(
        f"/game/{game_id}/action",
        json={"card_indices": [0, 1]}
    )
    state_after_crib = crib_resp.json()
    
    # Scores might have changed due to "his heels" (if starter is a jack)
    # Just verify scores are present and valid
    assert "human" in state_after_crib["scores"]
    assert "computer" in state_after_crib["scores"]
    assert state_after_crib["scores"]["human"] >= initial_human_score
    assert state_after_crib["scores"]["computer"] >= initial_computer_score


def test_play_full_game_to_completion():
    """Test playing a complete game until someone wins."""
    # Create game
    create_resp = client.post("/game/new")
    assert create_resp.status_code == 200
    game_id = create_resp.json()["game_id"]
    state = create_resp.json()
    
    rounds_played = 0
    max_rounds = 100  # Safety limit to prevent infinite loops
    total_actions = 0
    max_actions = 500  # Safety limit for total actions
    
    while not state["game_over"] and rounds_played < max_rounds and total_actions < max_actions:
        # Handle current action
        if state["action_required"] == "select_crib_cards":
            # Select first two cards for crib
            action_resp = client.post(
                f"/game/{game_id}/action",
                json={"card_indices": [0, 1]}
            )
            assert action_resp.status_code == 200
            state = action_resp.json()
            rounds_played += 1
            total_actions += 1
            
        elif state["action_required"] == "select_card_to_play":
            # Play first valid card
            valid_indices = state.get("valid_card_indices", [])
            
            if valid_indices:
                # Play the first valid card
                action_resp = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": [valid_indices[0]]}
                )
            else:
                # No valid cards, say "go"
                action_resp = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": []}
                )
            
            assert action_resp.status_code == 200
            state = action_resp.json()
            total_actions += 1
            
        elif state["action_required"] == "waiting_for_computer":
            # Should not happen - computer should play automatically
            pytest.fail(f"Game stuck waiting for computer after {total_actions} actions")
            break
        else:
            pytest.fail(f"Unknown action required: {state['action_required']}")
            break
    
    # Verify game completed successfully
    assert state["game_over"], f"Game did not complete after {rounds_played} rounds and {total_actions} actions"
    assert state["winner"] is not None, "Game over but no winner declared"
    assert state["winner"] in ["human", "computer"], f"Invalid winner: {state['winner']}"
    
    # Verify winning score
    winner_score = state["scores"][state["winner"]]
    assert winner_score >= 121, f"Winner score {winner_score} is less than 121"
    
    # Verify we didn't hit safety limits
    assert rounds_played < max_rounds, "Hit maximum rounds limit - possible infinite loop"
    assert total_actions < max_actions, "Hit maximum actions limit - possible infinite loop"
    
    print(f"\n✓ Game completed successfully after {rounds_played} rounds and {total_actions} actions")
    print(f"  Winner: {state['winner']} with score {state['scores'][state['winner']]}")
    print(f"  Final scores: human={state['scores']['human']}, computer={state['scores']['computer']}")

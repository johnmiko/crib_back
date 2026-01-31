"""Test that game shows round summary before ending when 121 is reached during hand counting."""
import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_game_shows_round_summary_before_ending():
    """Test that when game ends during hand counting, user sees round summary first."""
    
    # Create game with both players at 119
    response = client.post(
        "/game/new",
        json={
            "initial_scores": {"human": 119, "computer": 116},
            "dealer": "computer"
        }
    )
    assert response.status_code == 200
    state = response.json()
    game_id = state["game_id"]
    
    # Select crib cards
    response = client.post(
        f"/game/{game_id}/action",
        json={"card_indices": [0, 1]}
    )
    assert response.status_code == 200
    
    # Play through pegging phase until it's complete
    max_plays = 20
    plays = 0
    while plays < max_plays:
        state = response.json()
        if state["action_required"] == "round_complete":
            break
        if state["action_required"] == "select_card_to_play":
            # Play first valid card or say go
            valid = state.get("valid_card_indices", [])
            if valid:
                response = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": [valid[0]]}
                )
            else:
                response = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": []}
                )
            assert response.status_code == 200
            plays += 1
        else:
            break
    
    # At this point, we should be at ROUND_COMPLETE (not game_over)
    # Even though someone likely reached 121 during hand counting
    state = response.json()
    assert state["action_required"] == "round_complete", f"Expected round_complete, got {state['action_required']}"
    assert state["game_over"] == False, "Game should not be over yet - waiting for user to see round summary"
    assert state["round_summary"] is not None, "Round summary should be present"
    
    # Verify one player is at or above 121
    scores = state["scores"]
    assert scores["you"] >= 121 or scores["computer"] >= 121, "Someone should have reached 121"
    
    # Now click Continue - this should transition to game over
    response = client.post(
        f"/game/{game_id}/action",
        json={"card_indices": []}  # Empty array for continue action
    )
    assert response.status_code == 200
    
    # NOW the game should be over
    final_state = response.json()
    assert final_state["game_over"] == True, "Game should be over after clicking continue"
    assert final_state["winner"] in ["you", "computer"], "There should be a winner"
    assert final_state["win_reason"] is not None, "Win reason should be present"
    
    print(f"✓ Game correctly showed round summary before ending")
    print(f"  Winner: {final_state['winner']}")
    print(f"  Win reason: {final_state['win_reason']}")
    print(f"  Final scores: you={final_state['scores']['you']}, computer={final_state['scores']['computer']}")

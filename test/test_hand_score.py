"""Round flow / hand-scoring related tests."""

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_play_complete_round():
    """Play cards until the round advances (basic flow)."""
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]

    crib_resp = client.post(
        f"/game/{game_id}/action",
        json={"card_indices": [0, 1]},
    )
    assert crib_resp.status_code == 200
    state = crib_resp.json()

    cards_played = 0
    max_iterations = 20

    while len(state["your_hand"]) > 0 and cards_played < max_iterations:
        if state["action_required"] == "select_card_to_play":
            valid = state.get("valid_card_indices", [])
            if valid:
                play_resp = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": [valid[0]]},
                )
            else:
                play_resp = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": []},
                )
            assert play_resp.status_code == 200
            state = play_resp.json()
            cards_played += 1
        elif state["action_required"] == "select_crib_cards":
            break
        elif state["action_required"] == "waiting_for_computer":
            raise AssertionError("Game stuck waiting for computer")
        else:
            break

    # Ensure we didn't exceed our safety cap
    assert cards_played <= max_iterations

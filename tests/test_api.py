"""API endpoint tests for Crib backend."""

import logging
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_healthcheck():
    response = client.get("/healthcheck")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_game():
    response = client.post("/game/new")
    assert response.status_code == 200

    data = response.json()
    assert "game_id" in data
    assert data["action_required"] == "select_crib_cards"
    assert len(data["your_hand"]) == 6
    assert data["game_over"] is False


def test_get_game():
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]

    get_resp = client.get(f"/game/{game_id}")
    assert get_resp.status_code == 200

    data = get_resp.json()
    assert data["game_id"] == game_id
    assert len(data["your_hand"]) == 6


def test_get_nonexistent_game():
    response = client.get("/game/fake-id")
    assert response.status_code == 404


# def test_submit_crib_cards():
#     create_resp = client.post("/game/new")
#     game_id = create_resp.json()["game_id"]

#     action_resp = client.post(
#         f"/game/{game_id}/action",
#         json={"card_indices": [0, 1]},
#     )
#     assert action_resp.status_code == 200

#     data = action_resp.json()
#     assert len(data["your_hand"]) == 4  # 6 - 2 for crib
#     assert data["action_required"] in ["select_card_to_play", "waiting_for_computer"]
#     assert data["starter_card"] is not None


def test_invalid_crib_selection():
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]

    action_resp = client.post(
        f"/game/{game_id}/action",
        json={"card_indices": [0]},
    )
    assert action_resp.status_code == 400
    assert "exactly 2 cards" in action_resp.json()["detail"].lower()


def test_delete_game():
    create_resp = client.post("/game/new")
    game_id = create_resp.json()["game_id"]

    delete_resp = client.delete(f"/game/{game_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "deleted"

    get_resp = client.get(f"/game/{game_id}")
    assert get_resp.status_code == 404


# def test_scores_update():
#     create_resp = client.post("/game/new")
#     game_id = create_resp.json()["game_id"]
#     initial_state = create_resp.json()

#     initial_you = initial_state["scores"]["you"]
#     initial_comp = initial_state["scores"]["computer"]

#     crib_resp = client.post(
#         f"/game/{game_id}/action",
#         json={"card_indices": [0, 1]},
#     )
#     state = crib_resp.json()

#     assert "you" in state["scores"] and "computer" in state["scores"]
#     assert state["scores"]["you"] >= initial_you
#     assert state["scores"]["computer"] >= initial_comp


def test_play_full_game_to_completion():
    create_resp = client.post("/game/new")
    assert create_resp.status_code == 200
    game_id = create_resp.json()["game_id"]
    state = create_resp.json()

    rounds_played = 0
    max_rounds = 100
    total_actions = 0
    max_actions = 500

    while not state["game_over"] and rounds_played < max_rounds and total_actions < max_actions:
        if state["action_required"] == "select_crib_cards":
            action_resp = client.post(
                f"/game/{game_id}/action",
                json={"card_indices": [0, 1]},
            )
            assert action_resp.status_code == 200
            state = action_resp.json()
            rounds_played += 1
            total_actions += 1
        elif state["action_required"] == "select_card_to_play":
            valid = state.get("valid_card_indices", [])
            if valid:
                action_resp = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": [valid[0]]},
                )
            else:
                action_resp = client.post(
                    f"/game/{game_id}/action",
                    json={"card_indices": []},
                )
            assert action_resp.status_code == 200
            state = action_resp.json()
            total_actions += 1
        elif state["action_required"] == "round_complete":
            action_resp = client.post(
                f"/game/{game_id}/action",
                json={"card_indices": []},
            )
            assert action_resp.status_code == 200
            state = action_resp.json()
            rounds_played += 1
            total_actions += 1
        elif state["action_required"] == "waiting_for_computer":
            raise AssertionError(f"Game stuck waiting for computer after {total_actions} actions")
        else:
            raise AssertionError(f"Unknown action required: {state['action_required']}")

    assert state["game_over"], f"Game did not complete after {rounds_played} rounds and {total_actions} actions"
    assert state["winner"] in ["you", "computer"]
    winner_score = state["scores"][state["winner"]]
    assert winner_score >= 121

    logging.info("Game completed after %s rounds and %s actions", rounds_played, total_actions)
    logging.info("Winner: %s (%s)", state["winner"], state["scores"][state["winner"]])
    logging.info("Final scores: you=%s, computer=%s", state["scores"]["you"], state["scores"]["computer"]) 

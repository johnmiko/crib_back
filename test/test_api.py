# """API endpoint tests for app.py using pytest and TestClient."""

# import logging
# import uuid

# import pytest
# from fastapi.testclient import TestClient

# from app import app, games

# logger = logging.getLogger(__name__)


# client = TestClient(app)


# @pytest.fixture(autouse=True)
# def clear_games():
# 	"""Reset in-memory games before and after each test to keep tests isolated."""
# 	games.clear()
# 	yield
# 	games.clear()


# def test_root_healthcheck():
# 	response = client.get("/")
# 	assert response.status_code == 200
# 	data = response.json()
# 	assert data["status"] == "ok"
# 	assert data["active_games"] == 0


# def test_create_and_get_game_state():
# 	create = client.post("/game/new")
# 	assert create.status_code == 200
# 	created = create.json()
# 	game_id = created["game_id"]

# 	# Ensure game is tracked
# 	assert game_id in games

# 	# Fetch the same game
# 	fetched = client.get(f"/game/{game_id}")
# 	assert fetched.status_code == 200
# 	state = fetched.json()

# 	# Basic shape checks
# 	assert state["game_id"] == game_id
# 	assert len(state["your_hand"]) == 6
# 	assert state["action_required"] == "select_crib_cards"


# def test_get_game_state_not_found():
# 	missing_id = str(uuid.uuid4())
# 	response = client.get(f"/game/{missing_id}")
# 	assert response.status_code == 404


# def test_submit_crib_cards_and_progress_flow():
# 	# Create game
# 	created = client.post("/game/new").json()
# 	game_id = created["game_id"]

# 	# Submit two crib cards (first two indices)
# 	action_payload = {"card_indices": [0, 1]}
# 	action_resp = client.post(f"/game/{game_id}/action", json=action_payload)
# 	assert action_resp.status_code == 200
# 	new_state = action_resp.json()

# 	# After crib submission, hand should have 4 cards left
# 	assert len(new_state["your_hand"]) == 4
# 	# Action should advance away from crib selection
# 	assert new_state["action_required"] in {"select_card_to_play", "waiting_for_computer"}


# def test_submit_action_invalid_payload_returns_400():
# 	created = client.post("/game/new").json()
# 	game_id = created["game_id"]

# 	# Only one index for crib -> invalid
# 	bad_payload = {"card_indices": [0]}
# 	response = client.post(f"/game/{game_id}/action", json=bad_payload)
# 	assert response.status_code == 400
# 	assert "select exactly 2 cards" in response.json()["detail"].lower()


# def test_delete_game():
# 	created = client.post("/game/new").json()
# 	game_id = created["game_id"]

# 	deleted = client.delete(f"/game/{game_id}")
# 	assert deleted.status_code == 200
# 	assert deleted.json()["status"] == "deleted"

# 	# Now it should be gone
# 	missing = client.get(f"/game/{game_id}")
# 	assert missing.status_code == 404

# def test_create_game_and_play_until_2nd_hand():
# 	# Create game
# 	create_resp = client.post("/game/new")
# 	assert create_resp.status_code == 200
# 	game_state = create_resp.json()
# 	game_id = game_state["game_id"]

# 	# Submit crib cards
# 	crib_action = {"card_indices": [0, 1]}
# 	crib_resp = client.post(f"/game/{game_id}/action", json=crib_action)
# 	assert crib_resp.status_code == 200
# 	state_after_crib = crib_resp.json()

# 	# Play cards until no more cards in hand (hand complete)
# 	max_iterations = 20  # Safety limit
# 	iterations = 0
# 	while len(state_after_crib["your_hand"]) > 0 and iterations < max_iterations:
# 		print(f"iteration: {iterations}, action_required: {state_after_crib['action_required']}, cards_left: {len(state_after_crib['your_hand'])}, valid_indices: {state_after_crib.get('valid_card_indices', [])}")
# 		if state_after_crib["action_required"] == "select_card_to_play":
# 			# Play first valid card
# 			valid_indices = state_after_crib.get("valid_card_indices", [0])
# 			play_action = {"card_indices": [valid_indices[0]]}
# 			play_resp = client.post(f"/game/{game_id}/action", json=play_action)
# 			assert play_resp.status_code == 200
# 			state_after_crib = play_resp.json()
# 		elif state_after_crib["action_required"] == "waiting_for_computer":
# 			# Game should have already advanced computer turns
# 			# If we're still waiting, something went wrong
# 			print("Stuck waiting for computer - breaking")
# 			break
# 		iterations += 1

# 	# Should have played all cards
# 	assert len(state_after_crib["your_hand"]) == 0, f"Expected hand to be empty, but {len(state_after_crib['your_hand'])} cards remain"
# 	assert iterations < max_iterations, "Hit maximum iterations - possible infinite loop"
# # 	assert state_after_crib["action_required"] == "select_crib_cards"
# # 	assert len(state_after_crib["your_hand"]) == 6
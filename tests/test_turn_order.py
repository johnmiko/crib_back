"""Turn order and flow tests."""

import logging
from fastapi.testclient import TestClient
import pytest
from app import app

client = TestClient(app)


# def test_turn_order_is_respected():
#     """After the player move, computer plays once, then player's turn again."""
#     create_resp = client.post("/game/new")
#     assert create_resp.status_code == 200
#     game_id = create_resp.json()["game_id"]

#     crib_resp = client.post(
#         f"/game/{game_id}/action",
#         json={"card_indices": [0, 1]},
#     )
#     assert crib_resp.status_code == 200
#     state = crib_resp.json()

#     logging.debug("After crib: action_required=%s table_len=%s your_len=%s",
#                   state.get("action_required"),
#                   len(state.get("table_cards", [])),
#                   len(state.get("your_hand", [])))

#     assert state["action_required"] == "select_card_to_play"

#     table_len_before = len(state.get("table_cards", []))
#     valid_indices = state.get("valid_card_indices", [])
#     assert valid_indices, "Expected at least one valid card to play"

#     play_resp = client.post(
#         f"/game/{game_id}/action",
#         json={"card_indices": [valid_indices[0]]},
#     )
#     assert play_resp.status_code == 200
#     state_after_play = play_resp.json()

#     table_len_after = len(state_after_play.get("table_cards", []))
#     delta = table_len_after - table_len_before
#     logging.debug("After play: action_required=%s before=%s after=%s delta=%s",
#                   state_after_play.get("action_required"),
#                   table_len_before, table_len_after, delta)

#     assert delta == 2, f"Expected table to grow by ==2 (player+computer), got {delta}"
#     assert state_after_play["action_required"] == "select_card_to_play"

"""Regression tests for recent pegging event text when 31 is reached."""

from fastapi.testclient import TestClient
from unittest.mock import patch

from app import app
from cribbage.playingcards import build_hand


def _find_card_index(hand, rank: str, suit: str) -> int:
    for i, card in enumerate(hand):
        if card["rank"] == rank and card["suit"] == suit:
            return i
    raise AssertionError(f"Card {rank}{suit} not found in hand: {hand}")


def test_recent_events_show_31_for_2_without_go_for_1():
    client = TestClient(app)
    human_hand = build_hand(["jh", "jd", "qh", "qd", "2c", "3c"])
    computer_hand = build_hand(["9s", "9d", "10h", "as", "4c", "5c"])

    def mock_deal(self):
        self.hands = {
            self.game.players[0].name: list(human_hand),
            self.game.players[1].name: list(computer_hand),
        }
        self.player_hand_after_discard = {
            self.game.players[0].name: [],
            self.game.players[1].name: [],
        }

    with patch("cribbage.cribbageround.CribbageRound._deal", mock_deal):
        state = client.post(
            "/game/new",
            json={"opponent_type": "play first card", "dealer": "computer"},
        ).json()
        game_id = state["game_id"]

        state = client.post(
            f"/game/{game_id}/action",
            json={"card_indices": [0, 1]},  # discard jacks
        ).json()

        qh_idx = _find_card_index(state["your_hand"], "q", "h")
        state = client.post(
            f"/game/{game_id}/action",
            json={"card_indices": [qh_idx]},
        ).json()

        qd_idx = _find_card_index(state["your_hand"], "q", "d")
        state = client.post(
            f"/game/{game_id}/action",
            json={"card_indices": [qd_idx]},
        ).json()

        recent = state.get("recent_play_events") or []
        assert any("31 for 2" in event for event in recent), recent
        assert all("Go for 1" not in event for event in recent), recent
        assert all("31 for 1" not in event for event in recent), recent


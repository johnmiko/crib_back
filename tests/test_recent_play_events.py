from types import SimpleNamespace

from app import ActionType, GameSession
from cribbage.cribbageround import PlayRecord
from cribbage.playingcards import Card


def test_recent_play_events_populated_from_round_play_record():
    session = GameSession(game_id="test-recent-events", opponent_type="random")
    session.waiting_for = ActionType.SELECT_CARD_TO_PLAY
    session.message = "Select a card: "

    play_record = [
        PlayRecord(
            description="human: 15 for 2",
            full_table=[],
            active_table=[],
            table_count=15,
            player_name="human",
            card=Card("5h"),
            hand=[],
        ),
        PlayRecord(
            description="computer: Pair for 2",
            full_table=[],
            active_table=[],
            table_count=20,
            player_name="computer",
            card=Card("5d"),
            hand=[],
        ),
    ]

    session.current_round = SimpleNamespace(
        round=SimpleNamespace(play_record=play_record),
        hands={session.human.name: [], session.computer.name: []},
        table=[],
        starter=None,
        dealer=session.human,
        history=SimpleNamespace(score_after_pegging=[]),
    )

    state = session.get_state()
    assert state.recent_play_events is not None
    assert len(state.recent_play_events) == 2
    assert state.recent_play_events[0] == "Computer scored Pair for 2"
    assert state.recent_play_events[1] == "You scored 15 for 2"

"""Quick test to verify scoring messages are working."""
from app import _format_play_event

def test_scoring_messages():
    """Test that scoring messages are formatted correctly."""
    # Test format function
    assert _format_play_event('human: 15 for 2') == 'You scored 15 for 2'
    assert _format_play_event('computer: Pair for 2') == 'Computer scored Pair for 2'
    assert _format_play_event('human: Go') == 'You said go'
    assert _format_play_event('computer: Plays 5h') == 'Computer played 5h'
    assert _format_play_event('human: Run of 3 for 3') == 'You scored Run of 3 for 3'
    assert _format_play_event('computer: Three of a kind for 6') == 'Computer scored Three of a kind for 6'
    assert _format_play_event('human: 31 for 1') == 'You scored 31 for 1'
    print("✓ All scoring message format tests passed!")

if __name__ == "__main__":
    test_scoring_messages()
    print("\n✅ All tests passed! Scoring messages are working correctly.")


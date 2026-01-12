"""Test initial_scores parameter for testing end game scenarios."""

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_create_game_with_initial_scores():
    """Test that initial_scores parameter sets starting scores correctly."""
    response = client.post(
        "/game/new",
        json={
            "opponent_type": "random",
            "initial_scores": {"human": 115, "computer": 115}
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that scores were set to 115
    assert data["scores"]["you"] == 115
    assert data["scores"]["computer"] == 115
    
    # Game should not be over yet
    assert data["game_over"] is False
    assert data["winner"] is None


def test_create_game_with_asymmetric_initial_scores():
    """Test that initial_scores can be set differently for each player."""
    response = client.post(
        "/game/new",
        json={
            "opponent_type": "random",
            "initial_scores": {"human": 110, "computer": 118}
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["scores"]["you"] == 110
    assert data["scores"]["computer"] == 118


def test_create_game_without_initial_scores():
    """Test that game starts at 0-0 when initial_scores not provided."""
    response = client.post(
        "/game/new",
        json={"opponent_type": "random"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["scores"]["you"] == 0
    assert data["scores"]["computer"] == 0

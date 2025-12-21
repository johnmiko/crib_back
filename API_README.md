# Cribbage API

FastAPI backend for playing Cribbage against a computer opponent.

## Architecture

The API converts the synchronous CLI cribbage game into a stateful web service:
- Each game session is stored in-memory with a unique ID
- Instead of blocking on `input()`, the game pauses and returns the current state
- The frontend submits player choices via POST requests
- The game resumes from where it left off after receiving input

## Setup

1. **Activate virtual environment:**
   ```powershell
   cd C:\Users\johnm\ccode\crib
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies (if not already installed):**
   ```powershell
   pip install -r requirements.txt
   ```

## Running the Server

```powershell
python app.py
```

The server will start on `http://localhost:8000`

Or use uvicorn directly:
```powershell
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### `POST /game/new`
Create a new game session and start the first round.

**Response:**
```json
{
  "game_id": "uuid-here",
  "action_required": "select_crib_cards",
  "message": "Select 2 cards to place in the crib",
  "your_hand": [{"rank": "nine", "suit": "hearts", "symbol": "9♥", "value": 9}, ...],
  "table_cards": [],
  "scores": {"you": 0, "computer": 0},
  "dealer": "computer",
  "table_value": 0,
  "starter_card": null,
  "valid_card_indices": [],
  "game_over": false,
  "winner": null
}
```

### `GET /game/{game_id}`
Get the current state of an existing game.

### `WS /ws/{game_id}`
Open a WebSocket to receive pushed game-state updates (initial state is sent on connect).

### `POST /game/{game_id}/action`
Submit a player action (crib cards or card to play).

**Request body:**
```json
{
  "card_indices": [0, 1]  // For crib: 2 cards, for play: 1 card, for "go": []
}
```

**Response:** Same as game state

### `DELETE /game/{game_id}`
Delete a game session.

## Game Flow

1. **Create game** → Receive initial state with 6 cards
2. **Select crib cards** → Submit 2 card indices to discard
3. **Play phase begins** → Starter card is revealed
4. **Play cards** → Take turns playing cards until all are played
   - Submit 1 card index to play a card
   - Submit empty array `[]` to say "go"
5. **Scoring** → Hands and crib are scored automatically
6. **Next round** → If no one has reached 121, a new round starts
7. **Game over** → Winner is announced

## Action Types

- `select_crib_cards`: Need to select 2 cards to place in the crib
- `select_card_to_play`: Need to play a card or say "go"
- `waiting_for_computer`: Computer is making its move
- `game_over`: Game has ended

## Testing

Run the test script to verify the API:
```powershell
# In one terminal, start the server:
python app.py

# In another terminal, run the test:
python test_api.py
```

Or test manually with curl:
```powershell
# Create game
curl -X POST http://localhost:8000/game/new

# Submit action (replace {game_id})
curl -X POST http://localhost:8000/game/{game_id}/action -H "Content-Type: application/json" -d '{"card_indices": [0, 1]}'

# Get state
curl http://localhost:8000/game/{game_id}
```

## Next Steps

- **Frontend Integration**: Build a React UI that calls these endpoints
- **Persistent Storage**: Add database or Redis for game state persistence
- **Multiplayer**: Add WebSocket support for real-time multiplayer games
- **AI Improvement**: Replace random computer player with strategic AI
- **Authentication**: Add user accounts and game history

## Technical Details

- **Framework**: FastAPI with Pydantic models
- **Storage**: In-memory dictionary (games reset on server restart)
- **CORS**: Enabled for all origins (configure for production)
- **Port**: Default 8000 (configurable)

# Railway Database Setup for Cribbage Backend

## Overview
Match statistics tracking for crib_back using PostgreSQL on Railway.

## Database Schema

### MatchHistory Table
Tracks wins/losses per user per opponent type:

```sql
CREATE TABLE match_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    opponent_id VARCHAR NOT NULL,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_user_id ON match_history(user_id);
CREATE INDEX idx_opponent_id ON match_history(opponent_id);
```

## Railway Setup

### 1. Create PostgreSQL Database
1. Go to your Railway project
2. Click "New" → "Database" → "Add PostgreSQL"
3. Railway will provision a new PostgreSQL instance
4. Copy the `DATABASE_URL` from the database settings

### 2. Set Environment Variable
In your Railway service (crib_back):
- Navigate to Variables tab
- Add variable: `DATABASE_URL` = (paste the connection string from step 1)
- Example format: `postgresql://postgres:password@host:5432/railway`

### 3. Deploy
- Push your code changes to trigger deployment
- Railway will restart the service with the new environment variable
- Database tables are automatically created on app startup

## Local Development

### With Local PostgreSQL:
```bash
# Install PostgreSQL locally
# Create database
createdb cribbage_dev

# Set environment variable
$env:DATABASE_URL="postgresql://localhost:5432/cribbage_dev"

# Run backend
python -m uvicorn app:app --reload
```

### Without Database (Testing):
```bash
# Run without DATABASE_URL - stats tracking disabled
python -m uvicorn app:app --reload
```

## API Endpoints

### Create Game with User ID
```http
POST /game/new
Content-Type: application/json

{
  "opponent_type": "linearb",
  "user_id": "github_user_123"
}
```

**Note:** If `user_id` is omitted or null, no statistics are tracked.

### Get User Statistics
```http
GET /stats/{user_id}
```

**Response:**
```json
{
  "user_id": "github_user_123",
  "stats": [
    {
      "opponent_id": "linearb",
      "wins": 5,
      "losses": 3,
      "total_games": 8,
      "win_rate": 0.625
    },
    {
      "opponent_id": "myrmidon",
      "wins": 2,
      "losses": 7,
      "total_games": 9,
      "win_rate": 0.222
    }
  ]
}
```

## Code Flow

### Match Recording
1. Frontend creates game with `user_id` (if logged in)
2. `GameSession` stores `user_id` and `opponent_type`
3. When game reaches 121 points:
   - Determine winner (human vs computer)
   - Call `record_match_result(user_id, opponent_type, won)`
   - Updates or creates MatchHistory record
4. Match recorded only once per game via `match_recorded` flag

### Anonymous Users
- Frontend omits `user_id` field in game creation
- `GameSession.user_id` remains `None`
- `record_match_result()` returns `False` without recording
- Game works normally, just no stats tracked

## Database Functions

### `record_match_result(user_id, opponent_id, won)`
Records a completed match:
- `user_id`: User identifier (None = skip recording)
- `opponent_id`: Opponent type ("linearb", "myrmidon", etc.)
- `won`: True if user won, False if opponent won
- Returns: True if recorded, False if skipped

Creates or updates a single row per (user_id, opponent_id) pair with cumulative wins/losses.

### `get_user_stats(user_id)`
Retrieves all statistics for a user:
- Returns list of dicts with opponent stats
- Each dict includes win_rate calculation
- Returns empty list if no stats found

## Troubleshooting

### Tables Not Created
```bash
# Check DATABASE_URL is set correctly
echo $env:DATABASE_URL  # PowerShell
# or
python -c "import os; print(os.getenv('DATABASE_URL'))"
```

### Connection Errors
- Verify Railway database is running
- Check connection string format: `postgresql://` not `postgres://`
- Ensure database allows connections from your IP (Railway auto-configures)

### Stats Not Recording
- Check that `user_id` is passed in game creation request
- Verify DATABASE_URL is set in Railway environment
- Check Railway logs for database errors
- Ensure `psycopg2-binary` is in requirements.txt

## Dependencies

Already added to `requirements.txt`:
```
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
```

Install locally:
```bash
pip install -r requirements.txt
```

## Testing

Run database test script:
```bash
python test_database.py
```

This tests:
- Database initialization
- Anonymous user handling (user_id=None)
- Match recording
- Statistics retrieval

## Security Notes

- User IDs should come from authenticated sessions (OAuth, JWT, etc.)
- Railway DATABASE_URL is automatically secured and rotated
- Never commit DATABASE_URL to version control
- Use environment variables only

# Match Statistics Database Implementation Summary

## What Was Implemented

### Database Layer (database.py)
Created complete PostgreSQL integration for match statistics:

**MatchHistory Table:**
- Tracks wins/losses per user per opponent type
- Fields: user_id, opponent_id, wins, losses, timestamps
- Single row per (user_id, opponent_id) pair with cumulative stats

**Functions:**
- `init_db()`: Creates tables on app startup (only if DATABASE_URL set)
- `record_match_result(user_id, opponent_id, won)`: Records match outcome
- `get_user_stats(user_id)`: Retrieves all stats for a user with win rates

**Key Features:**
- Gracefully handles missing DATABASE_URL (no crash, just skips recording)
- Handles `user_id=None` (anonymous users - no tracking)
- Auto-converts Railway's `postgres://` to `postgresql://` 
- Uses SQLAlchemy ORM with proper session management

### Game Session Changes (app.py)

**GameSession Class:**
- Added `user_id` parameter to `__init__` (optional, defaults to None)
- Added `match_recorded` flag to prevent duplicate recordings
- Records match result when game reaches 121 points
- Only records if user_id is not None

**CreateGameRequest:**
- Added optional `user_id` field
- Frontend can pass user ID when creating games

**New API Endpoint:**
- `GET /stats/{user_id}`: Returns match statistics for a user

**Modified Endpoints:**
- `POST /game/new`: Now accepts `user_id` in request body

### Testing & Documentation

**test_database.py:**
- Tests database initialization
- Tests anonymous user handling (user_id=None)
- Tests match recording and retrieval
- Gracefully handles missing DATABASE_URL

**DATABASE_README.md:**
- Complete Railway setup instructions
- API documentation with examples
- Local development guide
- Troubleshooting section

## How It Works

### For Logged-In Users:
1. Frontend creates game with `user_id` (e.g., from GitHub OAuth)
2. GameSession stores user_id and opponent_type
3. When game ends (121 points reached):
   - Determine winner (human vs computer)
   - Call `record_match_result(user_id, opponent_type, won)`
   - Database creates or updates MatchHistory row
4. Frontend can fetch stats via `GET /stats/{user_id}`

### For Anonymous Users:
1. Frontend creates game without `user_id` field
2. GameSession.user_id remains None
3. Game plays normally
4. When game ends, `record_match_result()` returns False and skips recording
5. No stats tracked, no database writes

## API Examples

### Create Game (Logged In)
```http
POST /game/new
Content-Type: application/json

{
  "opponent_type": "linearb",
  "user_id": "github_user_123"
}
```

### Create Game (Anonymous)
```http
POST /game/new
Content-Type: application/json

{
  "opponent_type": "myrmidon"
}
```

### Get User Statistics
```http
GET /stats/github_user_123
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
    }
  ]
}
```

## Railway Deployment

### Required Steps:
1. Create PostgreSQL database in Railway project
2. Copy DATABASE_URL from database settings
3. Add DATABASE_URL to crib_back service variables
4. Deploy (tables auto-created on startup)

### Environment Variable:
```
DATABASE_URL=postgresql://postgres:password@host:5432/railway
```

## Dependencies Added

Already in requirements.txt:
- sqlalchemy>=2.0.0
- psycopg2-binary>=2.9.0

Install locally:
```bash
python -m pip install -r requirements.txt
```

## Testing Results

✅ Database initialization (graceful when DATABASE_URL missing)
✅ Anonymous user handling (user_id=None returns False, no recording)
✅ Match recording (skipped when no database)
✅ Stats retrieval (returns empty list when no database)
✅ App imports successfully with all changes
✅ All existing functionality preserved

## Notes

- Match statistics only tracked for logged-in users
- No breaking changes to existing API
- Backward compatible (works without DATABASE_URL)
- Frontend needs to implement user authentication
- user_id should come from OAuth/JWT token
- Database operations fail silently if DATABASE_URL not set

## Next Steps (Frontend)

To use match statistics, frontend needs to:
1. Implement user authentication (GitHub OAuth, etc.)
2. Pass `user_id` when creating games for logged-in users
3. Fetch and display stats via `/stats/{user_id}` endpoint
4. Show win rates, total games per opponent type
5. Optional: Add leaderboard, achievements, etc.

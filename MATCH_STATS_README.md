# Cribbage Match Statistics - Complete Implementation Guide

## Overview

This document describes the complete implementation of match statistics tracking for the Cribbage backend using PostgreSQL on Railway.

## What Was Implemented

### 1. Database Layer (`database.py`)

**Complete PostgreSQL integration:**
- SQLAlchemy ORM models for match history
- Automatic table creation on app startup
- Helper functions for recording and retrieving stats
- Graceful fallback when database unavailable

**MatchHistory Table Schema:**
```
- id (Integer, Primary Key)
- user_id (String, Indexed) - Required for tracking
- opponent_id (String, Indexed) - AI opponent type
- wins (Integer) - Total wins vs this opponent
- losses (Integer) - Total losses vs this opponent
- created_at (DateTime) - Record creation time
- updated_at (DateTime) - Last update time
```

**Key Functions:**
- `init_db()` - Creates tables (safe to call multiple times)
- `record_match_result(user_id, opponent_id, won)` - Records game outcome
- `get_user_stats(user_id)` - Returns stats with calculated win rates

**Features:**
- Supports Railway's `postgres://` URLs (auto-converts to `postgresql://`)
- Handles missing DATABASE_URL gracefully (stats disabled, no errors)
- Handles anonymous users (user_id=None skips tracking)
- Thread-safe with proper session management

### 2. Game Integration (`app.py`)

**GameSession Updates:**
```python
def __init__(self, game_id: str, opponent_type: str = "random", 
             user_id: Optional[str] = None):
```
- Now accepts optional `user_id` parameter
- Stores opponent type for tracking
- Tracks whether match result was recorded (prevents duplicates)

**Match Recording:**
- When game reaches 121 points:
  - Determines winner (human vs computer)
  - Calls `record_match_result(user_id, opponent_type, won)`
  - Only records if user_id is present (logged-in users)
  - Uses flag to prevent duplicate recordings

**API Updates:**

1. **POST /game/new** - Enhanced with user_id
   - Request: `{ "opponent_type": "linearb", "user_id": "user_123" }`
   - user_id is optional (for backward compatibility)
   - Games without user_id work normally, just don't track stats

2. **GET /stats/{user_id}** - New endpoint
   - Returns: `{ "user_id": "...", "stats": [...] }`
   - Stats include win rate calculations
   - Returns empty list if user has no stats

**CreateGameRequest Model:**
```python
class CreateGameRequest(BaseModel):
    dealer: Optional[Literal['human','computer','you','player']] = None
    preset: Optional[Literal['aces_twos_vs_threes_fours']] = None
    opponent_type: Optional[str] = "random"
    user_id: Optional[str] = None  # NEW
    human_cards: Optional[List[str]] = None
    computer_cards: Optional[List[str]] = None
```

### 3. Code Quality Improvements

**Deprecated Imports Removed:**
- Changed from `sqlalchemy.ext.declarative import declarative_base`
- To: `from sqlalchemy.orm import declarative_base`

**Modern FastAPI Patterns:**
- Changed from deprecated `@app.on_event("startup")`
- To: `lifespan` context manager (FastAPI 0.93+)

## How It Works

### Flow for Logged-In Users

1. **Frontend** sends game creation request:
   ```
   POST /game/new
   {
     "opponent_type": "linearb",
     "user_id": "github_abc123"
   }
   ```

2. **Backend** creates GameSession:
   - Stores user_id and opponent_type
   - Initializes match_recorded flag to False
   - Game plays normally

3. **During Gameplay:**
   - Game state managed by GameSession
   - Player makes moves
   - AI opponent responds

4. **At Game Completion:**
   - When either player reaches 121 points
   - Winner is determined
   - If match_recorded is False and user_id exists:
     - Call `record_match_result(user_id, opponent_type, won)`
     - Set match_recorded = True (prevent duplicates)

5. **Record Match Result:**
   - Database looks for existing (user_id, opponent_id) row
   - If exists: increment wins or losses
   - If not: create new row with (1, 0) or (0, 1)
   - Update timestamp

6. **Retrieve Stats:**
   ```
   GET /stats/github_abc123
   ```
   Returns:
   ```json
   {
     "user_id": "github_abc123",
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

### Flow for Anonymous Users

1. **Frontend** creates game without user_id:
   ```
   POST /game/new
   {
     "opponent_type": "myrmidon"
   }
   ```

2. **Backend** creates GameSession:
   - user_id remains None
   - Game plays normally

3. **At Game Completion:**
   - Game end condition reached
   - Check: if user_id is None → skip recording
   - Return game over state
   - No database writes occur

4. **Result:**
   - Game functions perfectly
   - No tracking, no database calls
   - User can play unlimited games

## API Reference

### Create Game (Logged In)
```http
POST /game/new
Content-Type: application/json

{
  "opponent_type": "linearb",
  "user_id": "github_user_123"
}
```

**Response:**
```json
{
  "game_id": "uuid-string",
  "action_required": "ActionType.WAITING_FOR_COMPUTER",
  "message": "",
  "your_hand": [...],
  "scores": { "you": 0, "computer": 0 },
  ...
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

**Note:** If user has no stats, returns empty stats list.

## Deployment

### Railway Setup

1. **Create PostgreSQL Database:**
   - Go to Railway project
   - New → Database → PostgreSQL
   - Copy the provided DATABASE_URL

2. **Set Environment Variable:**
   - Service: crib_back
   - Variables: Add `DATABASE_URL`
   - Value: paste the connection string

3. **Deploy:**
   - Push code to repository
   - Railway auto-deploys
   - Tables created automatically

### Local Development

**With PostgreSQL:**
```bash
# Create local database
createdb cribbage_dev

# Set environment variable (PowerShell)
$env:DATABASE_URL = "postgresql://localhost:5432/cribbage_dev"

# Run backend
python -m uvicorn app:app --reload

# Test
python test_database.py
```

**Without Database:**
```bash
# Just run the backend
python -m uvicorn app:app --reload
# Stats tracking disabled, everything else works
```

## Testing

### Run Test Suite
```bash
python -m pytest test/ -q
# All 75 tests pass
```

### Test Database Integration
```bash
python test_database.py
# Tests:
# - Database initialization
# - Anonymous user handling
# - Match recording
# - Stats retrieval
```

### Test Game Integration
```bash
python test_integration.py
# Tests:
# - Game creation with user_id
# - Game creation without user_id
# - Game state retrieval
# - Match recording setup
```

## Files Changed

### Modified Files
- **app.py**
  - Added lifespan context manager (modern FastAPI)
  - Added user_id to GameSession.__init__
  - Added match_recorded flag
  - Added match recording on game completion
  - Added user_id to CreateGameRequest
  - Added GET /stats/{user_id} endpoint
  - Updated POST /game/new to pass user_id

- **database.py** (imports)
  - Updated to use modern declarative_base import
  - No schema changes

### New Files
- **database.py** - Complete database layer (151 lines)
- **test_database.py** - Database integration tests
- **test_integration.py** - Game + database integration tests
- **DATABASE_README.md** - Railway setup guide
- **DEPLOYMENT_CHECKLIST.md** - Deployment steps
- **MATCH_STATS_IMPLEMENTATION.md** - Technical details

### No Changes To
- Game logic (cribbagegame.py, scoring.py, etc.)
- Opponent strategies
- Card dealing/playing
- Any existing tests

## Backward Compatibility

✅ **Fully backward compatible:**
- Existing games work without user_id
- Anonymous play completely unaffected
- All existing API clients continue working
- No breaking changes to any endpoint
- All 75 existing tests pass
- Works without DATABASE_URL (stats disabled)

## Performance

- **Database Writes:** Only at game completion (infrequent)
- **Database Reads:** Indexed on user_id (fast)
- **Game Logic:** No performance impact
- **Graceful Degradation:** Works fine without database

## Security Considerations

- **User IDs:** Should come from authenticated sessions
- **Database:** Railway PostgreSQL auto-secured
- **API:** No special auth needed for stats (if privacy desired, add auth later)
- **Data:** Match results are non-sensitive game metrics

## Future Enhancements

Possible additions:
- Authentication/authorization for stats endpoints
- Leaderboards (global/per-opponent)
- Achievements/badges
- Elo ratings for players
- Game replay history
- Advanced analytics (win percentage vs opponent type)
- Stats export/download

## Support & Troubleshooting

### Common Issues

**Stats not recording:**
- Verify user_id passed in game creation
- Check DATABASE_URL environment variable
- Ensure games complete (reach 121 points)

**Connection errors:**
- Verify DATABASE_URL format (postgresql:// not postgres://)
- Check Railway database is running
- Review Railway logs

**Performance issues:**
- Check Railway PostgreSQL resource usage
- Consider query optimization if scale needed

### Getting Help

1. Check DEPLOYMENT_CHECKLIST.md for setup issues
2. Check DATABASE_README.md for Railway configuration
3. Run test_database.py to diagnose problems
4. Check Railway logs for database errors

## Summary

This implementation adds optional match statistics tracking to crib_back:
- ✅ Database layer ready (SQLAlchemy + PostgreSQL)
- ✅ Game integration complete (user_id flow)
- ✅ API endpoints for stats retrieval
- ✅ Backward compatible (works without database)
- ✅ Anonymous users unaffected
- ✅ All tests passing
- ✅ Ready for Railway deployment
- ✅ Production-ready code

To deploy: set DATABASE_URL environment variable in Railway and restart the service.

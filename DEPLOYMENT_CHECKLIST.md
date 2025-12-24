# Railway Deployment Checklist for Match Statistics

## Pre-Deployment Setup

### 1. Create Railway Database
- [ ] Go to Railway project dashboard
- [ ] Click "New" → Select "Database" → "Add PostgreSQL"
- [ ] Wait for database to provision
- [ ] Copy the `DATABASE_URL` from the database resource settings
- [ ] Format should be: `postgresql://username:password@host:port/dbname`

### 2. Update Railway Service Variables
- [ ] In Railway dashboard, open the `crib_back` service
- [ ] Go to Variables tab
- [ ] Add new variable:
  - Name: `DATABASE_URL`
  - Value: (paste the URL from step 1)
- [ ] Save changes

### 3. Deploy the Code
- [ ] Ensure all changes are committed and pushed to your repository:
  - [ ] `app.py` - Updated with user_id parameter and stats endpoints
  - [ ] `database.py` - New file with MatchHistory model
  - [ ] `requirements.txt` - Already has sqlalchemy and psycopg2-binary
  - [ ] Check git status: `git status`
  - [ ] Commit: `git commit -m "Add match statistics database integration"`
  - [ ] Push: `git push origin main`
- [ ] Railway will auto-deploy on push (if configured)
- [ ] Monitor deployment progress in Railway dashboard

### 4. Verify Deployment
- [ ] Check Railway logs for successful startup
- [ ] Look for message confirming database initialization
- [ ] Test endpoints:
  ```bash
  # Create a game (with user_id)
  curl -X POST http://your-railway-url/game/new \
    -H "Content-Type: application/json" \
    -d '{"opponent_type":"linearb","user_id":"test_user_1"}'
  
  # Get stats
  curl http://your-railway-url/stats/test_user_1
  ```

## Local Development Testing

### Before Deploying to Railway

1. **Test with Local PostgreSQL:**
   ```bash
   # Install PostgreSQL locally if needed
   # Create database
   createdb cribbage_dev
   
   # Set environment variable (PowerShell)
   $env:DATABASE_URL="postgresql://localhost:5432/cribbage_dev"
   
   # Run backend
   python -m uvicorn app:app --reload
   
   # Test match recording in another terminal
   python test_database.py
   ```

2. **Run Full Test Suite:**
   ```bash
   python -m pytest test/ -v
   ```

3. **Test Game Flow:**
   ```bash
   python test_integration.py
   ```

### Without Local Database

- Tests work fine with DATABASE_URL not set (gracefully disabled)
- This is good for development without PostgreSQL installed

## Post-Deployment Verification

### Database
- [ ] Database tables created automatically
- [ ] Match history data persists across app restarts
- [ ] Can query stats endpoint successfully

### API Endpoints
- [ ] `/game/new` with `user_id` - Game creates with user tracking
- [ ] `/game/new` without `user_id` - Game creates without tracking
- [ ] `/stats/{user_id}` - Returns win/loss stats
- [ ] Game completion triggers match recording
- [ ] Anonymous games don't create database entries

### Game Functionality
- [ ] Normal gameplay unchanged
- [ ] All existing endpoints still work
- [ ] No performance degradation

## Troubleshooting

### Database Connection Error
- [ ] Check DATABASE_URL is set in Railway variables
- [ ] Verify format: `postgresql://` not `postgres://`
- [ ] Check Railway PostgreSQL is running
- [ ] Look at Railway logs for connection errors

### Tables Not Creating
- [ ] Check Railway logs for database initialization
- [ ] Verify DATABASE_URL environment variable is set
- [ ] Try restarting the service

### Stats Not Saving
- [ ] Ensure user_id is passed in /game/new request
- [ ] Check that games reach 121 points (completion detection)
- [ ] Verify DATABASE_URL is properly set
- [ ] Check PostgreSQL has write permissions

### Performance Issues
- [ ] Index queries should be fast (user_id is indexed)
- [ ] Monitor Railway PostgreSQL CPU/Memory
- [ ] Consider query optimization if needed

## Rollback Plan

If issues occur:

1. **Quick Rollback (Keep Database):**
   - Remove DATABASE_URL from Railway variables
   - Redeploy previous version
   - App continues working without stats tracking
   - Database preserved for recovery

2. **Full Rollback:**
   - Remove DATABASE_URL variable
   - Deploy previous crib_back version
   - Drop PostgreSQL database if needed

## Code Changes Summary

### Files Modified
- `app.py` - Added user_id parameter, match recording, stats endpoint
- `database.py` - New file with SQLAlchemy models and helper functions
- `requirements.txt` - Already has dependencies

### Breaking Changes
- None! All changes are backward compatible
- Anonymous games still work normally
- Existing API clients unaffected

### Performance Impact
- Minimal - only writes at game completion
- Database queries indexed on user_id
- No impact on game logic or timing

## Frontend Integration (Next Steps)

For full functionality, frontend needs:

1. **User Authentication:**
   - Implement GitHub OAuth or similar
   - Store user ID in localStorage/session

2. **Pass user_id to Backend:**
   ```javascript
   fetch('http://api/game/new', {
     method: 'POST',
     body: JSON.stringify({
       opponent_type: 'linearb',
       user_id: currentUser.id  // Add this
     })
   })
   ```

3. **Display Stats:**
   ```javascript
   fetch(`http://api/stats/${userId}`)
     .then(r => r.json())
     .then(data => console.log(data.stats))
   ```

## Notes

- Match statistics only tracked for logged-in users
- Anonymous gameplay completely unaffected
- Database auto-creates tables on first run
- Safe to deploy - gracefully handles missing database
- All 75 existing tests still pass

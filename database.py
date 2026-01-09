"""Database configuration and models for Crib statistics."""
import os
from typing import Optional
from sqlalchemy import create_engine, DateTime, func
from sqlalchemy.orm import sessionmaker, Session, declarative_base, Mapped, mapped_column
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()  # Load .env file
DATABASE_URL = os.getenv("DATABASE_URL")

# Railway Postgres URLs start with postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine - only if DATABASE_URL is set
engine = None
SessionLocal = None

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    """Authenticated user records sourced from Google SSO."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, index=True)  # Google 'sub' as stable id
    email: Mapped[str | None] = mapped_column(index=True, nullable=True)
    name: Mapped[str | None] = mapped_column(nullable=True)
    picture: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class GameResult(Base):
    """Track individual game results with detailed statistics for users."""
    __tablename__ = "game_results"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(index=True)
    opponent_id: Mapped[str] = mapped_column(index=True)
    win: Mapped[bool] = mapped_column()  # True if player won, False if lost
    average_points_pegged: Mapped[float] = mapped_column()  # avg points per hand
    average_hand_score: Mapped[float] = mapped_column()
    average_crib_score: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def init_db():
    """Initialize database tables."""
    if engine:
        Base.metadata.create_all(bind=engine)
def upsert_google_user(user_id: str, email: Optional[str], name: Optional[str], picture: Optional[str]) -> Optional[User]:
    """Create or update a user from verified Google payload."""
    db = get_db()
    if db is None:
        return None
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.email = email or user.email
            user.name = name or user.name
            user.picture = picture or user.picture
            user.updated_at = datetime.utcnow()
        else:
            user = User(id=user_id, email=email, name=name, picture=picture)
            db.add(user)
        db.commit()
        return user
    except Exception as e:
        db.rollback()
        print(f"Error upserting user: {e}")
        return None
    finally:
        db.close()



def get_db() -> Session | None:
    """Get database session. Returns None if no database configured."""
    if SessionLocal is None:
        return None
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        return None


def record_match_result(
    user_id: Optional[str],
    opponent_id: str,
    won: bool,
    average_points_pegged: float = 0.0,
    average_hand_score: float = 0.0,
    average_crib_score: float = 0.0
) -> bool:
    """
    Record a game result for a user.
    
    Args:
        user_id: User identifier (use "not_signed_in" for anonymous users, None to skip recording)
        opponent_id: Opponent type (e.g., 'linearb', 'myrmidon')
        won: True if user won, False if lost
        average_points_pegged: Average points pegged per round
        average_hand_score: Average score per hand played
        average_crib_score: Average crib score when user was dealer
        
    Returns:
        True if recorded successfully, False otherwise
    """
    # Don't track if user_id is explicitly None (skip tracking)
    if user_id is None:
        return False
    
    # Don't track if database is not configured
    db = get_db()
    if db is None:
        return False
    
    try:
        # Create new game result record
        record = GameResult(
            user_id=user_id,
            opponent_id=opponent_id,
            win=won,
            average_points_pegged=average_points_pegged,
            average_hand_score=average_hand_score,
            average_crib_score=average_crib_score
        )
        db.add(record)
        db.commit()
        return True
        
    except Exception as e:
        db.rollback()
        print(f"Error recording game result: {e}")
        return False
        
    finally:
        db.close()


def get_user_stats(user_id: str) -> list:
    """
    Get game statistics for a user aggregated by opponent.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of dicts with opponent stats, or empty list if no database
    """
    db = get_db()
    if db is None:
        return []
    
    try:
        records = db.query(GameResult).filter(GameResult.user_id == user_id).all()
        
        # Aggregate stats by opponent
        opponent_stats = {}
        for r in records:
            opp_id = r.opponent_id
            if opp_id not in opponent_stats:
                opponent_stats[opp_id] = {
                    "opponent_id": opp_id,
                    "wins": 0,
                    "losses": 0,
                    "total_games": 0,
                    "avg_points_pegged": 0.0,
                    "avg_hand_score": 0.0,
                    "avg_crib_score": 0.0,
                }
            
            stats = opponent_stats[opp_id]
            if bool(r.win):
                stats["wins"] += 1
            else:
                stats["losses"] += 1
            stats["total_games"] += 1
            stats["avg_points_pegged"] += r.average_points_pegged
            stats["avg_hand_score"] += r.average_hand_score
            stats["avg_crib_score"] += r.average_crib_score
        
        # Calculate averages
        for stats in opponent_stats.values():
            total = stats["total_games"]
            if total > 0:
                stats["avg_points_pegged"] /= total
                stats["avg_hand_score"] /= total
                stats["avg_crib_score"] /= total
                stats["win_rate"] = stats["wins"] / total
        
        return list(opponent_stats.values())
        
    except Exception as e:
        print(f"Error getting user stats: {e}")
        return []
        
    finally:
        db.close()


def get_game_history(user_id: str, opponent_id: str | None = None, limit: int = 50) -> list:
    """
    Get individual game history for a user (useful for charting).
    
    Args:
        user_id: User identifier
        opponent_id: Filter by opponent type (optional)
        limit: Max number of games to return
        
    Returns:
        List of game records in chronological order
    """
    db = get_db()
    if db is None:
        return []
    
    try:
        query = db.query(GameResult).filter(GameResult.user_id == user_id)
        
        if opponent_id:
            query = query.filter(GameResult.opponent_id == opponent_id)
        
        records = query.order_by(GameResult.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": r.id,
                "opponent_id": r.opponent_id,
                "win": r.win,
                "average_points_pegged": r.average_points_pegged,
                "average_hand_score": r.average_hand_score,
                "average_crib_score": r.average_crib_score,
                "created_at": r.created_at.isoformat() if r.created_at is not None else None,
            }
            for r in records
        ]
        
    except Exception as e:
        print(f"Error getting game history: {e}")
        return []
        
    finally:
        db.close()

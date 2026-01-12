"""FastAPI backend for Cribbage game using existing cribbagegame classes."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional, List, Literal, Any
from contextlib import asynccontextmanager
import uuid
import random

from cribbage.cribbageround import RoundHistory
from cribbage.cribbagegame import CribbageGame, CribbageRound
from cribbage.players.base_player import BasePlayer
from cribbage.players.random_player import RandomPlayer
from cribbage.models import ActionType, GameStateResponse, PlayerAction, CardData
from cribbage.playingcards import Card, Deck
from crib_api.opponents import get_opponent_strategy, list_opponent_types, OpponentStrategy
from database import init_db, record_match_result, get_user_stats, get_game_history as db_get_game_history, upsert_google_user
import os
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    # Startup: Initialize database tables
    init_db()
    yield
    # Shutdown: cleanup if needed (none required currently)


app = FastAPI(lifespan=lifespan)

# Strict audience for Google ID token verification
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Configure CORS - allow localhost for development and production domains
# Note: When allow_credentials=True, allow_origins cannot be ["*"]
# So we list development ports and production domains explicitly
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Local development
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
        # Production domains
        "https://crib-sigma.vercel.app",
        "https://*.vercel.app",  # Allow any Vercel deployment
        "https://*.up.railway.app",  # Allow Railway deployments
        # Loveable development
        "https://80688fe0-889d-4a8c-ab4e-ea2cd9b5e5d6.lovableproject.com",
        "https://id-preview--80688fe0-889d-4a8c-ab4e-ea2cd9b5e5d6.lovable.app",
        
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AwaitingPlayerInput(Exception):
    """Raised when the game needs input from the human player."""
    def __init__(self, msg: str, cards: List[Card], n_cards: int):
        self.msg = msg
        self.cards = cards
        self.n_cards = n_cards
        super().__init__(msg)


class APIPlayer(BasePlayer):
    """Player that pauses game execution when input is needed."""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.pending_selection: Optional[str] = None
    
    def set_selection(self, selection: str):
        """Set the selection from the API."""
        self.pending_selection = selection
    
    def get_input(self, msg: str, cards: List[Card], n_cards: int) -> str:
        """Get input - either from pending selection or raise exception to pause."""
        if self.pending_selection is not None:
            selection = self.pending_selection
            self.pending_selection = None
            return selection
        raise AwaitingPlayerInput(msg, cards, n_cards)
    
    def select_crib_cards(self, hand, dealer_is_self, your_score, opponent_score):
        """Select cards for the crib."""
        cards_selected = []
        while len(cards_selected) < 2:
            selection = self.get_input("Select 2 cards: ", hand, 2)
            indices = [int(s) for s in selection.split() if s.isdigit()]
            for idx in indices:
                if idx < 1 or idx > len(hand):
                    continue
                cards_selected.append(hand[idx - 1])
        return cards_selected
    
    def select_card_to_play(self, hand, table, crib, count=0):
        """Select a card to play."""
        if not hand:
            return None
        selection = self.get_input("Select a card: ", hand, 1)
        if not selection.strip():
            return None
        indices = [int(s) for s in selection.split() if s.isdigit()]
        if indices:
            idx = indices[0]
            if 1 <= idx <= len(hand):
                return hand[idx - 1]
        return None


class StrategyPlayer(BasePlayer):
    """Player that uses an opponent strategy for decision-making."""
    
    def __init__(self, name: str, strategy: OpponentStrategy):
        super().__init__(name)
        self.strategy = strategy
    
    def select_crib_cards(self, hand, dealer_is_self=True, your_score=None, opponent_score=None):
        # Strategy only needs the hand
        return self.strategy.select_crib_cards(hand=hand, dealer_is_self=dealer_is_self)
    
    def select_card_to_play(self, hand, table, crib, count=0):
        # Extract cards from table (table contains dicts with 'player' and 'card' keys)
        table_cards = [entry['card'] if isinstance(entry, dict) else entry for entry in table]
        # Use provided count if given, otherwise compute from table
        table_value = count if count else sum(c.get_value() for c in table_cards)
        return self.strategy.select_card_to_play(hand, table_cards, table_value, crib)


def card_to_data(card: Card) -> CardData:
    """Convert a Card object to CardData."""
    # card.value should always be an int for valid cards
    value = card.value if card.value is not None else 0
    return CardData(
        rank=card.rank,
        suit=card.suit,
        value=value,
        symbol=str(card)
    )


def _get_table_value(table: List[Dict], start_idx: int = 0) -> int:
    """Calculate table value from list of {'player': p, 'card': c} dicts."""
    return sum(m['card'].get_value() for m in table[start_idx:])


class ResumableRound:
    """Wrapper around CribbageRound that can be paused and resumed."""
    
    def __init__(self, game, dealer):
        self.round = CribbageRound(game=game, dealer=dealer)
        # Patch the get_table_value method to handle dict entries
        self.round.get_table_value = lambda start_idx: _get_table_value(self.round.table, start_idx)
        self.phase = 'start'
        self.active_players = None
        self.sequence_start_idx = 0
        # Optional overrides for deterministic starts
        self.overrides: Dict = {}
        # Track pegging scores for stats
        self.pegging_scores: Dict = {}  # {player: total_points}
        self.pegging_rounds_count = 0  # Number of scoring events
        # Track players who have said "go" in current sequence
        self.players_said_go: List = []
        self.game_winner = None
        self.history = RoundHistory()
        
    def run(self):
        """Run the round until completion or until player input needed."""
        r = self.round
        
        if self.phase == 'start':
            r.setup_deal_phase()
            # Apply any deal/hand overrides for deterministic test sessions
            if self.overrides.get('hands'):
                # Build a set of (rank_name, suit_name) for removal from deck
                def _key(c: Card):
                    return (c.get_rank(), c.get_suit())
                remove_keys = set()
                for plist in self.overrides['hands'].values():
                    for c in plist:
                        remove_keys.add(_key(c))
                # Filter deck to remove overridden cards so no duplicates appear later
                r.deck.cards = [c for c in r.deck.cards if _key(c) not in remove_keys]
                # Overwrite hands
                r.hands = {p: list(self.overrides['hands'].get(p, r.hands[p])) for p in r.hands}
            self.phase = 'crib'
        
        if self.phase == 'crib':
            r.setup_crib_phase()
            # Check for heels
            winner = r.setup_starter_scoring()
            if winner is not None:
                self.game_winner = winner
                self.phase = 'complete'
                return
            self.active_players = [r.nondealer, r.dealer]
            self.phase = 'play'
        
        if self.phase == 'play':
            # Initialize active_players only on first entry to play phase
            if self.active_players is None:
                self.active_players = [r.nondealer, r.dealer]
            
            # If we're resuming with a pending human selection, ensure human acts first
            try:
                from app import APIPlayer as _APIPlayer  # local check without circular import issues
            except Exception:
                _APIPlayer = APIPlayer  # fallback when already in this module
            if self.active_players:
                # Prioritize APIPlayer with a pending selection so we don't let the computer sneak an extra turn
                def _priority(p):
                    if isinstance(p, _APIPlayer) and getattr(p, 'pending_selection', None) is not None:
                        return 0
                    return 1
                # Stable sort keeps other order but moves the human with pending selection to front
                self.active_players = sorted(self.active_players, key=_priority)

            # Note: self.players_said_go persists across run() calls to track go state
            any_player_has_at_least_1_card = any(len(hand) > 0 for hand in self.hands.values())
            for p in self.active_players:
                if p not in self.pegging_scores:
                    self.pegging_scores[p] = 0
            while any_player_has_at_least_1_card and self.game_winner is None:
                while any_player_has_at_least_1_card and self.game_winner is None:
                    # breakpoint()
                    players_to_check = list(self.active_players)
                    for p in players_to_check:
                        # Skip players who have already said "go" this sequence
                        if p in self.players_said_go:
                            logger.debug(f"[GO] {p} has already said go, skipping.")
                            continue
                        
                        # Debug current selection context
                        try:
                            seq_cards = ", ".join(str(m['card']) for m in r.table[self.sequence_start_idx:])
                        except Exception:
                            seq_cards = ""
                        # logger.debug(f"[PLAY] Next: {p} | seq=[{seq_cards}] | value={_get_table_value(r.table, self.sequence_start_idx)} | hand={r.hands.get(p.name, [])}")
                        card = p.select_card_to_play(
                            hand=r.hands[p.name],
                            table=r.table[self.sequence_start_idx:],
                            crib=r.crib,
                            count=_get_table_value(r.table, self.sequence_start_idx)
                        )  # May raise AwaitingPlayerInput
                        
                        if card is None or card.get_value() + _get_table_value(r.table, self.sequence_start_idx) > 31:
                            logger.debug(f"[GO] {p} cannot play or chose go (value={_get_table_value(r.table, self.sequence_start_idx)})")
                            self.players_said_go.append(p)
                            # self.active_players.remove(p)
                        else:
                            logger.debug(f"[PLAY] {p} plays {card} -> value={_get_table_value(r.table, self.sequence_start_idx)}")
                            r.table.append({'player': p, 'card': card})
                            if _get_table_value(r.table, self.sequence_start_idx) == 31:
                                self.pegging_scores[p] += 1
                            r.hands[p.name].remove(card)
                            r.most_recent_player = p  # Track last player for go/31 scoring
                            # if not r.hands[p.name]:
                            #     self.active_players.remove(p)                            
                            score, description = r._score_play(card_seq=[move['card'] for move in r.table[self.sequence_start_idx:]])
                            if score:
                                # Track pegging score                                
                                self.pegging_scores[p] += score
                                self.pegging_rounds_count += 1
                                winner = r.game.board.peg(p, score)
                                if winner is not None:
                                    self.game_winner = winner
                                    break
                        
                        # Check if both players have said go
                        if self.game_winner is None:
                            if len(self.players_said_go) == 2:
                                logger.debug("All players have said go or reached 31.")
                                # Note: second parameter is table cards (list), not count (misleading param name in engine)
                                players_to_check = r.go_or_31_reached(self.players_said_go, [move['card'] for move in r.table[self.sequence_start_idx:]])
                                # After go: player who said go FIRST leads next sequence                                
                                self.players_said_go = []
                                self.sequence_start_idx = len(r.table)
                                # Reset active players with first_to_say_go leading
                                self.active_players = [p for p in r.game.players if r.hands[p.name]]
                            any_player_has_at_least_1_card = any(len(hand) > 0 for hand in self.hands.values())
                            if not any_player_has_at_least_1_card:                            
                                r.game.board.peg(p, 1)              
                                logger.debug(f"{p.name} scores 1 for last card.")                  
                                self.history.score_after_pegging = [r.game.board.get_score(p) for p in r.game.players]
                                break
                
                # If active_players is empty but players still have cards, restart the sequence
                # if not self.active_players and sum([len(v) for v in r.hands.values()]):
                #     self.active_players = [p for p in r.game.players if r.hands[p.name]]
            
            self.phase = 'scoring'
        
        if self.phase == 'scoring':
            r.score_hands_phase()
            self.phase = 'complete'
    
    @property
    def hands(self):
        return self.round.hands
    
    @property
    def table(self):
        return self.round.table
    
    @property
    def starter(self):
        return self.round.starter
    
    @property
    def dealer(self):
        return self.round.dealer


# Helper(s) to normalize player names for frontend
def _to_frontend_name(name_or_player) -> str:
    try:
        name = name_or_player if isinstance(name_or_player, str) else str(name_or_player)
    except Exception:
        name = str(name_or_player)
    name = name.lower()
    return "you" if name == "human" else name


def _map_scores_for_frontend(game: CribbageGame) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    for p in game.players:
        scores[_to_frontend_name(p)] = game.board.get_score(p)
    return scores


class GameSession:
    """Manages a single game session with pause/resume capability."""
    
    def __init__(self, game_id: str, opponent_type: str = "random", user_id: Optional[str] = None):
        self.game_id = game_id
        self.opponent_type = opponent_type
        self.user_id = user_id  # Track user for match statistics
        self.human = APIPlayer("human")
        strategy = get_opponent_strategy(opponent_type)
        self.computer = StrategyPlayer("computer", strategy)
        # Don't copy players so we can modify their state (pending_selection)
        self.game = CribbageGame(players=[self.human, self.computer], copy_players=False)
        self.current_round: Optional[ResumableRound] = None
        self.waiting_for: Optional[ActionType] = None
        self.message: str = ""
        self.last_cards: List[Card] = []
        self.last_n_cards: int = 0
        self.game_over: bool = False
        self.round_num: int = random.randint(0, 1)  # Random initial dealer
        self.match_recorded: bool = False  # Track if we've recorded stats
        # One-time overrides for next new round
        self.next_dealer_override: Optional[BasePlayer] = None
        self.next_round_overrides: Dict = {}
        # Last round summary for client pause
        self.last_round_summary: Optional[Dict] = None
        
        # Stats tracking for match history
        self.total_points_pegged_human = 0
        self.total_points_pegged_computer = 0
        self.pegging_rounds = 0
        self.total_hand_score_human = 0
        self.total_hand_score_computer = 0
        self.human_hands_count = 0
        self.computer_hands_count = 0
        self.total_crib_score_human = 0
        self.total_crib_score_computer = 0
        self.human_dealer_count = 0
        self.computer_dealer_count = 0
        self.table_history = []
        self.points_pegged = [0,0]
        
    def get_state(self) -> GameStateResponse:
        """Get current game state."""
        your_hand = []
        computer_hand = []
        table_cards = []        
        table_value = 0
        starter_card = None
        valid_indices = []
        
        if self.current_round:
            your_hand = [card_to_data(c) for c in self.current_round.hands.get(self.human.name, [])]
            computer_hand = [card_to_data(c) for c in self.current_round.hands.get(self.computer.name, [])]
            
            # Use the active sequence_start_idx to show only the current sequence
            sequence_start = getattr(self.current_round, 'sequence_start_idx', 0)
            
            # Table cards should only show the current sequence (cleared after go/31)
            table_cards = [card_to_data(m['card']) for m in self.current_round.table[sequence_start:]]
            
            if self.current_round.table:
                table_value = _get_table_value(self.current_round.table, sequence_start)

            
            if self.current_round.starter:
                starter_card = card_to_data(self.current_round.starter)
            
            # Calculate valid card indices
            if self.waiting_for == ActionType.SELECT_CARD_TO_PLAY:
                for i, card in enumerate(self.current_round.hands.get(self.human.name, [])):
                    if card.get_value() + table_value <= 31:
                        valid_indices.append(i)
            elif self.waiting_for == ActionType.SELECT_CRIB_CARDS:
                valid_indices = list(range(len(your_hand)))
        
        # Check for winner
        winner = None
        for p in self.game.players:
            if self.game.board.get_score(p) >= 121:
                self.game_over = True
                winner = _to_frontend_name(p)
                break
        
        # Get dealer
        dealer = "none"
        if self.current_round and self.current_round.dealer:
            dealer = _to_frontend_name(self.current_round.dealer)
        if self.current_round:
            self.table_history = [card_to_data(m['card']) for m in self.current_round.table]
            self.points_pegged = self.current_round.history.score_after_pegging
        
        # Get most recent play events (last 3) for display
        recent_events = []
        if self.current_round and hasattr(self.current_round, 'play_record'):
            # Get last 3 events, reversed so most recent is first
            for record in reversed(self.current_round.play_record[-3:]):
                recent_events.append(record.description)
        
        # Scores mapped for frontend
        scores_dict = _map_scores_for_frontend(self.game)
        game_state_response = GameStateResponse(
            game_id=self.game_id,
            action_required=self.waiting_for or ActionType.WAITING_FOR_COMPUTER,
            message=self.message,
            your_hand=your_hand,
            computer_hand=computer_hand,
            computer_hand_count=len(computer_hand) if computer_hand else 0,
            table_cards=table_cards,
            table_history=self.table_history,
            scores=scores_dict,
            dealer=dealer,
            table_value=table_value,
            starter_card=starter_card,
            valid_card_indices=valid_indices,
            game_over=self.game_over,
            winner=winner,
            round_summary=self.last_round_summary,
            points_pegged=self.points_pegged,
            recent_play_events=recent_events if recent_events else None,
        )
        logger.info(f"game_state: {game_state_response}")
        return game_state_response        

    def start_new_round(self):
        """Start a new round."""
        if self.next_dealer_override is not None:
            dealer = self.next_dealer_override
            # Clear override after use
            self.next_dealer_override = None
        else:
            dealer = self.game.players[self.round_num % len(self.game.players)]
        self.current_round = ResumableRound(game=self.game, dealer=dealer)
        if self.next_round_overrides:
            self.current_round.overrides = self.next_round_overrides
            self.next_round_overrides = {}
        self.round_num += 1
    
    def calculate_game_stats(self) -> tuple[float, float, float]:
        """
        Calculate average stats for the completed game.
        Returns: (avg_points_pegged, avg_hand_score, avg_crib_score)
        """
        avg_points_pegged = 0.0
        avg_hand_score = 0.0
        avg_crib_score = 0.0
        
        # Average points pegged per hand (user preference)
        # Divide total pegging points by number of hands the human played
        if self.human_hands_count > 0:
            avg_points_pegged = self.total_points_pegged_human / self.human_hands_count
        
        # Average hand score
        if self.human_hands_count > 0:
            avg_hand_score = self.total_hand_score_human / self.human_hands_count
        
        # Average crib score (only when human was dealer)
        if self.human_dealer_count > 0:
            avg_crib_score = self.total_crib_score_human / self.human_dealer_count
        
        return avg_points_pegged, avg_hand_score, avg_crib_score
    
    def advance(self) -> GameStateResponse:
        """Advance the game until player input is needed."""
        try:
            # Start new round if needed
            if self.current_round is None:
                self.start_new_round()
            assert self.current_round is not None
            
            # Run the round (will pause if player input needed)
            self.current_round.run()
            
            # If we reach here without exception, round completed
            # Build round summary and pause for user acknowledgement
            r = self.current_round.round
            summary_hands: Dict[str, List[CardData]] = {}
            summary_points: Dict[str, int] = {}
            summary_breakdowns: Dict[str, List[Dict[str, Any]]] = {}
            
            # Track pegging scores from this round
            if hasattr(self.current_round, "pegging_scores"):
                scores = getattr(self.current_round, "pegging_scores")
                if self.human in scores:
                    self.total_points_pegged_human += scores[self.human]
                if self.computer in scores:
                    self.total_points_pegged_computer += scores[self.computer]
            if hasattr(self.current_round, "pegging_rounds_count"):
                self.pegging_rounds += getattr(self.current_round, "pegging_rounds_count")

            # Hands with starter for scoring context
            for p in self.game.players:
                played_cards = [move['card'] for move in r.table if move['player'] == p]
                hand_cards = played_cards + ([r.starter] if r.starter else [])
                summary_hands[_to_frontend_name(p)] = [card_to_data(c) for c in hand_cards]
                points, breakdown = r._score_hand_with_breakdown(hand_cards, is_crib=False)
                summary_points[_to_frontend_name(p)] = points
                summary_breakdowns[_to_frontend_name(p)] = breakdown
                
                # Track hand scores for stats
                if p == self.human:
                    self.total_hand_score_human += points
                    self.human_hands_count += 1
                else:
                    self.total_hand_score_computer += points
                    self.computer_hands_count += 1

            # Crib
            crib_cards = r.crib + ([r.starter] if r.starter else [])
            summary_hands['crib'] = [card_to_data(c) for c in crib_cards]
            crib_points, crib_breakdown = r._score_hand_with_breakdown(crib_cards, is_crib=True)
            summary_points['crib'] = crib_points
            summary_breakdowns['crib'] = crib_breakdown
            
            # Track crib scores for stats
            if r.dealer == self.human:
                self.total_crib_score_human += crib_points
                self.human_dealer_count += 1
            else:
                self.total_crib_score_computer += crib_points
                self.computer_dealer_count += 1

            self.last_round_summary = {
                'hands': summary_hands,
                'points': summary_points,
                'breakdowns': summary_breakdowns,
            }

            # Check if game is over
            for p in self.game.players:
                if self.game.board.get_score(p) >= 121:
                    self.game_over = True
                    self.message = f"Game over! {p} wins!"
                    
                    # Record match result (only if not already recorded)
                    if not self.match_recorded:
                        won = (p == self.human)
                        avg_points_pegged, avg_hand_score, avg_crib_score = self.calculate_game_stats()
                        # Use "not_signed_in" if user_id is not provided
                        effective_user_id = self.user_id if self.user_id else "not_signed_in"
                        record_match_result(
                            effective_user_id,
                            self.opponent_type,
                            won,
                            average_points_pegged=avg_points_pegged,
                            average_hand_score=avg_hand_score,
                            average_crib_score=avg_crib_score
                        )
                        self.match_recorded = True
                    
                    return self.get_state()

            # Pause before starting next round
            self.waiting_for = ActionType.ROUND_COMPLETE
            self.message = "Round complete. Review hands and continue."
            return self.get_state()
            
        except AwaitingPlayerInput as e:
            # Game paused waiting for player input
            self.last_cards = e.cards
            self.last_n_cards = e.n_cards
            self.message = e.msg
            
            if e.n_cards == 2:
                self.waiting_for = ActionType.SELECT_CRIB_CARDS
            elif e.n_cards == 1:
                self.waiting_for = ActionType.SELECT_CARD_TO_PLAY
            
            return self.get_state()

    
    def submit_action(self, card_indices: List[int]) -> GameStateResponse:
        """Submit player action and continue game."""
        if self.waiting_for == ActionType.SELECT_CRIB_CARDS:
            if len(card_indices) != 2:
                raise HTTPException(status_code=400, detail="Must select exactly 2 cards for crib")
            # Convert 0-based indices to 1-based selection string
            selection = " ".join(str(i + 1) for i in sorted(card_indices))
        elif self.waiting_for == ActionType.SELECT_CARD_TO_PLAY:
            if len(card_indices) == 0:
                selection = ""  # Go
            elif len(card_indices) == 1:
                selection = str(card_indices[0] + 1)
            else:
                raise HTTPException(status_code=400, detail="Must select 0 or 1 card to play")
        elif self.waiting_for == ActionType.ROUND_COMPLETE:
            # User acknowledged round summary; start next round
            self.waiting_for = None
            self.current_round = None
            self.last_round_summary = None
            return self.advance()
        else:
            raise HTTPException(status_code=400, detail="No action required")
        
        # Validate indices
        for idx in card_indices:
            if idx < 0 or idx >= len(self.last_cards):
                raise HTTPException(status_code=400, detail=f"Invalid card index: {idx}")
        
        # Set the selection and continue
        self.human.set_selection(selection)
        self.waiting_for = None
        return self.advance()


# Request model for creating a new game with optional overrides
class CreateGameRequest(BaseModel):
    dealer: Optional[Literal['human','computer','you','player']] = None
    preset: Optional[Literal['aces_twos_vs_threes_fours']] = None
    opponent_type: Optional[str] = "random"  # "random", "greedy", "defensive"
    user_id: Optional[str] = None  # Optional user ID for match statistics
    initial_scores: Optional[dict] = None  # {"human": 115, "computer": 115} for testing end game
    # Future: explicit card lists like ["ace-hearts", "two-spades"], not used yet
    human_cards: Optional[List[str]] = None
    computer_cards: Optional[List[str]] = None


class GoogleAuthRequest(BaseModel):
    id_token: str



def _make_card(rank_name: str, suit_name: str) -> Card:
    return Card(rank_name + suit_name)


def _generate_cards_for_ranks(ranks: List[str], n: int) -> List[Card]:
    suits = list(Deck.SUITS)  # hearts, diamonds, clubs, spades
    cards: List[Card] = []
    i = 0
    while len(cards) < n:
        rank = ranks[i % len(ranks)]
        suit = suits[i % len(suits)]
        cards.append(_make_card(rank, suit))
        i += 1
    return cards


# In-memory game storage
games: Dict[str, GameSession] = {}


@app.get("/healthcheck")
def healthcheck():
    """Health check endpoint."""
    return {"status": "ok"}

@app.post("/auth/google")
def auth_google(req: GoogleAuthRequest):
    """Verify Google ID token and upsert user; return stable user_id."""
    try:
        # Verify token with strict audience
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured on backend")
        request = google_requests.Request()
        payload = id_token.verify_oauth2_token(req.id_token, request, audience=GOOGLE_CLIENT_ID)
        # Extract user info
        user_id = payload.get("sub")
        email = payload.get("email")
        name = payload.get("name")
        picture = payload.get("picture")
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid Google token: missing sub")
        # Upsert user
        upsert_google_user(user_id, email, name, picture)
        return {"user_id": user_id, "email": email, "name": name, "picture": picture}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid Google token: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth error: {e}")


@app.get("/opponents")
def get_opponents():
    """Get list of available opponent types."""
    opponents = []
    for opponent_type in list_opponent_types():
        strategy = get_opponent_strategy(opponent_type)
        opponents.append({
            "id": opponent_type,
            "name": strategy.get_name()
        })
    return {"opponents": opponents}


@app.get("/game/new")
def just_post_new_game(): 
    # Frontend is currently sending a get response instead of post, need to investigate
    return create_game(None)

@app.post("/game/new")
def create_game(req: Optional[CreateGameRequest] = None) -> GameStateResponse:
    """Create a new game with optional deterministic setup."""
    game_id = str(uuid.uuid4())
    
    # Get opponent type and user_id from request or use defaults
    opponent_type = "random"
    user_id = None
    if req:
        if req.opponent_type:
            opponent_type = req.opponent_type
            # Validate opponent type
            if opponent_type not in list_opponent_types():
                raise HTTPException(status_code=400, detail=f"Invalid opponent_type. Must be one of: {list_opponent_types()}")
        if req.user_id:
            user_id = req.user_id
    
    session = GameSession(game_id, opponent_type=opponent_type, user_id=user_id)

    # Set initial scores if specified
    if req and req.initial_scores:
        human_score = req.initial_scores.get("human", req.initial_scores.get("you", 0))
        computer_score = req.initial_scores.get("computer", 0)
        if human_score > 0:
            session.game.board.pegs["human"]['front'] = human_score
            session.game.board.pegs["human"]['rear'] = human_score
        if computer_score > 0:
            session.game.board.pegs["computer"]['front'] = computer_score
            session.game.board.pegs["computer"]['rear'] = computer_score

    # Configure dealer if specified
    if req and req.dealer:
        dealer_key = req.dealer.lower()
        if dealer_key in ("human", "you", "player"):
            session.next_dealer_override = session.human
        elif dealer_key == "computer":
            session.next_dealer_override = session.computer
        else:
            raise HTTPException(status_code=400, detail=f"Invalid dealer: {req.dealer}")

    # Configure preset hands if requested
    if req and req.preset:
        preset = req.preset
        if preset == 'aces_twos_vs_threes_fours':
            human_cards = _generate_cards_for_ranks(["ace", "two"], 6)
            computer_cards = _generate_cards_for_ranks(["three", "four"], 6)
            session.next_round_overrides = {
                'hands': {
                    session.human: human_cards,
                    session.computer: computer_cards,
                }
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown preset: {preset}")

    games[game_id] = session
    return session.advance()


@app.get("/game/{game_id}")
def get_game(game_id: str) -> GameStateResponse:
    """Get current game state."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    game_state = games[game_id].get_state()    
    return game_state


@app.post("/game/{game_id}/action")
def submit_action(game_id: str, action: PlayerAction) -> GameStateResponse:
    """Submit a player action."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    return games[game_id].submit_action(action.card_indices)


@app.delete("/game/{game_id}")
def delete_game(game_id: str):
    """Delete a game."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    del games[game_id]
    return {"status": "deleted"}


@app.get("/stats/{user_id}")
def get_stats(user_id: str):
    """Get aggregated match statistics for a user."""
    stats = get_user_stats(user_id)
    if not stats:
        return {"user_id": user_id, "stats": []}
    return {"user_id": user_id, "stats": stats}


@app.get("/stats/{user_id}/history")
def get_game_history_endpoint(user_id: str, opponent_id: Optional[str] = None, limit: int = 50):
    """Get individual game history for a user (for charting/analysis)."""
    history = db_get_game_history(user_id, opponent_id=opponent_id, limit=limit)
    return {
        "user_id": user_id,
        "opponent_id": opponent_id,
        "games": history
    }

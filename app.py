"""FastAPI backend for Cribbage game.

This API converts the synchronous cribbage game into a stateful web service.
The game maintains state between API calls and waits for player input via POST requests.
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Set
from enum import Enum
import uuid
import random

from cribbage.playingcards import Card, Deck
from cribbage import scoring


app = FastAPI(title="Cribbage API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== API Models =====

class ActionType(str, Enum):
    """Types of actions the game can request from the player."""
    SELECT_CRIB_CARDS = "select_crib_cards"
    SELECT_CARD_TO_PLAY = "select_card_to_play"
    WAITING_FOR_COMPUTER = "waiting_for_computer"
    GAME_OVER = "game_over"


class CardData(BaseModel):
    """Representation of a playing card for API responses."""
    rank: str
    suit: str
    symbol: str
    value: int


class PlayerAction(BaseModel):
    """Player's action submission."""
    card_indices: List[int]  # Indices of cards from hand: 2 for crib, 1 for play, 0 for "go"


class GameStateResponse(BaseModel):
    """Complete game state returned to frontend."""
    game_id: str
    action_required: ActionType
    message: str
    your_hand: List[CardData]
    table_cards: List[CardData]
    scores: Dict[str, int]  # {"you": 0, "computer": 0}
    dealer: str
    table_value: int
    starter_card: Optional[CardData] = None
    valid_card_indices: List[int]  # Which cards from hand can be played
    game_over: bool = False
    winner: Optional[str] = None


# ===== WebSocket Connection Manager =====


class ConnectionManager:
    """Tracks active websocket connections per game and broadcasts state changes."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, game_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(game_id, set()).add(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket):
        if game_id in self.active_connections:
            self.active_connections[game_id].discard(websocket)
            if not self.active_connections[game_id]:
                self.active_connections.pop(game_id, None)

    async def send_state(self, websocket: WebSocket, state: GameStateResponse):
        await websocket.send_json(state.model_dump())

    async def broadcast_state(self, game_id: str, state: GameStateResponse):
        connections = list(self.active_connections.get(game_id, set()))
        for connection in connections:
            try:
                await self.send_state(connection, state)
            except WebSocketDisconnect:
                self.disconnect(game_id, connection)
            except Exception:
                # Drop any connection that fails to send
                self.disconnect(game_id, connection)


# ===== Game State Management =====

class GameState:
    """Manages the state of a single cribbage game."""
    
    MAX_SCORE = 121
    
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.deck = Deck()
        
        # Player hands
        self.human_hand: List[Card] = []
        self.computer_hand: List[Card] = []
        
        # Game state
        self.crib: List[Card] = []
        self.table: List[Dict] = []  # [{"player": "human"|"computer", "card": Card}, ...]
        self.starter: Optional[Card] = None
        
        # Scoring
        self.scores = {"you": 0, "computer": 0}
        self.dealer = random.choice(["you", "computer"])
        
        # Round state
        self.waiting_for_action = None  # Type of action needed
        self.current_player = "you" if self.dealer == "computer" else "computer"
        self.sequence_start_idx = 0
        self.active_players = []
        self.game_over = False
        self.winner = None
        
        # Round phase tracking
        self.phase = "deal"  # deal, crib, play, score
        self.crib_cards_received = {"you": False, "computer": False}
        self.last_message = ""
        
    def start_round(self):
        """Deal cards and start a new round."""
        self.deck = Deck()
        for _ in range(3):
            self.deck.shuffle()
        
        # Deal 6 cards to each player
        self.human_hand = [self.deck.draw() for _ in range(6)]
        self.computer_hand = [self.deck.draw() for _ in range(6)]
        
        self.crib = []
        self.table = []
        self.starter = None
        self.sequence_start_idx = 0
        self.phase = "crib"
        self.crib_cards_received = {"you": False, "computer": False}
        
        # Non-dealer selects crib cards first
        if self.dealer == "you":
            self._computer_select_crib()
            self.waiting_for_action = ActionType.SELECT_CRIB_CARDS
            self.last_message = "Select 2 cards to place in the crib"
        else:
            self.waiting_for_action = ActionType.SELECT_CRIB_CARDS
            self.last_message = "Select 2 cards to place in the crib"
    
    def _computer_select_crib(self):
        """Computer randomly selects crib cards."""
        cards_to_crib = random.sample(self.computer_hand, 2)
        for card in cards_to_crib:
            self.crib.append(card)
            self.computer_hand.remove(card)
        self.crib_cards_received["computer"] = True
    
    def submit_crib_cards(self, card_indices: List[int]):
        """Player submits cards for the crib."""
        if len(card_indices) != 2:
            raise ValueError("Must select exactly 2 cards for the crib")
        
        cards_to_crib = [self.human_hand[i] for i in sorted(card_indices, reverse=True)]
        for card in cards_to_crib:
            self.crib.append(card)
            self.human_hand.remove(card)
        
        self.crib_cards_received["you"] = True
        
        # If dealer hasn't selected yet, computer does so now
        if not self.crib_cards_received["computer"]:
            self._computer_select_crib()
        
        # Cut for starter
        self.deck.shuffle()
        self.starter = self.deck.draw()
        
        # Check for "his heels" (Jack as starter)
        if self.starter.get_rank() == 'jack':
            self.scores[self.dealer] += 2
            self.last_message = f"Starter is {self._card_str(self.starter)}. 2 points for his heels!"
        else:
            self.last_message = f"Starter card: {self._card_str(self.starter)}"
        
        # Start play phase
        self.phase = "play"
        non_dealer = "computer" if self.dealer == "you" else "you"
        self.current_player = non_dealer
        self.active_players = [non_dealer, self.dealer]
        
        self._advance_play()
    
    def _advance_play(self):
        """Advance the play phase."""
        # Check if round is over
        if not self.human_hand and not self.computer_hand:
            self._score_hands()
            return
        
        # Check if anyone can play
        if not self.active_players:
            # Award point for last card
            if self.table:
                last_player = self.table[-1]["player"]
                self.scores[last_player] += 1
                self.last_message = f"1 point to {last_player} for last card"
            
            # Start new sequence
            self.sequence_start_idx = len(self.table)
            self.active_players = []
            if self.human_hand:
                self.active_players.append("you")
            if self.computer_hand:
                self.active_players.append("computer")
            
            if not self.active_players:
                # No cards left, score hands
                self._score_hands()
                return
            
            # Non-dealer goes first in new sequence
            non_dealer = "computer" if self.dealer == "you" else "you"
            if non_dealer in self.active_players:
                self.current_player = non_dealer
            else:
                self.current_player = self.dealer
        
        # Computer's turn
        while self.current_player == "computer" and self.active_players:
            self._computer_play_card()
            if not self.active_players or not self.computer_hand:
                break
            self._switch_player()
        
        # Check again if round is over
        if not self.human_hand and not self.computer_hand:
            self._score_hands()
            return
        
        # Now it's the human's turn if they're active
        if self.current_player == "you" and "you" in self.active_players:
            self.waiting_for_action = ActionType.SELECT_CARD_TO_PLAY
            valid_indices = self._get_valid_card_indices()
            if valid_indices:
                self.last_message = f"Table value: {self._get_table_value()}. Select a card to play"
            else:
                self.last_message = "No valid cards - must say 'Go'"
        else:
            # Should not happen, but safety check
            self.waiting_for_action = ActionType.WAITING_FOR_COMPUTER
    
    def _computer_play_card(self):
        """Computer plays a card or says go."""
        valid_cards = [c for c in self.computer_hand 
                      if c.get_value() + self._get_table_value() <= 31]
        
        if not valid_cards:
            # Computer says "go"
            self.active_players.remove("computer")
            self.last_message = "Computer says 'Go'"
        else:
            card = random.choice(valid_cards)
            self.table.append({"player": "computer", "card": card})
            self.computer_hand.remove(card)
            
            if not self.computer_hand:
                if "computer" in self.active_players:
                    self.active_players.remove("computer")
            
            # Score the play
            table_value = self._get_table_value()
            score = self._score_play([move['card'] for move in self.table[self.sequence_start_idx:]])
            if score:
                self.scores["computer"] += score
                self.last_message = f"Computer plays {self._card_str(card)}. {score} points! (Total: {table_value})"
            else:
                self.last_message = f"Computer plays {self._card_str(card)} (Total: {table_value})"
    
    def submit_play_card(self, card_indices: List[int]):
        """Player submits a card to play or 'go'."""
        if len(card_indices) == 0:
            # Player says "go"
            if "you" in self.active_players:
                self.active_players.remove("you")
            self.last_message = "You say 'Go'"
        elif len(card_indices) == 1:
            card = self.human_hand[card_indices[0]]
            
            # Validate play
            if card.get_value() + self._get_table_value() > 31:
                raise ValueError("Card would exceed 31")
            
            self.table.append({"player": "you", "card": card})
            self.human_hand.remove(card)
            
            if not self.human_hand:
                if "you" in self.active_players:
                    self.active_players.remove("you")
            
            # Score the play
            table_value = self._get_table_value()
            score = self._score_play([move['card'] for move in self.table[self.sequence_start_idx:]])
            if score:
                self.scores["you"] += score
                self.last_message = f"You play {self._card_str(card)}. {score} points! (Total: {table_value})"
            else:
                self.last_message = f"You play {self._card_str(card)} (Total: {table_value})"
        else:
            raise ValueError("Must select exactly 1 card to play (or 0 for 'go')")
        
        self._switch_player()
        self._advance_play()
    
    def _switch_player(self):
        """Switch to the other player."""
        if self.current_player == "you":
            self.current_player = "computer"
        else:
            self.current_player = "you"
    
    def _get_table_value(self) -> int:
        """Get the value of cards in the current sequence."""
        return sum(move['card'].get_value() 
                  for move in self.table[self.sequence_start_idx:])
    
    def _get_valid_card_indices(self) -> List[int]:
        """Get indices of cards that can be played."""
        table_value = self._get_table_value()
        return [i for i, card in enumerate(self.human_hand)
                if card.get_value() + table_value <= 31]
    
    def _score_play(self, card_seq: List[Card]) -> int:
        """Score the current play."""
        score = 0
        score_scenarios = [
            scoring.ExactlyEqualsN(n=15),
            scoring.ExactlyEqualsN(n=31),
            scoring.HasPairTripleQuad(),
            scoring.HasStraight_DuringPlay()
        ]
        for scenario in score_scenarios:
            s, _ = scenario.check(card_seq[:])
            score += s
        return score
    
    def _score_hands(self):
        """Score hands and crib at end of round."""
        # Score non-dealer's hand first
        non_dealer = "computer" if self.dealer == "you" else "you"
        
        # Get cards that each player played
        you_played = [move['card'] for move in self.table if move['player'] == 'you']
        comp_played = [move['card'] for move in self.table if move['player'] == 'computer']
        
        # Score hands (with starter)
        you_score = self._score_hand(you_played + [self.starter])
        comp_score = self._score_hand(comp_played + [self.starter])
        
        self.scores["you"] += you_score
        self.scores["computer"] += comp_score
        
        # Score crib (belongs to dealer)
        crib_score = self._score_hand(self.crib + [self.starter])
        self.scores[self.dealer] += crib_score
        
        self.last_message = f"Hand scoring: You: {you_score}, Computer: {comp_score}, Crib: {crib_score} (to {self.dealer})"
        
        # Check for game over
        if self.scores["you"] >= self.MAX_SCORE or self.scores["computer"] >= self.MAX_SCORE:
            self.game_over = True
            if self.scores["you"] >= self.MAX_SCORE:
                self.winner = "you"
                self.last_message = "Game Over! You won!"
            else:
                self.winner = "computer"
                self.last_message = "Game Over! Computer won!"
            self.waiting_for_action = ActionType.GAME_OVER
        else:
            # Start next round
            self.dealer = "computer" if self.dealer == "you" else "you"
            self.start_round()
    
    def _score_hand(self, cards: List[Card]) -> int:
        """Score a hand."""
        score = 0
        score_scenarios = [
            scoring.CountCombinationsEqualToN(n=15),
            scoring.HasPairTripleQuad(),
            scoring.HasStraight_InHand(),
            scoring.HasFlush()
        ]
        for scenario in score_scenarios:
            s, _ = scenario.check(cards[:])
            score += s
        return score
    
    def _card_str(self, card: Card) -> str:
        """Get string representation of card."""
        return str(card)
    
    def get_state_response(self) -> GameStateResponse:
        """Get the current game state as an API response."""
        return GameStateResponse(
            game_id=self.game_id,
            action_required=self.waiting_for_action or ActionType.WAITING_FOR_COMPUTER,
            message=self.last_message,
            your_hand=[self._card_to_data(c) for c in self.human_hand],
            table_cards=[self._card_to_data(move['card']) for move in self.table[self.sequence_start_idx:]],
            scores=self.scores.copy(),
            dealer=self.dealer,
            table_value=self._get_table_value(),
            starter_card=self._card_to_data(self.starter) if self.starter else None,
            valid_card_indices=self._get_valid_card_indices() if self.waiting_for_action == ActionType.SELECT_CARD_TO_PLAY else [],
            game_over=self.game_over,
            winner=self.winner
        )
    
    def _card_to_data(self, card: Card) -> CardData:
        """Convert Card to CardData."""
        return CardData(
            rank=card.get_rank(),
            suit=card.get_suit(),
            symbol=str(card),
            value=card.get_value()
        )


# ===== In-memory game storage =====
games: Dict[str, GameState] = {}
manager = ConnectionManager()


# ===== API Endpoints =====

@app.post("/game/new", response_model=GameStateResponse)
async def create_game():
    """Create a new game and start the first round."""
    game_id = str(uuid.uuid4())
    game = GameState(game_id)
    games[game_id] = game
    
    game.start_round()
    state = game.get_state_response()
    await manager.broadcast_state(game_id, state)
    return state


@app.get("/game/{game_id}", response_model=GameStateResponse)
async def get_game_state(game_id: str):
    """Get the current state of a game."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    return games[game_id].get_state_response()


@app.websocket("/ws/{game_id}")
async def websocket_game_state(websocket: WebSocket, game_id: str):
    """WebSocket endpoint to stream game state updates in real time."""
    if game_id not in games:
        await websocket.close(code=1008)
        return
    await manager.connect(game_id, websocket)
    try:
        # Send initial state
        await manager.send_state(websocket, games[game_id].get_state_response())
        # Keep the connection alive; incoming messages are ignored (client pushes via REST)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)


@app.post("/game/{game_id}/action", response_model=GameStateResponse)
async def submit_action(game_id: str, action: PlayerAction):
    """Submit a player action (crib cards or card to play)."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = games[game_id]
    
    try:
        if game.waiting_for_action == ActionType.SELECT_CRIB_CARDS:
            game.submit_crib_cards(action.card_indices)
        elif game.waiting_for_action == ActionType.SELECT_CARD_TO_PLAY:
            game.submit_play_card(action.card_indices)
        else:
            raise HTTPException(status_code=400, detail="No action expected at this time")
        state = game.get_state_response()
        await manager.broadcast_state(game_id, state)
        return state
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/game/{game_id}")
async def delete_game(game_id: str):
    """Delete a game session."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    del games[game_id]
    return {"status": "deleted"}


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Cribbage API is running",
        "active_games": len(games)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

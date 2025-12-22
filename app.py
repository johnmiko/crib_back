"""FastAPI backend for Cribbage game using existing cribbagegame classes."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional, List
import uuid

from cribbage.cribbagegame import CribbageGame, CribbageRound
from cribbage.player import Player, RandomPlayer
from cribbage.models import ActionType, GameStateResponse, PlayerAction, CardData
from cribbage.playingcards import Card


app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


class APIPlayer(Player):
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
    
    def select_crib_cards(self, hand):
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
    
    def select_card_to_play(self, hand, table, crib):
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


def card_to_data(card: Card) -> CardData:
    """Convert a Card object to CardData."""
    return CardData(
        rank=card.get_rank(),
        suit=card.get_suit(),
        value=card.get_value(),
        symbol=str(card)
    )


class ResumableRound:
    """Wrapper around CribbageRound that can be paused and resumed."""
    
    def __init__(self, game, dealer):
        self.round = CribbageRound(game=game, dealer=dealer)
        self.phase = 'start'
        self.active_players = None
        self.sequence_start_idx = 0
        
    def run(self):
        """Run the round until completion or until player input needed."""
        r = self.round
        
        if self.phase == 'start':
            r._cut()
            r._deal()
            self.phase = 'crib'
        
        if self.phase == 'crib':
            r._populate_crib()  # May raise AwaitingPlayerInput
            r._cut()
            r.starter = r.deck.draw()
            if r.starter.get_rank() == 'jack':
                r.game.board.peg(r.dealer, 1)
            self.active_players = [r.nondealer, r.dealer]
            self.phase = 'play'
        
        if self.phase == 'play':
            while sum([len(v) for v in r.hands.values()]):
                self.sequence_start_idx = len(r.table)
                
                while self.active_players:
                    players_to_check = list(self.active_players)
                    for p in players_to_check:
                        card = p.select_card_to_play(
                            hand=r.hands[p],
                            table=r.table[self.sequence_start_idx:],
                            crib=r.crib
                        )  # May raise AwaitingPlayerInput
                        
                        if card is None or card.get_value() + r.get_table_value(self.sequence_start_idx) > 31:
                            self.active_players.remove(p)
                        else:
                            r.table.append({'player': p, 'card': card})
                            r.hands[p].remove(card)
                            if not r.hands[p]:
                                self.active_players.remove(p)
                            score = r._score_play(card_seq=[move['card'] for move in r.table[self.sequence_start_idx:]])
                            if score:
                                r.game.board.peg(p, score)
                
                r.go_or_31_reached(self.active_players)
                self.active_players = [p for p in r.game.players if r.hands[p]]
            
            self.phase = 'scoring'
        
        if self.phase == 'scoring':
            for p in r.game.players:
                p_cards_played = [move['card'] for move in r.table if move['player'] == p]
                score = r._score_hand(cards=p_cards_played + [r.starter])
                if score:
                    r.game.board.peg(p, score)
            
            score = r._score_hand(cards=(r.crib + [r.starter]))
            if score:
                r.game.board.peg(r.dealer, score)
            
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


class GameSession:
    """Manages a single game session with pause/resume capability."""
    
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.human = APIPlayer("human")
        self.computer = RandomPlayer("computer")
        self.game = CribbageGame(players=[self.human, self.computer])
        self.current_round: Optional[ResumableRound] = None
        self.waiting_for: Optional[ActionType] = None
        self.message: str = ""
        self.last_cards: List[Card] = []
        self.last_n_cards: int = 0
        self.game_over: bool = False
        self.round_num: int = 0
        
    def get_state(self) -> GameStateResponse:
        """Get current game state."""
        your_hand = []
        table_cards = []
        table_value = 0
        starter_card = None
        valid_indices = []
        
        if self.current_round:
            your_hand = [card_to_data(c) for c in self.current_round.hands.get(self.human, [])]
            table_cards = [card_to_data(m['card']) for m in self.current_round.table]
            
            if self.current_round.table:
                # Find the current sequence start
                sequence_start = 0
                for i in range(len(self.current_round.table) - 1, -1, -1):
                    val_sum = sum(m['card'].get_value() for m in self.current_round.table[i:])
                    if val_sum > 31:
                        sequence_start = i + 1
                        break
                table_value = sum(m['card'].get_value() for m in self.current_round.table[sequence_start:])
            
            if self.current_round.starter:
                starter_card = card_to_data(self.current_round.starter)
            
            # Calculate valid card indices
            if self.waiting_for == ActionType.SELECT_CARD_TO_PLAY:
                for i, card in enumerate(self.current_round.hands.get(self.human, [])):
                    if card.get_value() + table_value <= 31:
                        valid_indices.append(i)
            elif self.waiting_for == ActionType.SELECT_CRIB_CARDS:
                valid_indices = list(range(len(your_hand)))
        
        # Check for winner
        winner = None
        for p in self.game.players:
            if self.game.board.get_score(p) >= 121:
                self.game_over = True
                winner = str(p).lower()
                break
        
        # Get dealer
        dealer = "none"
        if self.current_round and self.current_round.dealer:
            dealer = str(self.current_round.dealer).lower()
        
        return GameStateResponse(
            game_id=self.game_id,
            action_required=self.waiting_for or ActionType.WAITING_FOR_COMPUTER,
            message=self.message,
            your_hand=your_hand,
            table_cards=table_cards,
            scores={str(p).lower(): self.game.board.get_score(p) for p in self.game.players},
            dealer=dealer,
            table_value=table_value,
            starter_card=starter_card,
            valid_card_indices=valid_indices,
            game_over=self.game_over,
            winner=winner
        )
    
    def start_new_round(self):
        """Start a new round."""
        dealer = self.game.players[self.round_num % len(self.game.players)]
        self.current_round = ResumableRound(game=self.game, dealer=dealer)
        self.round_num += 1
    
    def advance(self) -> GameStateResponse:
        """Advance the game until player input is needed."""
        try:
            # Start new round if needed
            if self.current_round is None:
                self.start_new_round()
            
            # Run the round (will pause if player input needed)
            self.current_round.run()
            
            # If we reach here without exception, round completed
            # Check if game is over
            for p in self.game.players:
                if self.game.board.get_score(p) >= 121:
                    self.game_over = True
                    self.message = f"Game over! {p} wins!"
                    return self.get_state()
            
            # Start new round
            self.current_round = None
            return self.advance()
            
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
        """Advance the game until player input is needed."""
        try:
            # Start new round if needed
            if self.current_round is None:
                self.start_new_round()
            
            # Call play() - it will either complete or pause for input
            # We wrap it to make repeated calls safe
            r = self.current_round
            
            # Skip initialization if already done (check if hands are populated)
            if not any(r.hands.values()):
                # First time playing this round - hands are empty
                r.play()
            else:
                # Resuming - manually continue from where we left off
                # Since we can't easily resume play(), just call it again
                # but skip the parts already done
                
                # The issue is play() will re-cut, re-deal, re-populate-crib
                # We need to prevent this. Let's set a flag.
                if not hasattr(r, '_initialized'):
                    r._initialized = True
                    r.play()
                else:
                    # Already initialized, just run the remaining parts
                    # This is complex - we'd need to replicate play() logic
                    # For now, let's just call play() and make it idempotent
                    
                    # Save current state
                    saved_hands = {p: list(r.hands[p]) for p in r.hands}
                    saved_crib = list(r.crib)
                    saved_table = list(r.table)
                    saved_starter = r.starter
                    
                    # Call play() which will try to re-initialize
                    try:
                        r.play()
                    except AssertionError as e:
                        # If we get assertion errors about crib size, restore state and skip
                        if "Crib size" in str(e):
                            # Restore state
                            r.hands = saved_hands
                            r.crib = saved_crib
                            r.table = saved_table
                            r.starter = saved_starter
                            # The round is already complete or stuck
                            # Mark as complete and move on
                            pass
                        else:
                            raise
            
            # If we reach here without exception, round completed
            # Check if game is over
            for p in self.game.players:
                if self.game.board.get_score(p) >= 121:
                    self.game_over = True
                    self.message = f"Game over! {p} wins!"
                    return self.get_state()
            
            # Start new round
            self.current_round = None
            return self.advance()
            
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


# In-memory game storage
games: Dict[str, GameSession] = {}


@app.get("/healthcheck")
def healthcheck():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/game/new")
def create_game() -> GameStateResponse:
    """Create a new game."""
    game_id = str(uuid.uuid4())
    session = GameSession(game_id)
    games[game_id] = session
    return session.advance()


@app.get("/game/{game_id}")
def get_game(game_id: str) -> GameStateResponse:
    """Get current game state."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    return games[game_id].get_state()


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

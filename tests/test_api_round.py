"""Test API round with specific card deals to verify beginner player behavior."""

from fastapi.testclient import TestClient
from app import app, GameSession, ResumableRound
from cribbage.playingcards import Card, build_hand
from cribbage.players.beginner_player import BeginnerPlayer
from cribbage.players.base_player import BasePlayer
import pytest


class BeginnerPlayerAPIAdapter(BasePlayer):
    """Adapter to make BeginnerPlayer work with the API's interface."""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.beginner = BeginnerPlayer(name)
    
    def select_crib_cards(self, hand, dealer_is_self, your_score=None, opponent_score=None):
        """Select cards for the crib."""
        return self.beginner.select_crib_cards(hand, dealer_is_self, your_score, opponent_score)
    
    def select_card_to_play(self, hand, table, crib):
        """Select a card to play - adapt API interface to BeginnerPlayer interface."""
        # Extract cards from table (table contains dicts with 'player' and 'card' keys)
        table_cards = [entry['card'] if isinstance(entry, dict) else entry for entry in table]
        table_value = sum(c.get_value() for c in table_cards)
        return self.beginner.select_card_to_play(hand, table_cards, table_value)


class ManualPlayer(BasePlayer):
    """Player that plays cards according to a predefined sequence."""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.cards_to_discard = None
        self.cards_to_play = []
        self.play_index = 0
    
    def set_discard(self, cards):
        """Set the cards this player will discard to crib."""
        self.cards_to_discard = cards
    
    def set_play_sequence(self, cards):
        """Set the sequence of cards this player will play."""
        self.cards_to_play = cards
        self.play_index = 0
    
    def select_crib_cards(self, hand, dealer_is_self, your_score=None, opponent_score=None):
        """Select cards for the crib based on predetermined choice."""
        if self.cards_to_discard is None:
            raise ValueError("No discard cards set for ManualPlayer")
        # Find the cards in hand that match the ranks we want to discard
        cards_to_return = []
        for discard_card in self.cards_to_discard:
            for hand_card in hand:
                if hand_card.rank == discard_card.rank and hand_card.suit == discard_card.suit:
                    cards_to_return.append(hand_card)
                    break
        if len(cards_to_return) != 2:
            raise ValueError(f"Could not find exactly 2 cards to discard. Found {len(cards_to_return)}")
        return cards_to_return
    
    def select_card_to_play(self, hand, table, crib=None):
        """Play cards according to the predetermined sequence."""
        # Extract cards from table (table contains dicts with 'player' and 'card' keys)
        table_cards = [entry['card'] if isinstance(entry, dict) else entry for entry in table]
        table_value = sum(c.get_value() for c in table_cards)
        
        if self.play_index >= len(self.cards_to_play):
            # No more cards in sequence, play first valid card or None
            for card in hand:
                if card.get_value() + table_value <= 31:
                    return card
            return None
        
        card_to_play = self.cards_to_play[self.play_index]
        self.play_index += 1
        
        # Find the card in hand that matches
        for hand_card in hand:
            if hand_card.rank == card_to_play.rank and hand_card.suit == card_to_play.suit:
                return hand_card
        
        raise ValueError(f"Card {card_to_play} not found in hand {hand}")


def test_beginner_player_pegging_behavior():
    """Test that beginner player plays cards as expected against a specific hand.
    
    Setup:
    - Beginner player: 5♥, 5♦, 6♣, 7♠, 9♥, Q♦ (no flush)
    - User player: 6♥, 7♥, 8♥, 8♦, 2♣, 4♠ (no flush)
    - User discards: 2♣, 4♠
    - User plays: 8♥, 8♦, 7♥, 6♥
    
    This test will verify:
    1. What cards the beginner player discards
    2. What order the beginner player plays their cards
    3. The resulting table_history
    """
    # Create players
    beginner = BeginnerPlayerAPIAdapter(name="computer")
    user = ManualPlayer(name="human")
    
    # Set up user's predetermined actions
    user.set_discard([Card('2c'), Card('4s')])
    user.set_play_sequence([Card('8h'), Card('8d'), Card('7h'), Card('6h')])
    
    # Create game with these players
    from cribbage.cribbagegame import CribbageGame
    game = CribbageGame([beginner, user])
    
    # Create a round with beginner as dealer
    round_wrapper = ResumableRound(game=game, dealer=beginner)
    
    # Set up the specific hands
    beginner_hand = build_hand(['5h', '5d', '6c', '7s', '9h', 'qd'])
    user_hand = build_hand(['6h', '7h', '8h', '8d', '2c', '4s'])
    
    round_wrapper.overrides = {
        'hands': {
            'computer': beginner_hand,
            'human': user_hand
        }
    }
    
    # Run the round
    round_wrapper.run()
    
    # Get the round object
    r = round_wrapper.round
    
    # Check what cards were dealt
    print(f"\nBeginner dealt: {[str(c) for c in beginner_hand]}")
    print(f"User dealt: {[str(c) for c in user_hand]}")
    
    # Check what was discarded to crib
    print(f"\nCrib: {[str(c) for c in r.crib]}")
    
    # Check what hands are after discard
    print(f"Beginner hand after discard: {[str(c) for c in r.player_hand_after_discard['computer']]}")
    print(f"User hand after discard: {[str(c) for c in r.player_hand_after_discard['human']]}")
    
    # Check the starter card
    print(f"\nStarter: {r.starter}")
    
    # Check the play sequence (table history)
    print(f"\nTable history ({len(r.table)} plays):")
    for i, move in enumerate(r.table):
        player_name = move['player'].name
        card = move['card']
        print(f"  {i+1}. {player_name}: {card}")
    
    # Print full play record for detailed analysis
    print(f"\nPlay record:")
    for pr in r.play_record:
        print(f"  {pr}")
    
    # Placeholder assertion - user will inspect output and write proper assertions
    assert False, "Inspect the output above to verify beginner player behavior"

"""Opponent strategies for computer players."""
import random
from abc import ABC, abstractmethod
from typing import List
from .playingcards import Card


class OpponentStrategy(ABC):
    """Base class for opponent decision-making strategies."""
    
    @abstractmethod
    def select_crib_cards(self, hand: List[Card]) -> List[Card]:
        """Select 2 cards to place in the crib.
        
        Args:
            hand: List of cards in the player's hand
            
        Returns:
            List of 2 cards to place in the crib
        """
        pass
    
    @abstractmethod
    def select_card_to_play(self, hand: List[Card], table: List[Card], table_value: int) -> Card:
        """Select a card to play from hand.
        
        Args:
            hand: List of cards in the player's hand
            table: List of cards on the table in current sequence
            table_value: Current table value (sum of card values)
            
        Returns:
            Card to play, or None if no valid play
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the display name for this opponent strategy."""
        pass


class RandomOpponent(OpponentStrategy):
    """Opponent that makes completely random decisions."""
    
    def select_crib_cards(self, hand: List[Card]) -> List[Card]:
        return random.sample(hand, 2)
    
    def select_card_to_play(self, hand: List[Card], table: List[Card], table_value: int) -> Card:
        # Filter to valid cards that won't exceed 31
        valid_cards = [c for c in hand if c.get_value() + table_value <= 31]
        if not valid_cards:
            return None
        return random.choice(valid_cards)
    
    def get_name(self) -> str:
        return "Random"


class GreedyOpponent(OpponentStrategy):
    """Opponent that tries to score points aggressively (placeholder for future implementation)."""
    
    def select_crib_cards(self, hand: List[Card]) -> List[Card]:
        # TODO: Implement greedy crib selection (keep high-scoring combinations)
        # For now, just use random selection
        return random.sample(hand, 2)
    
    def select_card_to_play(self, hand: List[Card], table: List[Card], table_value: int) -> Card:
        # TODO: Implement greedy play (prioritize 15s, pairs, runs)
        # For now, just use random selection
        valid_cards = [c for c in hand if c.get_value() + table_value <= 31]
        if not valid_cards:
            return None
        return random.choice(valid_cards)
    
    def get_name(self) -> str:
        return "Greedy"


class DefensiveOpponent(OpponentStrategy):
    """Opponent that plays defensively to minimize opponent's scoring (placeholder for future implementation)."""
    
    def select_crib_cards(self, hand: List[Card]) -> List[Card]:
        # TODO: Implement defensive crib selection
        # For now, just use random selection
        return random.sample(hand, 2)
    
    def select_card_to_play(self, hand: List[Card], table: List[Card], table_value: int) -> Card:
        # TODO: Implement defensive play (avoid giving opponent scoring opportunities)
        # For now, just use random selection
        valid_cards = [c for c in hand if c.get_value() + table_value <= 31]
        if not valid_cards:
            return None
        return random.choice(valid_cards)
    
    def get_name(self) -> str:
        return "Defensive"


# Registry of available opponents
OPPONENT_REGISTRY = {
    "random": RandomOpponent,
    "greedy": GreedyOpponent,
    "defensive": DefensiveOpponent,
}


def get_opponent_strategy(opponent_type: str = "random") -> OpponentStrategy:
    """Get an opponent strategy instance by type.
    
    Args:
        opponent_type: Type of opponent ("random", "greedy", "defensive")
        
    Returns:
        OpponentStrategy instance
        
    Raises:
        ValueError: If opponent_type is not recognized
    """
    if opponent_type not in OPPONENT_REGISTRY:
        raise ValueError(f"Unknown opponent type: {opponent_type}. Available: {list(OPPONENT_REGISTRY.keys())}")
    return OPPONENT_REGISTRY[opponent_type]()


def list_opponent_types() -> List[str]:
    """Get list of available opponent types."""
    return list(OPPONENT_REGISTRY.keys())

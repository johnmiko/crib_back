import torch
from .playingcards import Card
from .features import encode_state, D_TOTAL  # You may need to port or adapt this from crib_ai_trainer2
from .opponents import OpponentStrategy

class BestAIOpponent(OpponentStrategy):
    """Opponent using the best neural network model (best-ai.pt)."""
    def __init__(self, model_path=None):
        if model_path is None:
            from pathlib import Path
            model_path = Path(__file__).parent.parent / "best-ai.pt"
        self.model = torch.load(model_path, map_location=torch.device('cpu'))
        self.model.eval()
        # Fallback: use random if model fails
        from .opponents import RandomOpponent
        self.teacher = RandomOpponent()

    def select_crib_cards(self, hand):
        # Dummy implementation: use model to pick two cards to throw
        # You may want to adapt this logic to match your model's expected input
        try:
            starter = Card({'name': 'five', 'symbol': '5', 'value': 5, 'rank': 5, 'unicode_flag': '5'}, {'name': 'spades', 'symbol': '♠', 'unicode_flag': 'A'})
            seen = []
            count = 0
            history = []
            x = encode_state(hand, starter, seen, count, history)
            x = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                logits = self.model(x)
                # Pick two highest indices as cards to throw
                top2 = torch.topk(logits[0], 2).indices.tolist()
            throw = [card for card in hand if hasattr(card, 'to_index') and card.to_index() in top2]
            if len(throw) == 2:
                return throw
        except Exception:
            pass
        return self.teacher.select_crib_cards(hand)

    def select_card_to_play(self, hand, table, table_value):
        # Use model to pick a card to play
        try:
            playable = [c for c in hand if c.get_value() + table_value <= 31]
            if not playable:
                return None
            starter = Card({'name': 'five', 'symbol': '5', 'value': 5, 'rank': 5, 'unicode_flag': '5'}, {'name': 'spades', 'symbol': '♠', 'unicode_flag': 'A'})
            seen = []
            count = table_value
            history = table
            x = encode_state(playable, starter, seen, count, history)
            x = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                logits = self.model(x)
                action_idx = torch.argmax(logits, dim=1).item()
            for card in playable:
                if hasattr(card, 'to_index') and card.to_index() == action_idx:
                    return card
        except Exception:
            pass
        return self.teacher.select_card_to_play(hand, table, table_value)

    def get_name(self):
        return "BestAI"

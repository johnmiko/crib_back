


from cribbage.cribbagegameapi import CribbageGame
from cribbage.player import HumanPlayer, RandomPlayer


def main():
	players = [HumanPlayer("You"), RandomPlayer("Computer")]
	game = CribbageGame(players=players)
	game.start()


if __name__ == "__main__":
	main()

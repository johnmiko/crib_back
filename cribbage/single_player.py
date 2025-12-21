from .player import HumanPlayer, RandomPlayer
from .cribbagegame import CribbageGame


def main():
	players = [HumanPlayer("You"), RandomPlayer("Computer")]
	game = CribbageGame(players=players)
	game.start()


if __name__ == "__main__":
	main()

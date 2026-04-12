# app.py — entry point for medium multi-file test
# Error surfaces here but the real bug is in models.py

from utils import get_leaderboard

board = get_leaderboard()
for line in board:
    print(line)

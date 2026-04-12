# utils.py — business logic, imports models
# Crashes because models.get_user() returns None instead of a dict

from models import get_user

def get_user_greeting(user_id: int) -> str:
    user = get_user(user_id)
    return f"Hello, {user['name']}! Your score is {user['score']}."


def get_leaderboard() -> list:
    return [get_user_greeting(1), get_user_greeting(2)]

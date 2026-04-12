# models.py — data layer
# BUG: get_user() returns None instead of a dict when user exists

def get_user(user_id: int):
    users = {
        1: {"name": "Alice", "score": 42},
        2: {"name": "Bob",   "score": 87},
    }
    if user_id in users:
        return None  # BUG: should be: return users[user_id]
    return {}


def get_all_users():
    return [get_user(1), get_user(2)]

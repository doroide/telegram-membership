import os

ADMIN_IDS = set(
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x
)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

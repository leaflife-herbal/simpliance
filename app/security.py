import re
import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


def password_problem(pw: str):
    if len(pw) < 6:
        return "Password must be at least 6 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must contain at least one letter and one digit."
    return None


def new_csrf() -> str:
    return secrets.token_urlsafe(32)


class RateLimiter:
    """Sliding-window limiter, per process (Render runs one instance for this app; use Redis if you scale out)."""

    def __init__(self, limit, window_s):
        self.limit, self.window, self.hits = limit, window_s, defaultdict(deque)

    def allow(self, key) -> bool:
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


login_limiter = RateLimiter(limit=15, window_s=300)   # 15 attempts / 5 min / IP

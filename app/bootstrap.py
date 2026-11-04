"""Creates the one Super Admin from environment variables (no public sign-up page exists).

* On Render's free plan there is no shell, so this runs automatically at start-up: if SUPERADMIN_USERNAME and
  SUPERADMIN_PASSWORD are set and no Super Admin exists yet, the account is created (password must be changed at
  first sign-in). After the first successful start, delete SUPERADMIN_PASSWORD from the Render environment.
* Locally you can also run:  python -m app.bootstrap
"""
import os
import sys

from sqlalchemy import func, select

from . import services
from .db import SessionLocal
from .models import ROLE_SUPER, User


def from_env() -> str:
    user, pw = os.getenv("SUPERADMIN_USERNAME"), os.getenv("SUPERADMIN_PASSWORD")
    if not user or not pw:
        return "no SUPERADMIN_* variables set"
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_SUPER)):
            return "a Super Admin already exists"
        services.create_super_admin(db, user, os.getenv("SUPERADMIN_NAME", "Super Admin"), pw)
        db.commit()
    return "Super Admin created - change the password at first sign-in and remove SUPERADMIN_PASSWORD"


def main():
    try:
        print(from_env())
    except (services.Invalid, services.Denied) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()

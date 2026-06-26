"""Promote a user to admin by email (creating the user if absent).

Usage (from backend/):
    uv run python scripts/seed_admin.py --email admin@truboard.com [--name "Admin"]

Admin assignment is IT-managed in the DB (FRD FR-AUTH-002). In dev a synthetic
microsoft_oid is generated; it is overwritten on the user's first real login.
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from db.connection import AsyncSessionLocal  # noqa: E402
from db.models import User  # noqa: E402


async def seed_admin(email: str, name: str | None) -> None:
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(
                slug=f"dev-{uuid.uuid4()}",
                email=email,
                display_name=name or email.split("@")[0],
                is_admin=True,
            )
            session.add(user)
            action = "created admin"
        else:
            user.is_admin = True
            if name:
                user.display_name = name
            action = "promoted to admin"
        await session.commit()
        print(f"{action}: {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed/promote an admin user by email.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    asyncio.run(seed_admin(args.email, args.name))


if __name__ == "__main__":
    main()

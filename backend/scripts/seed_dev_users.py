"""Seed dev users for AUTH_DEV_MODE (resolved by the X-Dev-User header).

Usage (from backend/):
    uv run python scripts/seed_dev_users.py

Creates one admin and one employee if they don't already exist.
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from db.connection import AsyncSessionLocal  # noqa: E402
from db.models import User  # noqa: E402

DEV_USERS = [
    {"email": "admin@truboard.com", "display_name": "Dev Admin", "is_admin": True},
    {"email": "employee@truboard.com", "display_name": "Dev Employee", "is_admin": False},
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        for spec in DEV_USERS:
            exists = (
                await session.execute(select(User).where(User.email == spec["email"]))
            ).scalar_one_or_none()
            if exists:
                print(f"exists: {spec['email']}")
                continue
            session.add(
                User(
                    slug=f"dev-{uuid.uuid4()}",
                    email=spec["email"],
                    display_name=spec["display_name"],
                    is_admin=spec["is_admin"],
                )
            )
            print(f"created: {spec['email']} (admin={spec['is_admin']})")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())

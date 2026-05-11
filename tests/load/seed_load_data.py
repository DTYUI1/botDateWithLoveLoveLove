"""Seed candidate profiles for Locust auth -> next -> swipe flow."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path
import sys
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from core.database import async_session_factory  # noqa: E402
from models.photo import Photo  # noqa: E402
from models.profile import Profile  # noqa: E402
from models.user import User  # noqa: E402


def _dob(age: int) -> date:
    today = date.today()
    return today.replace(year=today.year - age)


async def seed(count: int) -> None:
    async with async_session_factory() as db:
        created = 0
        for index in range(count):
            telegram_id = 8_800_000_000 + index
            result = await db.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(
                    id=uuid4(),
                    telegram_id=telegram_id,
                    username=f"load_candidate_{index}",
                    first_name="LoadCandidate",
                    language_code="ru",
                )
                db.add(user)
                await db.flush()

            result = await db.execute(select(Profile).where(Profile.user_id == user.id))
            profile = result.scalar_one_or_none()
            if profile is None:
                profile = Profile(
                    id=uuid4(),
                    user_id=user.id,
                    display_name=f"Load Candidate {index}",
                    date_of_birth=_dob(24 + index % 10),
                    gender="female",
                    looking_for="male",
                    bio="Seeded profile for Stage4 load test",
                    interests=["loadtest", "metrics"],
                    city="LoadCity",
                    is_active=True,
                    profile_completion_pct=90,
                )
                db.add(profile)
                created += 1
                await db.flush()

            result = await db.execute(
                select(Photo).where(
                    Photo.profile_id == profile.id,
                    Photo.deleted_at.is_(None),
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(
                    Photo(
                        id=uuid4(),
                        profile_id=profile.id,
                        s3_key=f"loadtest/{profile.id}.jpg",
                        s3_bucket="profile-photos",
                        is_primary=True,
                        sort_order=0,
                        mime_type="image/jpeg",
                        moderation_status="approved",
                    )
                )

        await db.commit()
        print(f"seeded_candidates={count} created_profiles={created}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    asyncio.run(seed(args.count))


if __name__ == "__main__":
    main()

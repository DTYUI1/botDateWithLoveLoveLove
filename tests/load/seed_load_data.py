"""Seed profiles for Stage4 Locust flows."""

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


async def _ensure_profile(
    db,
    *,
    telegram_id: int,
    username: str,
    display_name: str,
    age: int,
    gender: str,
    looking_for: str,
    with_photo: bool,
) -> tuple[Profile, bool]:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid4(),
            telegram_id=telegram_id,
            username=username,
            first_name=display_name,
            language_code="ru",
        )
        db.add(user)
        await db.flush()

    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    created = False
    if profile is None:
        profile = Profile(
            id=uuid4(),
            user_id=user.id,
            display_name=display_name,
            date_of_birth=_dob(age),
            gender=gender,
            looking_for=looking_for,
            bio="Seeded profile for Stage4 load test",
            interests=["loadtest", "metrics"],
            city="LoadCity",
            is_active=True,
            profile_completion_pct=90,
        )
        db.add(profile)
        await db.flush()
        created = True

    if with_photo:
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

    return profile, created


async def seed(count: int, requesters: int) -> None:
    async with async_session_factory() as db:
        created_candidates = 0
        for index in range(count):
            _, created = await _ensure_profile(
                db,
                telegram_id=8_800_000_000 + index,
                username=f"load_candidate_{index}",
                display_name=f"Load Candidate {index}",
                age=24 + index % 10,
                gender="female",
                looking_for="male",
                with_photo=True,
            )
            created_candidates += int(created)

        created_requesters = 0
        for index in range(requesters):
            _, created = await _ensure_profile(
                db,
                telegram_id=8_900_000_000 + index,
                username=f"load_requester_{index}",
                display_name=f"Load Requester {index}",
                age=25 + index % 8,
                gender="male",
                looking_for="female",
                with_photo=False,
            )
            created_requesters += int(created)

        await db.commit()
        print(
            f"seeded_candidates={count} created_candidates={created_candidates} "
            f"seeded_requesters={requesters} created_requesters={created_requesters}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--requesters", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(seed(args.count, args.requesters))


if __name__ == "__main__":
    main()

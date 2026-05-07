"""Сид мок-юзеров для тестирования свайп/мэтч-сценария.

Создаёт 8 фейковых анкет (4 м / 4 ж), и для 3 из них дополнительно записывает
swipe(action='like') в адрес тестируемого юзера — чтобы при ответном лайке
случался моментальный мэтч.

Запуск:
    cd backend
    .venv/bin/python ../scripts/seed_mock_users.py --for-telegram-id <твой_TG_ID>

Идемпотентен по telegram_id моков (диапазон 9_000_000_001 ... 9_000_000_008).
Для проверки кнопки «Написать» можно подставить реальный @username
существующего тестового аккаунта через переменную окружения
SEED_REAL_USERNAME (тогда первый мок получит этот username).
"""

import argparse
import asyncio
import mimetypes
import os
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

# Делаем backend/ и project root импортируемыми
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from core.database import async_session_factory  # noqa: E402
from models.user import User  # noqa: E402
from models.profile import Profile  # noqa: E402
from models.photo import Photo  # noqa: E402
from models.swipe import Swipe  # noqa: E402
from models.match import Match  # noqa: E402,F401  (нужен для resolve relationship)
from models.rating import RatingCombined  # noqa: E402,F401  (нужен для resolve relationship)
from services.photo_service import PhotoService  # noqa: E402

PHOTOS_GIRLS_DIR = Path(os.environ.get("SEED_PHOTOS_GIRLS_DIR") or (PROJECT_ROOT / "promts" / "data" / "photos" / "girls"))
PHOTOS_BOYS_DIR = Path(os.environ.get("SEED_PHOTOS_BOYS_DIR") or (PROJECT_ROOT / "promts" / "data" / "photos" / "boys"))


def _list_photo_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


MOCK_BASE_TG_ID = 9_000_000_000

MOCKS = [
    # (telegram_id_offset, username, first_name, display_name, gender, looking_for, age, bio, interests, will_pre_like)
    (1, "anna_test", "Anna",  "Анна",   "female", "male",   25, "Люблю книги и кофе по утрам.",      ["книги", "кофе", "йога"],       True),
    (2, "kate_test", "Kate",  "Катя",   "female", "male",   28, "Путешествия, фотография и горы.",   ["путешествия", "фото", "горы"], True),
    (3, "olya_test", "Olya",  "Оля",    "female", "male",   22, "Студентка, рисую и слушаю инди.",   ["рисование", "музыка"],         False),
    (4, "lena_test", "Lena",  "Лена",   "female", "male",   30, "Программист на Python, фанат игр.", ["python", "игры"],              False),
    (5, "ivan_test", "Ivan",  "Иван",   "male",   "female", 27, "Фитнес, кино, путешествия.",        ["фитнес", "кино"],              True),
    (6, "petr_test", "Pyotr", "Пётр",   "male",   "female", 31, "Музыкант и любитель готовить.",     ["музыка", "кулинария"],         False),
    (7, "max_test",  "Max",   "Максим", "male",   "female", 24, "Сноуборд, IT, котики.",             ["сноуборд", "it", "коты"],      False),
    (8, "alex_test", "Alex",  "Алекс",  "male",   "female", 29, "Дизайнер, увлекаюсь архитектурой.", ["дизайн", "архитектура"],       False),
]


def _dob_for_age(age: int) -> date:
    today = date.today()
    return today.replace(year=today.year - age)


async def _get_or_create_mock_user(
    db: AsyncSession,
    *,
    telegram_id: int,
    username: str,
    first_name: str,
) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(
        id=uuid4(),
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        language_code="ru",
        last_active_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()
    return user


async def _get_or_create_mock_profile(
    db: AsyncSession,
    *,
    user: User,
    display_name: str,
    gender: str,
    looking_for: str,
    age: int,
    city: str,
    bio: str,
    interests: list,
) -> Profile:
    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile:
        # Обновляем поля, чтобы повторный seed подтягивал актуальный город/гендер
        profile.city = city
        profile.gender = gender
        profile.looking_for = looking_for
        profile.display_name = display_name
        profile.bio = bio
        profile.interests = interests
        profile.date_of_birth = _dob_for_age(age)
        await db.flush()
        return profile
    profile = Profile(
        id=uuid4(),
        user_id=user.id,
        display_name=display_name,
        date_of_birth=_dob_for_age(age),
        gender=gender,
        looking_for=looking_for,
        bio=bio,
        interests=interests,
        city=city,
        is_active=True,
        profile_completion_pct=85,
    )
    db.add(profile)
    await db.flush()
    return profile


async def _ensure_mock_photo(
    db: AsyncSession,
    *,
    profile: Profile,
    photo_path: Path,
) -> bool:
    """Загрузить фото для мокка в MinIO + БД, если у профиля ещё нет фото.

    Возвращает True если фото было загружено (или уже было), False при ошибке.
    """
    existing = await db.execute(
        select(Photo).where(
            (Photo.profile_id == profile.id) & (Photo.deleted_at.is_(None))
        )
    )
    if existing.scalar_one_or_none():
        return True  # уже есть фото — пропускаем

    if not photo_path.exists():
        print(f"   ⚠️ Файл не найден: {photo_path}")
        return False

    file_bytes = photo_path.read_bytes()
    mime, _ = mimetypes.guess_type(photo_path.name)
    mime = mime or "image/jpeg"

    photo_service = PhotoService(db)
    s3_key = photo_service.generate_s3_key(str(profile.id), photo_path.name)
    try:
        await photo_service.upload_to_storage(
            file_content=file_bytes,
            s3_key=s3_key,
            content_type=mime,
        )
    except Exception as e:
        print(f"   ⚠️ MinIO upload failed для {profile.display_name}: {e}")
        return False

    await photo_service.create_photo_record(
        profile_id=str(profile.id),
        s3_key=s3_key,
        filename=photo_path.name,
        content_type=mime,
        file_size=len(file_bytes),
        is_primary=True,
    )
    return True


async def _ensure_pre_like(
    db: AsyncSession, *, swiper_profile_id, swiped_profile_id
) -> None:
    """Создать swipe(action='like') от мока к юзеру, если ещё нет."""
    result = await db.execute(
        select(Swipe).where(
            (Swipe.swiper_id == swiper_profile_id)
            & (Swipe.swiped_id == swiped_profile_id)
        )
    )
    if result.scalar_one_or_none():
        return
    db.add(Swipe(
        id=uuid4(),
        swiper_id=swiper_profile_id,
        swiped_id=swiped_profile_id,
        action="like",
    ))
    await db.flush()


async def seed(target_telegram_id: int, city_override: str | None = None) -> None:
    real_username_override = os.environ.get("SEED_REAL_USERNAME")

    async with async_session_factory() as db:
        # 1. Найти профиль тестируемого пользователя (он должен быть создан через бота)
        target_user_result = await db.execute(
            select(User).where(User.telegram_id == target_telegram_id)
        )
        target_user = target_user_result.scalar_one_or_none()
        if not target_user:
            print(f"❌ Пользователь с telegram_id={target_telegram_id} не найден в БД.")
            print("   Сначала запусти бота и пройди /start, чтобы создать профиль.")
            return

        target_profile_result = await db.execute(
            select(Profile).where(Profile.user_id == target_user.id)
        )
        target_profile = target_profile_result.scalar_one_or_none()
        if not target_profile:
            print(f"❌ У пользователя {target_telegram_id} нет анкеты. Создай её через /start.")
            return

        # Город моков: переопределение из CLI > город тестируемого юзера > "Москва"
        seed_city = city_override or target_profile.city or "Москва"

        print(f"✅ Целевой пользователь: id={target_profile.id}, name={target_profile.display_name}, city={target_profile.city}")
        print(f"📍 Моки будут созданы в городе: {seed_city}")

        girls_photos = _list_photo_files(PHOTOS_GIRLS_DIR)
        boys_photos = _list_photo_files(PHOTOS_BOYS_DIR)
        print(f"📸 Доступно фото: girls={len(girls_photos)}, boys={len(boys_photos)}")

        girl_idx = 0
        boy_idx = 0

        # 2. Создать моков
        created = []
        pre_likers = []
        with_photo = []
        without_photo = []
        for i, (offset, username, first_name, display_name, gender, looking_for,
                age, bio, interests, will_pre_like) in enumerate(MOCKS):
            tg_id = MOCK_BASE_TG_ID + offset
            uname = real_username_override if (i == 0 and real_username_override) else username

            user = await _get_or_create_mock_user(
                db, telegram_id=tg_id, username=uname, first_name=first_name
            )
            profile = await _get_or_create_mock_profile(
                db,
                user=user,
                display_name=display_name,
                gender=gender,
                looking_for=looking_for,
                age=age,
                city=seed_city,
                bio=bio,
                interests=interests,
            )
            created.append((tg_id, uname, display_name))

            # Загружаем фото мокку из соответствующей папки (циклически).
            photo_pool = girls_photos if gender == "female" else boys_photos
            if photo_pool:
                if gender == "female":
                    photo_path = photo_pool[girl_idx % len(photo_pool)]
                    girl_idx += 1
                else:
                    photo_path = photo_pool[boy_idx % len(photo_pool)]
                    boy_idx += 1
                ok = await _ensure_mock_photo(db, profile=profile, photo_path=photo_path)
                (with_photo if ok else without_photo).append(display_name)
            else:
                without_photo.append(display_name)

            if will_pre_like:
                await _ensure_pre_like(
                    db,
                    swiper_profile_id=profile.id,
                    swiped_profile_id=target_profile.id,
                )
                pre_likers.append((uname, display_name))

        await db.commit()

        print(f"\n✅ Создано/проверено моков: {len(created)}")
        for tg_id, uname, name in created:
            print(f"   • tg_id={tg_id}  @{uname}  {name}")

        print(f"\n📷 С фото ({len(with_photo)}): {', '.join(with_photo) if with_photo else '—'}")
        if without_photo:
            print(f"⚠️ Без фото ({len(without_photo)}): {', '.join(without_photo)}")
            print("   Эти моки НЕ будут показаны в подборе (фильтр требует фото).")

        print(f"\n💘 Моки, уже залайкавшие тебя ({len(pre_likers)}):")
        for uname, name in pre_likers:
            print(f"   • @{uname} ({name}) — лайкни их в /search и получишь мэтч сразу")


def main() -> None:
    parser = argparse.ArgumentParser(description="Сидер мок-юзеров для ConnectMe")
    parser.add_argument(
        "--for-telegram-id",
        type=int,
        required=True,
        help="Твой telegram_id, для которого создавать предзалайканные мэтчи",
    )
    parser.add_argument(
        "--city",
        type=str,
        default=None,
        help="Город для моков (по умолчанию — город из анкеты тестируемого юзера)",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.for_telegram_id, city_override=args.city))


if __name__ == "__main__":
    main()

"""
HTTP-клиент для взаимодействия с Backend API.
"""

from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import httpx
from loguru import logger

from config import settings


class APIClient:
    """Клиент для Backend API ConnectMe."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.backend_url
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Получает или создаёт HTTP-клиент."""
        if self._client is None or self._client.is_closed:
            # Для localhost полностью отключаем прокси
            # Временная очистка переменных окружения
            import os
            proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
            old_values = {}
            for var in proxy_vars:
                old_values[var] = os.environ.pop(var, None)

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )

            # Восстанавливаем переменные
            for var, val in old_values.items():
                if val is not None:
                    os.environ[var] = val

        return self._client

    async def close(self):
        """Закрывает HTTP-клиент."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ============================================
    # User / Auth
    # ============================================

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получает или создаёт пользователя по Telegram ID."""
        client = await self.get_client()
        response = await client.post(
            "/api/v1/auth/telegram",
            json={
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
            },
        )
        response.raise_for_status()
        return response.json()

    # ============================================
    # Profile
    # ============================================

    async def get_profile(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает профиль пользователя."""
        logger.debug(f"[APIClient] GET /profile telegram_id={telegram_id}")
        client = await self.get_client()
        try:
            response = await client.get(
                "/api/v1/profile",
                params={"telegram_id": telegram_id},
            )
            logger.debug(f"[APIClient] Ответ профиля: status={response.status_code}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"[APIClient] ОШИБКА get_profile: {type(e).__name__}: {e}")
            raise

    async def create_profile(self, telegram_id: int, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создаёт профиль пользователя."""
        client = await self.get_client()
        response = await client.post(
            "/api/v1/profile",
            params={"telegram_id": telegram_id},
            json=profile_data,
        )
        response.raise_for_status()
        return response.json()

    async def update_profile(self, telegram_id: int, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновляет профиль пользователя."""
        client = await self.get_client()
        response = await client.put(
            "/api/v1/profile",
            params={"telegram_id": telegram_id},
            json=profile_data,
        )
        response.raise_for_status()
        return response.json()

    # ============================================
    # Matching
    # ============================================

    async def get_next_profile(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает следующую анкету для свайпа."""
        client = await self.get_client()
        response = await client.get(
            "/api/v1/matching/next",
            params={"telegram_id": telegram_id},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def swipe(
        self,
        telegram_id: int,
        target_profile_id: str,
        action: str,  # "like" или "pass"
    ) -> Dict[str, Any]:
        """Отправляет свайп (лайк или пропуск)."""
        client = await self.get_client()
        response = await client.post(
            "/api/v1/matching/swipe",
            params={"telegram_id": telegram_id},
            json={"profile_id": target_profile_id, "action": action},
        )
        response.raise_for_status()
        return response.json()

    async def get_matches(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Получает список мэтчей."""
        client = await self.get_client()
        response = await client.get(
            "/api/v1/matching/matches",
            params={"telegram_id": telegram_id},
        )
        response.raise_for_status()
        return response.json()

    # ============================================
    # Rating
    # ============================================

    async def get_rating(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает рейтинг пользователя."""
        client = await self.get_client()
        response = await client.get(
            "/api/v1/rating/my",
            params={"telegram_id": telegram_id},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    # ============================================
    # Settings
    # ============================================

    async def get_settings(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает настройки пользователя."""
        client = await self.get_client()
        response = await client.get(
            "/api/v1/settings",
            params={"telegram_id": telegram_id},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def update_settings(self, telegram_id: int, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновляет настройки пользователя."""
        client = await self.get_client()
        response = await client.put(
            "/api/v1/settings",
            params={"telegram_id": telegram_id},
            json=settings_data,
        )
        response.raise_for_status()
        return response.json()

    # ============================================
    # Health
    # ============================================

    async def health_check(self) -> bool:
        """Проверяет доступность backend."""
        try:
            client = await self.get_client()
            response = await client.get("/api/v1/health")
            return response.status_code == 200
        except Exception:
            return False

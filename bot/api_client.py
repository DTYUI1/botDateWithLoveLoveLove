"""
HTTP-клиент для взаимодействия с Backend API.
"""

from typing import Optional, Dict, Any, List

import httpx
from loguru import logger

from config import settings
from metrics import BOT_API_ERRORS_TOTAL


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

    def _raise_for_status(self, response: httpx.Response, op: str) -> None:
        if response.status_code >= 400:
            BOT_API_ERRORS_TOTAL.labels(op=op).inc()
        response.raise_for_status()

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
        self._raise_for_status(response, "auth_telegram")
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
            self._raise_for_status(response, "get_profile")
            return response.json()
        except Exception as e:
            if not isinstance(e, httpx.HTTPStatusError):
                BOT_API_ERRORS_TOTAL.labels(op="get_profile").inc()
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
        self._raise_for_status(response, "create_profile")
        return response.json()

    async def update_profile(self, telegram_id: int, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновляет профиль пользователя."""
        client = await self.get_client()
        response = await client.put(
            "/api/v1/profile",
            params={"telegram_id": telegram_id},
            json=profile_data,
        )
        self._raise_for_status(response, "update_profile")
        return response.json()

    # ============================================
    # Matching
    # ============================================

    async def get_next_profile(
        self,
        telegram_id: int,
        session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Получает следующую анкету для свайпа.
        
        Args:
            telegram_id: Telegram ID пользователя
            session_id: ID сессии кэша (опционально)
        """
        client = await self.get_client()
        params = {"telegram_id": telegram_id}
        if session_id:
            params["session_id"] = session_id
        
        response = await client.get(
            "/api/v1/matching/next",
            params=params,
        )
        if response.status_code == 404:
            return None
        self._raise_for_status(response, "matching_next")
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
        self._raise_for_status(response, "matching_swipe")
        return response.json()

    async def get_matches(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Получает список мэтчей."""
        client = await self.get_client()
        response = await client.get(
            "/api/v1/matching/matches",
            params={"telegram_id": telegram_id},
        )
        self._raise_for_status(response, "get_matches")
        return response.json()

    async def refresh_session(
        self,
        telegram_id: int,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Обновляет сессию подбора анкет.
        
        Args:
            telegram_id: Telegram ID пользователя
            session_id: ID текущей сессии (опционально)
            
        Returns:
            Dict с session_id, cached_count, profiles
        """
        client = await self.get_client()
        params = {"telegram_id": telegram_id}
        if session_id:
            params["session_id"] = session_id
        
        response = await client.post(
            "/api/v1/matching/session/refresh",
            params=params,
        )
        self._raise_for_status(response, "refresh_session")
        return response.json()

    # ============================================
    # Photos
    # ============================================

    async def upload_photo(
        self,
        telegram_id: int,
        file_path: str,
    ) -> Dict[str, Any]:
        """Загружает фотографию профиля (multipart/form-data).

        Args:
            telegram_id: Telegram ID пользователя
            file_path: Путь к файлу на диске

        Returns:
            Dict с photo_id, s3_key, is_primary, message
        """
        client = await self.get_client()
        with open(file_path, "rb") as f:
            files = {"file": (file_path.split("/")[-1], f, "image/jpeg")}
            response = await client.post(
                "/api/v1/profile/photo",
                files=files,
                params={"telegram_id": telegram_id},
                timeout=30.0,
            )
            self._raise_for_status(response, "upload_photo")
            return response.json()

    async def fetch_photo_bytes(self, photo_url: str) -> Optional[bytes]:
        """Скачать байты фото с backend по относительному пути /api/v1/profile/photo/{id}/raw.

        Принимает абсолютный URL или относительный путь. Возвращает None при ошибке.
        """
        try:
            client = await self.get_client()
            url = photo_url if photo_url.startswith("http") else photo_url
            response = await client.get(url, timeout=15.0)
            if response.status_code != 200:
                BOT_API_ERRORS_TOTAL.labels(op="fetch_photo_bytes").inc()
                logger.warning(f"[APIClient] fetch_photo_bytes {url} status={response.status_code}")
                return None
            return response.content
        except Exception as e:
            BOT_API_ERRORS_TOTAL.labels(op="fetch_photo_bytes").inc()
            logger.error(f"[APIClient] fetch_photo_bytes ОШИБКА: {type(e).__name__}: {e}")
            return None

    async def get_photos(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Получает все фото профиля пользователя."""
        client = await self.get_client()
        response = await client.get(
            "/api/v1/profile/photo",
            params={"telegram_id": telegram_id},
        )
        self._raise_for_status(response, "get_photos")
        return response.json()

    async def delete_photo(self, telegram_id: int, photo_id: str) -> Dict[str, Any]:
        """Удаляет фотографию профиля."""
        client = await self.get_client()
        response = await client.delete(
            f"/api/v1/profile/photo/{photo_id}",
            params={"telegram_id": telegram_id},
        )
        self._raise_for_status(response, "delete_photo")
        return response.json()

    async def set_primary_photo(self, telegram_id: int, photo_id: str) -> Dict[str, Any]:
        """Назначает фотографию основной."""
        client = await self.get_client()
        response = await client.post(
            f"/api/v1/profile/photo/{photo_id}/set-primary",
            params={"telegram_id": telegram_id},
        )
        self._raise_for_status(response, "set_primary_photo")
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
        self._raise_for_status(response, "get_rating")
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
        self._raise_for_status(response, "get_settings")
        return response.json()

    async def update_settings(self, telegram_id: int, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновляет настройки пользователя."""
        client = await self.get_client()
        response = await client.put(
            "/api/v1/settings",
            params={"telegram_id": telegram_id},
            json=settings_data,
        )
        self._raise_for_status(response, "update_settings")
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
            BOT_API_ERRORS_TOTAL.labels(op="health_check").inc()
            return False

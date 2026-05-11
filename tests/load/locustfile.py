"""Locust-сценарий для нагрузочного теста ConnectMe.

Запуск:

    locust -f tests/load/locustfile.py --host http://localhost:8005 \
        --users 50 --spawn-rate 10 --run-time 60s --headless \
        --csv tests/load/results/run

Каждый «пользователь» Locust имитирует цикл auth → next → swipe.
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task


class ConnectMeUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        """Один раз при появлении виртуального юзера — авторизуемся."""
        self.telegram_id = random.randint(10_000_000, 99_999_999)
        payload = {
            "telegram_id": self.telegram_id,
            "username": f"loadtest_{self.telegram_id}",
            "first_name": "Load",
            "last_name": "Test",
            "language_code": "ru",
        }
        with self.client.post(
            "/api/v1/auth/telegram", json=payload, name="auth", catch_response=True
        ) as resp:
            if resp.status_code >= 400:
                resp.failure(f"auth failed: {resp.status_code} {resp.text[:120]}")

        profile_payload = {
            "display_name": f"Load {self.telegram_id}",
            "age": random.randint(22, 35),
            "gender": "male",
            "bio": "Load-test profile",
            "interests": ["loadtest", "observability"],
            "city": "LoadCity",
            "looking_for": "female",
        }
        with self.client.post(
            f"/api/v1/profile?telegram_id={self.telegram_id}",
            json=profile_payload,
            name="profile_create",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 400):
                resp.failure(f"profile failed: {resp.status_code} {resp.text[:120]}")

    @task(3)
    def next_and_swipe(self) -> None:
        with self.client.get(
            f"/api/v1/matching/next?telegram_id={self.telegram_id}",
            name="matching_next",
            catch_response=True,
        ) as resp:
            if resp.status_code == 404:
                # анкета закончилась — это валидный case
                return
            if resp.status_code >= 400:
                resp.failure(f"next failed: {resp.status_code}")
                return
            try:
                profile = resp.json()
            except Exception:
                resp.failure("invalid json from /next")
                return
            if not profile or not profile.get("id"):
                return

        action = random.choices(["like", "pass", "super_like"], weights=[40, 55, 5])[0]
        body = {"profile_id": profile["id"], "action": action}
        with self.client.post(
            f"/api/v1/matching/swipe?telegram_id={self.telegram_id}",
            json=body,
            name="matching_swipe",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 400:
                resp.failure(f"swipe failed: {resp.status_code} {resp.text[:120]}")

    @task(1)
    def health(self) -> None:
        self.client.get("/api/v1/health", name="health")

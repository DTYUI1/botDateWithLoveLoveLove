"""Endpoint-focused Locust profiles for Stage4 SLA checks.

The mixed profile in ``locustfile.py`` validates the user journey. This file is
for strict per-endpoint throughput checks where each Locust task performs one
request against a single matching endpoint.

Run examples:

    LOCUST_ENDPOINT=next locust -f tests/load/locustfile_endpoint.py \
        --host http://localhost:8005 --users 40 --spawn-rate 20 \
        --run-time 45s --headless --csv tests/load/results/endpoint_next

    LOCUST_ENDPOINT=swipe locust -f tests/load/locustfile_endpoint.py \
        --host http://localhost:8005 --users 40 --spawn-rate 20 \
        --run-time 45s --headless --csv tests/load/results/endpoint_swipe
"""

from __future__ import annotations

import os
import random
from itertools import count

from locust import HttpUser, constant_throughput, task


MODE = os.getenv("LOCUST_ENDPOINT", "next").strip().lower()
RPS_PER_USER = float(os.getenv("LOCUST_RPS_PER_USER", "2"))
PRESEEDED_REQUESTERS = int(os.getenv("LOCUST_PRESEEDED_REQUESTERS", "0"))
REQUESTER_BASE = int(os.getenv("LOCUST_REQUESTER_BASE", "8900000000"))
REQUESTER_COUNTER = count()
TARGET_PROFILE_ID = os.getenv("LOCUST_TARGET_PROFILE_ID")


class _BaseFocusedUser(HttpUser):
    abstract = True
    wait_time = constant_throughput(RPS_PER_USER)

    def on_start(self) -> None:
        if PRESEEDED_REQUESTERS > 0:
            offset = next(REQUESTER_COUNTER) % PRESEEDED_REQUESTERS
            self.telegram_id = REQUESTER_BASE + offset
            return

        self.telegram_id = random.randint(100_000_000, 999_999_999)
        auth_payload = {
            "telegram_id": self.telegram_id,
            "username": f"endpoint_{self.telegram_id}",
            "first_name": "Endpoint",
            "last_name": "Load",
            "language_code": "ru",
        }
        with self.client.post(
            "/api/v1/auth/telegram", json=auth_payload, name="setup_auth", catch_response=True
        ) as resp:
            if resp.status_code >= 400:
                resp.failure(f"auth failed: {resp.status_code} {resp.text[:120]}")

        profile_payload = {
            "display_name": f"Endpoint {self.telegram_id}",
            "age": random.randint(22, 35),
            "gender": "male",
            "bio": "Endpoint-focused load-test profile",
            "interests": ["loadtest", "rps"],
            "city": "LoadCity",
            "looking_for": "female",
        }
        with self.client.post(
            f"/api/v1/profile?telegram_id={self.telegram_id}",
            json=profile_payload,
            name="setup_profile",
            catch_response=True,
        ) as resp:
            if resp.status_code == 400:
                resp.success()
            elif resp.status_code != 200:
                resp.failure(f"profile failed: {resp.status_code} {resp.text[:120]}")

    def _next_profile_id(self) -> str | None:
        with self.client.get(
            f"/api/v1/matching/next?telegram_id={self.telegram_id}",
            name="setup_matching_next",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 400:
                resp.failure(f"next failed: {resp.status_code} {resp.text[:120]}")
                return None
            try:
                profile = resp.json()
            except Exception:
                resp.failure("invalid json from /matching/next")
                return None
        return profile.get("id") if profile else None


class NextFocusedUser(_BaseFocusedUser):
    abstract = MODE != "next"

    @task
    def matching_next(self) -> None:
        self.client.get(
            f"/api/v1/matching/next?telegram_id={self.telegram_id}",
            name="matching_next_focused",
        )


class SwipeFocusedUser(_BaseFocusedUser):
    abstract = MODE != "swipe"

    def on_start(self) -> None:
        super().on_start()
        self.target_profile_id = TARGET_PROFILE_ID or self._next_profile_id()

    @task
    def matching_swipe(self) -> None:
        if not self.target_profile_id:
            self.target_profile_id = self._next_profile_id()
            if not self.target_profile_id:
                return

        body = {"profile_id": self.target_profile_id, "action": "pass"}
        with self.client.post(
            f"/api/v1/matching/swipe?telegram_id={self.telegram_id}",
            json=body,
            name="matching_swipe_focused",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 400:
                resp.failure(f"swipe failed: {resp.status_code} {resp.text[:120]}")

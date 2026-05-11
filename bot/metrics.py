"""Метрики бота и HTTP-сервер /metrics.

Бот не имеет встроенного HTTP-сервера (aiogram использует только polling),
поэтому поднимаем легковесный aiohttp-эндпойнт на отдельном порту
(`settings.metrics_port`, по умолчанию 8001).

Метрики:
* `bot_messages_total{kind}` — обработанные обновления (message, callback)
* `bot_callbacks_total` — нажатия inline-кнопок
* `bot_api_errors_total{op}` — ошибки HTTP-вызовов backend API
* `bot_push_delivered_total` — успешно доставленные push'и
* `bot_push_failed_total` — провальные доставки push'ей
* `bot_fsm_state_total{state}` — счётчик переходов в FSM
"""

from __future__ import annotations

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest


BOT_MESSAGES_TOTAL = Counter(
    "bot_messages_total", "Обработанные обновления бота", ["kind"]
)
BOT_CALLBACKS_TOTAL = Counter(
    "bot_callbacks_total", "Нажатия inline-кнопок"
)
BOT_API_ERRORS_TOTAL = Counter(
    "bot_api_errors_total", "Ошибки HTTP-вызовов backend API", ["op"]
)
BOT_PUSH_DELIVERED_TOTAL = Counter(
    "bot_push_delivered_total", "Успешно отправленные push-уведомления"
)
BOT_PUSH_FAILED_TOTAL = Counter(
    "bot_push_failed_total", "Провалы при отправке push-уведомлений"
)
BOT_FSM_STATE_TOTAL = Counter(
    "bot_fsm_state_total", "Переходы в состояния FSM", ["state"]
)


async def _metrics_handler(request: web.Request) -> web.Response:  # noqa: ARG001
    return web.Response(
        body=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


async def _health_handler(request: web.Request) -> web.Response:  # noqa: ARG001
    return web.json_response({"status": "ok"})


def build_metrics_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/metrics", _metrics_handler)
    app.router.add_get("/health", _health_handler)
    return app


async def start_metrics_server(host: str, port: int) -> web.AppRunner:
    """Запустить /metrics-сервер. Возвращает runner для shutdown."""
    runner = web.AppRunner(build_metrics_app())
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner

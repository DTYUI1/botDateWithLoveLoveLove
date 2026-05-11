"""
Тесты Celery-приложения backend/celery_app.py.

Проверяют только статическую регистрацию задач и beat schedule —
без реального брокера.
"""



def test_celery_app_importable():
    from celery_app import celery_app
    assert celery_app.main == "connectme_backend"


def test_recalculate_ratings_task_registered():
    from celery_app import celery_app
    assert "backend.recalculate_all_ratings" in celery_app.tasks


def test_beat_schedule_has_daily_recalc():
    from celery_app import celery_app
    schedule = celery_app.conf.beat_schedule
    assert "recalculate-ratings-daily" in schedule
    assert schedule["recalculate-ratings-daily"]["task"] == "backend.recalculate_all_ratings"


def test_celery_serializer_is_json():
    from celery_app import celery_app
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert "json" in celery_app.conf.accept_content


def test_recalculate_function_callable_signature():
    """Сигнатура задачи: limit (опционально)."""
    import inspect
    from celery_app import recalculate_all_ratings
    sig = inspect.signature(recalculate_all_ratings)
    assert "limit" in sig.parameters

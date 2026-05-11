"""Celery tasks (см. celery_app.celery_app).

Внутренние модули регистрируют tasks через декоратор `@celery_app.task`,
поэтому достаточно их импортировать здесь, чтобы worker их увидел.
"""

from . import rating_tasks  # noqa: F401
from . import photo_tasks  # noqa: F401
from . import notification_tasks  # noqa: F401

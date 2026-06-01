"""Точка входа в пакет services.

Здесь происходит выбор реализации APIClient: реальный HTTP-клиент или mock.
Хендлеры должны импортировать `APIClient` отсюда (`from services import APIClient`),
а не из конкретного модуля — тогда переключение режимов работает прозрачно.
"""
from config import USE_MOCK

if USE_MOCK:
    from .mock_client import MockAPIClient as APIClient
    print("⚙️  services: USE_MOCK=true — используется MockAPIClient (захардкоженные данные)")
else:
    from .api_client import APIClient  # noqa: F401
    print("⚙️  services: USE_MOCK=false — используется реальный APIClient (HTTP к бэкенду)")

__all__ = ["APIClient"]

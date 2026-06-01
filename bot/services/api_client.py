import httpx
from config import BASE_API_URL


# Бэкенд обслуживается по голому IP — у такого хоста, как правило, нет валидного
# TLS-сертификата на IP. Чтобы httpx не падал с CERTIFICATE_VERIFY_FAILED,
# отключаем проверку. В production-окружении с нормальным доменом и сертификатом
# нужно убрать verify=False (или сделать его управляемым через env).
_VERIFY_TLS = not BASE_API_URL.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0].replace(".", "").isdigit()


class APIClient:
    _timeout = httpx.Timeout(10.0)

    @staticmethod
    async def register_driver(telegram_id: int):
        async with httpx.AsyncClient(timeout=APIClient._timeout, verify=_VERIFY_TLS) as client:
            r = await client.post(
                f"{BASE_API_URL}/api/drivers/register",
                json={"telegramId": telegram_id},
            )
            r.raise_for_status()
            return r.json()

    @staticmethod
    async def send_refuel(telegram_id: int, liters: float, price: float):
        async with httpx.AsyncClient(timeout=APIClient._timeout, verify=_VERIFY_TLS) as client:
            r = await client.post(
                f"{BASE_API_URL}/api/refuel",
                json={
                    "telegramId": telegram_id,
                    "liters": liters,
                    "price": price,
                },
            )
            r.raise_for_status()
            return r.json()

    @staticmethod
    async def get_status(telegram_id: int):
        async with httpx.AsyncClient(timeout=APIClient._timeout, verify=_VERIFY_TLS) as client:
            r = await client.get(
                f"{BASE_API_URL}/api/status",
                params={"telegramId": telegram_id},
            )
            r.raise_for_status()
            return r.json()

    @staticmethod
    async def get_alerts(telegram_id: int):
        async with httpx.AsyncClient(timeout=APIClient._timeout, verify=_VERIFY_TLS) as client:
            r = await client.get(
                f"{BASE_API_URL}/api/alerts",
                params={"telegramId": telegram_id},
            )
            r.raise_for_status()
            return r.json()

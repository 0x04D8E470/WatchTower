import httpx
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class HttpClientError(Exception):
    pass

class HttpTimeoutError(HttpClientError):
    pass

class HttpNetworkError(HttpClientError):
    pass

class AsyncHttpClient:
    def __init__(self, timeout: float = 10.0, max_keepalive: int = 5):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=max_keepalive),
            max_redirects=5
        )

    async def fetch_url(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Any] = None,
        body: Optional[str] = None            # <-- добавили
    ) -> httpx.Response:
        try:
            response = await self.client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_data,
                content=body,                  # передаём тело как есть
                follow_redirects=True
            )
            return response
        except httpx.TimeoutException as e:
            logger.warning(f"Таймаут запроса к {url}: {str(e)}")
            raise HttpTimeoutError("Сервер не ответил вовремя. Попробуйте позже.")
        except httpx.NetworkError as e:
            logger.error(f"Сбой сети при запросе к {url}: {str(e)}")
            raise HttpNetworkError("Не удалось связаться с сервером. Проверьте URL.")
        except httpx.HTTPStatusError as e:
            logger.info(f"Сервер вернул ошибку {e.response.status_code} для {url}")
            return e.response
        except Exception as e:
            logger.critical(f"Непредвиденная ошибка при запросе к {url}: {str(e)}", exc_info=True)
            raise HttpClientError("Произошла внутренняя ошибка при отправке запроса.")

    async def close(self):
        await self.client.aclose()

# Глобальный экземпляр (будет закрыт при остановке бота)
http_client = AsyncHttpClient()
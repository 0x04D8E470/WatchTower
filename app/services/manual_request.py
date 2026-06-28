import time
from typing import Optional
from app.utils.http_client import http_client, HttpTimeoutError, HttpNetworkError, HttpClientError
import logging

logger = logging.getLogger(__name__)

class ManualRequestService:
    async def execute(
        self,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        body: Optional[str] = None,
        timeout: int = 10,
    ) -> dict:
        start = time.monotonic()
        try:
            response = await http_client.fetch_url(
                url=url,
                method=method,
                headers=headers,
                body=body,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Безопасное чтение тела
            content_type = response.headers.get("content-type", "")
            is_text = (
                content_type.startswith("text/") or
                content_type.startswith("application/json") or
                content_type.startswith("application/xml")
            )

            if not is_text:
                # Для нетекстовых ответов (изображения, архивы и пр.) не пытаемся декодировать
                body_preview = f"[Бинарные данные: {len(response.content)} байт]"
            else:
                try:
                    raw = response.text[:10000]
                    if len(response.text) > 10000:
                        body_preview = raw + "\n... (сообщение обрезано)"
                    else:
                        body_preview = raw
                except (UnicodeDecodeError, LookupError):
                    body_preview = f"[Бинарные данные: {len(response.content)} байт]"
                except Exception as e:
                    logger.warning(f"Не удалось прочитать тело ответа: {e}")
                    body_preview = f"[Ошибка чтения ответа: {e}]"

            return {
                "ok": True,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": body_preview,
                "content_type": content_type,
                "elapsed_ms": elapsed_ms,
            }
        except (HttpTimeoutError, HttpNetworkError, HttpClientError) as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "ok": False,
                "error": str(e),
                "elapsed_ms": elapsed_ms,
            }
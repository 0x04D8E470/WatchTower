import asyncio
import html
import ipaddress
import socket
from typing import Optional, List, Dict, Any

from app.services.manual_request import ManualRequestService
from app.db.repositories.request_repo import RequestRepo
from app.db.models.request_template import RequestTemplate
from app.db.models.request_history import RequestHistory
from app.utils.format import format_response
from app.core.logger import logger


class RequestService:
    """Сервис для выполнения HTTP-запросов, сохранения истории и шаблонов."""

    # Локальные сети и спецадреса, которые запрещены
    BLOCKED_SUBNETS = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("224.0.0.0/4"),   # Multicast
        ipaddress.ip_network("240.0.0.0/4"),   # Reserved
        ipaddress.ip_network("::1/128"),       # IPv6 loopback
        ipaddress.ip_network("fe80::/10"),     # IPv6 link-local
        ipaddress.ip_network("fc00::/7"),      # IPv6 unique local
    ]

    def __init__(self, manual_request: ManualRequestService, repo: RequestRepo):
        self.manual_request = manual_request
        self.repo = repo

    # ----------------------------------------------------------------
    # Публичные методы
    # ----------------------------------------------------------------
    async def execute_and_record(
        self,
        user_id: int,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        body: Optional[str] = None,
        body_type: str = "raw",
    ) -> Dict[str, Any]:
        """
        Выполняет HTTP-запрос с проверками безопасности, сохраняет запись в историю,
        логирует результат и возвращает словарь с ключами:
        - 'text': HTML-строка для отправки пользователю
        - 'success': bool (True, если запрос выполнен без системных ошибок)
        - опционально может содержать другие ключи для внутреннего использования.
        """
        # Проверка URL на SSRF
        try:
            await self._validate_url(url)
        except ValueError as e:
            logger.warning("ssrf_blocked", user_id=user_id, url=url, reason=str(e))
            return {
                "text": f"❌ Недопустимый адрес: {html.escape(str(e))}",
                "success": False,
            }

        # Логируем начало запроса
        logger.info("request_started", user_id=user_id, method=method, url=url)
        try:
            result = await self.manual_request.execute(
                method=method, url=url, headers=headers, body=body
            )
        except Exception as e:
            logger.error("manual_request_exception", user_id=user_id, method=method, url=url, error=str(e))
            return {
                "text": f"❌ Ошибка выполнения запроса: {html.escape(str(e))}",
                "success": False,
            }

        # Логируем итог запроса
        status = result.get("status_code") if result.get("ok") else None
        logger.info("request_finished", user_id=user_id, method=method, url=url,
                    ok=result.get("ok"), status=status, elapsed=result.get("elapsed_ms"))

        # Сохраняем историю (не блокируем основной ответ, если сохранение упало)
        try:
            await self._save_history(
                user_id=user_id,
                method=method,
                url=url,
                headers=headers,
                body=body,
                result=result,
            )
        except Exception as e:
            logger.error("history_save_failed", user_id=user_id, error=str(e))
            # Не ломаем ответ пользователю, продолжаем

        # Форматируем текст для Telegram
        formatted_text = format_response(result, url, method)
        return {
            "text": formatted_text,
            "success": result.get("ok", False),
            "result": result,  # опционально
            "method": method,
            "url": url,
        }

    async def save_template(
        self,
        user_id: int,
        name: str,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        body: Optional[str] = None,
        body_type: str = "raw",
    ) -> RequestTemplate:
        """Сохраняет шаблон с проверкой уникальности (выполняется в репозитории)."""
        logger.info("template_save_started", user_id=user_id, name=name)
        # Валидация URL, чтобы не сохранили шаблон с запрещённым адресом
        await self._validate_url(url)
        template = await self.repo.save_template(
            user_id=user_id,
            name=name,
            method=method,
            url=url,
            headers=headers,
            body=body,
            body_type=body_type,
        )
        logger.info("template_saved", user_id=user_id, name=name, template_id=template.id)
        return template

    async def get_templates(self, user_id: int) -> list:
        return await self.repo.get_templates_by_user(user_id)

    async def run_template(self, user_id: int, name: str) -> Dict[str, Any]:
        """
        Выполняет запрос по сохранённому шаблону.
        Возвращает результат выполнения (как execute_and_record).
        """
        template = await self.repo.get_template_by_name(user_id, name)
        if not template:
            raise ValueError("Шаблон не найден")
        logger.info("template_run", user_id=user_id, name=name)
        return await self.execute_and_record(
            user_id=user_id,
            method=template.method,
            url=template.url,
            headers=template.headers,
            body=template.body,
            body_type=template.body_type,
        )

    async def get_history(self, user_id: int, limit: int = 5) -> List[RequestHistory]:
        return await self.repo.get_history_by_user(user_id, limit)

    # ----------------------------------------------------------------
    # Вспомогательные методы
    # ----------------------------------------------------------------
    @staticmethod
    def parse_headers(text: str) -> Optional[dict]:
        """
        Парсит пользовательский ввод заголовков из строки 'Key: Value'
        или слова 'пропустить'. Возвращает словарь или None.
        """
        if text.lower() == "пропустить":
            return None
        headers = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                raise ValueError("Неверный формат заголовка: отсутствует двоеточие")
            key, sep, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if not key:
                raise ValueError("Неверный формат заголовка: пустой ключ")
            headers[key] = value
        return headers

    @staticmethod
    def detect_body_type(body: str) -> str:
        """Эвристика типа тела запроса."""
        if body.startswith("{") or body.startswith("["):
            return "json"
        return "raw"

    async def _validate_url(self, url: str) -> None:
        """
        Проверяет, что URL не ведёт на локальные или запрещённые ресурсы.
        Выполняет DNS-резолвинг и сверяет IP-адрес с чёрным списком подсетей.
        Выбрасывает ValueError при нарушении.
        """
        # Простейшая проверка на схему
        if not url.startswith(("http://", "https://")):
            raise ValueError("Некорректная схема URL")

        # Извлекаем хост
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Не удалось извлечь хост из URL")

        # Прямые запреты строк (на случай, если DNS не используется)
        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]"):
            raise ValueError("Адрес ведёт на локальную машину")

        # Резолвим хост в IP в отдельном потоке (чтобы не блокировать event loop)
        loop = asyncio.get_running_loop()
        try:
            addrinfo = await loop.run_in_executor(
                None, socket.getaddrinfo, hostname, None
            )
        except socket.gaierror as e:
            raise ValueError(f"Не удалось разрешить имя хоста: {e}")

        # Проверяем все полученные IP-адреса
        for _, _, _, _, sockaddr in addrinfo:
            ip_str = sockaddr[0]
            try:
                ip_addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            for subnet in self.BLOCKED_SUBNETS:
                if ip_addr in subnet:
                    raise ValueError(f"Запрещённый IP-адрес {ip_str} (принадлежит {subnet})")

    async def _save_history(
        self,
        user_id: int,
        method: str,
        url: str,
        headers: Optional[dict],
        body: Optional[str],
        result: dict,
    ) -> None:
        """Сохраняет запись истории в БД."""
        history = RequestHistory(
            user_id=user_id,
            method=method,
            url=url,
            headers=headers,
            body=body,
            status_code=result.get("status_code") if result.get("ok") else None,
            response_time_ms=result.get("elapsed_ms"),
            response_preview=(
                (result.get("body") or "")[:500]
                if result.get("ok") and result.get("body")
                else None
            ),
        )
        await self.repo.add_history(history)
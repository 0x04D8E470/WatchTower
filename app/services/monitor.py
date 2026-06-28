# app/services/monitor.py
import asyncio
import time
import ssl
from datetime import datetime, timezone
from typing import Tuple, List
import httpx

from app.utils.http_client import http_client
from app.utils.url_validator import validate_url
from app.db.repositories.monitor_repo import MonitorRepo
from app.db.models.monitor import Monitor
from app.db.models.check_result import CheckResult
from app.core.logger import logger


class MonitorService:
    """Сервис для управления мониторами и выполнения проверок."""

    def __init__(self, repo: MonitorRepo):
        self.repo = repo

    async def add_monitor(
        self,
        user_id: int,
        url: str,
        method: str = "GET",
        expected_status: int = 200,
        check_interval: int = 300,
    ) -> Monitor:
        """Добавляет новый монитор с предварительной валидацией URL."""
        await validate_url(url)  # защита от SSRF
        monitor = await self.repo.add(
            user_id=user_id,
            url=url,
            method=method,
            expected_status=expected_status,
            check_interval=check_interval,
        )
        logger.info("monitor_added", user_id=user_id, monitor_id=monitor.id, url=url)
        return monitor

    async def get_user_monitors(self, user_id: int) -> List[Monitor]:
        """Возвращает все мониторы пользователя."""
        return await self.repo.get_by_user(user_id)

    async def check_monitor(self, monitor: Monitor) -> Tuple[CheckResult, bool]:
        """
        Выполняет проверку одного монитора: HTTP-запрос, SSL (асинхронно),
        сохранение результата и обновление статуса монитора.
        Возвращает результат проверки и флаг изменения статуса.
        """
        old_status = monitor.last_status
        start = time.monotonic()
        error_message = None
        status_code = None
        is_up = False
        ssl_expiry_date = None

        try:
            # 1. Асинхронный HTTP-запрос
            response = await http_client.fetch_url(url=monitor.url, method=monitor.method)
            status_code = response.status_code
            is_up = (status_code == monitor.expected_status)
            response_time_ms = int((time.monotonic() - start) * 1000)

            # 2. Асинхронная проверка SSL (если https и запрос успешен)
            if monitor.url.startswith("https://") and is_up:
                host = httpx.URL(monitor.url).host
                context = ssl.create_default_context()
                writer = None
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, 443, ssl=context, server_hostname=host),
                        timeout=5.0
                    )
                    transport = writer.transport
                    extra_info = transport.get_extra_info('ssl_object')
                    cert = extra_info.getpeercert() if extra_info else None
                    if cert and 'notAfter' in cert:
                        ssl_expiry_date = datetime.strptime(
                            cert['notAfter'], "%b %d %H:%M:%S %Y %Z"
                        ).replace(tzinfo=timezone.utc)
                except Exception:
                    # Ошибки SSL не должны ронять общую проверку
                    logger.warning("ssl_check_failed", monitor_id=monitor.id, exc_info=True)
                finally:
                    if writer:
                        writer.close()
                        await writer.wait_closed()

        except (httpx.RequestError, ssl.SSLError, asyncio.TimeoutError, Exception) as e:
            response_time_ms = int((time.monotonic() - start) * 1000)
            error_message = str(e)
            is_up = False

        # 3. Сохранение результатов
        check_result = CheckResult(
            monitor_id=monitor.id,
            timestamp=datetime.now(timezone.utc),
            response_time_ms=response_time_ms,
            status_code=status_code or 0,
            is_up=is_up,
            error_message=error_message,
            ssl_expiry_date=ssl_expiry_date,
        )
        await self.repo.add_check_result(check_result)

        monitor.last_checked_at = datetime.now(timezone.utc)
        monitor.last_status = "up" if is_up else "down"
        await self.repo.update(monitor)

        changed = (old_status != monitor.last_status)
        logger.info(
            "monitor_checked",
            monitor_id=monitor.id,
            is_up=is_up,
            changed=changed,
        )
        return check_result, changed

    # ---------- Управление мониторами ----------
    async def _get_user_monitor(self, user_id: int, monitor_id: int) -> Monitor:
        """Возвращает монитор с проверкой принадлежности пользователю."""
        monitor = await self.repo.get_by_id(monitor_id)
        if not monitor:
            raise ValueError("Монитор не найден")
        if monitor.user_id != user_id:
            raise ValueError("Монитор не принадлежит вам")
        return monitor

    async def pause_monitor(self, user_id: int, monitor_id: int) -> Monitor:
        """Приостанавливает мониторинг."""
        monitor = await self._get_user_monitor(user_id, monitor_id)
        monitor.is_active = False
        await self.repo.update(monitor)
        logger.info("monitor_paused", user_id=user_id, monitor_id=monitor_id)
        return monitor

    async def resume_monitor(self, user_id: int, monitor_id: int) -> Monitor:
        """Возобновляет мониторинг."""
        monitor = await self._get_user_monitor(user_id, monitor_id)
        monitor.is_active = True
        await self.repo.update(monitor)
        logger.info("monitor_resumed", user_id=user_id, monitor_id=monitor_id)
        return monitor

    async def delete_monitor(self, user_id: int, monitor_id: int) -> Monitor:
        """Удаляет мониторинг."""
        monitor = await self._get_user_monitor(user_id, monitor_id)
        await self.repo.delete(monitor)
        logger.info("monitor_deleted", user_id=user_id, monitor_id=monitor_id)
        return monitor
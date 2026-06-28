from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from app.db.base import async_session_factory
from app.db.repositories.user_repo import UserRepo
from app.db.repositories.monitor_repo import MonitorRepo
from app.db.repositories.request_repo import RequestRepo
from app.services.monitor import MonitorService
from app.services.manual_request import ManualRequestService
from app.services.request_service import RequestService

class DIMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            # Репозитории
            user_repo = UserRepo(session)
            monitor_repo = MonitorRepo(session)
            request_repo = RequestRepo(session)
            # Сервисы
            monitor_service = MonitorService(monitor_repo)
            manual_request_service = ManualRequestService()
            request_service = RequestService(manual_request_service, request_repo)

            data["user_repo"] = user_repo
            data["monitor_repo"] = monitor_repo
            data["monitor_service"] = monitor_service
            data["manual_request_service"] = manual_request_service
            data["request_repo"] = request_repo
            data["request_service"] = request_service

            return await handler(event, data)
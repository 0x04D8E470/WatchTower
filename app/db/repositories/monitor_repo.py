from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, text, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.monitor import Monitor
from app.db.models.check_result import CheckResult


class MonitorRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- Создание монитора ----------
    async def add(
        self,
        user_id: int,
        url: str,
        method: str = "GET",
        expected_status: int = 200,
        check_interval: int = 300,
    ) -> Monitor:
        monitor = Monitor(
            user_id=user_id,
            url=url,
            method=method,
            expected_status=expected_status,
            check_interval=check_interval,
        )
        self.session.add(monitor)
        await self.session.flush()          # чтобы получить id, транзакция открыта
        return monitor

    # ---------- Получение мониторов ----------
    async def get_by_user(self, user_id: int) -> List[Monitor]:
        stmt = select(Monitor).where(Monitor.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, monitor_id: int) -> Optional[Monitor]:
        stmt = select(Monitor).where(Monitor.id == monitor_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[Monitor]:
        stmt = select(Monitor).where(Monitor.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_monitors_due_for_check(self) -> List[Monitor]:
        now = datetime.now(timezone.utc)
        interval_expr = Monitor.check_interval * text("interval '1 second'")
        stmt = select(Monitor).where(
            Monitor.is_active == True,
            (Monitor.last_checked_at == None) |
            (Monitor.last_checked_at + interval_expr <= now)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ---------- Результаты проверок ----------
    async def add_check_result(self, result: CheckResult) -> CheckResult:
        self.session.add(result)
        await self.session.flush()          # id присвоен, транзакция открыта
        return result

    # ---------- Обновление и удаление ----------
    async def update(self, monitor: Monitor) -> None:
        """Помечает объект изменённым. Коммита нет — он произойдёт позже."""
        self.session.add(monitor)            # фактически «присоединяет» к сессии, если отсоединён

    async def delete(self, monitor: Monitor) -> None:
        # Сначала удаляем связанные результаты проверок
        stmt = sql_delete(CheckResult).where(CheckResult.monitor_id == monitor.id)
        await self.session.execute(stmt)
        # Затем сам монитор
        await self.session.delete(monitor)
        # Никакого commit! Всё будет закоммичено в конце транзакции
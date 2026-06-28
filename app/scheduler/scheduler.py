from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot

from app.db.base import async_session_factory
from app.db.repositories.monitor_repo import MonitorRepo
from app.services.monitor import MonitorService
from app.services.alert import AlertService
from app.core.logger import logger

scheduler = AsyncIOScheduler()

def start_scheduler(bot: Bot):
    """Запускает фоновую проверку мониторов, передавая бота в AlertService."""

    async def check_all_monitors():
        try:
            async with async_session_factory() as session:
                repo = MonitorRepo(session)
                service = MonitorService(repo)
                alert = AlertService(bot)
                monitors = await repo.get_monitors_due_for_check()
                logger.info(f"Проверка {len(monitors)} мониторов...")
                for monitor in monitors:
                    try:
                        result, changed = await service.check_monitor(monitor)
                        if changed:
                            new_status = "up" if result.is_up else "down"
                            await alert.send_status_change(monitor, new_status, result)
                        if result.ssl_expiry_date:
                            days_left = (result.ssl_expiry_date - datetime.now(timezone.utc)).days
                            if days_left in (14, 7, 3, 1):
                                await alert.send_ssl_warning(monitor, result.ssl_expiry_date, days_left)
                    except Exception as e:
                        logger.error(f"Ошибка проверки {monitor.url}: {e}")
        except Exception as e:
            logger.error(f"Критическая ошибка в планировщике мониторов: {e}")

    scheduler.add_job(
        check_all_monitors,
        trigger=IntervalTrigger(seconds=30),
        id="check_all_monitors",
        replace_existing=True,
        max_instances=1,   # без гонки
    )
    scheduler.start()
    logger.info("Планировщик запущен")
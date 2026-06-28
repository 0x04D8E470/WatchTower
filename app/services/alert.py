from aiogram import Bot
from app.core.logger import logger
from app.db.models.monitor import Monitor
from app.db.models.check_result import CheckResult

class AlertService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_status_change(self, monitor: Monitor, new_status: str, result: CheckResult):
        """Уведомление при смене статуса."""
        user_id = monitor.user_id
        if new_status == "down":
            text = (
                f"🔴 <b>Сервис недоступен!</b>\n"
                f"URL: {monitor.url}\n"
                f"Код ответа: {result.status_code or 'нет'}\n"
                f"Ошибка: {result.error_message or 'неизвестно'}\n"
                f"Время проверки: {result.timestamp.strftime('%d.%m %H:%M UTC')}"
            )
        else:
            text = (
                f"🟢 <b>Сервис восстановился</b>\n"
                f"URL: {monitor.url}\n"
                f"Код ответа: {result.status_code}\n"
                f"Время ответа: {result.response_time_ms} мс\n"
                f"Время проверки: {result.timestamp.strftime('%d.%m %H:%M UTC')}"
            )
        try:
            await self.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление {user_id}: {e}")

    async def send_ssl_warning(self, monitor: Monitor, expiry_date, days_left: int):
        """Предупреждение об истечении SSL."""
        text = (
            f"⚠️ <b>SSL-сертификат истекает через {days_left} дн.</b>\n"
            f"URL: {monitor.url}\n"
            f"Дата истечения: {expiry_date.strftime('%d.%m.%Y')}"
        )
        try:
            await self.bot.send_message(chat_id=monitor.user_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось отправить SSL-уведомление: {e}")
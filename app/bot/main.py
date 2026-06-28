import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from app.core.config import settings
from app.core.logger import logger
from app.bot.middlewares.di import DIMiddleware
from app.bot.handlers import monitoring
from app.scheduler.scheduler import start_scheduler
from app.bot.handlers.requests import router as requests_router
from app.bot.handlers.common import router as common_router
from app.utils.http_client import http_client

bot = Bot(token=settings.bot_token)
dp = Dispatcher()

# Подключаем DI-мидлварь
dp.update.middleware(DIMiddleware())
dp.include_router(common_router)
dp.include_router(monitoring.router)
dp.include_router(requests_router)

async def set_bot_commands():
    """Регистрирует меню команд с подсказками."""
    commands = [
        BotCommand(command="start", description="Начало работы"),
        BotCommand(command="monitor", description="Добавить URL для мониторинга"),
        BotCommand(command="status", description="Статус ваших мониторингов"),
        BotCommand(command="pause", description="Приостановить мониторинг /pause <id>"),
        BotCommand(command="resume", description="Возобновить мониторинг /resume <id>"),
        BotCommand(command="delete", description="Удалить мониторинг /delete <id>"),
        BotCommand(command="get", description="Быстрый GET-запрос /get <URL>"),
        BotCommand(command="post", description="Быстрый POST-запрос /post <URL> <body>"),
        BotCommand(command="request", description="Пошаговый мастер запросов"),
        BotCommand(command="templates", description="Список сохранённых шаблонов"),
        BotCommand(command="run", description="Выполнить шаблон /run <имя>"),
        BotCommand(command="history", description="История последних запросов"),
        BotCommand(command="cancel", description="Отменить текущий процесс"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Меню команд зарегистрировано")

async def on_shutdown():
    await http_client.close()
    logger.info("HTTP-клиент закрыт")

async def main():
    start_scheduler(bot)
    dp.shutdown.register(on_shutdown)
    await set_bot_commands()
    logger.info("Запуск бота")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
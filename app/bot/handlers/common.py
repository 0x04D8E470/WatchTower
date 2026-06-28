from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from app.db.repositories.user_repo import UserRepo

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, user_repo: UserRepo):
    # Сохраняем пользователя в БД (если ещё нет)
    user = await user_repo.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username
    )

    text = (
        f"👋 <b>Привет, {message.from_user.full_name}!</b>\n\n"
        "Я <b>WatchTower</b> — твой помощник для мониторинга сайтов и тестирования API прямо в Telegram.\n\n"
        "🔍 <b>Мониторинг</b>\n"
        "• /monitor — добавить URL для отслеживания\n"
        "• /status — статус всех мониторингов\n"
        "• /pause, /resume, /delete — управление\n\n"
        "🧪 <b>HTTP-клиент</b>\n"
        "• /get, /post — быстрые запросы\n"
        "• /request — пошаговый мастер (метод, заголовки, тело)\n"
        "• /templates — сохранённые шаблоны\n"
        "• /run — выполнить шаблон по имени\n"
        "• /history — история запросов\n\n"
        "❓ Все команды доступны в меню слева от ввода.\n"
        "Используй /cancel для выхода из любого диалога."
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🚫 Процесс отменён. Вы можете начать заново.")
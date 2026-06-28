import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.states.monitor import MonitorStates
from app.services.monitor import MonitorService
from app.core.logger import logger

router = Router()

# ------------------------------------------------------------
# /monitor – добавление монитора
# ------------------------------------------------------------
@router.message(Command("monitor"))
async def cmd_monitor(message: Message, state: FSMContext):
    await message.answer(
        "Введите URL для мониторинга (например, https://example.com):\n"
        "Для отмены – /cancel"
    )
    await state.set_state(MonitorStates.waiting_for_url)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
        await message.answer("❌ Действие отменено.")
    else:
        await message.answer("Нет активного действия для отмены.")

@router.message(MonitorStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith(("https://", "http://")):
        await message.answer("URL должен начинаться с http:// или https://. Попробуйте снова:")
        return
    await state.update_data(url=url)
    await message.answer("Введите интервал проверки в секундах (по умолчанию 300 = 5 минут):")
    await state.set_state(MonitorStates.waiting_for_interval)

@router.message(MonitorStates.waiting_for_interval)
async def process_interval(message: Message, state: FSMContext):
    try:
        interval = int(message.text)
        if interval < 10:
            await message.answer("Интервал не может быть меньше 10 секунд. Попробуйте снова:")
            return
    except ValueError:
        await message.answer("Некорректное число. Введите интервал в секундах (целое число):")
        return
    await state.update_data(check_interval=interval)
    await message.answer("Введите ожидаемый HTTP-статус (по умолчанию 200):")
    await state.set_state(MonitorStates.waiting_for_expected_status)

@router.message(MonitorStates.waiting_for_expected_status)
async def process_expected_status(message: Message, state: FSMContext, monitor_service: MonitorService):
    try:
        expected_status = int(message.text)
        if expected_status < 100 or expected_status > 599:
            await message.answer("Некорректный HTTP-статус. Введите число от 100 до 599:")
            return
    except ValueError:
        await message.answer("Введите числовой HTTP-статус (например, 200):")
        return

    data = await state.get_data()
    try:
        monitor = await monitor_service.add_monitor(
            user_id=message.from_user.id,
            url=data["url"],
            method="GET",
            expected_status=expected_status,
            check_interval=data["check_interval"],
        )
    except ValueError as e:
        # Ошибки валидации URL или другие
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()
        return
    except Exception:
        logger.exception("add_monitor_failed")
        await message.answer("❌ Не удалось добавить монитор из-за внутренней ошибки.")
        await state.clear()
        return

    safe_url = html.escape(monitor.url)
    await message.answer(
        f"✅ Мониторинг добавлен!\n"
        f"URL: {safe_url}\n"
        f"Интервал: {monitor.check_interval} сек.\n"
        f"Ожидаемый статус: {monitor.expected_status}",
        parse_mode="HTML"
    )
    await state.clear()

# ------------------------------------------------------------
# /status – список с инлайн-кнопками
# ------------------------------------------------------------
@router.message(Command("status"))
async def cmd_status(message: Message, monitor_service: MonitorService):
    try:
        monitors = await monitor_service.get_user_monitors(message.from_user.id)
    except Exception:
        logger.exception("get_user_monitors_failed")
        await message.answer("❌ Не удалось получить список мониторов.")
        return

    if not monitors:
        await message.answer("У вас нет активных мониторингов. Добавьте через /monitor")
        return

    lines = []
    builder = InlineKeyboardBuilder()
    for m in monitors:
        status_icon = "🟢" if m.last_status == "up" else "🔴" if m.last_status == "down" else "⚪️"
        safe_url = html.escape(m.url)
        last_check = m.last_checked_at.strftime("%d.%m %H:%M") if m.last_checked_at else "ещё не проверен"
        interval_min = m.check_interval // 60
        lines.append(
            f"{status_icon} <b>{safe_url}</b> (ID: {m.id})\n"
            f"   ▪ метод: {html.escape(m.method)}\n"
            f"   ▪ ожидаемый статус: {m.expected_status}\n"
            f"   ▪ интервал: {interval_min} мин\n"
            f"   ▪ последняя проверка: {last_check}"
        )
        # кнопки управления
        if m.is_active:
            builder.button(text=f"⏸ Пауза #{m.id}", callback_data=f"mon:pause:{m.id}")
        else:
            builder.button(text=f"▶ Запустить #{m.id}", callback_data=f"mon:resume:{m.id}")
        builder.button(text=f"🗑 Удалить #{m.id}", callback_data=f"mon:delete:{m.id}")
    builder.adjust(2)

    await message.answer(
        "📊 <b>Ваши мониторинги</b>\n\n" + "\n\n".join(lines),
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

# ------------------------------------------------------------
# Обработчики инлайн-кнопок
# ------------------------------------------------------------
@router.callback_query(F.data.startswith("mon:pause:"))
async def cb_pause(callback: CallbackQuery, monitor_service: MonitorService):
    monitor_id = int(callback.data.split(":")[2])
    try:
        monitor = await monitor_service.pause_monitor(callback.from_user.id, monitor_id)
        await callback.message.answer(
            f"⏸ Мониторинг <b>{html.escape(monitor.url)}</b> приостановлен", parse_mode="HTML"
        )
        await callback.answer("Приостановлен")
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)

@router.callback_query(F.data.startswith("mon:resume:"))
async def cb_resume(callback: CallbackQuery, monitor_service: MonitorService):
    monitor_id = int(callback.data.split(":")[2])
    try:
        monitor = await monitor_service.resume_monitor(callback.from_user.id, monitor_id)
        await callback.message.answer(
            f"▶ Мониторинг <b>{html.escape(monitor.url)}</b> возобновлён", parse_mode="HTML"
        )
        await callback.answer("Возобновлён")
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)

@router.callback_query(F.data.startswith("mon:delete:"))
async def cb_delete(callback: CallbackQuery, monitor_service: MonitorService):
    monitor_id = int(callback.data.split(":")[2])
    try:
        monitor = await monitor_service.delete_monitor(callback.from_user.id, monitor_id)
        await callback.message.answer(
            f"🗑 Мониторинг <b>{html.escape(monitor.url)}</b> удалён", parse_mode="HTML"
        )
        await callback.answer("Удалён")
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)

# ------------------------------------------------------------
# Текстовые команды (для совместимости)
# ------------------------------------------------------------
@router.message(Command("pause"))
async def cmd_pause(message: Message, monitor_service: MonitorService):
    try:
        monitor_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Использование: /pause <id>\nУзнайте ID через /status")
        return
    try:
        monitor = await monitor_service.pause_monitor(message.from_user.id, monitor_id)
        await message.answer(f"⏸ Мониторинг <b>{html.escape(monitor.url)}</b> приостановлен", parse_mode="HTML")
    except ValueError as e:
        await message.answer(f"❌ {e}")

@router.message(Command("resume"))
async def cmd_resume(message: Message, monitor_service: MonitorService):
    try:
        monitor_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Использование: /resume <id>")
        return
    try:
        monitor = await monitor_service.resume_monitor(message.from_user.id, monitor_id)
        await message.answer(f"▶ Мониторинг <b>{html.escape(monitor.url)}</b> возобновлён", parse_mode="HTML")
    except ValueError as e:
        await message.answer(f"❌ {e}")

@router.message(Command("delete"))
async def cmd_delete(message: Message, monitor_service: MonitorService):
    try:
        monitor_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Использование: /delete <id>")
        return
    try:
        monitor = await monitor_service.delete_monitor(message.from_user.id, monitor_id)
        await message.answer(f"🗑 Мониторинг <b>{html.escape(monitor.url)}</b> удалён", parse_mode="HTML")
    except ValueError as e:
        await message.answer(f"❌ {e}")
import html as html_mod

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.states.request import RequestStates
from app.services.request_service import RequestService

router = Router()


# ------------------------------------------------------------
# Быстрые команды /get и /post
# ------------------------------------------------------------
@router.message(Command("get"))
async def cmd_get(message: Message, command: CommandObject, request_service: RequestService):
    args = command.args
    if not args:
        await message.answer("Использование: /get <URL>")
        return
    url = args.strip()
    if not url.startswith(("http://", "https://")):
        await message.answer("URL должен начинаться с http:// или https://")
        return

    response = await request_service.execute_and_record(
        user_id=message.from_user.id,
        method="GET",
        url=url,
    )
    await message.answer(response["text"], parse_mode="HTML")


@router.message(Command("post"))
async def cmd_post(message: Message, command: CommandObject, request_service: RequestService):
    args = command.args
    if not args:
        await message.answer("Использование: /post <URL> <body>")
        return
    parts = args.split(" ", 1)
    if len(parts) < 2:
        await message.answer("Необходимо указать тело запроса. Пример: /post <URL> <body>")
        return
    url, body = parts[0].strip(), parts[1].strip()
    if not url.startswith(("http://", "https://")):
        await message.answer("URL должен начинаться с http:// или https://")
        return

    response = await request_service.execute_and_record(
        user_id=message.from_user.id,
        method="POST",
        url=url,
        headers={"Content-Type": "application/json"},
        body=body,
    )
    await message.answer(response["text"], parse_mode="HTML")


# ------------------------------------------------------------
# Мастер /request
# ------------------------------------------------------------
@router.message(Command("request"))
async def cmd_request(message: Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    for method in methods:
        builder.button(text=method, callback_data=f"req:method:{method}")
    builder.adjust(4)
    await message.answer("Выберите метод запроса:", reply_markup=builder.as_markup())
    await state.set_state(RequestStates.waiting_for_method)


@router.callback_query(RequestStates.waiting_for_method, F.data.startswith("req:method:"))
async def process_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":")[2]
    await state.update_data(method=method)
    await callback.message.answer(f"Метод: {method}\nВведите URL (или /cancel для отмены):")
    await callback.answer()
    await state.set_state(RequestStates.waiting_for_url)


@router.message(RequestStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        await message.answer("URL должен начинаться с http:// или https://. Попробуйте ещё раз:")
        return
    await state.update_data(url=url)
    await message.answer(
        "Введите заголовки в формате:\n"
        "Key: Value\n"
        "Каждый заголовок с новой строки.\n"
        "Или напишите 'пропустить', чтобы не добавлять заголовки."
    )
    await state.set_state(RequestStates.waiting_for_headers)


@router.message(RequestStates.waiting_for_headers)
async def process_headers(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        headers = RequestService.parse_headers(text)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}. Используйте формат 'Key: Value' или 'пропустить'.")
        return

    await state.update_data(headers=headers)
    if headers is None:
        await message.answer("Заголовки пропущены.")
    else:
        safe_headers = {k: v for k, v in headers.items()}
        await message.answer(f"Заголовки добавлены: {safe_headers}")

    data = await state.get_data()
    method = data.get("method", "GET")
    if method in ("POST", "PUT", "PATCH"):
        await message.answer("Введите тело запроса (или 'нет', если не нужно):")
        await state.set_state(RequestStates.waiting_for_body)
    else:
        await state.set_state(RequestStates.waiting_for_confirmation)
        await _ask_confirmation(message, state)


@router.message(RequestStates.waiting_for_body)
async def process_body(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() == "нет":
        body = None
        body_type = "none"
        await message.answer("Тело не указано.")
    else:
        body = text
        body_type = RequestService.detect_body_type(body)
        await message.answer(f"Тело получено (тип: {body_type}).")
    await state.update_data(body=body, body_type=body_type)
    await state.set_state(RequestStates.waiting_for_confirmation)
    await _ask_confirmation(message, state)


async def _ask_confirmation(message: Message, state: FSMContext):
    """Формирует сводку и клавиатуру подтверждения."""
    data = await state.get_data()
    method = data.get("method", "GET")
    url = data.get("url", "?")
    headers = data.get("headers")
    body = data.get("body")
    body_type = data.get("body_type", "none")

    safe_url = html_mod.escape(url)
    safe_method = html_mod.escape(method)
    summary = f"<b>Подтвердите запрос</b>\nМетод: {safe_method}\nURL: {safe_url}\n"
    if headers:
        hdr_str = ", ".join(
            f"{html_mod.escape(k)}: {html_mod.escape(v)}" for k, v in headers.items()
        )
        summary += f"Заголовки: {hdr_str}\n"
    if body:
        body_preview = html_mod.escape(body[:200])
        if len(body) > 200:
            body_preview += "..."
        summary += f"Тело ({body_type}): {body_preview}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="req:confirm")
    builder.button(text="❌ Отмена", callback_data="req:cancel")
    await message.answer(summary, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(RequestStates.waiting_for_confirmation, F.data == "req:confirm")
async def execute_request(callback: CallbackQuery, state: FSMContext, request_service: RequestService):
    data = await state.get_data()
    method = data["method"]
    url = data["url"]
    headers = data.get("headers")
    body = data.get("body")
    body_type = data.get("body_type", "raw")

    response = await request_service.execute_and_record(
        user_id=callback.from_user.id,
        method=method,
        url=url,
        headers=headers,
        body=body,
        body_type=body_type,
    )

    builder = InlineKeyboardBuilder()
    builder.button(
        text="💾 Сохранить как шаблон",
        callback_data=f"tmpl:save:{method}:{url}"
    )
    await callback.message.answer(response["text"], parse_mode="HTML", reply_markup=builder.as_markup())
    # Состояние НЕ сбрасываем — ждём, пока пользователь решит сохранить шаблон или отменить
    await callback.answer("Запрос выполнен!")


@router.callback_query(RequestStates.waiting_for_confirmation, F.data == "req:cancel")
async def cancel_request(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🚫 Запрос отменён.")
    await callback.answer()


# ------------------------------------------------------------
# Сохранение шаблона
# ------------------------------------------------------------
@router.callback_query(F.data.startswith("tmpl:save:"))
async def prompt_template_name(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")[2:]   # ["save", method, url_части...]
    if len(parts) < 2:
        await callback.answer("Неверные данные кнопки.")
        return
    method, url = parts[0], ":".join(parts[1:])  # на случай, если URL содержит двоеточия
    await state.update_data(template_method=method, template_url=url)
    await callback.message.answer("Введите имя для шаблона:")
    await state.set_state(RequestStates.waiting_for_template_name)
    await callback.answer()


@router.message(RequestStates.waiting_for_template_name)
async def save_template_with_name(message: Message, state: FSMContext, request_service: RequestService):
    name = message.text.strip()
    data = await state.get_data()
    method = data.get("template_method", "GET")
    url = data.get("template_url", "")
    headers = data.get("headers")          # их мы сохранили в состоянии
    body = data.get("body")
    body_type = data.get("body_type", "raw")

    try:
        template = await request_service.save_template(
            user_id=message.from_user.id,
            name=name,
            method=method,
            url=url,
            headers=headers,
            body=body,
            body_type=body_type,
        )
        safe_name = html_mod.escape(template.name)
        await message.answer(f"✅ Шаблон '<b>{safe_name}</b>' сохранён (ID: {template.id})", parse_mode="HTML")
    except ValueError as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        await state.clear()


# ------------------------------------------------------------
# Управление шаблонами и историей
# ------------------------------------------------------------
@router.message(Command("templates"))
async def list_templates(message: Message, request_service: RequestService):
    templates = await request_service.get_templates(message.from_user.id)
    if not templates:
        await message.answer("У вас нет сохранённых шаблонов.")
        return
    lines = []
    for t in templates:
        safe_name = html_mod.escape(t.name)
        safe_method = html_mod.escape(t.method)
        safe_url = html_mod.escape(t.url)
        lines.append(f"<b>{safe_name}</b> — {safe_method} {safe_url}")
    await message.answer("📋 <b>Ваши шаблоны:</b>\n" + "\n".join(lines), parse_mode="HTML")


@router.message(Command("run"))
async def run_template(message: Message, command: CommandObject, request_service: RequestService):
    name = command.args
    if not name:
        await message.answer("Укажите имя шаблона: /run имя")
        return
    try:
        response = await request_service.run_template(message.from_user.id, name.strip())
        await message.answer(response["text"], parse_mode="HTML")
    except ValueError:
        await message.answer("Шаблон не найден.")


@router.message(Command("history"))
async def show_history(message: Message, request_service: RequestService):
    history = await request_service.get_history(message.from_user.id)
    if not history:
        await message.answer("История запросов пуста.")
        return
    lines = []
    for h in history:
        icon = "✅" if h.status_code and 200 <= h.status_code < 300 else "❌"
        safe_url = html_mod.escape(h.url)
        lines.append(f"{icon} {h.method} {safe_url} ({h.status_code}) — {h.timestamp.strftime('%d.%m %H:%M')}")
    await message.answer("📜 <b>Последние запросы:</b>\n" + "\n".join(lines), parse_mode="HTML")
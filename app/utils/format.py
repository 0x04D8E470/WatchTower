import html
from typing import Optional

def format_response(result: dict, url: str, method: str) -> str:
    if not result.get("ok"):
        return f"❌ <b>Ошибка запроса</b>\nURL: {url}\nМетод: {method}\nОшибка: {html.escape(result['error'])}"

    status_code = result["status_code"]
    elapsed = result["elapsed_ms"]
    if 200 <= status_code < 300:
        icon = "✅"
    elif 400 <= status_code < 500:
        icon = "⚠️"
    elif 500 <= status_code:
        icon = "🔴"
    else:
        icon = "ℹ️"

    text = f"{icon} <b>{status_code}</b> | {elapsed} мс\n"
    text += f"<b>URL</b>: {html.escape(url)}\n"
    text += f"<b>Метод</b>: {html.escape(method)}\n"

    if result.get("is_binary"):
        text += f"<pre>Бинарный ответ (тип: {html.escape(result.get('content_type', 'unknown'))}, размер: {result.get('body')}</pre>"
    else:
        body = result.get("body", "")
        if body:
            # Экранируем и обрезаем до 3500 символов (Telegram-лимит 4096)
            body = html.escape(body)
            if len(body) > 3500:
                body = body[:3500] + "\n... (обрезано)"
            text += f"<pre><code>{body}</code></pre>"
    return text
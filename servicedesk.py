"""
Модуль интеграции с ServiceDesk (Magnit)
Добавляет функционал для работы с заявками BMC Helix
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (ApplicationBuilder, CallbackQueryHandler,
                          CommandHandler, ContextTypes, MessageHandler,
                          filters)

# === КОНФИГУРАЦИЯ ===
BASE_URL = "https://mobilebmc.tander.ru"
API_JWT_LOGIN = f"{BASE_URL}/api/jwt/login"
API_INCIDENTS = f"{BASE_URL}/api/arsys/v1/entry/HPD:Help%20Desk"

# Хранилище сессий
sd_sessions = {}
SD_TOKENS_FILE = "sd_tokens.json"  # user_id -> {"token": str, "login_id": str}
sd_states = {}  # user_id -> state


# === SERVICEDESK API ===
def load_sd_tokens():
    try:
        with open(SD_TOKENS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_sd_tokens(tokens):
    with open(SD_TOKENS_FILE, "w") as f:
        json.dump(tokens, f)


def sd_login(login_id: str, password: str) -> str:
    """Авторизация в ServiceDesk"""
    data = urllib.parse.urlencode({"username": login_id, "password": password}).encode(
        "utf-8"
    )
    req = urllib.request.Request(
        API_JWT_LOGIN,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12)",
        },
    )

    with urllib.request.urlopen(req) as response:
        result = response.read().decode("utf-8")

    token = result.strip().strip('"')
    if not token or len(token) < 20:
        raise Exception("Токен не получен")
    return token


def sd_get_incidents(token: str, group: str = "РГ Уфа Восток филиал") -> list:
    """Получить заявки"""
    headers = {
        "Authorization": token,
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12)",
        "Accept": "application/json",
    }

    query = f"'Status' = \"Assigned\" AND 'Assigned Group' = \"{group}\""
    url = f"{API_INCIDENTS}?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("entries", [])
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise Exception("Токен истёк")
        raise Exception(f"HTTP {e.code}")


def parse_incident(entry: dict) -> dict:
    values = entry.get("values", entry)

    # Short Description
    short_desc = (
        values.get("Short Description")
        or values.get("Summary")
        or values.get("Description")
        or values.get("Short_Description")
        or ""
    )[:80]

    # Full Description
    description = (
        values.get("Description")
        or values.get("Detailed Description")
        or values.get("Notes")
        or ""
    )[:500]

    # SLA
    sla = (
        values.get("SLA")
        or values.get("SLA Status")
        or values.get("Service Level Agreement")
        or values.get("SLA Deadline")
        or ""
    )

    return {
        "inc_num": values.get("Incident Number", "N/A"),
        "short_desc": short_desc or "—",
        "description": description or "—",
        "assignee": values.get("Assignee Login ID", "Нет"),
        "submit_date": values.get("Submit Date", "")[:10],
        "status": values.get("Status", ""),
        "priority": values.get("Priority", ""),
        "sla": sla,
    }


# === ОБРАБОТЧИКИ TELEGRAM ===
async def sd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /sd - начало работы с ServiceDesk"""
    chat_id = update.effective_chat.id

    # Проверяем сохранённый токен
    tokens = load_sd_tokens()
    if str(chat_id) in tokens:
        saved = tokens[str(chat_id)]
        sd_sessions[chat_id] = saved
        # Показываем меню
        keyboard = [
            [InlineKeyboardButton("📋 Все заявки", callback_data="sd_all")],
            [InlineKeyboardButton("👤 Мои заявки", callback_data="sd_my")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🔐 Сессия восстановлена\n👤 Логин: {saved.get('login_id')}\n\nВыберите:",
            reply_markup=reply_markup,
        )
        return

    keyboard = [
        [InlineKeyboardButton("🔑 Логин + Пароль", callback_data="sd_auth_login")],
        [InlineKeyboardButton("🎫 Токен", callback_data="sd_auth_token")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📋 ServiceDesk (Magnit)\n\n" "Выберите способ авторизации:",
        reply_markup=reply_markup,
    )


async def sd_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок"""
    print(
        f"[CALLBACK] data={update.callback_query.data if update.callback_query else None}"
    )
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if query.data == "sd_auth_login":
        sd_states[chat_id] = "awaiting_login"
        await query.message.reply_text("Введите логин:")
    elif query.data == "sd_auth_token":
        sd_states[chat_id] = "awaiting_token"
        await query.message.reply_text("Введите токен:")
    elif query.data == "sd_refresh":
        await sd_show_incidents(update, context, chat_id)
    elif query.data == "sd_all":
        await sd_show_incidents(update, context, chat_id, filter_type="all")
    elif query.data == "sd_my":
        await sd_show_incidents(update, context, chat_id, filter_type="my")


async def sd_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений для авторизации"""
    print(
        f"[SD_MESSAGE] chat_id={update.message.chat.id}, text={update.message.text[:20]}"
    )
    chat_id = update.message.chat.id
    text = update.message.text.strip()
    state = sd_states.get(chat_id)
    print(f"[SD_STATE] chat_id={chat_id}, state={state}")

    if state == "awaiting_login":
        sd_sessions[chat_id] = {"login_id": text}
        sd_states[chat_id] = "awaiting_password"
        await update.message.reply_text("Введите пароль:")

    elif state == "awaiting_password":
        login_id = sd_sessions.get(chat_id, {}).get("login_id")
        await update.message.reply_text("⏳ Авторизуюсь...")

        try:
            token = sd_login(login_id, text)
            sd_sessions[chat_id] = {"token": token, "login_id": login_id}
            sd_states.pop(chat_id, None)

            # Сохраняем токен для пользователя
            tokens = load_sd_tokens()
            tokens[str(chat_id)] = {"token": token, "login_id": login_id}
            save_sd_tokens(tokens)

            # Показываем меню выбора
            keyboard = [
                [InlineKeyboardButton("📋 Все заявки", callback_data="sd_all")],
                [InlineKeyboardButton("👤 Мои заявки", callback_data="sd_my")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ Успешно авторизован!\n👤 Логин: {login_id}\n\nВыберите:",
                reply_markup=reply_markup,
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            sd_states.pop(chat_id, None)
            sd_sessions.pop(chat_id, None)

    elif state == "awaiting_token":
        sd_sessions[chat_id] = {"token": text}
        sd_states.pop(chat_id, None)
        await update.message.reply_text("✅ Токен сохранён!")
        await sd_show_incidents(update, context, chat_id)
    else:
        # Не в процессе авторизации - игнорируем
        pass


async def sd_my(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /my - показать мои заявки"""
    await sd_show_incidents(update, context, update.message.chat.id)


async def sd_show_incidents(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    filter_type: str = "all",
):
    """Показать заявки"""
    session = sd_sessions.get(chat_id)
    login_id = session.get("login_id", "") if session else ""

    if not session or not session.get("token"):
        # Кнопка для авторизации
        keyboard = [
            [InlineKeyboardButton("🔑 Авторизоваться", callback_data="sd_auth_login")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.message.reply_text(
                "❌ Сессия истекла. Авторизуйтесь:", reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id,
                "❌ Сессия истекла. Используйте /sd для авторизации.",
                reply_markup=reply_markup,
            )
        return

    await context.bot.send_message(chat_id, "🔄 Загружаю заявки...")

    try:
        print(
            "[DEBUG] Sample entry:",
            json.dumps(entries[0] if entries else {}, indent=2)[:2000],
        )
        entries = sd_get_incidents(session["token"])

        # Фильтрация по логину
        if filter_type == "my" and login_id:
            entries = [
                e
                for e in entries
                if str(login_id).lower()
                in str(parse_incident(e).get("assignee", "")).lower()
            ]

        if not entries:
            await context.bot.send_message(chat_id, "📭 Заявок не найдено")
            return

        title = "Мои заявки" if filter_type == "my" else "Все заявки"
        text = f"📋 {title} (Assigned): {len(entries)}\n\n"

        for i, entry in enumerate(entries[:10], 1):
            inc = parse_incident(entry)
            text += f"🔹 #{inc['inc_num']}\n"
            text += f"   📝 {inc['short_desc']}\n"
            if inc.get("description") and inc["description"] != "—":
                text += f"   📄 {inc['description'][:100]}...\n"
            text += f"   👤 {inc['assignee']} | 📅 {inc['submit_date']}\n"
            if inc.get("priority"):
                text += f"   ⭐ {inc['priority']}\n"
            if inc.get("sla"):
                text += f"   ⏰ SLA: {inc['sla']}\n"
            text += "\n"

        keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data="sd_refresh")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(chat_id, text, reply_markup=reply_markup)

    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")
        if "истёк" in str(e).lower():
            sd_sessions.pop(chat_id, None)


# === РЕГИСТРАЦИЯ В ПРИЛОЖЕНИИ ===
def register_sd_handlers(app):
    """Добавить обработчики ServiceDesk в бота"""
    app.add_handler(CommandHandler("sd", sd_start))
    app.add_handler(CommandHandler("my", sd_my))
    app.add_handler(CallbackQueryHandler(sd_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sd_message))
    print("✅ ServiceDesk обработчики зарегистрированы")


# === Standalone запуск (для тестирования) ===
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN", "")
    if not TOKEN:
        print("Установите BOT_TOKEN")
        exit(1)

    print("Запуск ServiceDesk бота...")
    app = ApplicationBuilder().token(TOKEN).build()

    register_sd_handlers(app)

    app.run_polling()

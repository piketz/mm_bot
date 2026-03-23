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

# === BACKGROUND POLLING: ХРАНИЛИЩЕ ПОЛЬЗОВАТЕЛЕЙ И ИНЦИДЕНТОВ ===
# chat_id -> login_id mapping (for background polling)
sd_user_logins = {}  # {chat_id: login_id}
# last known incident IDs per login_id
last_incidents = {}  # {login_id: set(incident_ids)}

# === НАСТРОЙКИ ПОЛЬЗОВАТЕЛЕЙ ===
# chat_id -> {notifications_enabled: bool, interval_minutes: int}
sd_user_settings = {}
sd_user_logins = {}
last_incidents = {}


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


def load_sd_settings():
    """Загрузить настройки пользователей"""
    settings_file = "sd_settings.json"
    try:
        with open(settings_file, "r") as f:
            return json.load(f)
    except:
        return {}


def save_sd_settings(settings):
    """Сохранить настройки пользователей"""
    settings_file = "sd_settings.json"
    with open(settings_file, "w") as f:
        json.dump(settings, f, ensure_ascii=False)


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


async def sd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /sdmenu - показать меню ServiceDesk"""
    chat_id = update.effective_chat.id
    
    # Load settings
    global sd_user_settings
    global sd_user_logins
    global last_incidents
    sd_user_settings = load_sd_settings()
    user_settings = sd_user_settings.get(str(chat_id), {
        'notifications_enabled': True,
        'interval_minutes': 5
    })
    
    keyboard = [
        [InlineKeyboardButton("📋 Мои заявки", callback_data="sd_my")],
        [InlineKeyboardButton("📋 Все заявки", callback_data="sd_all")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="sd_settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if user is logged in
    session = sd_sessions.get(chat_id)
    login_info = f"\n👤 Логин: {session.get('login_id')}" if session and session.get('login_id') else ""
    
    # Show notification status
    notif_status = "🔔" if user_settings.get('notifications_enabled', True) else "🔕"
    interval = user_settings.get('interval_minutes', 5)
    
    await update.message.reply_text(
        f"📋 ServiceDesk Меню{login_info}\n\n{notif_status} Уведомления: {'Вкл' if user_settings.get('notifications_enabled', True) else 'Выкл'} | Интервал: {interval} мин",
        reply_markup=reply_markup,
    )


async def sd_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать настройки уведомлений"""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    
    # Load settings
    global sd_user_settings
    global sd_user_logins
    global last_incidents
    sd_user_settings = load_sd_settings()
    user_settings = sd_user_settings.get(str(chat_id), {
        'notifications_enabled': True,
        'interval_minutes': 5
    })
    
    # Toggle button
    notif_enabled = user_settings.get('notifications_enabled', True)
    notif_btn_text = "🔕 Выключить уведомления" if notif_enabled else "🔔 Включить уведомления"
    notif_btn_cb = "sd_notif_off" if notif_enabled else "sd_notif_on"
    
    # Interval buttons (radio-style)
    intervals = [5, 10, 30, 60]
    current_interval = user_settings.get('interval_minutes', 5)
    interval_buttons = []
    for intv in intervals:
        prefix = "✅ " if intv == current_interval else ""
        interval_buttons.append(InlineKeyboardButton(
            f"{prefix}{intv} мин", 
            callback_data=f"sd_interval_{intv}"
        ))
    
    keyboard = [
        [InlineKeyboardButton(notif_btn_text, callback_data=notif_btn_cb)],
        interval_buttons,
        [InlineKeyboardButton("🔙 Назад", callback_data="sd_menu_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        "⚙️ Настройки уведомлений\n\n"
        "Выберите интервал проверки новых заявок:",
        reply_markup=reply_markup,
    )


async def sd_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка настроек уведомлений"""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    
    # Load settings
    global sd_user_settings
    global sd_user_logins
    global last_incidents
    sd_user_settings = load_sd_settings()
    
    if not str(chat_id) in sd_user_settings:
        sd_user_settings[str(chat_id)] = {
            'notifications_enabled': True,
            'interval_minutes': 5
        }
    
    data = query.data
    
    if data == "sd_notif_on":
        sd_user_settings[str(chat_id)]['notifications_enabled'] = True
        save_sd_settings(sd_user_settings)
        await sd_settings_menu(update, context)
        
    elif data == "sd_notif_off":
        sd_user_settings[str(chat_id)]['notifications_enabled'] = False
        save_sd_settings(sd_user_settings)
        await sd_settings_menu(update, context)
        
    elif data.startswith("sd_interval_"):
        interval = int(data.split("_")[-1])
        sd_user_settings[str(chat_id)]['interval_minutes'] = interval
        save_sd_settings(sd_user_settings)
        await sd_settings_menu(update, context)
        
    elif data == "sd_menu_back":
        # Return to main menu
        keyboard = [
            [InlineKeyboardButton("📋 Мои заявки", callback_data="sd_my")],
            [InlineKeyboardButton("📋 Все заявки", callback_data="sd_all")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="sd_settings")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        session = sd_sessions.get(chat_id)
        login_info = f"\n👤 Логин: {session.get('login_id')}" if session and session.get('login_id') else ""
        user_settings = sd_user_settings.get(str(chat_id), {'notifications_enabled': True, 'interval_minutes': 5})
        notif_status = "🔔" if user_settings.get('notifications_enabled', True) else "🔕"
        interval = user_settings.get('interval_minutes', 5)
        
        await query.message.edit_text(
            f"📋 ServiceDesk Меню{login_info}\n\n{notif_status} Уведомления: {'Вкл' if user_settings.get('notifications_enabled', True) else 'Выкл'} | Интервал: {interval} мин",
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
    elif query.data == "sd_settings":
        await sd_settings_menu(update, context)
    elif query.data in ["sd_notif_on", "sd_notif_off"] or query.data.startswith("sd_interval_") or query.data == "sd_menu_back":
        await sd_settings_callback(update, context)


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
            # Store user login for background polling
            sd_user_logins[chat_id] = login_id
            
                sd_user_settings[str(chat_id)] = {
                    'notifications_enabled': True,
                    'interval_minutes': 5
                }
                save_sd_settings(sd_user_settings)
            
            # Store initial incidents for tracking
            try:
                entries = sd_get_incidents(token)
                last_incidents[login_id] = {parse_incident(e)["inc_num"] for e in entries}
            except:
                pass
            
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
        # For token auth, store chat_id for background polling
        sd_user_logins[chat_id] = str(chat_id)
        
        # Initialize user settings if not exists
        global sd_user_settings
    global sd_user_logins
    global last_incidents
        sd_user_settings = load_sd_settings()
        if str(chat_id) not in sd_user_settings:
            sd_user_settings[str(chat_id)] = {
                'notifications_enabled': True,
                'interval_minutes': 5
            }
            save_sd_settings(sd_user_settings)
            
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
        entries = sd_get_incidents(session["token"])
        print(
            "[DEBUG] Sample entry:",
            json.dumps(entries[0] if entries else {}, indent=2)[:2000],
        )

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


# === BACKGROUND POLLING: ПРОВЕРКА НОВЫХ ИНЦИДЕНТОВ ===
async def check_incidents_background(context: ContextTypes.DEFAULT_TYPE):
    """Background task: проверяет новые инциденты с учетом настроек пользователя"""
    import logging
    logger = logging.getLogger(__name__)
    
    bot = context.application.bot
    
    # Load settings
    global sd_user_settings
    global sd_user_logins
    global last_incidents
    sd_user_settings = load_sd_settings()
    
    if not sd_user_logins:
        return
    
    for chat_id, login_id in list(sd_user_logins.items()):
        # Check if notifications are enabled for this user
        user_settings = sd_user_settings.get(str(chat_id), {})
        if not user_settings.get('notifications_enabled', True):
            continue
        
        try:
            session = sd_sessions.get(chat_id)
            if not session or not session.get("token"):
                continue
            
            entries = sd_get_incidents(session["token"])
            current_incident_ids = {parse_incident(e)["inc_num"] for e in entries}
            previous_ids = last_incidents.get(login_id, set())
            new_ids = current_incident_ids - previous_ids
            
            if new_ids:
                new_incidents = [e for e in entries if parse_incident(e)["inc_num"] in new_ids]
                
                text = f"🔔 <b>Новые инциденты ({len(new_ids)})</b>\n\n"
                
                for entry in new_incidents[:5]:
                    inc = parse_incident(entry)
                    text += f"🔹 #{inc['inc_num']}\n"
                    text += f"   📝 {inc['short_desc']}\n"
                    text += f"   👤 {inc['assignee']} | 📅 {inc['submit_date']}\n\n"
                
                if len(new_incidents) > 5:
                    text += f"... и ещё {len(new_incidents) - 5} инцидентов"
                
                try:
                    await bot.send_message(chat_id, text, parse_mode="HTML")
                except Exception as e:
                    pass
            
            last_incidents[login_id] = current_incident_ids
            
        except Exception as e:
            continue


# Store job references for dynamic interval updates
background_jobs = {}

def register_sd_background_task(app):
    """Зарегистрировать фоновую задачу проверки инцидентов"""
    jq = app.job_queue
    
    # Default: run every 5 minutes (will be filtered by user settings in the task)
    job = jq.run_repeating(check_incidents_background, interval=300, first=60)
    background_jobs['sd_polling'] = job
    print("✅ Background task for SD incident polling registered (every 5 minutes, respects user settings)")


def update_background_interval(app, interval_minutes: int):
    """Обновить интервал фоновой задачи"""
    jq = app.job_queue
    
    # Remove old job
    if 'sd_polling' in background_jobs:
        background_jobs['sd_polling'].remove()
    
    # Create new job with updated interval
    job = jq.run_repeating(check_incidents_background, interval=interval_minutes * 60, first=60)
    background_jobs['sd_polling'] = job
    print(f"✅ Background polling interval updated to {interval_minutes} minutes")


# === РЕГИСТРАЦИЯ В ПРИЛОЖЕНИИ ===
def register_sd_handlers(app):
    """Добавить обработчики ServiceDesk в бота"""
    app.add_handler(CommandHandler("sd", sd_start))
    app.add_handler(CommandHandler("sdmenu", sd_menu))
    app.add_handler(CommandHandler("my", sd_my))
    app.add_handler(CallbackQueryHandler(sd_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sd_message))
    print("✅ ServiceDesk обработчики зарегистрированы")


# === EXPORTED STORAGE ===
def get_sd_sessions():
    return sd_sessions

def get_sd_user_settings():
    return sd_user_settings

def set_sd_user_logins(logins):
    global sd_user_logins
    sd_user_logins = logins

def get_sd_user_logins():
    return sd_user_logins


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

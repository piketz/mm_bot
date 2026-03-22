"""
Модуль интеграции с ServiceDesk (Magnit)
Добавляет функционал для работы с заявками BMC Helix
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

# === КОНФИГУРАЦИЯ ===
BASE_URL = "https://mobilebmc.tander.ru"
API_JWT_LOGIN = f"{BASE_URL}/api/jwt/login"
API_INCIDENTS = f"{BASE_URL}/api/arsys/v1/entry/HPD:Help%20Desk"

# Хранилище сессий
sd_sessions = {}      # user_id -> {"token": str, "login_id": str}
sd_states = {}        # user_id -> state

# === SERVICEDESK API ===
def sd_login(login_id: str, password: str) -> str:
    """Авторизация в ServiceDesk"""
    data = urllib.parse.urlencode({'username': login_id, 'password': password}).encode('utf-8')
    req = urllib.request.Request(API_JWT_LOGIN, data=data, 
                                 headers={
                                     'Content-Type': 'application/x-www-form-urlencoded',
                                     'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 12)'
                                 })
    
    with urllib.request.urlopen(req) as response:
        result = response.read().decode('utf-8')
    
    token = result.strip().strip('"')
    if not token or len(token) < 20:
        raise Exception("Токен не получен")
    return token


def sd_get_incidents(token: str, group: str = "РГ Уфа Восток филиал") -> list:
    """Получить заявки"""
    headers = {
        'Authorization': token,
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 12)',
        'Accept': 'application/json'
    }
    
    query = f"'Status' = \"Assigned\" AND 'Assigned Group' = \"{group}\""
    url = f"{API_INCIDENTS}?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('entries', [])
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise Exception("Токен истёк")
        raise Exception(f"HTTP {e.code}")


def parse_incident(entry: dict) -> dict:
    values = entry.get('values', entry)
    return {
        'inc_num': values.get('Incident Number', 'N/A'),
        'short_desc': values.get('Short Description', '')[:50],
        'assignee': values.get('Assignee Login ID', 'Нет'),
        'submit_date': values.get('Submit Date', '')[:10],
        'status': values.get('Status', ''),
    }


# === ОБРАБОТЧИКИ TELEGRAM ===
async def sd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /sd - начало работы с ServiceDesk"""
    keyboard = [
        [InlineKeyboardButton("🔑 Логин + Пароль", callback_data="sd_auth_login")],
        [InlineKeyboardButton("🎫 Токен", callback_data="sd_auth_token")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📋 ServiceDesk (Magnit)\n\n"
        "Выберите способ авторизации:",
        reply_markup=reply_markup
    )


async def sd_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок"""
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


async def sd_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
    """Обработка текстовых сообщений для авторизации"""
    chat_id = update.message.chat.id
    text = update.message.text.strip()
    state = sd_states.get(chat_id)
    
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
            await update.message.reply_text("✅ Успешно авторизован!")
            await sd_show_incidents(update, context, chat_id)
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


async def sd_show_incidents(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Показать заявки"""
    session = sd_sessions.get(chat_id)
    if not session or not session.get("token"):
        # Кнопка для авторизации
        keyboard = [
            [InlineKeyboardButton("🔑 Авторизоваться", callback_data="sd_auth_login")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "❌ Сессия истекла. Авторизуйтесь:",
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id, 
                "❌ Сессия истекла. Используйте /sd для авторизации.",
                reply_markup=reply_markup
            )
        return
    
    await context.bot.send_message(chat_id, "🔄 Загружаю заявки...")
    
    try:
        entries = sd_get_incidents(session["token"])
        
        if not entries:
            await context.bot.send_message(chat_id, "📭 Заявок не найдено")
            return
        
        text = f"📋 Заявок (Assigned): {len(entries)}\n\n"
        
        for i, entry in enumerate(entries[:10], 1):
            inc = parse_incident(entry)
            text += f"{i}. #{inc['inc_num']}\n"
            text += f"   📝 {inc['short_desc']}\n"
            text += f"   👤 {inc['assignee']}\n"
            text += f"   📅 {inc['submit_date']}\n\n"
        
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
    app.add_handler(CallbackQueryHandler(sd_callback, pattern="^sd_"))
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

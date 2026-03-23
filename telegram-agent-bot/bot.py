"""
Telegram Bot with Agents: Programmer, Tester, DevOps, TeamLead
"""

import logging
import os

from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token from environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


# === AGENTS ===


class Agent:
    """Base agent class"""

    def __init__(self, name: str, role: str, description: str):
        self.name = name
        self.role = role
        self.description = description

    def respond(self, message: str) -> str:
        return f"[{self.name}] Получил сообщение: {message}"


class ProgrammerAgent(Agent):
    def __init__(self):
        super().__init__(
            "Programmer", "Разработчик", "Пишет код, создаёт функции, исправляет баги"
        )

    def respond(self, message: str) -> str:
        return f"""💻 *Programmer Agent*

Задача: {message}

_Готов написать код для этой задачи._"""


class TesterAgent(Agent):
    def __init__(self):
        super().__init__(
            "Tester", "Тестировщик", "Пишет тесты, ищет баги, проверяет качество"
        )

    def respond(self, message: str) -> str:
        return f"""🧪 *Tester Agent*

Задача: {message}

_Готов написать тесты и проверить код._"""


class DevOpsAgent(Agent):
    def __init__(self):
        super().__init__("DevOps", "Девопс", "Настраивает CI/CD, докер, деплой")

    def respond(self, message: str) -> str:
        return f"""🚀 *DevOps Agent*

Задача: {message}

_Готов настроить деплой и инфраструктуру._"""


class TeamLeadAgent(Agent):
    def __init__(self):
        super().__init__(
            "TeamLead", "Тимлид", "Координирует команду, проверяет архитектуру"
        )

    def respond(self, message: str) -> str:
        return f"""👑 *TeamLead Agent*

Задача: {message}

_Готов оценить задачу и распределить работу._"""


# Initialize agents
agents = {
    "programmer": ProgrammerAgent(),
    "tester": TesterAgent(),
    "devops": DevOpsAgent(),
    "teamlead": TeamLeadAgent(),
}


# === BOT HANDLERS ===


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message"""
    welcome_text = """👋 *Привет! Я бот с агентами!*

Я могу помочь тебе с:
- 💻 *Programmer* — написание кода
- 🧪 *Tester* — тестирование
- 🚀 *DevOps* — деплой и инфраструктура
- 👑 *TeamLead* — координация команды

Просто напиши @username нужного агента и задачу!

Например: `programmer написать функцию сложения`"""

    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help message"""
    help_text = """📖 *Доступные команды:*

/start — Приветствие
/help — Это сообщение

*Агенты:*
@programmer — разработка
@tester — тестирование  
@devops — деплой
@teamlead — тимлид

_Просто напиши имя агента и задачу в одном сообщении_"""

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    text = update.message.text.lower()
    chat_id = update.message.chat.id

    # Check which agent is mentioned
    response = None

    if "programmer" in text:
        response = agents["programmer"].respond(text)
    elif "tester" in text:
        response = agents["tester"].respond(text)
    elif "devops" in text:
        response = agents["devops"].respond(text)
    elif "teamlead" in text:
        response = agents["teamlead"].respond(text)
    else:
        response = """🤔 Не понял сообщение.

Попробуй так:
- `programmer написать функцию`
- `tester проверить код`
- `devops настроить деплой`
- `teamlead оценить задачу`"""

    await context.bot.send_message(
        chat_id=chat_id, text=response, parse_mode="Markdown"
    )


# === MAIN ===


def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        print("Error: Set TELEGRAM_BOT_TOKEN environment variable")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting...")
    print("🤖 Bot is running! Press Ctrl+C to stop.")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

"""
mm_bot - Telegram бот для ServiceDesk
"""

import logging
import os

from loguru import logger
from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

# Configure logging
logger.add("logs/bot.log", rotation="10 MB", retention="7 days", level="INFO")
logger.info("mm_bot starting...")

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SERVICE_DESK_URL = os.getenv("SERVICE_DESK_URL", "https://mobilebmc.tander.ru")
SERVICE_DESK_TOKEN = os.getenv("SERVICE_DESK_TOKEN")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await update.message.reply_text(
        "👋 Привет! Я mm_bot — бот для работы с ServiceDesk.\n\n"
        "Используй /help для списка команд."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(
        "📖 *Доступные команды:*\n\n"
        "/start - Начать работу\n"
        "/help - Показать справку\n"
        "/status - Статус подключения\n\n"
        "Просто отправь текст для создания заявки.",
        parse_mode="Markdown",
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    await update.message.reply_text(
        f"✅ *Статус:*\n\n" f"Service Desk: {SERVICE_DESK_URL}\n" f"Бот: Работает",
        parse_mode="Markdown",
    )


async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    user_text = update.message.text
    await update.message.reply_text(f"Получено: {user_text}")


def main():
    """Main application entry point"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

    # Debug: log first 4 chars of token
    logger.info(f"Bot token prefix: {TELEGRAM_BOT_TOKEN[:4]}****")

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, echo_handler)
    )

    # Start polling
    logger.info("Starting bot polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

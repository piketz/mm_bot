import re

# Read the file
with open('/home/ub/bot_uff_mm_prod/mm_bot.py', 'r') as f:
    content = f.read()

# Find and replace the start function
old_start = '''async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return await update.message.reply_text("⛔ У вас нет доступа.")

    await update.message.reply_text("Бот активирован и слушает.")'''

new_start = '''async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return await update.message.reply_text("⛔ У вас нет доступа.")

    menu_text = """📋 <b>МЕНЮ</b>

<b>Основные команды:</b>
/start - Показать это меню
/listusers - Список пользователей
/adduser - Добавить пользователя

<b>Поиск магазинов:</b>
Просто напишите название или адрес магазина

<b>Обновление данных:</b>
Отправьте Excel файл для обновления базы

💡 Бот автоматически ищет магазины по названию или адресу"""

    await update.message.reply_text(menu_text, parse_mode="HTML")'''

content = content.replace(old_start, new_start)

# Write back
with open('/home/ub/bot_uff_mm_prod/mm_bot.py', 'w') as f:
    f.write(content)

print('Done')

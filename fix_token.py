# Read the file
with open('/home/ub/bot_uff_mm_prod/mm_bot.py', 'r') as f:
    content = f.read()

# Find and replace the main function
old_main = '''def main():
    print("Старт бота...")
    load_table()
    if df.empty:
        print("Таблица пуста. Загрузите Excel файл.")

    app = ApplicationBuilder().token(TOKEN).build()


    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler("listusers", list_users))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(MessageHandler(filters.Document.ALL, update_excel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, listen_chat))

    print("Бот запущен и слушает чат.")
    app.run_polling()

if __name__ == "__main__":
    main()'''

new_main = '''def main():
    print("Старт бота...")
    load_table()
    if df.empty:
        print("Таблица пуста. Загрузите Excel файл.")

    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()

            app.add_handler(CommandHandler('start', start))
            app.add_handler(CommandHandler("listusers", list_users))
            app.add_handler(CommandHandler("adduser", add_user))
            app.add_handler(MessageHandler(filters.Document.ALL, update_excel))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, listen_chat))

            print("Бот запущен и слушает чат.")
            app.run_polling()
        except Exception as e:
            error_str = str(e).lower()
            if "invalidtoken" in error_str or "unauthorized" in error_str or "token" in error_str:
                print(f"❌ Ошибка токена: {e}")
                print("⏳ Жду 10 секунд перед повторной попыткой...")
                import time
                time.sleep(10)
            else:
                raise

if __name__ == "__main__":
    main()'''

content = content.replace(old_main, new_main)

# Write back
with open('/home/ub/bot_uff_mm_prod/mm_bot.py', 'w') as f:
    f.write(content)

print('Done')

import pandas as pd
import servicedesk
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, filters, CallbackQueryHandler
)
import time
import os
import re
from telegram import ReactionTypeEmoji
import json

# -------------------------------------------------
# НАСТРОЙКИ
# -------------------------------------------------

#ALLOWED_USERS = {4279064, 8256795316, 5242213145, 356114896, 353840047, 8515453915, 1720935090,
#                 312347422, 8552570310, 999335968, 5193031454}


# 4279064 - pz
# 8256795316 миша
# 5242213145 макс
# 356114896 паша
# 353840047 гриша
# 8515453915 ринат
# 1720935090 женя
# 312347422 артем
# 8552570310 мой2
# 999335968 алмаз
# 5193031454 ринат2
#

CONFIG_FILE = "config.json"

def load_config():
    # Если файла нет — создаём пустой
    if not os.path.exists(CONFIG_FILE):
        config = {
            "bot_token": os.getenv("BOT_TOKEN", ""),
            "admins": [],
            "allowed": []
        }
        save_config(config)
        return config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Проверяем первичного админа
    primary_admin = os.getenv("PRIMARY_ADMIN_ID")
    if primary_admin and int(primary_admin) not in config.get("admins", []):
        config["admins"].append(int(primary_admin))
        if int(primary_admin) not in config.get("allowed", []):
            config["allowed"].append(int(primary_admin))
        save_config(config)
        print(f"✅ Первичный админ {primary_admin} добавлен в config.json")

    return config

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

config = load_config()
TOKEN = config["bot_token"]
ADMINS = set(config["admins"])
ALLOWED = set(config["allowed"])

df = pd.DataFrame()
last_response_time = {}  # {нормализованное_название_мм: время_последнего_ответа}


# -------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -------------------------------------------------
def is_allowed(user_id):
    return user_id in ALLOWED


def norm(text):
   # """Нормализация текста для точного и частичного поиска"""
    if not text:
        return ""
    text = str(text).strip().lower()
    # убираем все не буквенно-цифровые символы, кроме пробелов
    text = re.sub(r'[^а-яa-z0-9\s]', '', text)
    # заменяем несколько пробелов одним
    text = re.sub(r'\s+', ' ', text)
    return text

# -------------------------------------------------
# ЗАГРУЗКА ТАБЛИЦЫ EXCEL + ФИЛЬТР ПО ФИЛИАЛУ
# -------------------------------------------------
REQUIRED_COLUMNS = [
    "магазин",
    "код",
    "статус",
    "тип",
    "фио системотехника",
    "телефон системотехника",
    "филиал"
]


def load_table():
    global df
    print("📥 Попытка загрузки data.xlsx...")
    start_time = time.time()
    try:
        tmp = pd.read_excel("data.xlsx")
        tmp.columns = tmp.columns.str.lower().str.strip()
        print(f"📄 Файл загружен. Колонки: {tmp.columns.tolist()}")

        # Проверка всех обязательных столбцов
        missing_columns = [col for col in REQUIRED_COLUMNS if col not in tmp.columns]
        if missing_columns:
            print(f"❌ Ошибка: отсутствуют обязательные колонки: {missing_columns}")
            print("❌ Файл не обновлён.")
            return  # не обновляем df

        # Фильтруем по филиалам
        allowed_branches = ["уфа восток", "уфа запад"]
        filtered = tmp[tmp["филиал"].astype(str).str.lower().str.strip().isin(allowed_branches)]

        if filtered.empty:
            print("⚠ Внимание: нет строк с Филиал = 'Уфа Восток'. Таблица не обновлена.")
        else:
            print(f"✔ Загружено ММ после фильтра по филиалам: {len(filtered)} строк")
            df = filtered  # обновляем только если строки есть

    except FileNotFoundError:
        print("❌ Файл data.xlsx не найден. Таблица пуста.")
    except Exception as e:
        print("❌ Ошибка при загрузке data.xlsx:", e)
    finally:
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"⏱ Время загрузки файла: {elapsed:.2f} секунд")



async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    if not user:
        return  # например channel_post — у него нет отправителя

    user_id = user.id

    # Проверка прав
    if user_id not in ADMINS:
        await update.effective_message.reply_text("❌ У вас нет прав для добавления пользователей.")
        return

    if len(context.args) != 1:
        await update.effective_message.reply_text("Использование: /adduser <user_id>")
        return

    try:
        new_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("❌ ID должен быть числом.")
        return

    if new_id in ALLOWED:
        await update.effective_message.reply_text("ℹ Этот пользователь уже есть в списке.")
        return

    ALLOWED.add(new_id)
    config["allowed"] = list(ALLOWED)
    save_config(config)

    await update.effective_message.reply_text(f"✅ Пользователь {new_id} добавлен.")


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in ADMINS:
        await update.message.reply_text("❌ У вас нет прав.")
        return

    admins_str = "\n".join(str(uid) for uid in ADMINS)
    allowed_str = "\n".join(str(uid) for uid in ALLOWED)

    text = (
        "📋 *Список пользователей*\n\n"
        "*Админы:*\n"
        f"{admins_str}\n\n"
        "*Разрешённые пользователи:*\n"
        f"{allowed_str}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# -------------------------------------------------
# /start
# -------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return await update.message.reply_text("⛔ У вас нет доступа.")

    keyboard = [
        [InlineKeyboardButton("📋 Меню", callback_data="show_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = """👋 Добро пожаловать в бот управления ММ!

Нажмите кнопку ниже, чтобы открыть меню."""

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку Меню"""
    query = update.callback_query
    await query.answer()

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

    keyboard = [
        [InlineKeyboardButton("📋 Меню", callback_data="show_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(menu_text, parse_mode="HTML", reply_markup=reply_markup)


# -------------------------------------------------
# ОБНОВЛЕНИЕ EXCEL
# -------------------------------------------------
async def update_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    print(f"[CHAT:{chat.title if chat.title else chat.id}] {user.full_name} ({user.id}) отправил файл: {update.message.document.file_name}")

    if not is_allowed(user.id):
        return await update.message.reply_text("⛔ У вас нет доступа.")

    if not update.message.document:
        return

    file = update.message.document

    if not file.file_name.lower().endswith(".xlsx"):
        return await update.message.reply_text("Требуется Excel (.xlsx) файл!")

    new_file = await file.get_file()
    await new_file.download_to_drive("data.xlsx")

    # --- Загружаем временный df ---
    temp_df = pd.read_excel("data.xlsx")
    temp_df.columns = [str(c).strip().lower() for c in temp_df.columns]
    required_cols = ["код", "магазин", "статус", "тип", "фио системотехника", "телефон системотехника", "филиал"]
    if not all(col in temp_df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in temp_df.columns]
        await update.message.reply_text(f"❌ Файл не содержит обязательные колонки: {', '.join(missing)}")
        return

    # Фильтруем филиалы
    temp_df = temp_df[temp_df["филиал"].isin(["Уфа Восток", "Уфа Запад"])]
    if temp_df.empty:
        return await update.message.reply_text("❌ Файл не содержит строки с филиалами Уфа Восток или Уфа Запад.")

    global df
    if df is not None and df.equals(temp_df):
        await update.message.reply_text("❌ Файл не обновлён. Данные совпадают с текущей таблицей.")
        return

    df = temp_df.copy()
    await update.message.reply_text(f"✔ Таблица успешно обновлена! Количество ММ: {len(df)}")



# -------------------------------------------------
# ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ
# -------------------------------------------------
async def listen_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    # ---------------------------------------
    # Реакция на конкретного пользователя
    # ---------------------------------------

  #  try:
  #      if update.message.from_user and update.message.from_user.id == 4279064: # 8256795316
  #          await update.message.set_reaction(ReactionTypeEmoji("🔩"))
  #          print("Добавлена реакция 🔩 на сообщение пользователя 8256795316")
  #  except Exception as e:
  #      print("Ошибка при попытке добавить реакцию:", e)

    user = update.effective_user
    chat = update.effective_chat
    text_raw = update.message.text
    # Skip if user is in ServiceDesk session
    import servicedesk
    if chat.id in servicedesk.sd_sessions:
        return  # Let SD handlers process this message


    # --------------------- ОТЛАДКА ---------------------
    print(f"[CHAT:{chat.title if chat.title else chat.id}] {user.full_name} ({user.id}): {text_raw}")

    if not is_allowed(user.id):
        print(f"⛔ Доступ запрещён: {user.full_name} ({user.id})")
        return

    if df.empty:
        print("⚠ Таблица пуста — пропускаю обработку")
        return

    msg_norm = norm(text_raw)

    # --------------------- УСЛОВИЯ ЧАСТИЧНОГО ПОИСКА ---------------------
    is_question = msg_norm.startswith("чей ") or msg_norm.startswith("какой ") or msg_norm.startswith("кто ")
    bot_mentioned = context.bot.username.lower() in msg_norm
    reply_to_bot = update.message.reply_to_message and \
                    update.message.reply_to_message.from_user.id == context.bot.id

    use_partial = is_question or bot_mentioned or reply_to_bot

    # ----------------------------------------------------
    #                  ПОИСК МАГАЗИНА
    # ----------------------------------------------------
    for _, row in df.iterrows():
        mm_raw = str(row["магазин"]).strip()
        mm_norm = norm(mm_raw)
        mm_words = mm_norm.split()

        found = False

        # ---------- ТОЧНОЕ СОВПАДЕНИЕ СЛОВОМ ----------
        if re.search(rf"\b{re.escape(mm_norm)}\b", msg_norm):
            found = True

        # ---------- ЧАСТИЧНОЕ СОВПАДЕНИЕ (ПО СЛОВАМ) ----------
        elif use_partial:
            if any(re.search(rf"\b{re.escape(w)}\b", msg_norm) for w in mm_words):
                found = True

        if not found:
            continue

        # ---------------- ОГРАНИЧЕНИЕ 1 РАЗ В ЧАС ----------------
        now = datetime.now()
        last_time = last_response_time.get(mm_norm)
        if last_time and now - last_time < timedelta(hours=1):
            print(f"⏳ Ограничение: уже отвечал по {mm_raw}")
            return
        last_response_time[mm_norm] = now

        # ---------------- ПОДГОТОВКА ДАННЫХ ----------------
        branch = str(row.get("филиал", "-")).strip()
        branch_suffix = f" ! {branch}" if branch.lower() == "уфа запад" else ""

        # Телефон без .0
        phone_val = row.get("телефон системотехника")
        if pd.notna(phone_val):
            try:
                phone = str(int(phone_val))
            except:
                phone = str(phone_val)
        else:
            phone = "-"
        FULL_REPORT_KEYWORDS = ["полный отчет", "полностью", "отчет", "информация", "инфо", "статус"]
        # Определяем — нужен ли полный отчёт
        full_report = any(k in msg_norm for k in FULL_REPORT_KEYWORDS)

        # ---------------- ПОЛНЫЙ ОТЧЁТ ----------------
        if full_report:
            reply_lines = []

            for col in row.index:
                val = row[col]
                if pd.isna(val):
                    val = "-"
                if col == "телефон системотехника":
                    try:
                        val = str(int(val))
                    except:
                        val = str(val)
                reply_lines.append(f"{col}: {val}")

            # дата обновления data.xlsx
            try:
                mtime = os.path.getmtime("data.xlsx")
                update_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                reply_lines.append(f"Дата обновления базы: {update_time}")
            except:
                reply_lines.append("Дата обновления базы: неизвестна")

            reply = "\n".join(reply_lines)

        else:
            # ---------------- КОМПАКТНЫЙ ВЫВОД ----------------
            name = row.get("магазин", "-")
            mm_type = row.get("тип", "-")
            code = row.get("код", "-")
            status = row.get("статус", "-")
            tech = row.get("фио системотехника", "-")

            status_text = f"<b>{status}</b>" if status.lower() == "закрыт" else status

            line1 = f"{name} {mm_type} ({code}) {status_text}{branch_suffix}"
            line2 = f"{tech} {phone}"
            reply = f"{line1}\n{line2}"

        print(f"✅ Бот отвечает на ММ: {mm_raw} (полный отчёт: {full_report})")
        await update.message.reply_text(reply, parse_mode="HTML")
        return




# -------------------------------------------------
# ЗАПУСК
# -------------------------------------------------
def main():
    print("Старт бота...")
    load_table()
    if df.empty:
        print("Таблица пуста. Загрузите Excel файл.")

    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()

            app.add_handler(CommandHandler('start', start))
            app.add_handler(CallbackQueryHandler(menu_callback, pattern="show_menu"))
            app.add_handler(CommandHandler("listusers", list_users))
            app.add_handler(CommandHandler("adduser", add_user))
            app.add_handler(MessageHandler(filters.Document.ALL, update_excel))
            servicedesk.register_sd_handlers(app)
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
    main()


import pandas as pd
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, filters
)
import time
import os
import re
from telegram import ReactionTypeEmoji
import json


CONFIG_FILE = "config.json"

def load_config():

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
last_response_time = {}


def is_allowed(user_id):
    return user_id in ALLOWED


def norm(text):
    if not text:
        return ""
    text = str(text).strip().lower()
    text = re.sub(r'[^а-яa-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


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

        missing_columns = [col for col in REQUIRED_COLUMNS if col not in tmp.columns]
        if missing_columns:
            print(f"❌ Ошибка: отсутствуют обязательные колонки: {missing_columns}")
            print("❌ Файл не обновлён.")
            return

        allowed_branches = ["уфа восток", "уфа запад"]
        filtered = tmp[tmp["филиал"].astype(str).str.lower().str.strip().isin(allowed_branches)]

        if filtered.empty:
            print("⚠ Внимание: нет строк с Филиал = 'Уфа Восток'. Таблица не обновлена.")
        else:
            print(f"✔ Загружено ММ после фильтра по филиалам: {len(filtered)} строк")
            df = filtered

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
        return

    user_id = user.id

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




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return await update.message.reply_text("⛔ У вас нет доступа.")

    await update.message.reply_text("Бот активирован и слушает.")


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

    temp_df = pd.read_excel("data.xlsx")
    temp_df.columns = [str(c).strip().lower() for c in temp_df.columns]
    required_cols = ["код", "магазин", "статус", "тип", "фио системотехника", "телефон системотехника", "филиал"]
    if not all(col in temp_df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in temp_df.columns]
        await update.message.reply_text(f"❌ Файл не содержит обязательные столбцы: {', '.join(missing)}")
        return

    temp_df = temp_df[temp_df["филиал"].isin(["Уфа Восток", "Уфа Запад"])]
    if temp_df.empty:
        return await update.message.reply_text("❌ Файл не содержит строки с филиалами Уфа Восток или Уфа Запад.")

    global df
    if df is not None and df.equals(temp_df):
        await update.message.reply_text("❌ Файл не обновлён. Данные совпадают с текущей таблицей.")
        return

    df = temp_df.copy()
    await update.message.reply_text(f"✔ Таблица успешно обновлена! Количество ММ: {len(df)}")



async def listen_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    chat = update.effective_chat
    text_raw = update.message.text

    #print(f"[CHAT:{chat.title if chat.title else chat.id}] {user.full_name} ({user.id}): {text_raw}")

    if not is_allowed(user.id):
        print(f"⛔ Доступ запрещён: {user.full_name} ({user.id})")
        return

    if df.empty:
        print("⚠ Таблица пуста — пропускаю обработку")
        return

    msg_norm = norm(text_raw)

    is_question = msg_norm.startswith("чей ") or msg_norm.startswith("какой ") or msg_norm.startswith("кто ")
    bot_mentioned = context.bot.username.lower() in msg_norm
    reply_to_bot = update.message.reply_to_message and \
                    update.message.reply_to_message.from_user.id == context.bot.id

    use_partial = is_question or bot_mentioned or reply_to_bot

    for _, row in df.iterrows():
        mm_raw = str(row["магазин"]).strip()
        mm_norm = norm(mm_raw)
        mm_words = mm_norm.split()

        found = False

        if re.search(rf"\b{re.escape(mm_norm)}\b", msg_norm):
            found = True

        elif use_partial:
            if any(re.search(rf"\b{re.escape(w)}\b", msg_norm) for w in mm_words):
                found = True

        if not found:
            continue

        FULL_REPORT_KEYWORDS = ["полный отчет", "полностью", "отчет", "информация", "инфо", "статус"]
        full_report = any(k in msg_norm for k in FULL_REPORT_KEYWORDS)

        # 🔒 Лимит ТОЛЬКО для обычных запросов
        if not full_report:
            now = datetime.now()
            last_time = last_response_time.get(mm_norm)
            if last_time and now - last_time < timedelta(hours=1):
                print(f"⏳ Ограничение: уже отвечал по {mm_raw}")
                return
            last_response_time[mm_norm] = now

        branch = str(row.get("филиал", "-")).strip()
        branch_suffix = f" ! {branch}" if branch.lower() == "уфа запад" else ""

        phone_val = row.get("телефон системотехника")
        if pd.notna(phone_val):
            try:
                phone = str(int(phone_val))
            except:
                phone = str(phone_val)
        else:
            phone = "-"

        if full_report:
            def safe(v):
                return "-" if pd.isna(v) else str(v)

            shop = safe(row.get("магазин"))
            mm_type = safe(row.get("тип"))
            code = safe(row.get("код"))
            format_mm = safe(row.get("формат"))
            branch = safe(row.get("филиал"))
            open_date = safe(row.get("дата открытия"))
            close_date = safe(row.get("дата закрытия"))
            email = safe(row.get("email"))
            tech = safe(row.get("фио системотехника"))

            phone_val = row.get("телефон системотехника")
            if pd.notna(phone_val):
                try:
                    tech_phone = str(int(phone_val))
                except:
                    tech_phone = str(phone_val)
            else:
                tech_phone = "-"

            address = safe(row.get("полный адрес"))

            reply_lines = [
                f"магазин: {mm_type} {shop} ({code})",
                f"формат: {format_mm}",
                f"филиал: {branch}",
                f"дата открытия: {open_date}",
                f"дата закрытия: {close_date}",
                f"email: {email}",
                f"фио системотехника: {tech} ({tech_phone})",
                f"полный адрес: {address}",
            ]

            try:
                mtime = os.path.getmtime("data.xlsx")
                update_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                reply_lines.append(f"Дата обновления выгрузки: {update_time}")
            except:
                reply_lines.append("Дата обновления выгрузки: неизвестна")

            reply = "\n".join(reply_lines)

        else:
            name = row.get("магазин", "-")
            mm_type = row.get("тип", "-")
            code = row.get("код", "-")
            status = row.get("статус", "-")
            tech = row.get("фио системотехника", "-")

            status_text = f"<b>{status}</b>" if status.lower() == "закрыт" else status

            line1 = f"{name} {mm_type} ({code}) {status_text}{branch_suffix}"
            line2 = f"{tech} {phone}"
            reply = f"{line1}\n{line2}"

       # print(f"✅ Бот отвечает на ММ: {mm_raw} (полный отчёт: {full_report})")
        await update.message.reply_text(reply, parse_mode="HTML")
        return


def main():
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

    print("Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()

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

def mask_password(text):
    """Замаскировать пароли в логах"""
    return re.sub(r'(пароль|password|passwd):\s*\S+', r': ***', text, flags=re.IGNORECASE)
import json

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        config = {"bot_token": os.getenv("BOT_TOKEN", ""), "admins": [], "allowed": []}
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

REQUIRED_COLUMNS = ["магазин", "код", "статус", "тип", "фио системотехника", "телефон системотехника", "филиал"]

def load_table():
    global df
    print("📥 Загрузка data.xlsx...")
    start = time.time()
    try:
        tmp = pd.read_excel("data.xlsx")
        tmp.columns = tmp.columns.str.lower().str.strip()
        print(f"📄 Колонки: {tmp.columns.tolist()}")
        miss = [c for c in REQUIRED_COLUMNS if c not in tmp.columns]
        if miss:
            print(f"❌ Нет колонок: {miss}")
            return
        allowed = ["уфа восток", "уфа запад"]
        filtered = tmp[tmp["филиал"].astype(str).str.lower().str.strip().isin(allowed)]
        if filtered.empty:
            print("⚠ Нет строк")
        else:
            print(f"✔ Загружено: {len(filtered)}")
            df = filtered
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    print(f"⏱ {time.time()-start:.2f} сек")

async def add_user(update, context):
    user = update.effective_user
    if not user or user.id not in ADMINS:
        return
    if len(context.args) != 1:
        await update.message.reply_text("/adduser <id>")
        return
    try:
        new_id = int(context.args[0])
    except:
        await update.message.reply_text("ID число")
        return
    ALLOWED.add(new_id)
    config["allowed"] = list(ALLOWED)
    save_config(config)
    await update.message.reply_text(f"✅ {new_id} добавлен")

async def list_users(update, context):
    if update.message.from_user.id not in ADMINS:
        return
    await update.message.reply_text(f"Админы: {ADMINS}\nРазрешённые: {ALLOWED}", parse_mode="Markdown")

async def start(update, context):
    if not is_allowed(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа")
    cnt = len(df) if not df.empty else 0
    await update.message.reply_text(f"👋 Бот ММ\nММ в базе: {cnt}\nНапиши название магазина")

async def menu_callback(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📋 МЕНЮ\n/start - Меню\n/sd - Заявки", parse_mode="HTML")

async def update_excel(update, context):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    if not update.message.document:
        return
    if not update.message.document.file_name.lower().endswith(".xlsx"):
        return
    await update.message.document.get_file().download_to_drive("data.xlsx")
    tmp = pd.read_excel("data.xlsx")
    tmp.columns = [c.strip().lower() for c in tmp.columns]
    cols = ["код", "магазин", "статус", "тип", "фио системотехника", "телефон системотехника", "филиал"]
    if not all(c in tmp.columns for c in cols):
        return
    tmp = tmp[tmp["филиал"].isin(["Уфа Восток", "Уфа Запад"])]
    if tmp.empty:
        return
    global df
    df = tmp.copy()
    await update.message.reply_text(f"✔ Обновлено! ММ: {len(df)}")

async def handle_message(update, context):
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    chat = update.effective_chat
    print(f"[{user.id}] {update.message.text[:30]}")
    if not is_allowed(user.id):
        return
    if chat.type == "private" and servicedesk.sd_states.get(chat.id):
        await servicedesk.sd_handle_auth(update, context)
        return
    if df.empty:
        return
    txt = norm(update.message.text)
    is_q = txt.startswith("чей ") or txt.startswith("какой ")
    use_part = is_q or context.bot.username.lower() in txt
    for _, r in df.iterrows():
        mm = norm(str(r["магазин"]))
        words = mm.split()
        found = False
        if re.search(rf"\b{re.escape(mm)}\b", txt):
            found = True
        elif use_part and any(re.search(rf"\b{re.escape(w)}\b", txt) for w in words):
            found = True
        if not found:
            continue
        now = datetime.now()
        if mm in last_response_time and now - last_response_time[mm] < timedelta(hours=1):
            return
        last_response_time[mm] = now
        branch = str(r.get("филиал","")).strip()
        suffix = f" ! {branch}" if branch.lower() == "уфа запад" else ""
        ph = r.get("телефон системотехника")
        phone = str(int(ph)) if pd.notna(ph) else "-"
        full = any(k in txt for k in ["полный","отчет","инфо","статус"])
        if full:
            lines = [f"{c}: {r[c]}" for c in r.index]
            try:
                lines.append(f"База: {datetime.fromtimestamp(os.path.getmtime('data.xlsx')).strftime('%Y-%m-%d %H:%M')}")
            except:
                pass
            reply = "\n".join(lines)
        else:
            reply = f"{r['магазин']} {r['тип']} ({r['код']}) {r['статус']}{suffix}\n{r['фио системотехника']} {phone}"
        await update.message.reply_text(reply, parse_mode="HTML")
        return

def main():
    print("Старт...")
    load_table()
    while True:
        try:
            async def on_start(app):
                v = os.getenv("BOT_VERSION","?")
                c = len(df) if not df.empty else 0
                try:
                    await app.bot.send_message(chat_id=4279064, text=f"Bot {v}\nММ: {c}")
                except: pass
            app = ApplicationBuilder().token(TOKEN).post_init(on_start).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CallbackQueryHandler(menu_callback, pattern="show_menu"))
            app.add_handler(CommandHandler("listusers", list_users))
            app.add_handler(CommandHandler("adduser", add_user))
            app.add_handler(CommandHandler("sd", servicedesk.sd_start))
            app.add_handler(CommandHandler("my", servicedesk.sd_my))
            app.add_handler(CallbackQueryHandler(servicedesk.sd_callback))
            app.add_handler(MessageHandler(filters.Document.ALL, update_excel))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            print("✅ Бот работает")
            app.run_polling()
        except Exception as e:
            print(f"❌ {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

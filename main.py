import telebot
from telebot import types
from datetime import datetime, timedelta
import sqlite3
import threading
import time
import pytz
import random
import calendar
import json

TOKEN = "8416301413:AAEUNs3pvR80Rci-RokQ3Ks6mzRTgIUAeMo"
bot = telebot.TeleBot(TOKEN)

# ================= БД =================
db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    timezone TEXT,
    points INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    last_done TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    time TEXT,
    status TEXT DEFAULT 'active',
    notified_count INTEGER DEFAULT 0,
    media TEXT
)
""")
db.commit()


# ================= STATE =================
user_states = {}

def reset(uid):
    user_states[uid] = {}

def get_state(uid):
    return user_states.get(uid, {})

# ================= TIMEZONES =================
TIMEZONE_MAP = {
    "🕐 Калининград": "Europe/Kaliningrad",
    "🕑 Москва": "Europe/Moscow",
    "🕒 Самара": "Europe/Samara",
    "🕓 Екатеринбург": "Asia/Yekaterinburg",
    "🕔 Омск": "Asia/Omsk",
    "🕕 Красноярск": "Asia/Krasnoyarsk",
    "🕖 Иркутск": "Asia/Irkutsk",
    "🕗 Якутск": "Asia/Yakutsk",
    "🕘 Владивосток": "Asia/Vladivostok",
    "🕙 Магадан": "Asia/Magadan",
    "🕚 Камчатка": "Asia/Kamchatka"
}

# ================= ФРАЗЫ =================
phrases_done = [
    "Красава! Так держать 💪",
    "Отличная работа 🔥",
    "Ты становишься дисциплинированнее 😎",
    "Ещё один шаг к цели 🚀"
]

phrases_streak = [
    "Серия продолжается 🔥",
    "Ты в ритме 💯",
    "Так держать!"
]

# ================= START =================
@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.chat.id
    reset(uid)

    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    db.commit()

    cursor.execute("SELECT timezone FROM users WHERE user_id=?", (uid,))
    tz = cursor.fetchone()

    if not tz or tz[0] is None:
        user_states[uid] = {"step": "tz"}

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for region in TIMEZONE_MAP.keys():
            kb.add(region)

        bot.send_message(uid, "🇷🇺 Выбери свой регион:", reply_markup=kb)
        return

    menu(uid)

# ================= MENU =================
def menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить", "📋 Список")
    kb.add("📊 Прогресс")
    bot.send_message(uid, "📌 Главное меню:", reply_markup=kb)

# ================= TZ =================
@bot.message_handler(func=lambda m: get_state(m.chat.id).get("step") == "tz")
def set_tz(msg):
    uid = msg.chat.id

    if msg.text not in TIMEZONE_MAP:
        bot.send_message(uid, "❌ Выбери регион с кнопок")
        return

    tz = TIMEZONE_MAP[msg.text]
    cursor.execute("UPDATE users SET timezone=? WHERE user_id=?", (tz, uid))
    db.commit()

    reset(uid)
    bot.send_message(uid, f"✅ Регион установлен: {msg.text}")
    menu(uid)


#------------------------------calendar-------------

def get_calendar(year, month):
    kb = types.InlineKeyboardMarkup()

    # заголовок
    kb.row(
        types.InlineKeyboardButton("<", callback_data=f"cal_prev_{year}_{month}"),
        types.InlineKeyboardButton(f"{month}.{year}", callback_data="ignore"),
        types.InlineKeyboardButton(">", callback_data=f"cal_next_{year}_{month}")
    )

    # дни недели
    kb.row(*[types.InlineKeyboardButton(d, callback_data="ignore") for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]])

    cal = calendar.monthcalendar(year, month)

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                row.append(types.InlineKeyboardButton(str(day), callback_data=f"day_{year}_{month}_{day}"))
        kb.row(*row)

    return kb

@bot.callback_query_handler(func=lambda c: c.data.startswith("cal_"))
def calendar_nav(call):
    _, action, year, month = call.data.split("_")
    year, month = int(year), int(month)

    if action == "prev":
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    elif action == "next":
        month += 1
        if month == 13:
            month = 1
            year += 1

    bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_calendar(year, month)
    )

# ================= ADD =================
@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add(msg):
    uid = msg.chat.id
    user_states[uid] = {"step": "text"}
    bot.send_message(uid, "✏️ Введи текст задачи:")

@bot.message_handler(func=lambda m: get_state(m.chat.id).get("step") == "text")
def add_text(msg):
    uid = msg.chat.id
    user_states[uid]["text"] = msg.text
    now = datetime.now()
    user_states[uid]["step"] = "calendar"
    bot.send_message(uid, "📅 Выбери дату:", reply_markup=get_calendar(now.year, now.month))
@bot.callback_query_handler(func=lambda c: c.data.startswith("day_"))
def select_day(call):
    _, y, m, d = call.data.split("_")

    uid = call.message.chat.id

    user_states[uid]["date"] = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    user_states[uid]["step"] = "time"

    bot.send_message(uid, f"📅 Дата выбрана: {d}.{m}\n⏰ Введи время (ЧЧ:ММ)")

@bot.message_handler(func=lambda m: get_state(m.chat.id).get("step") == "time")
def add_time(msg):
    uid = msg.chat.id

    try:
        t = datetime.strptime(msg.text, "%H:%M").time()
    except:
        bot.send_message(uid, "❌ Неверный формат времени (пример: 14:30)")
        return

    dt = datetime.combine(datetime.now().date(), t)

    user_states[uid]["time"] = dt.isoformat()
    user_states[uid]["media"] = []
    user_states[uid]["step"] = "media"

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Готово")

    bot.send_message(uid, "📎 Отправь фото / голос / файл (при необходимости), потом нажми Готово", reply_markup=kb)
@bot.callback_query_handler(func=lambda c: c.data == "ignore")
def ignore(call):
    bot.answer_callback_query(call.id)


# ================= MEDIA =================
@bot.message_handler(content_types=['photo', 'voice', 'document'],
                     func=lambda m: get_state(m.chat.id).get("step") == "media")
def handle_media(msg):
    uid = msg.chat.id
    media = user_states[uid].get("media", [])

    if msg.content_type == 'photo':
        media.append({"type": "photo", "id": msg.photo[-1].file_id})

    elif msg.content_type == 'voice':
        media.append({"type": "voice", "id": msg.voice.file_id})

    elif msg.content_type == 'document':
        media.append({"type": "document", "id": msg.document.file_id})

    user_states[uid]["media"] = media
    bot.send_message(uid, f"📎 Добавлено: {len(media)}")


@bot.message_handler(func=lambda m: get_state(m.chat.id).get("step") == "media")
def finish_media(msg):
    if msg.text == "✅ Готово":
        save_reminder(msg.chat.id)


# ================= SAVE =================
def save_reminder(uid):
    data = user_states[uid]

    cursor.execute("""
        INSERT INTO reminders (user_id, text, time, media)
        VALUES (?, ?, ?, ?)
        """, (
        uid,
        data["text"],
        data["time"],
        json.dumps(data.get("media", []))
    ))

    db.commit()
    reset(uid)

    bot.send_message(uid, "✅ Напоминание создано")
    menu(uid)


# ================= LIST =================
@bot.message_handler(func=lambda m: m.text == "📋 Список")
def list_reminders(msg):
    uid = msg.chat.id

    cursor.execute("SELECT id, text, time FROM reminders WHERE user_id=? AND status='active'", (uid,))
    rows = cursor.fetchall()

    if not rows:
        bot.send_message(uid, "📭 Нет задач")
        return

    for rid, text, t in rows:
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("✅", callback_data=f"done_{rid}"),
            types.InlineKeyboardButton("✏️", callback_data=f"edit_{rid}"),
            types.InlineKeyboardButton("❌", callback_data=f"del_{rid}")
        )
        bot.send_message(uid, f"📌 {text}\n⏰ {t}", reply_markup=kb)


# ================= DONE =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("done_"))
def done(call):
    uid = call.message.chat.id
    rid = int(call.data.split("_")[1])

    cursor.execute("UPDATE reminders SET status='done', notified_count=0 WHERE id=?", (rid,))
    cursor.execute("UPDATE users SET points = points + 10 WHERE user_id=?", (uid,))

    today = datetime.now().date().isoformat()
    cursor.execute("SELECT last_done, streak FROM users WHERE user_id=?", (uid,))
    last, streak = cursor.fetchone()

    if last == today:
        pass
    elif last == (datetime.now().date() - timedelta(days=1)).isoformat():
        streak += 1
    else:
        streak = 1

    cursor.execute("UPDATE users SET streak=?, last_done=? WHERE user_id=?", (streak, today, uid))
    db.commit()

    text = random.choice(phrases_done)
    if streak >= 3:
        text += "\n" + random.choice(phrases_streak)

    bot.answer_callback_query(call.id, "✅ Выполнено")
    bot.send_message(uid, text)


# ================= DELETE =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete(call):
    rid = int(call.data.split("_")[1])
    cursor.execute("DELETE FROM reminders WHERE id=?", (rid,))
    db.commit()
    bot.answer_callback_query(call.id, "Удалено")


# ================= EDIT =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_"))
def edit(call):
    uid = call.message.chat.id
    rid = int(call.data.split("_")[1])
    user_states[uid] = {"edit": rid}
    bot.send_message(uid, "✏️ Введи новый текст:")


@bot.message_handler(func=lambda m: "edit" in get_state(m.chat.id))
def save_edit(msg):
    uid = msg.chat.id
    rid = user_states[uid]["edit"]

    cursor.execute("UPDATE reminders SET text=? WHERE id=?", (msg.text, rid))
    db.commit()

    reset(uid)
    bot.send_message(uid, "✅ Обновлено")

# ================= PROGRESS =================
@bot.message_handler(func=lambda m: m.text == "📊 Прогресс")
def progress(msg):
    uid = msg.chat.id

    cursor.execute("SELECT points, streak FROM users WHERE user_id=?", (uid,))
    points, streak = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM reminders WHERE user_id=? AND status='done'", (uid,))
    done = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reminders WHERE user_id=? AND status='active'", (uid,))
    active = cursor.fetchone()[0]

    bot.send_message(uid,
                     f"📊 Прогресс:\n"
                     f"⭐ Очки: {points}\n"
                     f"🔥 Серия: {streak}\n"
                     f"✅ Выполнено: {done}\n"
                     f"⏳ Активных: {active}")

# ================= SEND =================
def send_reminder(uid, rid, text, media_json=None, repeat=False):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅", callback_data=f"done_{rid}"),
        types.InlineKeyboardButton("⏳", callback_data=f"snooze_{rid}")
    )

    msg_text = f"🔔 Повтор:\n{text}" if repeat else f"⏰ Напоминание:\n{text}"
    bot.send_message(uid, msg_text, reply_markup=kb)

    if media_json:
        media = json.loads(media_json)
        for item in media:
            try:
                if item["type"] == "photo":
                    bot.send_photo(uid, item["id"])
                elif item["type"] == "voice":
                    bot.send_voice(uid, item["id"])
                elif item["type"] == "document":
                    bot.send_document(uid, item["id"])
            except:
                continue

# ================= CHECKER =================
def checker():
    while True:
        now = datetime.now()

        cursor.execute("""
            SELECT id, user_id, text, time, media, notified_count 
            FROM reminders 
            WHERE status='active'
        """)
        rows = cursor.fetchall()

        for rid, uid, text, t, media, count in rows:
            try:
                rt = datetime.fromisoformat(t)

                if rt <= now and count == 0:
                    send_reminder(uid, rid, text, media)
                    cursor.execute("UPDATE reminders SET notified_count=1 WHERE id=?", (rid,))

                elif count > 0 and count < 4:
                    if rt + timedelta(minutes=5 * count) <= now:
                        send_reminder(uid, rid, text, media, repeat=True)
                        cursor.execute("UPDATE reminders SET notified_count=? WHERE id=?", (count + 1, rid))

                db.commit()
            except:
                continue

        time.sleep(10)

# ================= SNOOZE =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("snooze_"))
def snooze(call):
    rid = int(call.data.split("_")[1])

    cursor.execute("SELECT time FROM reminders WHERE id=?", (rid,))
    t = datetime.fromisoformat(cursor.fetchone()[0])
    new = t + timedelta(minutes=10)

    cursor.execute("UPDATE reminders SET time=?, notified_count=0 WHERE id=?", (new.isoformat(), rid))
    db.commit()

    bot.answer_callback_query(call.id, "⏳ Отложено")

# ================= FALLBACK =================
@bot.message_handler(func=lambda m: True)
def fallback(msg):
    bot.send_message(msg.chat.id, "🤔 Используй кнопки меню")

# ================= RUN =================
threading.Thread(target=checker, daemon=True).start()
bot.infinity_polling()
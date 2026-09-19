# BlockDrop — Telegram case simulator
# Part 1 of 3

import asyncio
import os
import random
import re
import sqlite3
from datetime import datetime, timezone
from html import escape

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_PATH = "/telegram-webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "blockdrop-secret").strip()

# Вкажи свій Telegram ID
ADMIN_IDS = {
    # Наприклад: 123456789
}

# Збереження бази на Persistent Disk у Render, щоб прогрес не зникав
DATA_DIR = "/data" if os.path.exists("/data") else "."
DB_FILE = os.path.join(DATA_DIR, "blockdrop.db")

START_COINS = 1000
START_GOLD = 0
PROMO_CREATE_FEE = 50
DAILY_COOLDOWN = 24 * 60 * 60
COINS_PER_GOLD = 100

# ============================================================
# GAME CONTENT
# ============================================================
RARITY_ORDER = {
    "Ззвичайний": 1,
    "Незвичайний": 2,
    "Рідкісний": 3,
    "Епічний": 4,
    "Легендарний": 5,
    "Міфічний": 6,
    "Ексклюзивний": 7,
    "Хелловін": 8,
}

ITEMS = {
    "neon_knife": {"name": "🔪 Neon Fang", "rarity": "Ззвичайний", "price": 35},
    "pixel_glock": {"name": "🔫 Pixel Glock", "rarity": "Ззвичайний", "price": 50},
    "blue_m4": {"name": "🔫 Blue M4", "rarity": "Незвичайний", "price": 90},
    "toxic_deagle": {"name": "☣️ Toxic Deagle", "rarity": "Незвичайний", "price": 140},
    "crimson_ak": {"name": "🩸 Crimson AK", "rarity": "Рідкісний", "price": 260},
    "cyber_awp": {"name": "⚡ Cyber AWP", "rarity": "Рідкісний", "price": 420},
    "lava_usp": {"name": "🌋 Lava USP", "rarity": "Епічний", "price": 750},
    "shadow_ak": {"name": "🌑 Shadow AK", "rarity": "Епічний", "price": 1100},
    "dragon_awp": {"name": "🐉 Dragon AWP", "rarity": "Легендарний", "price": 2400},
    "void_m4": {"name": "🌀 Void M4", "rarity": "Легендарний", "price": 4200},
    "golden_deagle": {"name": "👑 Golden Deagle", "rarity": "Міфічний", "price": 8000},
    "galaxy_awp": {"name": "🌌 Galaxy AWP", "rarity": "Міфічний", "price": 15000},
    "royal_knife": {"name": "💎 Royal Knife", "rarity": "Ексклюзивний", "price": 30000},
    "phantom_ak": {"name": "👾 Phantom AK", "rarity": "Ексклюзивний", "price": 60000},

    # Halloween collection
    "pumpkin_pistol": {"name": "🎃 Pumpkin Blaster", "rarity": "Хелловін", "price": 900},
    "ghost_knife": {"name": "👻 Ghost Fang", "rarity": "Хелловін", "price": 1800},
    "bat_ak": {"name": "🦇 Bat AK", "rarity": "Хелловін", "price": 4000},
    "witch_awp": {"name": "🧙 Witch AWP", "rarity": "Хелловін", "price": 8500},
    "reaper_knife": {"name": "💀 Reaper Knife", "rarity": "Хелловін", "price": 20000},
}

CASES = {
    "starter": {
        "name": "📦 Starter Case",
        "price": 250,
        "drops": [
            ("neon_knife", 35.0),
            ("pixel_glock", 28.0),
            ("blue_m4", 20.0),
            ("toxic_deagle", 10.0),
            ("crimson_ak", 5.0),
            ("cyber_awp", 1.8),
            ("lava_usp", 0.2),
        ],
    },
    "weapon": {
        "name": "🔫 Weapon Case",
        "price": 900,
        "drops": [
            ("blue_m4", 24.0),
            ("toxic_deagle", 22.0),
            ("crimson_ak", 24.0),
            ("cyber_awp", 16.0),
            ("lava_usp", 9.0),
            ("shadow_ak", 4.0),
            ("dragon_awp", 1.0),
        ],
    },
    "legendary": {
        "name": "💎 Legendary Case",
        "price": 3500,
        "drops": [
            ("cyber_awp", 20.0),
            ("lava_usp", 24.0),
            ("shadow_ak", 22.0),
            ("dragon_awp", 18.0),
            ("void_m4", 10.0),
            ("golden_deagle", 5.0),
            ("galaxy_awp", 0.9),
            ("royal_knife", 0.1),
        ],
    },
    "elite": {
        "name": "🔥 Elite Case",
        "price": 12000,
        "drops": [
            ("lava_usp", 15.0),
            ("shadow_ak", 24.0),
            ("dragon_awp", 25.0),
            ("void_m4", 18.0),
            ("golden_deagle", 10.0),
            ("galaxy_awp", 7.0),
            ("royal_knife", 0.8),
            ("phantom_ak", 0.2),
        ],
    },
    "gold": {
        "name": "🟡 Gold Case",
        "price_gold": 25,
        "drops": [
            ("blue_m4", 35.0),
            ("toxic_deagle", 25.0),
            ("crimson_ak", 18.0),
            ("cyber_awp", 12.0),
            ("lava_usp", 6.0),
            ("shadow_ak", 3.0),
            ("dragon_awp", 1.0),
        ],
    },
    "halloween": {
        "name": "🎃 Halloween Case",
        "price": 500,
        "event_only": True,
        "drops": [
            ("pumpkin_pistol", 48.0),
            ("ghost_knife", 28.0),
            ("bat_ak", 15.0),
            ("witch_awp", 7.0),
            ("reaper_knife", 2.0),
        ],
    },
}

# ============================================================
# DATABASE SETUP
# ============================================================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=ON")


def db(sql, params=(), fetch=False, many=False):
    cur = conn.cursor()
    if many:
        cur.executemany(sql, params)
    else:
        cur.execute(sql, params)
    if fetch:
        return cur.fetchall()
    conn.commit()
    return cur


def init_db():
    db("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            block_id TEXT UNIQUE NOT NULL,
            coins INTEGER NOT NULL DEFAULT 1000,
            gold INTEGER NOT NULL DEFAULT 0,
            halloween_coins INTEGER NOT NULL DEFAULT 0,
            cases_opened INTEGER NOT NULL DEFAULT 0,
            total_earned INTEGER NOT NULL DEFAULT 0,
            total_sold INTEGER NOT NULL DEFAULT 0,
            daily_at INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        )
    """)
    db("""
        CREATE TABLE IF NOT EXISTS inventory (
            tg_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (tg_id, item_id),
            FOREIGN KEY (tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
        )
    """)
    db("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            coins INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,
            max_uses INTEGER NOT NULL DEFAULT 1,
            uses INTEGER NOT NULL DEFAULT 0,
            creator_tg_id INTEGER
        )
    """)
    db("""
        CREATE TABLE IF NOT EXISTS promo_used (
            tg_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            PRIMARY KEY (tg_id, code),
            FOREIGN KEY (tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
        )
    """)
# BlockDrop — Telegram case simulator
# Part 2 of 3

def new_block_id():
    while True:
        block_id = "BD-" + "".join(random.choices("0123456789", k=7))
        if not db("SELECT 1 FROM users WHERE block_id=?", (block_id,), True):
            return block_id


def ensure_user(tg_user):
    row = db("SELECT * FROM users WHERE tg_id=?", (tg_user.id,), True)
    if row:
        db("UPDATE users SET username=?, first_name=? WHERE tg_id=?",
           (tg_user.username or "", tg_user.first_name or "", tg_user.id))
        return db("SELECT * FROM users WHERE tg_id=?", (tg_user.id,), True)[0]

    block_id = new_block_id()
    now = int(datetime.now(timezone.utc).timestamp())
    db("""
        INSERT INTO users(tg_id, username, first_name, block_id, coins, gold, created_at)
        VALUES(?,?,?,?,?,?,?)
    """, (tg_user.id, tg_user.username or "", tg_user.first_name or "", block_id, START_COINS, START_GOLD, now))
    return db("SELECT * FROM users WHERE tg_id=?", (tg_user.id,), True)[0]


def is_halloween():
    return datetime.now().month == 10


def rarity_emoji(rarity):
    return {
        "Ззвичайний": "⚪",
        "Незвичайний": "🟢",
        "Рідкісний": "🔵",
        "Епічний": "🟣",
        "Легендарний": "🟠",
        "Міфічний": "🔴",
        "Ексклюзивний": "💎",
        "Хелловін": "🎃",
    }.get(rarity, "▫️")


def add_item(tg_id, item_id, amount=1):
    db("""
        INSERT INTO inventory(tg_id,item_id,amount) VALUES(?,?,?)
        ON CONFLICT(tg_id,item_id) DO UPDATE SET amount=amount+excluded.amount
    """, (tg_id, item_id, amount))


def weighted_drop(drop_list):
    r = random.uniform(0, sum(weight for _, weight in drop_list))
    cur = 0
    for item_id, weight in drop_list:
        cur += weight
        if r <= cur:
            return item_id
    return drop_list[-1][0]


def get_inventory(tg_id):
    return db("SELECT item_id, amount FROM inventory WHERE tg_id=? AND amount>0 ORDER BY amount DESC", (tg_id,), True)


def inventory_value(tg_id):
    rows = get_inventory(tg_id)
    return sum(ITEMS[r["item_id"]]["price"] * r["amount"] for r in rows if r["item_id"] in ITEMS)


# ============================================================
# KEYBOARDS & TEXT BUILDERS
# ============================================================
def menu_kb():
    b = InlineKeyboardBuilder()
    buttons = [
        ("🎁 Кейси", "cases"), ("🎒 Інвентар", "inventory"),
        ("👤 Профіль", "profile"), ("🎁 Бонус", "daily"),
        ("🎟️ Промокод", "promo_help")
    ]
    for text, data in buttons:
        b.button(text=text, callback_data=data)
    b.adjust(2, 2, 1)
    return b.as_markup()


def back_kb(target="menu"):
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data=target)
    return b.as_markup()


def cases_kb():
    b = InlineKeyboardBuilder()
    for cid, case in CASES.items():
        if case.get("event_only") and not is_halloween():
            continue
        if cid == "gold":
            b.button(text=f"{case['name']} • {case['price_gold']} 🟡", callback_data=f"case:{cid}")
        else:
            b.button(text=f"{case['name']} • {case['price']} 🪙", callback_data=f"case:{cid}")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def case_buttons(case_id):
    b = InlineKeyboardBuilder()
    b.button(text="🔓 Відкрити", callback_data=f"open:{case_id}")
    b.button(text="⬅️ Кейси", callback_data="cases")
    b.adjust(1, 1)
    return b.as_markup()


def inventory_kb():
    b = InlineKeyboardBuilder()
    b.button(text="💰 Продати все NPC", callback_data="sell_all")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def main_text(user):
    event = "\n🎃 Halloween: АКТИВНИЙ" if is_halloween() else ""
    return (
        f"<b>🟩 BLOCKDROP</b>\n\n"
        f"Привіт, <b>{escape(user['first_name'] or 'гравець')}</b>!\n"
        f"Твій ID: <code>{user['block_id']}</code>\n\n"
        f"💰 BlockCoins: <b>{user['coins']:,}</b>\n"
        f"🟡 Gold: <b>{user['gold']:,}</b>"
        + event
        + "\n\nОбирай розділ нижче 👇"
    ).replace(",", " ")


def inventory_text(tg_id):
    rows = get_inventory(tg_id)
    if not rows:
        return "<b>🎒 Інвентар</b>\n\nПоки що тут порожньо. Відкрий перший кейс! 🎁"
    lines = ["<b>🎒 Інвентар</b>", ""]
    for r in rows:
        item = ITEMS.get(r["item_id"])
        if not item:
            continue
        lines.append(
            f"{rarity_emoji(item['rarity'])} {item['name']} × <b>{r['amount']}</b>\n"
            f"   {item['rarity']} • продаж: {item['price']} 🪙"
        )
    lines.append(f"\n💎 Загальна вартість: <b>{inventory_value(tg_id):,}</b> 🪙".replace(",", " "))
    return "\n".join(lines)


# ============================================================
# BOT INITIALIZATION & PROMO COMMANDS
# ============================================================
init_db()

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())


# КОМАНДА ДЛЯ АДМІНІВ: Створення промокоду
@dp.message(Command("addpromo"))
async def cmd_add_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS and len(ADMIN_IDS) > 0:
        await message.answer("❌ У вас немає прав для використання цієї команди.")
        return

    args = message.text.split()[1:]
    if len(args) < 4:
        await message.answer("ℹ️ Використання: <code>/addpromo КОД МОНЕТИ ГОЛДА КІЛЬКІСТЬ</code>\n\nПриклад: <code>/addpromo START100 1000 10 50</code>")
        return

    code = args[0].upper()
    try:
        coins = int(args[1])
        gold = int(args[2])
        max_uses = int(args[3])
    except ValueError:
        await message.answer("❌ Числа вказані некоректно.")
        return

    try:
        db("INSERT INTO promo_codes(code, coins, gold, max_uses, creator_tg_id) VALUES(?,?,?,?,?)",
           (code, coins, gold, max_uses, message.from_user.id))
        await message.answer(
            f"✅ <b>Промокод створено!</b>\n\n"
            f"🎟️ Код: <code>{code}</code>\n"
            f"💰 Монети: <b>{coins}</b>\n"
            f"🟡 Голда: <b>{gold}</b>\n"
            f"👥 Використань: <b>{max_uses}</b>"
        )
    except sqlite3.IntegrityError:
        await message.answer("❌ Такий промокод вже існує.")


# АКТИВАЦІЯ ПРОМОКОДУ
@dp.message(Command("promo"))
async def cmd_use_promo(message: Message):
    user = ensure_user(message.from_user)
    args = message.text.split()[1:]

    if not args:
        await message.answer("ℹ️ Введіть промокод після команди:\n<code>/promo ВАШ_КОД</code>")
        return

    code = args[0].upper()

    if db("SELECT 1 FROM promo_used WHERE tg_id=? AND code=?", (user['tg_id'], code), True):
        await message.answer("❌ Ви вже активували цей промокод.")
        return

    promo = db("SELECT * FROM promo_codes WHERE code=?", (code,), True)
    if not promo:
        await message.answer("❌ Промокод не знайдено.")
        return

    promo = promo[0]
    if promo["uses"] >= promo["max_uses"]:
        await message.answer("❌ Ліміт активацій цього промокоду вичерпано.")
        return

    db("UPDATE users SET coins=coins+?, gold=gold+? WHERE tg_id=?", (promo["coins"], promo["gold"], user["tg_id"]))
    db("UPDATE promo_codes SET uses=uses+1 WHERE code=?", (code,))
    db("INSERT INTO promo_used(tg_id, code) VALUES(?,?)", (user["tg_id"], code))

    await message.answer(
        f"🎉 <b>Промокод успішно активовано!</b>\n\n"
        f"Ви отримали:\n"
        f"💰 +<b>{promo['coins']}</b> BlockCoins\n"
        f"🟡 +<b>{promo['gold']}</b> Gold"
    )
# BlockDrop — Telegram case simulator
# Part 3 of 3

# ============================================================
# HANDLERS (CALLBACKS & COMMANDS)
# ============================================================
@dp.message(CommandStart())
async def start(message: Message):
    user = ensure_user(message.from_user)
    await message.answer(main_text(user), reply_markup=menu_kb())


@dp.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    user = ensure_user(call.from_user)
    await call.message.edit_text(main_text(user), reply_markup=menu_kb())
    await call.answer()


@dp.callback_query(F.data == "cases")
async def cb_cases(call: CallbackQuery):
    ensure_user(call.from_user)
    await call.message.edit_text("<b>🎁 Кейси BlockDrop</b>\n\nОбирай кейс:", reply_markup=cases_kb())
    await call.answer()


@dp.callback_query(F.data.startswith("case:"))
async def cb_case(call: CallbackQuery):
    ensure_user(call.from_user)
    cid = call.data.split(":", 1)[1]
    if cid not in CASES:
        await call.answer("Кейс не знайдено", show_alert=True)
        return
    case = CASES[cid]
    price_text = f"{case['price_gold']} 🟡" if "price_gold" in case else f"{case['price']} 🪙"
    await call.message.edit_text(f"<b>{case['name']}</b>\n\n💰 Ціна: <b>{price_text}</b>", reply_markup=case_buttons(cid))
    await call.answer()


@dp.callback_query(F.data.startswith("open:"))
async def cb_open(call: CallbackQuery):
    user = ensure_user(call.from_user)
    cid = call.data.split(":", 1)[1]
    if cid not in CASES:
        await call.answer("Кейс не знайдено", show_alert=True)
        return
    case = CASES[cid]

    cur = conn.cursor()
    if "price_gold" in case:
        cost = case["price_gold"]
        cur.execute("UPDATE users SET gold=gold-?, cases_opened=cases_opened+1 WHERE tg_id=? AND gold>=?", (cost, user["tg_id"], cost))
    else:
        cost = case["price"]
        cur.execute("UPDATE users SET coins=coins-?, cases_opened=cases_opened+1 WHERE tg_id=? AND coins>=?", (cost, user["tg_id"], cost))

    if cur.rowcount == 0:
        await call.answer("❌ Не вистачає коштів!", show_alert=True)
        return
    conn.commit()

    item_id = weighted_drop(case["drops"])
    item = ITEMS[item_id]
    add_item(user["tg_id"], item_id, 1)

    for i in range(3):
        fake = random.choice(list(ITEMS.values()))
        await call.message.edit_text(f"<b>🎁 Відкриття...</b>\n\n🔄 {fake['name']}")
        await asyncio.sleep(0.3)

    text = f"<b>🎉 Отримано: {item['name']}!</b>\n\n{rarity_emoji(item['rarity'])} {item['rarity']} • ціна: {item['price']} 🪙"
    await call.message.edit_text(text, reply_markup=back_kb("cases"))
    await call.answer()


@dp.callback_query(F.data == "inventory")
async def cb_inventory(call: CallbackQuery):
    ensure_user(call.from_user)
    await call.message.edit_text(inventory_text(call.from_user.id), reply_markup=inventory_kb())
    await call.answer()


@dp.callback_query(F.data == "sell_all")
async def cb_sell_all(call: CallbackQuery):
    user = ensure_user(call.from_user)
    val = inventory_value(user["tg_id"])
    if val == 0:
        await call.answer("У тебе немає предметів для продажу!", show_alert=True)
        return

    db("DELETE FROM inventory WHERE tg_id=?", (user["tg_id"],))
    db("UPDATE users SET coins=coins+? WHERE tg_id=?", (val, user["tg_id"]))

    await call.message.edit_text(f"✅ Усі предмети успішно продано за <b>{val:,}</b> 🪙".replace(",", " "), reply_markup=back_kb("inventory"))
    await call.answer()


@dp.callback_query(F.data == "promo_help")
async def cb_promo_help(call: CallbackQuery):
    await call.message.edit_text(
        "<b>🎟️ Активація промокоду</b>\n\n"
        "Напиши в чат команду:\n"
        "<code>/promo ВАШ_КОД</code>\n\n"
        "<i>Промокоди роздаються в офіційному каналі та під час івентів!</i>",
        reply_markup=back_kb()
    )
    await call.answer()


# ============================================================
# WEB SERVER & MAIN
# ============================================================
async def webhook_handler(request: web.Request):
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return web.Response(status=403, text="Forbidden")
    try:
        data = await request.json()
        from aiogram.types import Update
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return web.Response(text="OK")
    except Exception as exc:
        print(f"[BlockDrop] Webhook error: {exc}")
        return web.Response(status=500, text="Webhook error")


async def health_handler(request: web.Request):
    return web.Response(text="BlockDrop is online")


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не заданий.")

    port = int(os.getenv("PORT", "10000"))
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not render_url:
        raise RuntimeError("RENDER_EXTERNAL_URL не знайдено.")

    webhook_url = render_url + WEBHOOK_PATH
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_post(WEBHOOK_PATH, webhook_handler)

    await bot.set_webhook(
        webhook_url,
        secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
        drop_pending_updates=True,
    )
    print(f"[BlockDrop] Webhook set to: {webhook_url}")
    print(f"[BlockDrop] Server listening on port {port}")
    try:
        await web._run_app(app, host="0.0.0.0", port=port)
    finally:
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

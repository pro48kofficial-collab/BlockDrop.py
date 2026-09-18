# BlockDrop — Telegram case simulator
# One-file version for Pydroid 3 + aiogram 3
# Virtual economy only. No real-money betting/cash-out.

import asyncio
import random
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = "8939970989:AAH9RBhxduGPhbLZ3HxpaO_YT1jDgZ7G5Fc"

# Put your Telegram numeric ID here after using /tgid.
ADMIN_IDS = {
    # 123456789,
}

DB_FILE = "blockdrop.db"
START_COINS = 1000
START_GOLD = 0
PROMO_CREATE_FEE = 50
DAILY_COOLDOWN = 24 * 60 * 60
PROMO_CREATE_FEE = 50
COINS_PER_GOLD = 100
VIP_CASE_STARS = 15
VIP_REWARD_ITEM = "royal_knife"

# ============================================================
# GAME CONTENT
# ============================================================
RARITY_ORDER = {
    "Звичайний": 1,
    "Незвичайний": 2,
    "Рідкісний": 3,
    "Епічний": 4,
    "Легендарний": 5,
    "Міфічний": 6,
    "Ексклюзивний": 7,
    "Хелловін": 8,
}

ITEMS = {
    "neon_knife": {"name": "🔪 Neon Fang", "rarity": "Звичайний", "price": 35},
    "pixel_glock": {"name": "🔫 Pixel Glock", "rarity": "Звичайний", "price": 50},
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

    # Halloween collection — unique BlockDrop skins, not Block Strike assets.
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
# DATABASE
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
            event_daily_at INTEGER NOT NULL DEFAULT 0,
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
            halloween_coins INTEGER NOT NULL DEFAULT 0,
            max_uses INTEGER NOT NULL DEFAULT 1,
            uses INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,
            item_id TEXT,
            case_id TEXT,
            creator_tg_id INTEGER
        )
    """)
    # Migrations for Gold and player-created promos.
    for sql in (
        "ALTER TABLE users ADD COLUMN gold INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE promo_codes ADD COLUMN gold INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE promo_codes ADD COLUMN creator_tg_id INTEGER",
    ):
        try:
            db(sql)
        except sqlite3.OperationalError:
            pass

    db("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL,
            task_key TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            target INTEGER NOT NULL,
            reward_gold INTEGER NOT NULL DEFAULT 0,
            claimed INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            UNIQUE(tg_id, task_key),
            FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
        )
    """)
    db("""
        CREATE TABLE IF NOT EXISTS market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_tg_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            price_gold INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(seller_tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
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
    db("""
        CREATE TABLE IF NOT EXISTS market_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_tg_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (seller_tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
        )
    """)
    db("""
        CREATE TABLE IF NOT EXISTS achievements (
            tg_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            PRIMARY KEY (tg_id, key),
            FOREIGN KEY (tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
        )
    """)


# Migrate databases created by older BlockDrop versions.
for table, columns in {
    "users": [("gold", "INTEGER NOT NULL DEFAULT 0")],
    "promo_codes": [("gold", "INTEGER NOT NULL DEFAULT 0"), ("item_id", "TEXT"), ("case_id", "TEXT"), ("creator_tg_id", "INTEGER")],
}.items():
    for col, definition in columns:
        try:
            existing = {r["name"] for r in db(f"PRAGMA table_info({table})", fetch=True)}
            if col not in existing:
                db(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        except Exception:
            pass


def new_block_id():
    while True:
        block_id = "BD-" + "".join(random.choices("0123456789", k=7))
        if not db("SELECT 1 FROM users WHERE block_id=?", (block_id,), True):
            return block_id


def ensure_user(tg_user):
    row = db("SELECT * FROM users WHERE tg_id=?", (tg_user.id,), True)
    if row:
        # Keep profile data fresh.
        db("UPDATE users SET username=?, first_name=? WHERE tg_id=?",
           (tg_user.username or "", tg_user.first_name or "", tg_user.id))
        return db("SELECT * FROM users WHERE tg_id=?", (tg_user.id,), True)[0]

    block_id = new_block_id()
    now = int(datetime.now(timezone.utc).timestamp())
    db("""
        INSERT INTO users(tg_id, username, first_name, block_id, coins, created_at)
        VALUES(?,?,?,?,?,?)
    """, (tg_user.id, tg_user.username or "", tg_user.first_name or "", block_id, START_COINS, now))
    return db("SELECT * FROM users WHERE tg_id=?", (tg_user.id,), True)[0]


def get_user(tg_id):
    rows = db("SELECT * FROM users WHERE tg_id=?", (tg_id,), True)
    return rows[0] if rows else None


def is_halloween():
    return datetime.now().month == 10


def format_time_left(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}г {m}хв" if h else f"{m}хв {s}с"


def rarity_emoji(rarity):
    return {
        "Звичайний": "⚪",
        "Незвичайний": "🟢",
        "Рідкісний": "🔵",
        "Епічний": "🟣",
        "Легендарний": "🟠",
        "Міфічний": "🔴",
        "Ексклюзивний": "💎",
        "Хелловін": "🎃",
    }.get(rarity, "▫️")


def add_coins(tg_id, amount):
    db("UPDATE users SET coins=coins+?, total_earned=total_earned+? WHERE tg_id=?",
       (amount, max(0, amount), tg_id))
    if amount > 0:
        update_task(tg_id, "earn_1000", amount)


def add_gold(tg_id, amount):
    db("UPDATE users SET gold=gold+? WHERE tg_id=?", (amount, tg_id))


def add_event_coins(tg_id, amount):
    db("UPDATE users SET halloween_coins=halloween_coins+? WHERE tg_id=?", (amount, tg_id))


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


def inventory_value(tg_id):
    rows = db("SELECT item_id, amount FROM inventory WHERE tg_id=? AND amount>0", (tg_id,), True)
    return sum(ITEMS[r["item_id"]]["price"] * r["amount"] for r in rows if r["item_id"] in ITEMS)


def get_inventory(tg_id):
    return db("SELECT item_id, amount FROM inventory WHERE tg_id=? AND amount>0 ORDER BY amount DESC", (tg_id,), True)


def menu_kb():
    b = InlineKeyboardBuilder()
    buttons = [
        ("🎁 Кейси", "cases"), ("🎒 Інвентар", "inventory"),
        ("🏪 Ринок", "market"),
        ("👤 Профіль", "profile"), ("🏪 Магазин", "shop"),
        ("🎁 Бонус", "daily"), ("🏆 Топ", "top"),
        ("🎟️ Промокод", "promo_help"), ("🟡 Gold", "gold"),
        ("📋 Завдання", "tasks"), ("🏪 Gold Market", "market"),
        ("📊 Статистика", "stats"),
        ("🎃 Halloween", "halloween"),
    ]
    for text, data in buttons:
        b.button(text=text, callback_data=data)
    b.adjust(2, 2, 2, 2, 1)
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
    b.button(text="📊 Шанси", callback_data=f"odds:{case_id}")
    b.button(text="⬅️ Кейси", callback_data="cases")
    b.adjust(2, 1)
    return b.as_markup()


def inventory_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🏷️ Продати скін на ринку", callback_data="market_sell_choose")
    b.button(text="💸 Продати найдешевший NPC", callback_data="sell_one")
    b.button(text="💰 Продати все NPC", callback_data="sell_all")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def market_kb():
    b = InlineKeyboardBuilder()
    rows = db("""SELECT m.id,m.item_id,m.price,u.first_name,u.block_id
                 FROM market_listings m JOIN users u ON u.tg_id=m.seller_tg_id
                 ORDER BY m.id DESC LIMIT 15""", fetch=True)
    for r in rows:
        item = ITEMS.get(r["item_id"])
        if item:
            b.button(text=f"{item['name']} • {r['price']} 🪙", callback_data=f"market_buy:{r['id']}")
    b.button(text="🔄 Оновити", callback_data="market")
    b.button(text="🏷️ Мої продажі", callback_data="market_mine")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def admin_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика бота", callback_data="admin_stats")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def admin_only(tg_id):
    return tg_id in ADMIN_IDS


# ============================================================
# TEXT BUILDERS
# ============================================================
def main_text(user):
    event = "\n🎃 Halloween: АКТИВНИЙ" if is_halloween() else ""
    return (
        f"<b>🟩 BLOCKDROP</b>\n\n"
        f"Привіт, <b>{escape(user['first_name'] or 'гравець')}</b>!\n"
        f"Твій ID: <code>{user['block_id']}</code>\n\n"
        f"💰 BlockCoins: <b>{user['coins']:,}</b>".replace(",", " ")
        + f"\n🟡 Gold: <b>{user['gold']:,}</b>".replace(",", " ")
        + f"\n🟡 Gold: <b>{user['gold']:,}</b>".replace(",", " ")
        + f"\n🎃 Halloween Coins: <b>{user['halloween_coins']:,}</b>".replace(",", " ")
        + event
        + "\n\nОбирай розділ нижче 👇"
    )


def profile_text(user):
    inv = get_inventory(user["tg_id"])
    unique = len(inv)
    total_items = sum(r["amount"] for r in inv)
    return (
        f"<b>👤 Твій профіль</b>\n\n"
        f"🆔 BlockDrop ID: <code>{user['block_id']}</code>\n"
        f"👤 Ім'я: <b>{escape(user['first_name'] or '—')}</b>\n"
        f"💰 BlockCoins: <b>{user['coins']:,}</b>\n"
        f"🟡 Gold: <b>{user['gold']:,}</b>\n"
        f"🎃 Halloween Coins: <b>{user['halloween_coins']:,}</b>\n\n"
        f"🎁 Відкрито кейсів: <b>{user['cases_opened']}</b>\n"
        f"💵 Зароблено: <b>{user['total_earned']:,}</b> 🪙\n"
        f"💸 Продано предметів: <b>{user['total_sold']}</b>\n"
        f"🎒 Предметів: <b>{total_items}</b> ({unique} видів)\n"
        f"💎 Вартість інвентарю: <b>{inventory_value(user['tg_id']):,}</b> 🪙"
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


def case_text(cid):
    case = CASES[cid]
    return (
        f"<b>{case['name']}</b>\n\n"
        f"💰 Ціна: <b>{case['price']:,}</b> 🪙\n\n"
        f"Це унікальний кейс BlockDrop зі скінами власної колекції.\n\n"
        f"Натисни <b>Відкрити</b>, щоб отримати випадковий предмет."
    ).replace(",", " ")


def odds_text(cid):
    case = CASES[cid]
    lines = [f"<b>📊 Шанси — {case['name']}</b>", ""]
    for item_id, chance in case["drops"]:
        item = ITEMS[item_id]
        lines.append(f"{rarity_emoji(item['rarity'])} {item['name']} — <b>{chance:g}%</b>")
    return "\n".join(lines)


# ============================================================
# ACHIEVEMENTS
# ============================================================
def check_achievements(tg_id):
    user = get_user(tg_id)
    if not user:
        return []
    unlocked = []
    checks = [
        ("first_case", user["cases_opened"] >= 1, "🎁 Перший кейс"),
        ("cases_10", user["cases_opened"] >= 10, "🔟 10 кейсів"),
        ("cases_100", user["cases_opened"] >= 100, "💯 100 кейсів"),
        ("rich", user["coins"] >= 100000, "💰 100 000 BlockCoins"),
    ]
    for key, condition, label in checks:
        if condition and not db("SELECT 1 FROM achievements WHERE tg_id=? AND key=?", (tg_id, key), True):
            db("INSERT INTO achievements(tg_id,key) VALUES(?,?)", (tg_id, key))
            unlocked.append(label)
    return unlocked


class MarketSellState(StatesGroup):
    price = State()


# ============================================================
# GOLD / TASKS / MARKET HELPERS
# ============================================================
def add_gold(tg_id, amount):
    db("UPDATE users SET gold=gold+? WHERE tg_id=?", (amount, tg_id))


def task_seed(tg_id):
    now = int(datetime.now(timezone.utc).timestamp())
    tasks = [
        ("open_3", "🎁 Відкрити 3 кейси", 3, 3),
        ("sell_5", "💸 Продати 5 скінів", 5, 5),
        ("earn_1000", "💰 Заробити 1000 🪙", 1000, 10),
    ]
    for key, _, target, reward in tasks:
        db("""INSERT OR IGNORE INTO tasks(tg_id,task_key,target,reward_gold,created_at)
               VALUES(?,?,?,?,?)""", (tg_id, key, target, reward, now))


def tasks_text(tg_id):
    task_seed(tg_id)
    rows = db("SELECT * FROM tasks WHERE tg_id=? ORDER BY id", (tg_id,), True)
    lines = ["<b>📋 Завдання</b>", "", "Виконуй завдання та отримуй 🟡 Gold:\n"]
    labels = {
        "open_3": "🎁 Відкрити 3 кейси",
        "sell_5": "💸 Продати 5 скінів",
        "earn_1000": "💰 Заробити 1000 🪙",
    }
    for r in rows:
        status = "✅ Забрано" if r["claimed"] else ("🎁 Забрати" if r["progress"] >= r["target"] else "⏳")
        lines.append(f"{labels.get(r['task_key'], r['task_key'])}\nПрогрес: <b>{min(r['progress'],r['target'])}/{r['target']}</b> • +{r['reward_gold']} 🟡 • {status}")
    return "\n\n".join(lines)


def update_task(tg_id, task_key, amount=1):
    task_seed(tg_id)
    db("UPDATE tasks SET progress=MIN(target, progress+?) WHERE tg_id=? AND task_key=? AND claimed=0", (amount, tg_id, task_key))


def market_text(tg_id):
    rows = db("SELECT * FROM market ORDER BY id DESC LIMIT 20", fetch=True)
    if not rows:
        return "<b>🏪 Gold Market</b>\n\nПоки що ніхто не виставив скіни."
    lines=["<b>🏪 Gold Market</b>", "", "Обери лот:"]
    for r in rows:
        item=ITEMS.get(r["item_id"])
        if item:
            lines.append(f"#{r['id']} {item['name']} — <b>{r['price_gold']} 🟡</b>")
    return "\n".join(lines)


def market_kb(tg_id):
    b=InlineKeyboardBuilder()
    rows=db("SELECT * FROM market ORDER BY id DESC LIMIT 20", fetch=True)
    for r in rows:
        item=ITEMS.get(r["item_id"])
        if item:
            b.button(text=f"#{r['id']} {item['name']} • {r['price_gold']} 🟡", callback_data=f"buygold:{r['id']}")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def gold_cases_kb():
    b=InlineKeyboardBuilder()
    b.button(text="🟡 Gold Case • 25 Gold", callback_data="case:gold")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


# ============================================================
# BOT
# ============================================================
init_db()

if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
    print("[BlockDrop] Увага: встав свій BOT_TOKEN у код перед запуском.")

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def start(message: Message):
    user = ensure_user(message.from_user)
    await message.answer(main_text(user), reply_markup=menu_kb())


@dp.message(Command("menu"))
async def menu(message: Message):
    user = ensure_user(message.from_user)
    await message.answer(main_text(user), reply_markup=menu_kb())


@dp.message(Command("tgid"))
async def tgid(message: Message):
    ensure_user(message.from_user)
    await message.answer(f"🆔 Твій Telegram ID: <code>{message.from_user.id}</code>")


@dp.message(Command("id"))
async def block_id(message: Message):
    user = ensure_user(message.from_user)
    await message.answer(f"🆔 Твій BlockDrop ID: <code>{user['block_id']}</code>")


@dp.message(Command("promo"))
async def promo(message: Message):
    user = ensure_user(message.from_user)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("🎟️ Використання: <code>/promo CODE</code>")
        return
    code = parts[1].strip().upper()
    try:
        conn.execute("BEGIN IMMEDIATE")
        p = conn.execute("SELECT * FROM promo_codes WHERE code=?", (code,)).fetchone()
        if not p:
            conn.rollback(); await message.answer("❌ Такого промокоду не існує."); return
        if p["uses"] >= p["max_uses"]:
            conn.rollback(); await message.answer("❌ Ліміт використань вичерпано."); return
        if conn.execute("SELECT 1 FROM promo_used WHERE tg_id=? AND code=?", (user["tg_id"], code)).fetchone():
            conn.rollback(); await message.answer("❌ Ти вже використовував цей промокод."); return
        conn.execute("INSERT INTO promo_used(tg_id,code) VALUES(?,?)", (user["tg_id"], code))
        conn.execute("UPDATE promo_codes SET uses=uses+1 WHERE code=?", (code,))
        conn.execute("UPDATE users SET coins=coins+?, gold=gold+?, halloween_coins=halloween_coins+? WHERE tg_id=?",
                     (p["coins"], p["gold"], p["halloween_coins"], user["tg_id"]))
        conn.commit()
    except Exception:
        conn.rollback(); await message.answer("❌ Не вдалося активувати промокод. Спробуй ще раз."); return
    rewards=[]
    if p["coins"]: rewards.append(f"+{p['coins']:,} 🪙".replace(","," "))
    if p["gold"]: rewards.append(f"+{p['gold']} 🟡 Gold")
    if p["halloween_coins"]: rewards.append(f"+{p['halloween_coins']} 🎃")
    await message.answer("🎟️ <b>Промокод активовано!</b>\n\n"+"\n".join(rewards))


@dp.message(Command("createpromo"))
async def createpromo(message: Message):
    user=ensure_user(message.from_user)
    p=message.text.split()
    if len(p)!=5:
        await message.answer("🎟️ <b>Створення промо</b>\n\n<code>/createpromo CODE USES COINS GOLD</code>\n\nПриклад: <code>/createpromo TEST 3 100 0</code>")
        return
    code=p[1].upper()
    try: uses, reward_coins, reward_gold = map(int,p[2:5])
    except ValueError:
        await message.answer("❌ USES, COINS та GOLD мають бути числами."); return
    if not re.fullmatch(r"[A-Z0-9_]{3,32}", code) or not (1<=uses<=1000) or reward_coins<0 or reward_gold<0 or (reward_coins==0 and reward_gold==0):
        await message.answer("❌ Невірні дані. Код: 3–32 символи A-Z/0-9/_."); return
    need_coins=PROMO_CREATE_FEE + reward_coins*uses
    need_gold=reward_gold*uses
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM promo_codes WHERE code=?",(code,)).fetchone():
            conn.rollback(); await message.answer("❌ Такий промокод вже існує."); return
        u=conn.execute("SELECT coins,gold FROM users WHERE tg_id=?",(user["tg_id"],)).fetchone()
        if u["coins"]<need_coins or u["gold"]<need_gold:
            conn.rollback(); await message.answer(f"❌ Недостатньо балансу.\n\nПотрібно: {need_coins} 🪙 + {need_gold} 🟡\nУ тебе: {u['coins']} 🪙 + {u['gold']} 🟡")
            return
        conn.execute("UPDATE users SET coins=coins-?, gold=gold-? WHERE tg_id=?",(need_coins,need_gold,user["tg_id"]))
        conn.execute("INSERT INTO promo_codes(code,coins,gold,halloween_coins,max_uses,uses,creator_tg_id) VALUES(?,?,0,0,?,0,?)" if False else
                     "INSERT INTO promo_codes(code,coins,gold,halloween_coins,max_uses,uses,creator_tg_id) VALUES(?,?,?,0,?,0,?)",
                     (code,reward_coins,reward_gold,uses,user["tg_id"]))
        conn.commit()
    except Exception:
        conn.rollback(); await message.answer("❌ Не вдалося створити промо."); return
    await message.answer(f"✅ Промокод <code>{code}</code> створено!\n\n🎟️ Активацій: {uses}\n🎁 За активацію: {reward_coins} 🪙 + {reward_gold} 🟡\n💸 Комісія: {PROMO_CREATE_FEE} 🪙\n🔒 Зарезервовано: {reward_coins*uses} 🪙 + {reward_gold*uses} 🟡")


@dp.message(Command("admin"))
async def admin(message: Message):
    ensure_user(message.from_user)
    if not admin_only(message.from_user.id):
        await message.answer("⛔ Доступ заборонено.")
        return
    await message.answer(
        "<b>🛠️ BlockDrop Admin</b>\n\n"
        "/give ID AMOUNT — видати BlockCoins\n"
        "/take ID AMOUNT — забрати BlockCoins\n"
        "/giveitem ID ITEM AMOUNT — видати скін\n"
        "/promoadd CODE COINS HCOINS USES [GOLD] [ITEM_ID] [CASE_ID] — адмін-промо\n"
        "/createpromo CODE USES COINS — промо гравця\n"
        "/user ID — інформація про гравця\n"
        "/botstats — статистика бота",
        reply_markup=admin_kb(),
    )


@dp.message(Command("give"))
async def admin_give(message: Message):
    if not admin_only(message.from_user.id):
        return
    p = message.text.split()
    if len(p) != 3:
        await message.answer("Використання: /give BLOCKDROP_ID AMOUNT")
        return
    target = db("SELECT * FROM users WHERE block_id=?", (p[1].upper(),), True)
    try:
        amount = int(p[2])
    except ValueError:
        amount = -1
    if not target or amount <= 0:
        await message.answer("❌ Невірні дані.")
        return
    add_coins(target[0]["tg_id"], amount)
    await message.answer(f"✅ Видано {amount:,} 🪙 гравцю <code>{p[1].upper()}</code>.".replace(",", " "))


@dp.message(Command("take"))
async def admin_take(message: Message):
    if not admin_only(message.from_user.id):
        return
    p = message.text.split()
    if len(p) != 3:
        await message.answer("Використання: /take BLOCKDROP_ID AMOUNT")
        return
    target = db("SELECT * FROM users WHERE block_id=?", (p[1].upper(),), True)
    try:
        amount = int(p[2])
    except ValueError:
        amount = -1
    if not target or amount <= 0:
        await message.answer("❌ Невірні дані.")
        return
    db("UPDATE users SET coins=MAX(0, coins-?) WHERE tg_id=?", (amount, target[0]["tg_id"]))
    await message.answer(f"✅ Забрано до {amount:,} 🪙 у <code>{p[1].upper()}</code>.".replace(",", " "))


@dp.message(Command("giveitem"))
async def admin_giveitem(message: Message):
    if not admin_only(message.from_user.id):
        return
    p = message.text.split()
    if len(p) != 4:
        await message.answer("Використання: /giveitem BLOCKDROP_ID ITEM_ID AMOUNT")
        return
    target = db("SELECT * FROM users WHERE block_id=?", (p[1].upper(),), True)
    try:
        amount = int(p[3])
    except ValueError:
        amount = -1
    if not target or p[2] not in ITEMS or amount <= 0:
        await message.answer("❌ Невірні дані. Використовуй ITEM_ID із коду ITEMS.")
        return
    add_item(target[0]["tg_id"], p[2], amount)
    await message.answer(f"✅ Видано {ITEMS[p[2]]['name']} × {amount}.")


@dp.message(Command("promoadd"))
async def admin_promoadd(message: Message):
    if not admin_only(message.from_user.id):
        return
    p = message.text.split()
    if len(p) < 5 or len(p) > 8:
        await message.answer("Використання:\n/promoadd CODE COINS HCOINS USES [GOLD] [ITEM_ID] [CASE_ID]\nПриклад:\n/promoadd HALLOWEEN 1000 100 50 5 ghost_knife")
        return
    code = p[1].upper()
    try:
        coins, hcoins, uses = map(int, p[2:5])
        gold = int(p[5]) if len(p) >= 6 else 0
    except ValueError:
        await message.answer("❌ Значення мають бути числами.")
        return
    item_id = p[6] if len(p) >= 7 else None
    case_id = p[7] if len(p) >= 8 else None
    if uses <= 0 or min(coins, hcoins, gold) < 0 or (item_id and item_id not in ITEMS) or (case_id and case_id not in CASES):
        await message.answer("❌ Невірні значення або ID предмета/кейса.")
        return
    try:
        db("INSERT INTO promo_codes(code,coins,halloween_coins,max_uses,gold,item_id,case_id,creator_tg_id) VALUES(?,?,?,?,?,?,?,?)",
           (code, coins, hcoins, uses, gold, item_id, case_id, message.from_user.id))
    except sqlite3.IntegrityError:
        await message.answer("❌ Такий промокод вже існує.")
        return
    await message.answer(f"✅ Промокод <code>{code}</code> створено.")


@dp.message(Command("createpromo"))
async def createpromo(message: Message):
    user = ensure_user(message.from_user)
    p = message.text.split()
    if len(p) != 4:
        await message.answer("🎟️ Створення промокоду\n\nКомісія: <b>50 🪙</b>\nФормат: <code>/createpromo CODE USES COINS</code>\n\nПриклад: <code>/createpromo MYCODE 10 100</code>")
        return
    code = p[1].upper()
    try:
        uses, reward = int(p[2]), int(p[3])
    except ValueError:
        await message.answer("❌ USES і COINS мають бути числами.")
        return
    if not re.fullmatch(r"[A-Z0-9_]{3,24}", code):
        await message.answer("❌ Код: 3–24 символи, тільки A-Z, 0-9 та _.")
        return
    if not (1 <= uses <= 10000 and 1 <= reward <= 1000000):
        await message.answer("❌ Ліміт: 1–10000 активацій і 1–1 000 000 🪙 за активацію.")
        return
    if user["coins"] < PROMO_CREATE_FEE:
        await message.answer(f"❌ Потрібно {PROMO_CREATE_FEE} 🪙 комісії.")
        return
    if db("SELECT 1 FROM promo_codes WHERE code=?", (code,), True):
        await message.answer("❌ Такий промокод вже існує.")
        return
    db("UPDATE users SET coins=coins-? WHERE tg_id=?", (PROMO_CREATE_FEE, user["tg_id"]))
    db("INSERT INTO promo_codes(code,coins,max_uses,uses,creator_tg_id) VALUES(?,?,?,?,?)", (code,reward,uses,0,user["tg_id"]))
    await message.answer(f"✅ <code>{code}</code> створено!\n\n💸 Комісія: {PROMO_CREATE_FEE} 🪙\n🎟️ Активацій: {uses}\n💰 Нагорода: {reward} 🪙")


@dp.message(Command("user"))
async def admin_user(message: Message):
    if not admin_only(message.from_user.id):
        return
    p = message.text.split(maxsplit=1)
    if len(p) != 2:
        await message.answer("Використання: /user BLOCKDROP_ID")
        return
    row = db("SELECT * FROM users WHERE block_id=?", (p[1].upper(),), True)
    if not row:
        await message.answer("❌ Гравця не знайдено.")
        return
    u = row[0]
    await message.answer(
        f"<b>👤 Гравець</b>\n\n"
        f"ID: <code>{u['block_id']}</code>\n"
        f"TG ID: <code>{u['tg_id']}</code>\n"
        f"💰 {u['coins']:,} 🪙\n"
        f"🎃 {u['halloween_coins']} HC\n"
        f"🎁 Кейсів: {u['cases_opened']}\n"
        f"🎒 Вартість інвентарю: {inventory_value(u['tg_id']):,} 🪙"
    )


@dp.message(Command("botstats"))
async def botstats(message: Message):
    if not admin_only(message.from_user.id):
        return
    users = db("SELECT COUNT(*) c FROM users", fetch=True)[0]["c"]
    cases = db("SELECT COALESCE(SUM(cases_opened),0) c FROM users", fetch=True)[0]["c"]
    coins = db("SELECT COALESCE(SUM(coins),0) c FROM users", fetch=True)[0]["c"]
    await message.answer(
        f"<b>📊 BlockDrop Stats</b>\n\n"
        f"👥 Гравців: <b>{users}</b>\n"
        f"🎁 Відкрито кейсів: <b>{cases}</b>\n"
        f"💰 BlockCoins у системі: <b>{coins:,}</b>"
    )


# ============================================================
# MARKET
# ============================================================
def market_text():
    rows = db("SELECT m.id,m.item_id,m.price,u.first_name,u.block_id FROM market_listings m JOIN users u ON u.tg_id=m.seller_tg_id ORDER BY m.id DESC LIMIT 15", fetch=True)
    lines=["<b>🏪 Ринок BlockDrop</b>","","Гравці продають тут свої скіни.",""]
    if not rows:
        lines.append("Ринок поки порожній.")
    for i,r in enumerate(rows,1):
        item=ITEMS.get(r["item_id"])
        if item:
            lines.append(f"<b>{i}.</b> {item['name']} • {item['rarity']}\n   💰 <b>{r['price']:,}</b> 🪙 • {escape(r['first_name'] or r['block_id'])}".replace(","," "))
    return "\n".join(lines)


@dp.callback_query(F.data == "market")
async def cb_market(call: CallbackQuery):
    ensure_user(call.from_user)
    await call.message.edit_text(market_text(), reply_markup=market_kb())
    await call.answer()


@dp.callback_query(F.data.startswith("market_buy:"))
async def cb_market_buy(call: CallbackQuery):
    user=ensure_user(call.from_user)
    try: lid=int(call.data.split(":",1)[1])
    except ValueError:
        await call.answer("❌ Помилка.",show_alert=True); return
    row=db("SELECT * FROM market_listings WHERE id=?",(lid,),True)
    if not row: await call.answer("❌ Оголошення вже недоступне.",show_alert=True); return
    listing=row[0]
    if listing["seller_tg_id"]==user["tg_id"]: await call.answer("❌ Не можна купити власний скін.",show_alert=True); return
    if user["coins"]<listing["price"]: await call.answer("❌ Не вистачає BlockCoins.",show_alert=True); return
    item=ITEMS.get(listing["item_id"])
    if not item: await call.answer("❌ Скін не знайдено.",show_alert=True); return
    try:
        conn.execute("BEGIN IMMEDIATE")
        x=conn.execute("SELECT seller_tg_id,item_id,price FROM market_listings WHERE id=?",(lid,)).fetchone()
        if not x: raise ValueError("gone")
        if x[0]==user["tg_id"]: raise ValueError("self")
        buyer=conn.execute("SELECT coins FROM users WHERE tg_id=?",(user["tg_id"],)).fetchone()
        inv=conn.execute("SELECT amount FROM inventory WHERE tg_id=? AND item_id=?",(x[0],x[1])).fetchone()
        if not buyer or buyer[0]<x[2] or not inv or inv[0]<1: raise ValueError("unavailable")
        conn.execute("UPDATE users SET coins=coins-? WHERE tg_id=?",(x[2],user["tg_id"]))
        conn.execute("UPDATE users SET coins=coins+?, total_earned=total_earned+? WHERE tg_id=?",(x[2],x[2],x[0]))
        conn.execute("UPDATE inventory SET amount=amount-1 WHERE tg_id=? AND item_id=?",(x[0],x[1]))
        conn.execute("INSERT INTO inventory(tg_id,item_id,amount) VALUES(?,?,1) ON CONFLICT(tg_id,item_id) DO UPDATE SET amount=amount+1",(user["tg_id"],x[1]))
        conn.execute("DELETE FROM market_listings WHERE id=?",(lid,))
        conn.commit()
    except Exception:
        try: conn.rollback()
        except: pass
        await call.answer("❌ Оголошення вже недоступне або недостатньо коштів.",show_alert=True); return
    await call.message.edit_text(f"<b>🛒 Куплено!</b>\n\n{item['name']}\n💰 Ціна: <b>{listing['price']:,}</b> 🪙".replace(","," "),reply_markup=market_kb())
    await call.answer("Куплено!")


@dp.callback_query(F.data == "market_sell_choose")
async def cb_market_sell_choose(call: CallbackQuery, state: FSMContext):
    rows=get_inventory(call.from_user.id)
    if not rows: await call.answer("Інвентар порожній.",show_alert=True); return
    b=InlineKeyboardBuilder()
    for r in rows:
        item=ITEMS[r["item_id"]]
        b.button(text=f"{item['name']} ×{r['amount']}",callback_data=f"market_item:{r['item_id']}")
    b.button(text="⬅️ Інвентар",callback_data="inventory"); b.adjust(1)
    await call.message.edit_text("<b>🏷️ Продати скін</b>\n\nОбери скін. Буде виставлено 1 копію.",reply_markup=b.as_markup()); await call.answer()


@dp.callback_query(F.data.startswith("market_item:"))
async def cb_market_item(call: CallbackQuery,state:FSMContext):
    item_id=call.data.split(":",1)[1]
    rows=db("SELECT amount FROM inventory WHERE tg_id=? AND item_id=?",(call.from_user.id,item_id),True)
    if not rows or rows[0]["amount"]<1 or item_id not in ITEMS: await call.answer("❌ Скін не знайдено.",show_alert=True); return
    await state.set_state(MarketSellState.price); await state.update_data(item_id=item_id)
    await call.message.edit_text(f"<b>🏷️ {ITEMS[item_id]['name']}</b>\n\nВведи ціну в BlockCoins. Наприклад: <code>2500</code>"); await call.answer()


@dp.message(MarketSellState.price)
async def market_set_price(message:Message,state:FSMContext):
    data=await state.get_data(); item_id=data.get("item_id")
    try: price=int(message.text.strip())
    except (ValueError,AttributeError): await message.answer("❌ Введи ціле число."); return
    if not 1<=price<=100000000: await message.answer("❌ Ціна: 1–100 000 000 🪙."); return
    rows=db("SELECT amount FROM inventory WHERE tg_id=? AND item_id=?",(message.from_user.id,item_id),True)
    if not rows or rows[0]["amount"]<1: await state.clear(); await message.answer("❌ Скіна вже немає."); return
    db("UPDATE inventory SET amount=amount-1 WHERE tg_id=? AND item_id=?",(message.from_user.id,item_id))
    db("INSERT INTO market_listings(seller_tg_id,item_id,price,created_at) VALUES(?,?,?,?)",(message.from_user.id,item_id,price,int(datetime.now(timezone.utc).timestamp())))
    await state.clear(); await message.answer(f"✅ {ITEMS[item_id]['name']} виставлено за <b>{price:,} 🪙</b>.".replace(","," "),reply_markup=market_kb())


@dp.callback_query(F.data == "market_mine")
async def cb_market_mine(call:CallbackQuery):
    rows=db("SELECT id,item_id,price FROM market_listings WHERE seller_tg_id=? ORDER BY id DESC",(call.from_user.id,),True)
    b=InlineKeyboardBuilder(); lines=["<b>🏷️ Мої продажі</b>",""]
    if not rows: lines.append("Активних оголошень немає.")
    for r in rows:
        item=ITEMS[r["item_id"]]; lines.append(f"{item['name']} — <b>{r['price']:,}</b> 🪙".replace(","," ")); b.button(text=f"❌ Зняти: {item['name']}",callback_data=f"market_cancel:{r['id']}")
    b.button(text="⬅️ Ринок",callback_data="market"); b.adjust(1)
    await call.message.edit_text("\n".join(lines),reply_markup=b.as_markup()); await call.answer()


@dp.callback_query(F.data.startswith("market_cancel:"))
async def cb_market_cancel(call:CallbackQuery):
    try: lid=int(call.data.split(":",1)[1])
    except ValueError: await call.answer("❌",show_alert=True); return
    row=db("SELECT * FROM market_listings WHERE id=? AND seller_tg_id=?",(lid,call.from_user.id),True)
    if not row: await call.answer("❌ Оголошення не знайдено.",show_alert=True); return
    r=row[0]; add_item(call.from_user.id,r["item_id"],1); db("DELETE FROM market_listings WHERE id=?",(lid,)); await call.answer("Скін повернуто."); await cb_market_mine(call)


# ============================================================
# CALLBACKS
# ============================================================
@dp.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    user = ensure_user(call.from_user)
    await call.message.edit_text(main_text(user), reply_markup=menu_kb())
    await call.answer()


@dp.callback_query(F.data == "profile")
async def cb_profile(call: CallbackQuery):
    user = ensure_user(call.from_user)
    await call.message.edit_text(profile_text(user), reply_markup=back_kb())
    await call.answer()


@dp.callback_query(F.data == "inventory")
async def cb_inventory(call: CallbackQuery):
    ensure_user(call.from_user)
    await call.message.edit_text(inventory_text(call.from_user.id), reply_markup=inventory_kb())
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
    if CASES[cid].get("event_only") and not is_halloween():
        await call.answer("🎃 Halloween зараз неактивний.", show_alert=True)
        return
    if cid == "gold":
        await call.message.edit_text("<b>🟡 Gold Case</b>\n\n💰 Ціна: <b>25 Gold</b>\n\nВідкривай за Gold.", reply_markup=case_buttons(cid))
    else:
        await call.message.edit_text(case_text(cid), reply_markup=case_buttons(cid))
    await call.answer()


@dp.callback_query(F.data.startswith("odds:"))
async def cb_odds(call: CallbackQuery):
    cid = call.data.split(":", 1)[1]
    if cid not in CASES:
        await call.answer("Кейс не знайдено", show_alert=True)
        return
    await call.message.edit_text(odds_text(cid), reply_markup=back_kb(f"case:{cid}"))
    await call.answer()


@dp.callback_query(F.data.startswith("open:"))
async def cb_open(call: CallbackQuery):
    user=ensure_user(call.from_user); cid=call.data.split(":",1)[1]
    if cid not in CASES: await call.answer("Кейс не знайдено",show_alert=True); return
    case=CASES[cid]
    if case.get("event_only") and not is_halloween(): await call.answer("🎃 Halloween зараз неактивний.",show_alert=True); return
    if cid=="gold":
        cost=case["price_gold"]
        cur=conn.cursor(); cur.execute("UPDATE users SET gold=gold-?, cases_opened=cases_opened+1 WHERE tg_id=? AND gold>=?",(cost,user["tg_id"],cost))
    else:
        cost=case["price"]
        cur=conn.cursor(); cur.execute("UPDATE users SET coins=coins-?, cases_opened=cases_opened+1 WHERE tg_id=? AND coins>=?",(cost,user["tg_id"],cost))
    if cur.rowcount==0: conn.rollback(); await call.answer("❌ Не вистачає валюти.",show_alert=True); return
    conn.commit()
    item_id=weighted_drop(case["drops"]); item=ITEMS[item_id]; add_item(user["tg_id"],item_id,1)
    update_task(user["tg_id"],"open_3",1)
    # Visual opening animation through edited messages.
    for i in range(5):
        fake=random.choice(list(ITEMS.values()))
        await call.message.edit_text(f"<b>🎁 Відкриття кейса...</b>\\n\\n🔄 {fake['name']}\\n\\n{'▰'*(i+1)}{'▱'*(4-i)}")
        await asyncio.sleep(0.35)
    text=f"<b>🎉 КЕЙС ВІДКРИТО!</b>\\n\\n{item['name']}\\n{rarity_emoji(item['rarity'])} Рідкість: <b>{item['rarity']}</b>\\n💰 Продаж: <b>{item['price']:,}</b> 🪙\\n\\n🎁 {case['name']}".replace(","," ")
    b=InlineKeyboardBuilder(); b.button(text="🔓 Відкрити ще",callback_data=f"open:{cid}"); b.button(text="🎒 Інвентар",callback_data="inventory"); b.button(text="🎁 Кейси",callback_data="cases"); b.adjust(1,2)
    await call.message.edit_text(text,reply_markup=b.as_markup()); await call.answer()


@dp.callback_query(F.data == "shop")
async def cb_shop(call: CallbackQuery):
    b=InlineKeyboardBuilder()
    b.button(text="🟡 Gold Case • 25 Gold",callback_data="case:gold")
    b.button(text="⭐ VIP Case • 15 Stars",callback_data="vip_info")
    b.button(text="🏪 Gold Market",callback_data="market")
    b.button(text="⬅️ Меню",callback_data="menu" ); b.adjust(1)
    await call.message.edit_text("<b>🏪 Магазин</b>\n\n🟡 Gold Case — 25 Gold\n⭐ VIP Case — 15 Telegram Stars\n🏪 Gold Market — скіни від гравців",reply_markup=b.as_markup()); await call.answer()


@dp.callback_query(F.data == "vip_info")
async def vip_info(call: CallbackQuery):
    b=InlineKeyboardBuilder(); b.button(text="⭐ Купити VIP Case за 15 Stars",callback_data="vip_buy"); b.button(text="⬅️ Магазин",callback_data="shop"); b.adjust(1)
    await call.message.edit_text("<b>⭐ VIP CASE</b>\n\nЦіна: <b>15 Telegram Stars</b>\n\n🎁 Нагорода гарантована: <b>👑 Royal Knife</b>\n\nПісля оплати Stars зараховуються боту через Telegram Payments.",reply_markup=b.as_markup()); await call.answer()


@dp.callback_query(F.data == "vip_buy")
async def vip_buy(call: CallbackQuery):
    await bot.send_invoice(chat_id=call.from_user.id,title="⭐ VIP Case",description="VIP Case BlockDrop — гарантована нагорода Royal Knife",payload=f"vip:{call.from_user.id}",currency="XTR",prices=[LabeledPrice(label="VIP Case",amount=VIP_CASE_STARS)])
    await call.answer()


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    if query.invoice_payload.startswith("vip:") and query.invoice_payload == f"vip:{query.from_user.id}":
        await query.answer(ok=True)
    else:
        await query.answer(ok=False,error_message="Платіж недійсний.")


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment=message.successful_payment
    if payment.invoice_payload != f"vip:{message.from_user.id}": return
    user=ensure_user(message.from_user)
    add_item(user["tg_id"],VIP_REWARD_ITEM,1)
    await message.answer("<b>⭐ VIP CASE ВІДКРИТО!</b>\n\n🎁 Твоя гарантована нагорода:\n👑 <b>Royal Knife</b>\n\nСкін додано в інвентар.")


@dp.callback_query(F.data == "daily")
async def cb_daily(call: CallbackQuery):
    user = ensure_user(call.from_user)
    now = int(datetime.now(timezone.utc).timestamp())
    remaining = DAILY_COOLDOWN - (now - user["daily_at"])
    if remaining > 0:
        await call.answer(f"⏳ Наступний бонус через {format_time_left(remaining)}.", show_alert=True)
        return
    reward = random.randint(300, 800)
    db("UPDATE users SET daily_at=? WHERE tg_id=?", (now, user["tg_id"]))
    add_coins(user["tg_id"], reward)
    await call.message.edit_text(
        f"<b>🎁 Щоденний бонус</b>\n\n"
        f"Ти отримав <b>+{reward} 🪙</b>!\n\n"
        f"Повертайся завтра за новим бонусом.",
        reply_markup=back_kb(),
    )
    await call.answer()


@dp.callback_query(F.data == "top")
async def cb_top(call: CallbackQuery):
    rows = db("SELECT block_id, first_name, coins, cases_opened FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    lines = ["<b>🏆 TOP 10 BlockDrop</b>", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"<b>{i}.</b> {escape(r['first_name'] or 'Гравець')} — <b>{r['coins']:,}</b> 🪙\n   <code>{r['block_id']}</code>")
    if len(lines) == 2:
        lines.append("Поки що немає гравців.")
    await call.message.edit_text("\n".join(lines).replace(",", " "), reply_markup=back_kb())
    await call.answer()


@dp.callback_query(F.data == "stats")
async def cb_stats(call: CallbackQuery):
    user = ensure_user(call.from_user)
    inv = get_inventory(user["tg_id"])
    rare = 0
    for r in inv:
        if ITEMS[r["item_id"]]["rarity"] in {"Легендарний", "Міфічний", "Ексклюзивний"}:
            rare += r["amount"]
    await call.message.edit_text(
        f"<b>📊 Твоя статистика</b>\n\n"
        f"🎁 Кейсів відкрито: <b>{user['cases_opened']}</b>\n"
        f"💰 Зароблено: <b>{user['total_earned']:,}</b> 🪙\n"
        f"💸 Продано предметів: <b>{user['total_sold']}</b>\n"
        f"💎 Цінних скінів: <b>{rare}</b>\n"
        f"🎒 Вартість інвентарю: <b>{inventory_value(user['tg_id']):,}</b> 🪙",
        reply_markup=back_kb(),
    )
    await call.answer()


@dp.callback_query(F.data == "promo_help")
async def cb_promo_help(call: CallbackQuery):
    await call.message.edit_text(
        "<b>🎟️ Промокоди</b>\n\n"
        "Якщо маєш промокод, введи його командою:\n\n"
        "<code>/promo CODE</code>\n\n"
        "Кожен промокод можна використати лише один раз на акаунт.\n\n"
        "Створити свій: <code>/createpromo CODE USES COINS</code>\n"
        f"Комісія: <b>{PROMO_CREATE_FEE} 🪙</b>",
        reply_markup=back_kb(),
    )
    await call.answer()


@dp.callback_query(F.data == "halloween")
async def cb_halloween(call: CallbackQuery):
    ensure_user(call.from_user)
    if not is_halloween():
        await call.message.edit_text(
            "<b>🎃 Halloween Event</b>\n\n"
            "Івент проходить протягом жовтня.\n"
            "У жовтні відкриється спеціальний Halloween Case та буде доступна подієва валюта.",
            reply_markup=back_kb(),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "<b>🎃 HALLOWEEN EVENT</b>\n\n"
        "👻 Спеціальні скіни\n"
        "🎃 Halloween Case\n"
        "🍬 Halloween Coins\n"
        "🎁 Щоденний Halloween-бонус\n\n"
        "Івентові скіни є унікальною колекцією BlockDrop.",
        reply_markup=halloween_kb(),
    )
    await call.answer()


def halloween_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🎃 Halloween Case", callback_data="case:halloween")
    b.button(text="🍬 Halloween Bonus", callback_data="event_daily")
    b.button(text="🏆 Halloween TOP", callback_data="halloween_top")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


@dp.callback_query(F.data == "halloween_top")
async def cb_halloween_top(call: CallbackQuery):
    rows=db("SELECT first_name,halloween_coins FROM users ORDER BY halloween_coins DESC LIMIT 10",fetch=True)
    lines=["<b>🏆 Halloween TOP 10</b>",""]
    for i,r in enumerate(rows,1): lines.append(f"<b>{i}.</b> {escape(r['first_name'] or 'Гравець')} — <b>{r['halloween_coins']}</b> 🍬")
    if len(lines)==2: lines.append("Поки що немає гравців.")
    await call.message.edit_text("\n".join(lines),reply_markup=back_kb("halloween")); await call.answer()


@dp.callback_query(F.data == "event_daily")
async def cb_event_daily(call: CallbackQuery):
    user = ensure_user(call.from_user)
    if not is_halloween():
        await call.answer("🎃 Івент ще не активний.", show_alert=True)
        return
    now = int(datetime.now(timezone.utc).timestamp())
    remaining = DAILY_COOLDOWN - (now - user["event_daily_at"])
    if remaining > 0:
        await call.answer(f"⏳ Наступний Halloween-бонус через {format_time_left(remaining)}.", show_alert=True)
        return
    reward = random.randint(25, 100)
    db("UPDATE users SET event_daily_at=? WHERE tg_id=?", (now, user["tg_id"]))
    add_event_coins(user["tg_id"], reward)
    await call.message.edit_text(
        f"<b>🍬 Halloween Bonus</b>\n\n"
        f"Ти отримав <b>+{reward} Halloween Coins</b>!\n\n"
        f"Збирай їх протягом івенту.",
        reply_markup=back_kb("halloween"),
    )
    await call.answer()


@dp.callback_query(F.data == "gold")
async def cb_gold(call: CallbackQuery):
    user=ensure_user(call.from_user)
    await call.message.edit_text(f"<b>🟡 Gold</b>\n\nБаланс: <b>{user['gold']}</b> 🟡\n\n🔄 Обмін: <b>100 🪙 = 1 🟡</b>\n\nКоманда: <code>/exchange 100</code> — обміняти 100 🪙 на 1 Gold.", reply_markup=back_kb())
    await call.answer()


@dp.message(Command("exchange"))
async def exchange(message: Message):
    user=ensure_user(message.from_user)
    p=message.text.split()
    if len(p)!=2:
        await message.answer("Використання: <code>/exchange AMOUNT_COINS</code>")
        return
    try: amount=int(p[1])
    except ValueError:
        await message.answer("❌ Вкажи число."); return
    if amount<=0 or amount%COINS_PER_GOLD!=0:
        await message.answer("❌ Кількість Coins має бути кратною 100."); return
    gold=amount//COINS_PER_GOLD
    cur=conn.cursor()
    cur.execute("UPDATE users SET coins=coins-?, gold=gold+? WHERE tg_id=? AND coins>=?",(amount,gold,user["tg_id"],amount))
    conn.commit()
    if cur.rowcount==0:
        await message.answer("❌ Недостатньо BlockCoins."); return
    await message.answer(f"🔄 Обмін виконано!\n\n-{amount} 🪙\n+{gold} 🟡 Gold")


@dp.callback_query(F.data == "tasks")
async def cb_tasks(call: CallbackQuery):
    ensure_user(call.from_user)
    b=InlineKeyboardBuilder()
    rows=db("SELECT * FROM tasks WHERE tg_id=?",(call.from_user.id,),True)
    task_seed(call.from_user.id); rows=db("SELECT * FROM tasks WHERE tg_id=?",(call.from_user.id,),True)
    for r in rows:
        if r["progress"]>=r["target"] and not r["claimed"]:
            b.button(text=f"🎁 Забрати +{r['reward_gold']} Gold",callback_data=f"claimtask:{r['id']}")
    b.button(text="⬅️ Меню",callback_data="menu"); b.adjust(1)
    await call.message.edit_text(tasks_text(call.from_user.id),reply_markup=b.as_markup()); await call.answer()


@dp.callback_query(F.data.startswith("claimtask:"))
async def cb_claimtask(call: CallbackQuery):
    tid=int(call.data.split(":")[1]); user=ensure_user(call.from_user)
    cur=conn.cursor(); cur.execute("UPDATE tasks SET claimed=1 WHERE id=? AND tg_id=? AND claimed=0 AND progress>=target",(tid,user["tg_id"]));
    if cur.rowcount==0: conn.rollback(); await call.answer("Завдання ще не готове.",show_alert=True); return
    row=conn.execute("SELECT reward_gold FROM tasks WHERE id=?",(tid,)).fetchone(); conn.execute("UPDATE users SET gold=gold+? WHERE tg_id=?",(row[0],user["tg_id"])); conn.commit()
    await call.answer(f"+{row[0]} Gold!",show_alert=True); await call.message.edit_text(tasks_text(user["tg_id"]),reply_markup=back_kb())


@dp.callback_query(F.data == "market")
async def cb_market(call: CallbackQuery):
    ensure_user(call.from_user); await call.message.edit_text(market_text(call.from_user.id),reply_markup=market_kb(call.from_user.id)); await call.answer()


@dp.message(Command("sellgold"))
async def sellgold(message: Message):
    user=ensure_user(message.from_user); p=message.text.split()
    if len(p)!=3:
        await message.answer("Використання: <code>/sellgold ITEM_ID PRICE_GOLD</code>"); return
    item_id=p[1]
    try: price=int(p[2])
    except ValueError: price=0
    if item_id not in ITEMS or price<=0:
        await message.answer("❌ Невірний ITEM_ID або ціна."); return
    cur=conn.cursor(); cur.execute("UPDATE inventory SET amount=amount-1 WHERE tg_id=? AND item_id=? AND amount>0",(user["tg_id"],item_id))
    if cur.rowcount==0: conn.rollback(); await message.answer("❌ У тебе немає цього скіна."); return
    conn.execute("DELETE FROM inventory WHERE tg_id=? AND item_id=? AND amount<=0",(user["tg_id"],item_id))
    conn.execute("INSERT INTO market(seller_tg_id,item_id,price_gold,created_at) VALUES(?,?,?,?)",(user["tg_id"],item_id,price,int(datetime.now(timezone.utc).timestamp())))
    conn.commit(); await message.answer(f"✅ {ITEMS[item_id]['name']} виставлено на Gold Market за {price} 🟡")


@dp.callback_query(F.data.startswith("buygold:"))
async def cb_buygold(call: CallbackQuery):
    buyer=ensure_user(call.from_user); listing_id=int(call.data.split(":")[1])
    try:
        conn.execute("BEGIN IMMEDIATE")
        lot=conn.execute("SELECT * FROM market WHERE id=?",(listing_id,)).fetchone()
        if not lot: conn.rollback(); await call.answer("Лот уже продано.",show_alert=True); return
        if lot["seller_tg_id"]==buyer["tg_id"]: conn.rollback(); await call.answer("Не можна купити власний лот.",show_alert=True); return
        if buyer["gold"]<lot["price_gold"]: conn.rollback(); await call.answer("Недостатньо Gold.",show_alert=True); return
        conn.execute("UPDATE users SET gold=gold-? WHERE tg_id=?",(lot["price_gold"],buyer["tg_id"]))
        conn.execute("UPDATE users SET gold=gold+? WHERE tg_id=?",(lot["price_gold"],lot["seller_tg_id"]))
        conn.execute("INSERT INTO inventory(tg_id,item_id,amount) VALUES(?,?,1) ON CONFLICT(tg_id,item_id) DO UPDATE SET amount=amount+1",(buyer["tg_id"],lot["item_id"]))
        conn.execute("DELETE FROM market WHERE id=?",(listing_id,)); conn.commit()
    except Exception:
        conn.rollback(); await call.answer("Помилка покупки.",show_alert=True); return
    await call.message.edit_text(f"✅ Куплено {ITEMS[lot['item_id']]['name']} за {lot['price_gold']} 🟡",reply_markup=market_kb(buyer["tg_id"])); await call.answer()


@dp.callback_query(F.data == "goldcase")
async def cb_goldcase(call: CallbackQuery):
    await call.message.edit_text("<b>🟡 Gold Case</b>\n\nЦіна: <b>25 Gold</b>\n\nШанси дивись нижче.",reply_markup=gold_cases_kb()); await call.answer()


@dp.callback_query(F.data == "sell_one")
async def cb_sell_one(call: CallbackQuery):
    user = ensure_user(call.from_user)
    rows = db("""
        SELECT item_id, amount FROM inventory
        WHERE tg_id=? AND amount>0
        ORDER BY (SELECT price FROM item_dummy WHERE 1=0)
    """, (user["tg_id"],), True) if False else get_inventory(call.from_user.id)
    if not rows:
        await call.answer("Інвентар порожній.", show_alert=True)
        return
    # Cheapest item by configured price.
    row = min(rows, key=lambda r: ITEMS[r["item_id"]]["price"])
    item = ITEMS[row["item_id"]]
    db("UPDATE inventory SET amount=amount-1 WHERE tg_id=? AND item_id=?", (user["tg_id"], row["item_id"]))
    db("UPDATE users SET total_sold=total_sold+1 WHERE tg_id=?", (user["tg_id"],))
    add_coins(user["tg_id"], item["price"])
    update_task(user["tg_id"], "sell_5", 1)
    await call.message.edit_text(
        f"<b>💸 Предмет продано!</b>\n\n{item['name']}\n+{item['price']:,} 🪙".replace(",", " "),
        reply_markup=inventory_kb(),
    )
    await call.answer()


@dp.callback_query(F.data == "sell_all")
async def cb_sell_all(call: CallbackQuery):
    user = ensure_user(call.from_user)
    rows = get_inventory(user["tg_id"])
    if not rows:
        await call.answer("Інвентар порожній.", show_alert=True)
        return
    total = 0
    count = 0
    for r in rows:
        if r["item_id"] not in ITEMS:
            continue
        amount = r["amount"]
        price = ITEMS[r["item_id"]]["price"]
        total += amount * price
        count += amount
    db("DELETE FROM inventory WHERE tg_id=?", (user["tg_id"],))
    db("UPDATE users SET total_sold=total_sold+? WHERE tg_id=?", (count, user["tg_id"]))
    add_coins(user["tg_id"], total)
    update_task(user["tg_id"], "sell_5", count)
    await call.message.edit_text(
        f"<b>💰 Інвентар продано!</b>\n\n"
        f"Предметів: <b>{count}</b>\n"
        f"Отримано: <b>+{total:,} 🪙</b>".replace(",", " "),
        reply_markup=inventory_kb(),
    )
    await call.answer()


@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    if not admin_only(call.from_user.id):
        await call.answer("⛔", show_alert=True)
        return
    users = db("SELECT COUNT(*) c FROM users", fetch=True)[0]["c"]
    cases = db("SELECT COALESCE(SUM(cases_opened),0) c FROM users", fetch=True)[0]["c"]
    await call.message.edit_text(
        f"<b>🛠️ Admin statistics</b>\n\n👥 {users} гравців\n🎁 {cases} відкритих кейсів",
        reply_markup=back_kb(),
    )
    await call.answer()


# Simple text fallback.
@dp.message(F.text)
async def fallback(message: Message):
    user = ensure_user(message.from_user)
    text = message.text.strip().lower()
    if text in {"кейси", "🎁 кейси"}:
        await message.answer("<b>🎁 Кейси BlockDrop</b>", reply_markup=cases_kb())
    elif text in {"інвентар", "🎒 інвентар"}:
        await message.answer(inventory_text(user["tg_id"]), reply_markup=inventory_kb())
    else:
        await message.answer("Обери розділ у меню 👇", reply_markup=menu_kb())


async def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Встав BOT_TOKEN у змінну BOT_TOKEN на початку файлу.")
    print("[BlockDrop] Bot started")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

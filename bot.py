# BlockDrop — safe one-file Telegram game bot
# aiogram 3.x + SQLite
# Render-ready webhook. No external payment system is used.

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
from aiogram.types import Message, CallbackQuery, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "BlockDropSecret2026X7")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DB_FILE = os.getenv("DB_FILE") or ("/var/data/blockdrop.db" if os.path.isdir("/var/data") else "blockdrop.db")

START_COINS = 1000
START_GOLD = 0
PROMO_CREATE_FEE = 50
COINS_PER_GOLD = 100
DAILY_COOLDOWN = 24 * 60 * 60

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

# Cosmetic BlockDrop items. They are intentionally not tied to real-world equipment.
ITEMS = {
    "neon_cube": {"name": "🔷 Crystal Blade", "rarity": "Звичайний", "price": 35},
    "pixel_star": {"name": "🟣 Neon Blaster", "rarity": "Звичайний", "price": 50},
    "blue_wave": {"name": "🔵 Blue Striker", "rarity": "Незвичайний", "price": 90},
    "toxic_blob": {"name": "☣️ Toxic Shooter", "rarity": "Незвичайний", "price": 140},
    "crimson_core": {"name": "🔴 Crimson Blaster", "rarity": "Рідкісний", "price": 260},
    "cyber_orbit": {"name": "⚡ Cyber Striker", "rarity": "Рідкісний", "price": 420},
    "lava_core": {"name": "🔥 Lava Shooter", "rarity": "Епічний", "price": 750},
    "shadow_cube": {"name": "🌑 Shadow Blaster", "rarity": "Епічний", "price": 1100},
    "dragon_orbit": {"name": "🐉 Dragon Rifle", "rarity": "Легендарний", "price": 2400},
    "void_portal": {"name": "🌀 Void Launcher", "rarity": "Легендарний", "price": 4200},
    "golden_crown": {"name": "👑 Golden Blaster", "rarity": "Міфічний", "price": 8000},
    "galaxy_core": {"name": "🌌 Galaxy Rifle", "rarity": "Міфічний", "price": 15000},
    "royal_crystal": {"name": "💎 Royal Blade", "rarity": "Ексклюзивний", "price": 30000},
    "phantom_mask": {"name": "👾 Phantom Blaster", "rarity": "Ексклюзивний", "price": 60000},
    "pumpkin_cube": {"name": "🎃 Pumpkin Blaster", "rarity": "Хелловін", "price": 900},
    "ghost_star": {"name": "👻 Ghost Hunter", "rarity": "Хелловін", "price": 1800},
    "bat_core": {"name": "🦇 Bat Striker", "rarity": "Хелловін", "price": 4000},
    "witch_orbit": {"name": "🧙 Witch Blaster", "rarity": "Хелловін", "price": 8500},
    "reaper_mask": {"name": "💀 Reaper Blade", "rarity": "Хелловін", "price": 20000},
}

CASES = {
    "starter": {
        "name": "📦 Starter Box", "price": 250,
        "drops": [("neon_cube", 35), ("pixel_star", 28), ("blue_wave", 20),
                   ("toxic_blob", 10), ("crimson_core", 5), ("cyber_orbit", 1.8), ("lava_core", .2)]},
    "premium": {
        "name": "✨ Premium Box", "price": 900,
        "drops": [("blue_wave", 24), ("toxic_blob", 22), ("crimson_core", 24),
                   ("cyber_orbit", 16), ("lava_core", 9), ("shadow_cube", 4), ("dragon_orbit", 1)]},
    "legendary": {
        "name": "💎 Legendary Box", "price": 3500,
        "drops": [("cyber_orbit", 20), ("lava_core", 24), ("shadow_cube", 22),
                   ("dragon_orbit", 18), ("void_portal", 10), ("golden_crown", 5),
                   ("galaxy_core", .9), ("royal_crystal", .1)]},
    "elite": {
        "name": "🔥 Elite Box", "price": 12000,
        "drops": [("lava_core", 15), ("shadow_cube", 24), ("dragon_orbit", 25),
                   ("void_portal", 18), ("golden_crown", 10), ("galaxy_core", 7),
                   ("royal_crystal", .8), ("phantom_mask", .2)]},
    "gold": {
        "name": "🟡 Gold Box", "price_gold": 25,
        "drops": [("blue_wave", 35), ("toxic_blob", 25), ("crimson_core", 18),
                   ("cyber_orbit", 12), ("lava_core", 6), ("shadow_cube", 3), ("dragon_orbit", 1)]},
    "halloween": {
        "name": "🎃 Halloween Box", "price": 500, "event_only": True,
        "drops": [("pumpkin_cube", 48), ("ghost_star", 28), ("bat_core", 15),
                   ("witch_orbit", 7), ("reaper_mask", 2)]},
}

TASK_DEFS = [
    ("open_3", "🎁 Відкрий 3 кейси", 3, 3),
    ("earn_1000", "💰 Зароби 1000 BlockCoins", 1000, 5),
    ("sell_1", "🏷️ Продай 1 предмет NPC", 1, 4),
    ("visit_market", "🏪 Відкрий Ринок", 1, 2),
]

# ============================================================
# DATABASE
# ============================================================
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True) if os.path.dirname(DB_FILE) else None
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
    db("""CREATE TABLE IF NOT EXISTS users(
        tg_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, block_id TEXT UNIQUE NOT NULL,
        coins INTEGER NOT NULL DEFAULT 1000, gold INTEGER NOT NULL DEFAULT 0,
        halloween_coins INTEGER NOT NULL DEFAULT 0, cases_opened INTEGER NOT NULL DEFAULT 0,
        total_earned INTEGER NOT NULL DEFAULT 0, total_sold INTEGER NOT NULL DEFAULT 0,
        daily_at INTEGER NOT NULL DEFAULT 0, event_daily_at INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)""")
    db("""CREATE TABLE IF NOT EXISTS inventory(
        tg_id INTEGER NOT NULL, item_id TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(tg_id,item_id), FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE)""")
    db("""CREATE TABLE IF NOT EXISTS promo_codes(
        code TEXT PRIMARY KEY, coins INTEGER NOT NULL DEFAULT 0, halloween_coins INTEGER NOT NULL DEFAULT 0,
        max_uses INTEGER NOT NULL DEFAULT 1, uses INTEGER NOT NULL DEFAULT 0, gold INTEGER NOT NULL DEFAULT 0,
        item_id TEXT, case_id TEXT, creator_tg_id INTEGER)""")
    db("""CREATE TABLE IF NOT EXISTS promo_used(
        tg_id INTEGER NOT NULL, code TEXT NOT NULL, PRIMARY KEY(tg_id,code),
        FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE)""")
    db("""CREATE TABLE IF NOT EXISTS market_listings(
        id INTEGER PRIMARY KEY AUTOINCREMENT, seller_tg_id INTEGER NOT NULL, item_id TEXT NOT NULL,
        price INTEGER NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(seller_tg_id) REFERENCES users(tg_id) ON DELETE CASCADE)""")
    db("""CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, task_key TEXT NOT NULL,
        progress INTEGER NOT NULL DEFAULT 0, target INTEGER NOT NULL, reward_gold INTEGER NOT NULL DEFAULT 0,
        claimed INTEGER NOT NULL DEFAULT 0, task_date TEXT NOT NULL,
        UNIQUE(tg_id,task_key), FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE)""")

    # Migrations for older databases.
    migrations = {
        "users": [("gold", "INTEGER NOT NULL DEFAULT 0"), ("halloween_coins", "INTEGER NOT NULL DEFAULT 0")],
        "promo_codes": [("gold", "INTEGER NOT NULL DEFAULT 0"), ("item_id", "TEXT"), ("case_id", "TEXT"), ("creator_tg_id", "INTEGER")],
        "tasks": [("task_date", "TEXT")],
    }
    for table, cols in migrations.items():
        existing = {r["name"] for r in db(f"PRAGMA table_info({table})", fetch=True)}
        for col, definition in cols:
            if col not in existing:
                try: db(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
                except sqlite3.OperationalError: pass


def now_ts():
    return int(datetime.now(timezone.utc).timestamp())


def today_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def new_block_id():
    while True:
        value = "BD-" + "".join(random.choices("0123456789", k=7))
        if not db("SELECT 1 FROM users WHERE block_id=?", (value,), True): return value


def ensure_user(tg_user):
    row = db("SELECT * FROM users WHERE tg_id=?", (tg_user.id,), True)
    if not row:
        db("INSERT INTO users(tg_id,username,first_name,block_id,coins,gold,created_at) VALUES(?,?,?,?,?,?,?)",
           (tg_user.id, tg_user.username or "", tg_user.first_name or "", new_block_id(), START_COINS, START_GOLD, now_ts()))
    else:
        db("UPDATE users SET username=?,first_name=? WHERE tg_id=?",
           (tg_user.username or "", tg_user.first_name or "", tg_user.id))
    ensure_daily_tasks(tg_user.id)
    return db("SELECT * FROM users WHERE tg_id=?", (tg_user.id,), True)[0]


def get_user(tg_id):
    rows = db("SELECT * FROM users WHERE tg_id=?", (tg_id,), True)
    return rows[0] if rows else None


def is_halloween(): return datetime.now().month == 10


def rarity_emoji(r):
    return {"Звичайний":"⚪","Незвичайний":"🟢","Рідкісний":"🔵","Епічний":"🟣",
            "Легендарний":"🟠","Міфічний":"🔴","Ексклюзивний":"💎","Хелловін":"🎃"}.get(r,"▫️")


def weighted_drop(drops):
    total = sum(w for _, w in drops)
    pick, cur = random.uniform(0, total), 0
    for item_id, weight in drops:
        cur += weight
        if pick <= cur: return item_id
    return drops[-1][0]


def add_item(tg_id, item_id, amount=1):
    db("INSERT INTO inventory(tg_id,item_id,amount) VALUES(?,?,?) ON CONFLICT(tg_id,item_id) DO UPDATE SET amount=amount+excluded.amount",
       (tg_id,item_id,amount))


def add_coins(tg_id, amount):
    db("UPDATE users SET coins=coins+?,total_earned=total_earned+? WHERE tg_id=?", (amount,max(0,amount),tg_id))


def add_gold(tg_id, amount): db("UPDATE users SET gold=gold+? WHERE tg_id=?", (amount,tg_id))


def get_inventory(tg_id):
    return db("SELECT item_id,amount FROM inventory WHERE tg_id=? AND amount>0 ORDER BY amount DESC", (tg_id,), True)


def inventory_value(tg_id):
    return sum(ITEMS[r["item_id"]]["price"]*r["amount"] for r in get_inventory(tg_id) if r["item_id"] in ITEMS)

# ============================================================
# DAILY TASKS
# ============================================================
def ensure_daily_tasks(tg_id):
    day = today_key()
    row = db("SELECT task_date FROM tasks WHERE tg_id=? LIMIT 1", (tg_id,), True)
    if row and row[0]["task_date"] == day:
        return
    db("DELETE FROM tasks WHERE tg_id=?", (tg_id,))
    for key, _, target, reward in TASK_DEFS:
        db("INSERT OR IGNORE INTO tasks(tg_id,task_key,progress,target,reward_gold,claimed,task_date) VALUES(?,?,?,?,?,0,?)",
           (tg_id,key,0,target,reward,day))


def update_task(tg_id, task_key, amount=1):
    ensure_daily_tasks(tg_id)
    db("UPDATE tasks SET progress=MIN(target,progress+?) WHERE tg_id=? AND task_key=? AND claimed=0",
       (amount,tg_id,task_key))

# ============================================================
# KEYBOARDS
# ============================================================
def menu_kb():
    b=InlineKeyboardBuilder()
    for text, data in [("👤 Профіль","profile"),("🏪 Магазин","shop"),("🏪 Ринок","market"),("🎒 Інвентар","inventory"),
                       ("🎁 Бонус","daily"),("🏆 Топ","top"),("📋 Завдання","tasks"),("🎟️ Промокод","promo_help"),
                       ("📊 Статистика","stats"),("🎃 Halloween","halloween")]: b.button(text=text,callback_data=data)
    b.adjust(2,2,2,2,2)
    return b.as_markup()


def profile_kb():
    b=InlineKeyboardBuilder()
    b.button(text="🎒 Інвентар",callback_data="inventory")
    b.button(text="🏆 Досягнення",callback_data="achievements")
    b.button(text="📊 Статистика",callback_data="stats")
    b.button(text="⬅️ Меню",callback_data="menu")
    b.adjust(2,1,1); return b.as_markup()


def shop_kb():
    b=InlineKeyboardBuilder()
    b.button(text="🎁 Кейси",callback_data="cases")
    b.button(text="🟡 Gold",callback_data="gold")
    b.button(text="💱 Обмін Coins → Gold",callback_data="exchange_info")
    b.button(text="⬅️ Меню",callback_data="menu")
    b.adjust(2,1,1); return b.as_markup()


def cases_kb():
    b=InlineKeyboardBuilder()
    for cid,c in CASES.items():
        if c.get("event_only") and not is_halloween(): continue
        price = f"{c['price_gold']} 🟡" if cid=="gold" else f"{c['price']} 🪙"
        b.button(text=f"{c['name']} • {price}",callback_data=f"case:{cid}")
    b.button(text="⬅️ Магазин",callback_data="shop")
    b.adjust(1); return b.as_markup()


def case_kb(cid):
    b=InlineKeyboardBuilder(); b.button(text="🔓 Відкрити",callback_data=f"open:{cid}"); b.button(text="📊 Шанси",callback_data=f"odds:{cid}"); b.button(text="⬅️ Кейси",callback_data="cases"); b.adjust(2,1); return b.as_markup()


def inventory_kb():
    b=InlineKeyboardBuilder(); b.button(text="🏷️ Продати на ринку",callback_data="market_sell_choose"); b.button(text="💸 Продати NPC",callback_data="sell_one"); b.button(text="💰 Продати все NPC",callback_data="sell_all"); b.button(text="⬅️ Профіль",callback_data="profile"); b.adjust(1); return b.as_markup()


def market_kb():
    b=InlineKeyboardBuilder()
    for r in db("SELECT id,item_id,price FROM market_listings ORDER BY id DESC LIMIT 15",fetch=True):
        item=ITEMS.get(r["item_id"])
        if item: b.button(text=f"#{r['id']} {item['name']} • {r['price']} 🪙",callback_data=f"market_buy:{r['id']}")
    b.button(text="🏷️ Мої продажі",callback_data="market_mine"); b.button(text="🔄 Оновити",callback_data="market"); b.button(text="⬅️ Меню",callback_data="menu"); b.adjust(1); return b.as_markup()

# ============================================================
# TEXT
# ============================================================
def main_text(u):
    event="\n🎃 Halloween: <b>АКТИВНИЙ</b>" if is_halloween() else ""
    return (f"<b>🟩 BLOCKDROP</b>\n\nПривіт, <b>{escape(u['first_name'] or 'гравець')}</b>!\n"
            f"🆔 <code>{u['block_id']}</code>\n\n💰 BlockCoins: <b>{u['coins']:,}</b>\n🟡 Gold: <b>{u['gold']:,}</b>".replace(","," ")+
            f"\n🎃 Halloween Coins: <b>{u['halloween_coins']:,}</b>{event}\n\nОбирай розділ нижче 👇")


def profile_text(u):
    inv=get_inventory(u["tg_id"])
    return (f"<b>👤 Профіль</b>\n\n🆔 <code>{u['block_id']}</code>\n👤 {escape(u['first_name'] or '—')}\n"
            f"💰 {u['coins']:,} 🪙\n🟡 {u['gold']:,} Gold\n🎃 {u['halloween_coins']:,} HC\n\n"
            f"🎁 Кейсів відкрито: <b>{u['cases_opened']}</b>\n🎒 Предметів: <b>{sum(x['amount'] for x in inv)}</b>\n"
            f"💎 Вартість інвентарю: <b>{inventory_value(u['tg_id']):,}</b> 🪙").replace(","," ")


def inventory_text(tg_id):
    rows=get_inventory(tg_id)
    if not rows: return "<b>🎒 Інвентар</b>\n\nПоки що тут порожньо. Відкрий кейс у Магазині!"
    lines=["<b>🎒 Інвентар</b>",""]
    for r in sorted(rows,key=lambda x:(-RARITY_ORDER.get(ITEMS[x['item_id']]['rarity'],0),-x['amount'])):
        item=ITEMS[r['item_id']]; lines.append(f"{rarity_emoji(item['rarity'])} {item['name']} × <b>{r['amount']}</b> — {item['price']} 🪙")
    return "\n".join(lines)


def market_text():
    rows=db("SELECT m.id,m.item_id,m.price,u.first_name,u.block_id FROM market_listings m JOIN users u ON u.tg_id=m.seller_tg_id ORDER BY m.id DESC LIMIT 15",fetch=True)
    lines=["<b>🏪 Ринок BlockDrop</b>","","Гравці виставляють предмети за BlockCoins.",""]
    if not rows: lines.append("Ринок поки порожній.")
    for r in rows:
        item=ITEMS.get(r['item_id'])
        if item: lines.append(f"<b>#{r['id']}</b> {item['name']} • {item['rarity']}\n💰 <b>{r['price']}</b> 🪙 • {escape(r['first_name'] or r['block_id'])}")
    return "\n".join(lines)

# ============================================================
# BOT
# ============================================================
init_db()
bot=Bot(BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp=Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def start(message:Message):
    u=ensure_user(message.from_user); await message.answer(main_text(u),reply_markup=menu_kb())

@dp.message(Command("menu"))
async def menu(message:Message):
    u=ensure_user(message.from_user); await message.answer(main_text(u),reply_markup=menu_kb())

@dp.message(Command("tgid"))
async def tgid(message:Message): await message.answer(f"🆔 Telegram ID: <code>{message.from_user.id}</code>")

@dp.message(Command("id"))
async def blockid(message:Message):
    u=ensure_user(message.from_user); await message.answer(f"🆔 BlockDrop ID: <code>{u['block_id']}</code>")

# ---------------- PROFILE / SHOP ----------------
@dp.callback_query(F.data=="profile")
async def cb_profile(call:CallbackQuery):
    u=ensure_user(call.from_user); await call.message.edit_text(profile_text(u),reply_markup=profile_kb()); await call.answer()

@dp.callback_query(F.data=="shop")
async def cb_shop(call:CallbackQuery):
    u=ensure_user(call.from_user)
    await call.message.edit_text("<b>🏪 Магазин</b>\n\n🎁 Тут знаходяться всі кейси.\n🟡 Gold — окрема внутрішня валюта.\n💱 Coins можна обміняти на Gold.",reply_markup=shop_kb()); await call.answer()

@dp.callback_query(F.data=="gold")
async def cb_gold(call:CallbackQuery):
    u=ensure_user(call.from_user)
    await call.message.edit_text(f"<b>🟡 Gold</b>\n\nТвій баланс: <b>{u['gold']}</b> 🟡\n\nКурс: <b>{COINS_PER_GOLD} 🪙 = 1 🟡</b>\n\nGold використовується для Gold Box.",reply_markup=shop_kb()); await call.answer()

@dp.callback_query(F.data=="exchange_info")
async def exchange_info(call:CallbackQuery):
    b=InlineKeyboardBuilder(); b.button(text="💱 Обміняти 100 🪙 → 1 🟡",callback_data="exchange:1"); b.button(text="💱 Обміняти 500 🪙 → 5 🟡",callback_data="exchange:5"); b.button(text="⬅️ Магазин",callback_data="shop"); b.adjust(1)
    await call.message.edit_text("<b>💱 Обмін валют</b>\n\n100 BlockCoins = 1 Gold.",reply_markup=b.as_markup()); await call.answer()

@dp.callback_query(F.data.startswith("exchange:"))
async def exchange(call:CallbackQuery):
    u=ensure_user(call.from_user); gold=int(call.data.split(":")[1]); cost=gold*COINS_PER_GOLD
    if u["coins"]<cost: await call.answer("❌ Недостатньо BlockCoins.",show_alert=True); return
    db("UPDATE users SET coins=coins-?,gold=gold+? WHERE tg_id=?",(cost,gold,u["tg_id"]))
    u=get_user(u["tg_id"]); await call.message.edit_text(f"✅ Обмін виконано!\n\n-{cost} 🪙\n+{gold} 🟡",reply_markup=shop_kb()); await call.answer()

# ---------------- CASES ----------------
@dp.callback_query(F.data=="cases")
async def cb_cases(call:CallbackQuery):
    ensure_user(call.from_user); await call.message.edit_text("<b>🎁 Кейси</b>\n\nОбери кейс. Усі вони відкриваються за внутрішні BlockCoins або Gold.",reply_markup=cases_kb()); await call.answer()

@dp.callback_query(F.data.startswith("case:"))
async def cb_case(call:CallbackQuery):
    cid=call.data.split(":",1)[1]; c=CASES.get(cid)
    if not c or (c.get("event_only") and not is_halloween()): await call.answer("❌ Цей кейс зараз недоступний.",show_alert=True); return
    price=f"{c['price_gold']} 🟡" if cid=="gold" else f"{c['price']} 🪙"
    text=f"<b>{c['name']}</b>\n\nЦіна: <b>{price}</b>\n\nНатисни «Відкрити», щоб отримати косметичний предмет."
    await call.message.edit_text(text,reply_markup=case_kb(cid)); await call.answer()

@dp.callback_query(F.data.startswith("odds:"))
async def cb_odds(call:CallbackQuery):
    cid=call.data.split(":",1)[1]; c=CASES.get(cid)
    if not c: await call.answer("❌ Кейс не знайдено.",show_alert=True); return
    total=sum(x[1] for x in c['drops']); lines=[f"<b>📊 Шанси — {c['name']}</b>",""]
    for item_id,w in c['drops']:
        item=ITEMS[item_id]; lines.append(f"{rarity_emoji(item['rarity'])} {item['name']} — <b>{w/total*100:.2f}%</b>")
    await call.message.edit_text("\n".join(lines),reply_markup=case_kb(cid)); await call.answer()

@dp.callback_query(F.data.startswith("open:"))
async def cb_open(call:CallbackQuery):
    u=ensure_user(call.from_user); cid=call.data.split(":",1)[1]; c=CASES.get(cid)
    if not c or (c.get("event_only") and not is_halloween()): await call.answer("❌ Недоступно.",show_alert=True); return
    if cid=="gold":
        if u['gold']<c['price_gold']: await call.answer("❌ Недостатньо Gold.",show_alert=True); return
        db("UPDATE users SET gold=gold-?,cases_opened=cases_opened+1 WHERE tg_id=?",(c['price_gold'],u['tg_id']))
    else:
        if u['coins']<c['price']: await call.answer("❌ Недостатньо BlockCoins.",show_alert=True); return
        db("UPDATE users SET coins=coins-?,cases_opened=cases_opened+1 WHERE tg_id=?",(c['price'],u['tg_id']))
    await call.answer("✨ Відкриваємо...")
    for frame in ["🎁 Відкриваємо...", "🎁 ▫️▫️▫️▫️▫️", "🎁 ▪️▫️▪️▫️▪️"]:
        try: await call.message.edit_text(frame); await asyncio.sleep(.35)
        except Exception: pass
    item_id=weighted_drop(c['drops']); item=ITEMS[item_id]; add_item(u['tg_id'],item_id); update_task(u['tg_id'],"open_3",1)
    await call.message.edit_text(f"<b>🎉 Тобі випало!</b>\n\n{rarity_emoji(item['rarity'])} <b>{item['name']}</b>\nРідкість: <b>{item['rarity']}</b>\nЦінність: <b>{item['price']}</b> 🪙",reply_markup=case_kb(cid))

# ---------------- INVENTORY ----------------
@dp.callback_query(F.data=="inventory")
async def cb_inventory(call:CallbackQuery):
    ensure_user(call.from_user); await call.message.edit_text(inventory_text(call.from_user.id),reply_markup=inventory_kb()); await call.answer()

@dp.callback_query(F.data=="sell_one")
async def sell_one(call:CallbackQuery):
    rows=get_inventory(call.from_user.id)
    if not rows: await call.answer("Інвентар порожній.",show_alert=True); return
    row=min(rows,key=lambda r:ITEMS[r['item_id']]['price']); item=ITEMS[row['item_id']]; value=item['price']
    db("UPDATE inventory SET amount=amount-1 WHERE tg_id=? AND item_id=?",(call.from_user.id,row['item_id']))
    db("DELETE FROM inventory WHERE tg_id=? AND item_id=? AND amount<=0",(call.from_user.id,row['item_id']))
    db("UPDATE users SET coins=coins+?,total_sold=total_sold+? WHERE tg_id=?",(value,value,call.from_user.id)); update_task(call.from_user.id,"sell_1",1)
    await call.message.edit_text(f"✅ Продано NPC: {item['name']}\n\n+{value} 🪙",reply_markup=inventory_kb()); await call.answer()

@dp.callback_query(F.data=="sell_all")
async def sell_all(call:CallbackQuery):
    rows=get_inventory(call.from_user.id)
    if not rows: await call.answer("Інвентар порожній.",show_alert=True); return
    value=sum(ITEMS[r['item_id']]['price']*r['amount'] for r in rows); count=sum(r['amount'] for r in rows)
    db("DELETE FROM inventory WHERE tg_id=?",(call.from_user.id,)); db("UPDATE users SET coins=coins+?,total_sold=total_sold+? WHERE tg_id=?",(value,value,call.from_user.id)); update_task(call.from_user.id,"sell_1",1)
    await call.message.edit_text(f"✅ Продано NPC: <b>{count}</b> предметів\n\n+{value:,} 🪙".replace(","," "),reply_markup=inventory_kb()); await call.answer()

# ---------------- MARKET ----------------
class MarketSellState(StatesGroup): price=State()

@dp.callback_query(F.data=="market")
async def cb_market(call:CallbackQuery):
    ensure_user(call.from_user); update_task(call.from_user.id,"visit_market",1); await call.message.edit_text(market_text(),reply_markup=market_kb()); await call.answer()

@dp.callback_query(F.data=="market_sell_choose")
async def market_sell_choose(call:CallbackQuery):
    rows=get_inventory(call.from_user.id)
    if not rows: await call.answer("Інвентар порожній.",show_alert=True); return
    b=InlineKeyboardBuilder()
    for r in rows:
        item=ITEMS[r['item_id']]; b.button(text=f"{item['name']} ×{r['amount']}",callback_data=f"market_item:{r['item_id']}")
    b.button(text="⬅️ Інвентар",callback_data="inventory"); b.adjust(1)
    await call.message.edit_text("<b>🏷️ Продаж на ринку</b>\n\nОбери предмет. Буде виставлено 1 копію.",reply_markup=b.as_markup()); await call.answer()

@dp.callback_query(F.data.startswith("market_item:"))
async def market_item(call:CallbackQuery,state:FSMContext):
    item_id=call.data.split(":",1)[1]
    if item_id not in ITEMS: await call.answer("❌ Предмет не знайдено.",show_alert=True); return
    inv=db("SELECT amount FROM inventory WHERE tg_id=? AND item_id=?",(call.from_user.id,item_id),True)
    if not inv or inv[0]['amount']<1: await call.answer("❌ Предмет відсутній.",show_alert=True); return
    await state.update_data(item_id=item_id); await state.set_state(MarketSellState.price)
    await call.message.edit_text(f"🏷️ <b>{ITEMS[item_id]['name']}</b>\n\nНапиши ціну в BlockCoins одним повідомленням.\nНаприклад: <code>500</code>")
    await call.answer()

@dp.message(MarketSellState.price)
async def market_price(message:Message,state:FSMContext):
    try: price=int(message.text.strip())
    except (ValueError,AttributeError): await message.answer("❌ Введи ціле число."); return
    if not 1<=price<=10_000_000: await message.answer("❌ Ціна має бути від 1 до 10 000 000 🪙."); return
    data=await state.get_data(); item_id=data.get('item_id'); u=ensure_user(message.from_user)
    inv=db("SELECT amount FROM inventory WHERE tg_id=? AND item_id=?",(u['tg_id'],item_id),True)
    if not inv or inv[0]['amount']<1: await state.clear(); await message.answer("❌ Предмет уже відсутній."); return
    db("UPDATE inventory SET amount=amount-1 WHERE tg_id=? AND item_id=?",(u['tg_id'],item_id)); db("DELETE FROM inventory WHERE tg_id=? AND item_id=? AND amount<=0",(u['tg_id'],item_id))
    db("INSERT INTO market_listings(seller_tg_id,item_id,price,created_at) VALUES(?,?,?,?)",(u['tg_id'],item_id,price,now_ts())); await state.clear()
    await message.answer(f"✅ {ITEMS[item_id]['name']} виставлено за <b>{price}</b> 🪙.",reply_markup=market_kb())

@dp.callback_query(F.data=="market_mine")
async def market_mine(call:CallbackQuery):
    rows=db("SELECT id,item_id,price FROM market_listings WHERE seller_tg_id=? ORDER BY id DESC",(call.from_user.id,),True)
    lines=["<b>🏷️ Мої продажі</b>",""]
    b=InlineKeyboardBuilder()
    if not rows: lines.append("У тебе немає активних лотів.")
    for r in rows:
        item=ITEMS[r['item_id']]; lines.append(f"#{r['id']} {item['name']} — {r['price']} 🪙"); b.button(text=f"❌ Зняти #{r['id']}",callback_data=f"market_cancel:{r['id']}")
    b.button(text="⬅️ Ринок",callback_data="market"); b.adjust(1)
    await call.message.edit_text("\n".join(lines),reply_markup=b.as_markup()); await call.answer()

@dp.callback_query(F.data.startswith("market_cancel:"))
async def market_cancel(call:CallbackQuery):
    lid=int(call.data.split(":",1)[1]); row=db("SELECT * FROM market_listings WHERE id=? AND seller_tg_id=?",(lid,call.from_user.id),True)
    if not row: await call.answer("❌ Лот не знайдено.",show_alert=True); return
    r=row[0]; add_item(call.from_user.id,r['item_id']); db("DELETE FROM market_listings WHERE id=?",(lid,)); await call.message.edit_text("✅ Лот знято, предмет повернуто в інвентар.",reply_markup=market_kb()); await call.answer()

@dp.callback_query(F.data.startswith("market_buy:"))
async def market_buy(call:CallbackQuery):
    u=ensure_user(call.from_user); lid=int(call.data.split(":",1)[1])
    try:
        conn.execute("BEGIN IMMEDIATE")
        listing=conn.execute("SELECT seller_tg_id,item_id,price FROM market_listings WHERE id=?",(lid,)).fetchone()
        if not listing: raise ValueError("gone")
        if listing[0]==u['tg_id']: raise ValueError("self")
        buyer=conn.execute("SELECT coins FROM users WHERE tg_id=?",(u['tg_id'],)).fetchone()
        if not buyer or buyer[0]<listing[2]: raise ValueError("money")
        conn.execute("UPDATE users SET coins=coins-? WHERE tg_id=?",(listing[2],u['tg_id']))
        conn.execute("UPDATE users SET coins=coins+?,total_earned=total_earned+? WHERE tg_id=?",(listing[2],listing[2],listing[0]))
        conn.execute("INSERT INTO inventory(tg_id,item_id,amount) VALUES(?,?,1) ON CONFLICT(tg_id,item_id) DO UPDATE SET amount=amount+1",(u['tg_id'],listing[1]))
        conn.execute("DELETE FROM market_listings WHERE id=?",(lid,)); conn.commit()
    except Exception:
        try: conn.rollback()
        except Exception: pass
        await call.answer("❌ Лот уже продано або недостатньо Coins.",show_alert=True); return
    item=ITEMS[listing[1]]; await call.message.edit_text(f"🛒 <b>Куплено!</b>\n\n{item['name']}\n💰 -{listing[2]} 🪙",reply_markup=market_kb()); await call.answer()

# ---------------- DAILY / TOP / STATS ----------------
@dp.callback_query(F.data=="daily")
async def daily(call:CallbackQuery):
    u=ensure_user(call.from_user); now=now_ts(); left=DAILY_COOLDOWN-(now-u['daily_at'])
    if left>0:
        h=left//3600; m=(left%3600)//60; text=f"<b>🎁 Щоденний бонус</b>\n\n⏳ Наступний бонус через <b>{h}г {m}хв</b>."
    else:
        reward=random.randint(150,300); db("UPDATE users SET coins=coins+?,daily_at=? WHERE tg_id=?",(reward,now,u['tg_id'])); text=f"<b>🎁 Бонус отримано!</b>\n\n+{reward} 🪙"
    b=InlineKeyboardBuilder(); b.button(text="⬅️ Меню",callback_data="menu"); await call.message.edit_text(text,reply_markup=b.as_markup()); await call.answer()

@dp.callback_query(F.data=="top")
async def top(call:CallbackQuery):
    rows=db("SELECT first_name,block_id,coins,gold FROM users ORDER BY coins DESC LIMIT 10",fetch=True); lines=["<b>🏆 Топ BlockDrop</b>",""]
    for i,r in enumerate(rows,1): lines.append(f"<b>{i}.</b> {escape(r['first_name'] or r['block_id'])} — {r['coins']:,} 🪙 • {r['gold']} 🟡".replace(","," "))
    await call.message.edit_text("\n".join(lines),reply_markup=menu_back()); await call.answer()

@dp.callback_query(F.data=="stats")
async def stats(call:CallbackQuery):
    u=ensure_user(call.from_user); total=db("SELECT COUNT(*) c FROM users",fetch=True)[0]['c']; cases=db("SELECT COALESCE(SUM(cases_opened),0) c FROM users",fetch=True)[0]['c']
    await call.message.edit_text(f"<b>📊 Статистика</b>\n\n👥 Гравців: <b>{total}</b>\n🎁 Кейсів відкрито: <b>{cases}</b>\n💰 Зароблено тобою: <b>{u['total_earned']}</b> 🪙\n🏷️ Продано NPC: <b>{u['total_sold']}</b> 🪙",reply_markup=menu_back()); await call.answer()

@dp.callback_query(F.data=="achievements")
async def achievements(call:CallbackQuery):
    u=ensure_user(call.from_user); cases=u['cases_opened']; sold=u['total_sold']; lines=["<b>🏆 Досягнення</b>",""]
    for need,label,kind in [(3,"🎁 Новачок кейсів",cases),(25,"🎁 Колекціонер",cases),(100,"🎁 Майстер кейсів",cases),(1000,"💰 Великий продавець",sold)]:
        lines.append(f"{'✅' if kind>=need else '⬜'} {label} — {kind}/{need}")
    await call.message.edit_text("\n".join(lines),reply_markup=profile_kb()); await call.answer()

# ---------------- TASKS ----------------
@dp.callback_query(F.data=="tasks")
async def tasks(call:CallbackQuery):
    u=ensure_user(call.from_user); ensure_daily_tasks(u['tg_id']); rows=db("SELECT * FROM tasks WHERE tg_id=? ORDER BY id",(u['tg_id'],),True)
    labels={k:t for k,t,_,_ in TASK_DEFS}; lines=["<b>📋 Щоденні завдання</b>",f"📅 {today_key()}",""]; b=InlineKeyboardBuilder()
    for r in rows:
        status="✅ Виконано" if r['claimed'] else ("🎁 Забрати" if r['progress']>=r['target'] else "⏳")
        lines.append(f"{labels.get(r['task_key'],r['task_key'])}\n<b>{min(r['progress'],r['target'])}/{r['target']}</b> • +{r['reward_gold']} 🟡 • {status}")
        if not r['claimed'] and r['progress']>=r['target']: b.button(text=f"🎁 Забрати +{r['reward_gold']} Gold",callback_data=f"claimtask:{r['id']}")
    b.button(text="🔄 Оновити",callback_data="tasks"); b.button(text="⬅️ Меню",callback_data="menu"); b.adjust(1)
    await call.message.edit_text("\n\n".join(lines),reply_markup=b.as_markup()); await call.answer()

@dp.callback_query(F.data.startswith("claimtask:"))
async def claimtask(call:CallbackQuery):
    tid=int(call.data.split(":",1)[1]); row=db("SELECT * FROM tasks WHERE id=? AND tg_id=?",(tid,call.from_user.id),True)
    if not row or row[0]['claimed'] or row[0]['progress']<row[0]['target']: await call.answer("❌ Ще не виконано.",show_alert=True); return
    db("UPDATE tasks SET claimed=1 WHERE id=?",(tid,)); add_gold(call.from_user.id,row[0]['reward_gold']); await call.answer(f"+{row[0]['reward_gold']} Gold!"); await tasks(call)

# ---------------- PROMOS ----------------
@dp.callback_query(F.data=="promo_help")
async def promo_help(call:CallbackQuery):
    await call.message.edit_text("<b>🎟️ Промокоди</b>\n\nАктивувати: <code>/promo CODE</code>\nСтворити свій: <code>/createpromo CODE USES REWARD</code>\n\nСтворення коштує 50 🪙 + резерв нагороди.",reply_markup=menu_back()); await call.answer()

@dp.message(Command("promo"))
async def promo(message:Message):
    u=ensure_user(message.from_user); parts=message.text.split(maxsplit=1)
    if len(parts)<2: await message.answer("Використання: /promo CODE"); return
    code=parts[1].strip().upper()
    try:
        conn.execute("BEGIN IMMEDIATE"); p=conn.execute("SELECT * FROM promo_codes WHERE code=?",(code,)).fetchone()
        if not p: raise ValueError("notfound")
        if p['uses']>=p['max_uses']: raise ValueError("limit")
        if conn.execute("SELECT 1 FROM promo_used WHERE tg_id=? AND code=?",(u['tg_id'],code)).fetchone(): raise ValueError("used")
        conn.execute("INSERT INTO promo_used(tg_id,code) VALUES(?,?)",(u['tg_id'],code)); conn.execute("UPDATE promo_codes SET uses=uses+1 WHERE code=?",(code,))
        conn.execute("UPDATE users SET coins=coins+?,gold=gold+?,halloween_coins=halloween_coins+? WHERE tg_id=?",(p['coins'],p['gold'],p['halloween_coins'],u['tg_id']))
        if p['item_id'] and p['item_id'] in ITEMS: conn.execute("INSERT INTO inventory(tg_id,item_id,amount) VALUES(?,?,1) ON CONFLICT(tg_id,item_id) DO UPDATE SET amount=amount+1",(u['tg_id'],p['item_id']))
        conn.commit()
    except ValueError as e:
        try: conn.rollback()
        except Exception: pass
        msgs={"notfound":"❌ Промокод не існує.","limit":"❌ Ліміт використань вичерпано.","used":"❌ Ти вже використовував цей промокод."}; await message.answer(msgs.get(str(e),"❌ Помилка.")); return
    except Exception:
        try: conn.rollback()
        except Exception: pass
        await message.answer("❌ Не вдалося активувати промокод."); return
    rewards=[]
    if p['coins']: rewards.append(f"+{p['coins']} 🪙")
    if p['gold']: rewards.append(f"+{p['gold']} 🟡")
    if p['halloween_coins']: rewards.append(f"+{p['halloween_coins']} 🎃")
    if p['item_id'] and p['item_id'] in ITEMS: rewards.append(f"+{ITEMS[p['item_id']]['name']}")
    await message.answer("🎟️ <b>Промокод активовано!</b>\n\n"+"\n".join(rewards))

from aiogram import F
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message

STAR_PRICE = 15
PREMIUM_ITEM_ID = "royal_blade"

# Кнопка/обробник покупки
@dp.callback_query(F.data == "buy_premium")
async def buy_premium(call: CallbackQuery):
    await call.message.answer_invoice(
        title="⭐ Premium Item",
        description="💎 Royal Blade — MYTHIC",
        payload=f"premium:{call.from_user.id}:{PREMIUM_ITEM_ID}",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Premium Item",
                amount=STAR_PRICE
            )
        ],
    )
    await call.answer()


# Telegram питає: чи можна провести оплату?
@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


# Оплата успішна
@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment

    if not payment.invoice_payload.startswith("premium:"):
        return

    user_id = message.from_user.id

    # Тут твоя функція додавання предмета в інвентар
    add_item_to_inventory(
        user_id=user_id,
        item_id=PREMIUM_ITEM_ID
    )

    await message.answer(
        "✅ Оплата успішна!\n\n"
        "Ти отримав:\n"
        "💎 Royal Blade\n"
        "🔴 MYTHIC"
    )

@dp.message(Command("createpromo"))
async def createpromo(message:Message):
    u=ensure_user(message.from_user); p=message.text.split()
    if len(p)!=4: await message.answer("Формат: /createpromo CODE USES REWARD\nПриклад: /createpromo TEST 3 100"); return
    code=p[1].upper()
    try: uses,reward=int(p[2]),int(p[3])
    except ValueError: await message.answer("❌ USES і REWARD мають бути числами."); return
    if not re.fullmatch(r"[A-Z0-9_]{3,24}",code) or not 1<=uses<=1000 or not 1<=reward<=1000000: await message.answer("❌ Невірні параметри."); return
    reserve=PROMO_CREATE_FEE+uses*reward
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM promo_codes WHERE code=?",(code,)).fetchone(): raise ValueError("exists")
        bal=conn.execute("SELECT coins FROM users WHERE tg_id=?",(u['tg_id'],)).fetchone()
        if bal[0]<reserve: raise ValueError("money")
        conn.execute("UPDATE users SET coins=coins-? WHERE tg_id=?",(reserve,u['tg_id']))
        conn.execute("INSERT INTO promo_codes(code,coins,max_uses,uses,creator_tg_id) VALUES(?,?,?,?,?)",(code,reward,uses,0,u['tg_id'])); conn.commit()
    except ValueError as e:
        try: conn.rollback()
        except Exception: pass
        await message.answer("❌ Такий код уже існує." if str(e)=="exists" else f"❌ Потрібно {reserve} 🪙 (50 комісія + резерв нагород).")
        return
    await message.answer(f"✅ Промокод <code>{code}</code> створено!\n\n🎟️ Активацій: {uses}\n🎁 Нагорода: {reward} 🪙\n💸 Списано: {reserve} 🪙")

# ---------------- HALLOWEEN ----------------
@dp.callback_query(F.data=="halloween")
async def halloween(call:CallbackQuery):
    if not is_halloween(): text="<b>🎃 Halloween</b>\n\nПодія автоматично активується 1 жовтня і триває весь жовтень."
    else: text="<b>🎃 Halloween АКТИВНИЙ!</b>\n\nСпеціальний Halloween Box доступний у Магазині."
    b=InlineKeyboardBuilder(); b.button(text="🎁 Відкрити Halloween Box",callback_data="case:halloween"); b.button(text="⬅️ Меню",callback_data="menu"); b.adjust(1)
    await call.message.edit_text(text,reply_markup=b.as_markup()); await call.answer()

# ---------------- ADMIN ----------------

def admin_only(tg_id): return tg_id in ADMIN_IDS

@dp.message(Command("admin"))
async def admin(message:Message):
    if not admin_only(message.from_user.id): await message.answer("⛔ Доступ заборонено."); return
    users=db("SELECT COUNT(*) c FROM users",fetch=True)[0]['c']; cases=db("SELECT COALESCE(SUM(cases_opened),0) c FROM users",fetch=True)[0]['c']
    await message.answer(f"<b>🛠️ Admin</b>\n\n👥 Гравців: {users}\n🎁 Відкрито кейсів: {cases}\n\n/give ID AMOUNT\n/giveitem ID ITEM AMOUNT\n/user ID")

@dp.message(Command("give"))
async def give(message:Message):
    if not admin_only(message.from_user.id): return
    p=message.text.split(); target=db("SELECT * FROM users WHERE block_id=?",(p[1].upper(),),True) if len(p)==3 else []
    try: amount=int(p[2])
    except (ValueError,IndexError): amount=0
    if not target or amount<=0: await message.answer("Формат: /give BLOCKDROP_ID AMOUNT"); return
    add_coins(target[0]['tg_id'],amount); await message.answer("✅ Видано.")

@dp.message(Command("giveitem"))
async def giveitem(message:Message):
    if not admin_only(message.from_user.id): return
    p=message.text.split(); target=db("SELECT * FROM users WHERE block_id=?",(p[1].upper(),),True) if len(p)==4 else []
    try: amount=int(p[3])
    except (ValueError,IndexError): amount=0
    if not target or p[2] not in ITEMS or amount<=0: await message.answer("Формат: /giveitem BLOCKDROP_ID ITEM_ID AMOUNT"); return
    add_item(target[0]['tg_id'],p[2],amount); await message.answer(f"✅ Видано {ITEMS[p[2]]['name']} × {amount}.")

@dp.message(Command("user"))
async def admin_user(message:Message):
    if not admin_only(message.from_user.id): return
    p=message.text.split(maxsplit=1)
    if len(p)!=2: await message.answer("Формат: /user BLOCKDROP_ID"); return
    r=db("SELECT * FROM users WHERE block_id=?",(p[1].upper(),),True)
    if not r: await message.answer("❌ Не знайдено."); return
    u=r[0]; await message.answer(f"<b>👤 {u['block_id']}</b>\nTG: <code>{u['tg_id']}</code>\n💰 {u['coins']} 🪙\n🟡 {u['gold']} Gold\n🎁 Кейсів: {u['cases_opened']}\n🎒 Інвентар: {inventory_value(u['tg_id'])} 🪙")


def menu_back():
    b=InlineKeyboardBuilder(); b.button(text="⬅️ Меню",callback_data="menu"); return b.as_markup()

@dp.callback_query(F.data=="menu")
async def cb_menu(call:CallbackQuery):
    u=ensure_user(call.from_user); await call.message.edit_text(main_text(u),reply_markup=menu_kb()); await call.answer()

# Unknown text: keep bot friendly.
@dp.message(F.text)
async def unknown(message:Message):
    if message.text.startswith("/"): return
    await message.answer("Обери розділ кнопками нижче 👇",reply_markup=menu_kb())

# ============================================================
# RENDER WEBHOOK
# ============================================================
async def handle_webhook(request:web.Request):
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return web.Response(status=403,text="Forbidden")
    try:
        data=await request.json()
        update=Update.model_validate(data,context={"bot":bot})
        await dp.feed_update(bot,update)
        return web.Response(text="ok")
    except Exception as exc:
        print("[BlockDrop] webhook error:",repr(exc))
        return web.Response(status=400,text="Bad Request")

async def health(request:web.Request): return web.Response(text="BlockDrop OK")

async def on_startup(app:web.Application):
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL+"/telegram",secret_token=WEBHOOK_SECRET,drop_pending_updates=True)
        print("[BlockDrop] Webhook:",WEBHOOK_URL+"/telegram")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        print("[BlockDrop] WEBHOOK_URL is empty; use webhook URL on Render or run with polling locally.")

async def on_cleanup(app:web.Application):
    try: await bot.session.close()
    except Exception: pass

async def main():
    if BOT_TOKEN=="PASTE_YOUR_BOT_TOKEN_HERE": raise RuntimeError("Встанови BOT_TOKEN у Render Environment Variables.")
    app=web.Application(); app.router.add_get("/",health); app.router.add_get("/health",health); app.router.add_post("/telegram",handle_webhook)
    app.on_startup.append(on_startup); app.on_cleanup.append(on_cleanup)
    runner=web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner,"0.0.0.0",PORT); await site.start()
    print(f"[BlockDrop] HTTP server started on :{PORT}")
    while True: await asyncio.sleep(3600)

if __name__=="__main__": asyncio.run(main())

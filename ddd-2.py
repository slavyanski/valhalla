import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8515473614:AAEpds0dJQ1XGwi7UY5rEwup1Sq-SX8e85g'
OWNER_ID = 1889889051 
CHAT_LINK = "https://t.me/+N7eMd_R5tUFiNDQy"
DB_NAME = "valhalla_data.db"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class WhitelistForm(StatesGroup):
    nickname, age, experience, rules, plans = State(), State(), State(), State(), State()
    broadcast_message = State()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
        await db.commit()
        
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
        await db.commit()

async def is_admin(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

# --- КОМАНДЫ ДЛЯ ВЛАДЕЛЬЦА ---

@dp.message(Command("add_admin"))
async def add_admin(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    try:
        new_id = int(message.text.split()[1])
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,))
            await db.commit()
        await message.answer(f"✅ Пользователь {new_id} назначен администратором.")
    except:
        await message.answer("Используйте: `/add_admin ID`")

@dp.message(Command("remove_admin"))
async def remove_admin(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    try:
        rem_id = int(message.text.split()[1])
        if rem_id == OWNER_ID: return await message.answer("Нельзя удалить владельца.")
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM admins WHERE user_id = ?", (rem_id,))
            await db.commit()
        await message.answer(f"✅ Пользователь {rem_id} удален из админов.")
    except:
        await message.answer("Используйте: `/remove_admin ID`")

# --- ПРОЦЕСС АНКЕТЫ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        await db.commit()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Подать заявку")]], resize_keyboard=True)
    await message.answer("Привет! Это бот сервера Valhalla. Заполни анкету, чтобы попасть в вайтлист.", reply_markup=kb)

@dp.message(F.text == "Подать заявку")
async def start_survey(message: types.Message, state: FSMContext):
    await state.set_state(WhitelistForm.nickname)
    await message.answer("1. Ваш никнейм:", reply_markup=ReplyKeyboardRemove())

@dp.message(WhitelistForm.nickname)
async def step1(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await state.set_state(WhitelistForm.age); await message.answer("2. Ваш возраст:")

@dp.message(WhitelistForm.age)
async def step2(message: types.Message, state: FSMContext):
    await state.update_data(age=message.text)
    await state.set_state(WhitelistForm.experience); await message.answer("3. Какой ваш опыт игры?")

@dp.message(WhitelistForm.experience)
async def step3(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await state.set_state(WhitelistForm.rules)
    await message.answer("4. Ознакомлены ли вы с правилами?")

@dp.message(WhitelistForm.rules)
async def step4(message: types.Message, state: FSMContext):
    await state.update_data(rules=message.text)
    await state.set_state(WhitelistForm.plans); await message.answer("5. Ваши планы (2-3 предложения):")

@dp.message(WhitelistForm.plans)
async def step5(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = (f"📝 **Новая заявка!**\nОт: @{message.from_user.username} (ID: {message.from_user.id})\n\n"
            f"1. Ник: {data['nickname']}\n2. Возраст: {data['age']}\n3. Опыт: {data['experience']}\n"
            f"4. Правила: {data['rules']}\n5. Планы: {message.text}")
    
    # Отправка всем админам из БД
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM admins") as cur:
            admins = await cur.fetchall()
            for (adm_id,) in admins:
                try: await bot.send_message(adm_id, text)
                except: pass

    await message.answer(f"✅ Заявка отправлена! Вступайте в чат: {CHAT_LINK}")
    await state.clear()

# --- РАССЫЛКА ДЛЯ АДМИНОВ ---

@dp.message(Command("broadcast"))
async def start_broadcast(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await state.set_state(WhitelistForm.broadcast_message)
    await message.answer("📢 Введите сообщение для рассылки всем игрокам:")

@dp.message(WhitelistForm.broadcast_message)
async def do_broadcast(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()
            for (u_id,) in users:
                try: await bot.send_message(u_id, message.text); await asyncio.sleep(0.05)
                except: pass
    await message.answer("✅ Рассылка завершена.")
    await state.clear()

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


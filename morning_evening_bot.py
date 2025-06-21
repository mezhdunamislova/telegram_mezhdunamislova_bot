# morning_evening_bot.py

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
import asyncio
import json
import pytz
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

API_TOKEN = os.getenv('API_TOKEN')  # Bot token from BotFather

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
scheduler = AsyncIOScheduler()
scheduler.start()

user_data_file = 'users.json'

class Form(StatesGroup):
    character = State()
    age = State()
    nicknames = State()
    timezone = State()
    style = State()
    schedule = State()

CHARACTERS = ["Мама", "Папа", "Любимая женщина", "Любимый мужчина", "Подруга", "Друг", "Бабушка", "Дедушка"]
STYLES = ["Заботливый", "Романтичный", "Дружеский / весёлый", "Нейтральный"]
TIMES = ["Только утром", "Только вечером", "И утром, и вечером"]

def load_users():
    try:
        with open(user_data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(data):
    with open(user_data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def cmd_start(message: types.Message):
    await message.answer("Привет! 💌 Давай начнём. От кого ты хочешь получать пожелания? (Выбери одного)")
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for ch in CHARACTERS:
        kb.add(KeyboardButton(ch))
    await Form.character.set()
    await message.answer("Выбери из списка:", reply_markup=kb)

@dp.message_handler(commands='start')
async def start_bot(message: types.Message):
    await cmd_start(message)

@dp.message_handler(state=Form.character)
async def set_character(message: types.Message, state: FSMContext):
    if message.text not in CHARACTERS:
        return await message.reply("Пожалуйста, выбери из списка")
    await state.update_data(character=message.text)
    await Form.next()
    await message.answer("Сколько лет этому человеку?")

@dp.message_handler(state=Form.age)
async def set_age(message: types.Message, state: FSMContext):
    await state.update_data(age=message.text)
    await Form.next()
    await message.answer("Как он(а) тебя обычно называет? (Можно через запятую)")

@dp.message_handler(state=Form.nicknames)
async def set_nicknames(message: types.Message, state: FSMContext):
    nicks = [n.strip() for n in message.text.split(',') if n.strip()]
    await state.update_data(nicknames=nicks)
    await Form.next()
    await message.answer("В каком городе ты живёшь (для определения часового пояса)?")

@dp.message_handler(state=Form.timezone)
async def set_timezone(message: types.Message, state: FSMContext):
    await state.update_data(timezone=message.text)
    await Form.next()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for s in STYLES:
        kb.add(KeyboardButton(s))
    await message.answer("Выбери стиль сообщений:", reply_markup=kb)

@dp.message_handler(state=Form.style)
async def set_style(message: types.Message, state: FSMContext):
    if message.text not in STYLES:
        return await message.reply("Выбери стиль из предложенных")
    await state.update_data(style=message.text)
    await Form.next()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for t in TIMES:
        kb.add(KeyboardButton(t))
    await message.answer("Когда ты хочешь получать сообщения?", reply_markup=kb)

@dp.message_handler(state=Form.schedule)
async def set_schedule(message: types.Message, state: FSMContext):
    if message.text not in TIMES:
        return await message.reply("Выбери один из предложенных вариантов")
    data = await state.get_data()
    user_id = str(message.from_user.id)
    users = load_users()
    data['schedule'] = message.text
    users[user_id] = data
    save_users(users)
    await message.answer("Спасибо! Всё сохранено 💌 Теперь я буду писать тебе ежедневно")
    await state.finish()

def generate_message(info, evening=False):
    nick = info['nicknames'][0] if info['nicknames'] else 'дорогой'
    character = info['character']
    if evening:
        # Evening variants
        return {
            'Мама': f"Спокойной ночи, {nick}! Мамочка рядом в мыслях.",
            'Папа': f"Спокойной ночи, {nick}. Папа уверен – всё будет хорошо.",
            'Любимый мужчина': f"Спи сладко, {nick} 😘 Я рядом.",
            'Любимая женщина': f"Спокойной ночи, моя нежная {nick}.",
            'Подруга': f"Сладких снов, {nick}! Завтра продолжим веселье.",
            'Друг': f"Добрых снов, {nick}. Завтра снова в бой.",
            'Бабушка': f"Спи спокойно, внук. Бабуля любит.",
            'Дедушка': f"Спокойной ночи, внучек. Дедушка рядом."
        }.get(character, f"Спокойной ночи, {nick}!")

    return {
        'Мама': f"Доброе утро, {nick}! Мамочка желает тебе чудесного дня.",
        'Папа': f"Доброе утро, {nick}. Папа гордится тобой!",
        'Любимый мужчина': f"Доброе утро, {nick} 😘 Я скучаю.",
        'Любимая женщина': f"Доброе утро, моя {nick}! Ты лучшая.",
        'Подруга': f"Привет, {nick}! Давай зажжём этот день.",
        'Друг': f"Доброе утро, {nick}! Вперёд к приключениям.",
        'Бабушка': f"Доброе утро, {nick}. Бабуля обнимает.",
        'Дедушка': f"Доброе утро, {nick}. Дедушка желает хорошего дня."
    }.get(character, f"Доброе утро, {nick}!")

async def send_daily_messages():
    users = load_users()
    for user_id, info in users.items():
        tz = info.get('timezone', 'Europe/Moscow')
        try:
            now = datetime.now(pytz.timezone(tz))
        except:
            now = datetime.now()
        hour = now.hour
        # Morning at 08:00, Evening at 20:00
        if info['schedule'] in ["Только утром", "И утром, и вечером"] and hour == 8:
            await bot.send_message(user_id, generate_message(info, evening=False))
        if info['schedule'] in ["Только вечером", "И утром, и вечером"] and hour == 20:
            await bot.send_message(user_id, generate_message(info, evening=True))

scheduler.add_job(send_daily_messages, 'cron', minute=0)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters.command import Command
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from aiogram_dialog import setup_dialogs
from redis.asyncio.client import Redis

import settings
from routers import admin, student, tutor
from shared import Role, format_symbols, get_role, get_timetable
from utils import compare_date_str_to_now


async def register_chat(message: types.Message):
    '''регистрация пользователя в боте'''
    role = await get_role(message, True)
    if role:
        await message.answer("Привет👋! Я бот для интенсивного <b><i>Курса по Фигме</i></b>🔥!", parse_mode=ParseMode.HTML)
        await message.answer_sticker(sticker='CAACAgIAAxkBAAIFG2aNBoXibOmgdbZig7Kmjjl9uB1NAALyEgAC8aOgSNoW844h2hMwNQQ')
    else:
        return

    if role == Role.STUDENT.value:
        await message.answer("Ты успешно зарегистрировался на курс🤩! "
                             "В процессе курса ты будешь кидать мне домашки)\n\n"
                             "А вот список полезных команд:\n"
                             "/help - список команд❓\n"
                             "/faq - ответы на частые вопросы❗️\n"
                             "/timetable - дедлайны домашек🕔\n"
                             "/sendhw - твоя <b>самая важная команда</b>, когда придёт время <b>сдавать дз</b>☺️\n"
                             "/leave - исключить себя из курса⚠️",
                             parse_mode=ParseMode.HTML)
        await message.answer(f"Также не забывай, что вся информация по курсу будет выкладываться "
                             f'в <a href="{settings.CHANNEL_LINK}">канале</a>! А в <a href="{settings.CHAT_LINK}">чате</a> '
                             f"можно задавать свои вопросы и общаться😁", parse_mode=ParseMode.HTML)
    elif role == Role.TUTOR.value:
        await message.answer("Твоя роль на курсе: <b>ментор</b>🤓\n\n"
                             "Список команд:\n"
                             "/help - список команд❓\n"
                             "/timetable - дедлайны домашек🕔\n"
                             "/students - получить свой список участников, чьи дз ты будешь проверять\n"
                             "/checkhw - <b>основная команда для проверки дз</b>✅\n"
                             "/statistics <i>&lt;число&gt;</i> - получить некоторое число (не больше 20) "
                             "своих лучших участников (учитываются только проверенные дз)\n"
                             "/expel - исключить участника из курса⚠️\n\n"
                             f'Гугл таблица с оценками и данными всех участников курса: <a href="{settings.TABLE_LINK}">тык</a>',
                             parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    elif role == Role.ADMIN.value:
        await message.answer("Твоя роль на курсе: <b>админ</b>.", parse_mode=ParseMode.HTML)
    elif role is not None:
        await message.answer(f"Ты зарегистрирован, но я всё равно тебя не узнаю😳. Напиши, пожалуйста {settings.ADMIN}.")


async def get_help(message: types.Message):
    role = await get_role(message)
    if role == Role.STUDENT.value:
        await message.answer("/help - список команд❓\n"
                             "/faq - ответы на частые вопросы❗️\n"
                             "/timetable - дедлайны домашек🕔\n"
                             "/sendhw - твоя <b>самая важная команда</b>, когда придёт время <b>сдавать дз</b>☺️\n"
                             "/leave - исключить себя из курса⚠️",
                             parse_mode=ParseMode.HTML)
    elif role == Role.TUTOR.value:
        await message.answer("/help - список команд\n"
                             "/timetable - дедлайны домашек\n"
                             "/students - получить свой список участников, чьи дз ты будешь проверять\n"
                             "/checkhw - <b>основная команда для проверки дз</b>\n"
                             "/statistics <i>&lt;число&gt;</i> - получить некоторое число (не больше 20) "
                             "своих лучших участников (учитываются только проверенные дз)\n"
                             "/expel - исключить участника из курса⚠️\n",
                             parse_mode=ParseMode.HTML)
    elif role == Role.ADMIN.value:
        await message.answer("Твоя роль на курсе: <b>админ</b>.", parse_mode=ParseMode.HTML)
    elif role is not None:
        await message.answer(f"Ты зарегистрирован, но я не понимаю кто ты😳. Напиши, пожалуйста {settings.ADMIN}.")


async def get_whoami(message: types.Message):
    role = await get_role(message)
    if role == Role.ADMIN.value:
        await message.answer("<b>админ</b>", parse_mode=ParseMode.HTML)
    elif role == Role.TUTOR.value:
        await message.answer("<b>ментор</b>", parse_mode=ParseMode.HTML)
    elif role == Role.STUDENT.value:
        await message.answer("<b>студент</b>", parse_mode=ParseMode.HTML)
    elif role is not None:
        await message.answer(f"Ты зарегистрирован, но я не понимаю кто ты😳. Напиши, пожалуйста {settings.ADMIN}.")


async def get_faq(message: types.Message):
    await message.answer(settings.FAQ_URL)


async def get_curs_progress(message: types.Message):
    role = await get_role(message)
    if role is None:
        return

    tasks = await get_timetable(message)
    if tasks is None:
        return

    timetable = []
    for task in tasks:
        if compare_date_str_to_now(task['start_date']) <= 0:
            start_date = datetime.strptime(task['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(task['end_date'], '%Y-%m-%d')
            timetable.append(f"{format_symbols[task['id']]}: с {start_date.month:02}.{start_date.day:02} "
                             f"по {end_date.month:02}.{end_date.day:02}")
    await message.answer("Расписание домашек🕔\n\n" + '\n'.join(timetable))


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )
    bot = Bot(token=settings.TOCKEN)

    storage = RedisStorage(
        Redis.from_url(url=settings.REDIS_URL),
        key_builder=DefaultKeyBuilder(with_destiny=True),
    )
    dp = Dispatcher(storage=storage)

    dp.message.register(register_chat, Command("start"))
    dp.message.register(get_help, Command("help"))
    dp.message.register(get_whoami, Command("whoami"))
    dp.message.register(get_faq, Command("faq"))
    dp.message.register(get_curs_progress, Command("timetable"))

    dp.include_routers(admin.router, student.router, tutor.router)
    setup_dialogs(dp)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

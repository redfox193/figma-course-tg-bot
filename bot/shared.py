import logging
from enum import Enum
from typing import Any, Awaitable, Callable, Dict

import pytz
import requests
from aiogram import BaseMiddleware, types
from aiogram.types import Message
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from requests import HTTPError
from requests.exceptions import ConnectionError

import settings
from utils import slugify

format_symbols = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    'checked': "проверено ✅",
    'not_checked': "на проверке ❌"
}


class Role(Enum):
    ADMIN = 1
    TUTOR = 2
    STUDENT = 3


async def get_role(message: types.Message, cache=False):
    username = message.from_user.username

    if not cache:
        try:
            redis = Redis.from_url(url=settings.REDIS_URL)
        except RedisConnectionError as error:
            logging.error(error)
        role = redis.get(username)
        redis.close()
        if role:
            return int(role.decode())

    try:
        response = requests.get(settings.BACKEND_URL + f'/{slugify(username)}/whoami')
    except ConnectionError as error:
        logging.error(error)
        await message.answer("Сервер временно недоступен 😔\nНад этим уже работают!\n\nПопробуй ещё раз позже.")
        return None

    if response.status_code == 200:
        try:
            redis = Redis.from_url(url=settings.REDIS_URL)
            redis.set(username, response.json()['role'])
            redis.close()
        except ConnectionError as error:
            logging.error(error)
        return response.json()['role']
    elif response.status_code == 404:
        await message.answer("Не вижу тебя среди участников 😭.\n\n"
                             f"Если ты заполнял гугл форму, то напиши, пожалуйста, {settings.ADMIN}."
                             " Если нет, то, к сожалению, регистрация уже закончилась😢\n\n"
                             f"Если у тебя уже был доступ у боту, значит ты был исключён из курса☹️\n\n"
                             "Ждём тебя в следующем сезоне!")
    else:
        await message.answer(f"Упс, что-то пошло не так😳. Напиши, пожалуйста {settings.ADMIN}.")
    return None


async def get_timetable(message: types.Message):
    try:
        response = requests.get(settings.BACKEND_URL + "/timetable")
        response.raise_for_status()
    except ConnectionError as error:
        logging.error(error)
        await message.answer("Сервер временно недоступен 😔\nНад этим уже работают!\n\nПопробуй ещё раз позже.")
        return None
    except HTTPError as error:
        logging.error(error)
        await message.answer(f"Упс, что-то пошло не так😳. Напиши, пожалуйста {settings.ADMIN}.")
        return None
    return response.json()


class AccessMiddleware(BaseMiddleware):
    def __init__(self, role: Role) -> None:
        self.role = role

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        role_ = await get_role(event)
        if role_ != self.role.value and role_ != Role.ADMIN.value:
            return
        result = await handler(event, data)
        return result

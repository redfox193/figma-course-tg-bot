import asyncio
import logging

import requests
from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters.command import Command, CommandObject
from requests import HTTPError
from requests.exceptions import ConnectionError

import settings
from shared import AccessMiddleware, Role
from utils import del_from_redis, stringify

router = Router()
router.message.middleware(AccessMiddleware(Role.ADMIN))


@router.message(Command("top"))
async def get_top_students(message: types.Message, command: CommandObject):
    '''возвращает определённое кол-во лучших студентов'''
    if command.args is None:
        limit = 5
    else:
        args = command.args.split(" ")
        if len(args) > 1:
            await message.answer("/top <i>&lt;число: от 1 до 20&gt;</i>", parse_mode=ParseMode.HTML)
            return

        limit = args[0]
        try:
            limit = int(limit)
            if limit < 1 or limit > 20:
                raise ValueError
        except ValueError:
            await message.answer("/top <i>&lt;число: от 1 до 20&gt;</i>", parse_mode=ParseMode.HTML)
            return

    try:
        response = requests.get(settings.BACKEND_URL + f"/statistic/{limit}")
        response.raise_for_status()
    except ConnectionError as error:
        logging.error(error)
        await message.answer(f"Сервер временно недоступен 😔\nНапиши {settings.ADMIN}.")
        return
    except HTTPError as error:
        logging.error(error)
        await message.answer(f"Упс, что-то пошло не так😳. Напиши {settings.ADMIN}.")
        return

    statistics = response.json()
    students_statistics = []
    num = 1
    for statistic in statistics:
        if statistic['passed'] == -1:
            students_statistics.append(f"<b>{num}.</b> @{stringify(statistic['username'])}: "
                                       f"<i>сдано</i>: <b>0</b>, "
                                       f"<i>ср.балл</i>: <b>0.0</b>, "
                                       f"<i>проект</i>: ❌")
        else:
            project = f"{statistic['project']}✅" if statistic['project'] is not None else "❌"
            students_statistics.append(f"<b>{num}.</b> @{stringify(statistic['username'])}: "
                                       f"<i>сдано</i>: <b>{statistic['passed']}/{settings.TASKS}</b>, "
                                       f"<i>ср.балл</i>: <b>{round(statistic['average'], 1)}</b>, "
                                       f"<i>проект</i>: <b>{project}</b>")
        num += 1

    await message.answer("🏅 Рейтинг лучших участников курса.\n\n"
                         "Сортировка по кол-ву <b>проверенных</b> домашек, затем по среднему баллу.\n\n" +
                         '\n'.join(students_statistics), parse_mode=ParseMode.HTML)


@router.message(Command("delete"))
async def delete_student(message: types.Message, command: CommandObject):
    if command.args is None:
        await message.answer("/delete <i>&lt;username&gt;</i>", parse_mode=ParseMode.HTML)
        return

    username = command.args.split(" ")[0]

    try:
        response = requests.delete(settings.BACKEND_URL + f"/delmember/{stringify(username)}")
        response.raise_for_status()
    except ConnectionError as error:
        logging.error(error)
        await message.answer(f"Сервер временно недоступен 😔\nНапиши {settings.ADMIN}.")
        return
    except HTTPError as error:
        if error.response.status_code == 404:
            await message.answer(f"Не вижу такого участника🤨")
        else:
            logging.error(error)
            await message.answer(f"Упс, что-то пошло не так😳. Напиши {settings.ADMIN}.")
        return

    del_from_redis(username)
    await message.answer(f"Участник <b>@{username}</b> успешно исключён.", parse_mode=ParseMode.HTML)

import logging
import re
from typing import Any

import requests
from aiogram import Bot, Router, types
from aiogram.dispatcher.middlewares.user_context import EventContext
from aiogram.enums import ParseMode
from aiogram.filters.command import Command, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import Dialog, DialogManager, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (Back, Button, Cancel, Column, Row,
                                        ScrollingGroup, Select, Url)
from aiogram_dialog.widgets.text import Const, Format
from requests import HTTPError
from requests.exceptions import ConnectionError

import settings
from shared import AccessMiddleware, Role, format_symbols
from utils import del_from_redis, slugify, stringify

router = Router()
router.message.middleware(AccessMiddleware(role=Role.TUTOR))


class CheckHw(StatesGroup):
    view_students = State()
    homeworks_list = State()
    students_to_check = State()
    hws_to_check = State()


async def make_request(url, bot: Bot, dialog_manager: DialogManager, event_context: EventContext, data=None):
    try:
        response = requests.get(url, data=data)
        response.raise_for_status()
        return response
    except ConnectionError as error:
        logging.error(error)
        await bot.send_message(chat_id=event_context.chat_id, text="Сервер временно недоступен 😔\n"
                                                                   f"Напиши {settings.ADMIN}.")
        return None
    except HTTPError as error:
        logging.error(error)
        await bot.send_message(chat_id=event_context.chat_id, text=f"Упс, что-то пошло не так😳. "
                                                                   f"Напиши {settings.ADMIN}.")
        await dialog_manager.done()
        return None


async def make_request_(url, message: Message, dialog_manager: DialogManager = None, data=None):
    try:
        response = requests.get(url, data=data)
        response.raise_for_status()
        return response
    except ConnectionError as error:
        logging.error(error)
        await message.answer(f"Сервер временно недоступен 😔\nНапиши {settings.ADMIN}.")
        if dialog_manager:
            await dialog_manager.done()
        return None
    except HTTPError as error:
        logging.error(error)
        await message.answer(f"Упс, что-то пошло не так😳. Напиши {settings.ADMIN}.")
        if dialog_manager:
            await dialog_manager.done()
        return None


def format_hws_info_for_dialog(hws_info: list):
    result = []
    for id_, url, mark in hws_info:
        if url:
            if mark > 0:
                text = f"{format_symbols[id_]} | {format_symbols['checked']} | оценка: {mark}"
            else:
                text = f"{format_symbols[id_]} | {format_symbols['not_checked']}"
        else:
            text = f"{format_symbols[id_]} | не сдано"
            url = "https://www.figma.com/"
        result.append({"text": text, "url": url})
    return {
        'hws_info': result,
    }


async def students_getter(bot: Bot, dialog_manager: DialogManager, event_context: EventContext, **kwargs):
    '''возвращает список всех студентов, числящихся за ментором'''

    tutor_username = event_context.user.username
    response = await make_request(settings.BACKEND_URL + f"/{slugify(tutor_username)}/students", bot, dialog_manager,
                                  event_context)
    if not response:
        return

    students = response.json()
    students_list = []
    for student in students:
        students_list.append(stringify(student['username']))

    return {
        'students_list': students_list
    }


async def homework_to_check_getter(bot: Bot, dialog_manager: DialogManager, event_context: EventContext, **kwargs):
    '''возвращает список студентов для проверки дз вместе с номерами дз, которые у них не проверены'''

    tutor_username = event_context.user.username
    response = await make_request(settings.BACKEND_URL + f"/{slugify(tutor_username)}/groupedhwinfo", bot,
                                  dialog_manager,
                                  event_context)

    tasks = response.json()
    homeworks_to_check = [[i + 1, format_symbols[i + 1], "0🏖"] for i in range(settings.TASKS)]
    for task in tasks:
        if task['kol']:
            homeworks_to_check[task['task_id'] - 1][2] = task['kol']

    return {
        'homeworks_list': homeworks_to_check
    }


async def on_homework_chosen(callback: CallbackQuery, widget: Any, dialog_manager: DialogManager, homework: str):
    dialog_manager.dialog_data['chosen_homework'] = homework
    dialog_manager.dialog_data['chosen_homework_format'] = format_symbols[int(homework)]
    await dialog_manager.switch_to(CheckHw.students_to_check)


async def students_by_hw_getter(bot: Bot, dialog_manager: DialogManager, event_context: EventContext, **kwargs):
    '''возвращает список всех студентов, числящихся за ментором'''

    tutor_username = event_context.user.username
    hw_id = int(dialog_manager.dialog_data['chosen_homework'])
    response = await make_request(settings.BACKEND_URL + f"/{slugify(tutor_username)}/students/{hw_id}", bot,
                                  dialog_manager,
                                  event_context)

    students = response.json()
    students_list = []
    for student in students:
        students_list.append(stringify(student['username']))

    return {
        'students_list': students_list
    }


async def on_student_chosen(callback: CallbackQuery, widget: Any, dialog_manager: DialogManager, student_username: str):
    dialog_manager.dialog_data['chosen_student'] = student_username
    await dialog_manager.switch_to(CheckHw.hws_to_check)


async def chosen_student_hw_getter(bot: Bot, dialog_manager: DialogManager, event_context: EventContext, **kwargs):
    student_username = dialog_manager.dialog_data['chosen_student']  # для запроса в бд
    response = await make_request(settings.BACKEND_URL + f"/{slugify(student_username)}/homeworks", bot, dialog_manager,
                                  event_context)

    homeworks = response.json()
    hws_info = [[i + 1, "", -1] for i in range(settings.TASKS)]
    for homework in homeworks:
        hws_info[homework['task'] - 1][1] = homework['url']
        mark = homework['mark']
        hws_info[homework['task'] - 1][2] = mark if mark is not None else -1

    return format_hws_info_for_dialog(hws_info)


async def check_hw_handler(message: Message, message_input: MessageInput, dialog_manager: DialogManager):
    text = message.text
    send_mark_pattern = r'^(\d+)\s+((10|[0-9](\.\d+)?))$'
    student_username = dialog_manager.dialog_data['chosen_student']

    response = await make_request_(settings.BACKEND_URL + f"/{slugify(student_username)}/homeworks", message,
                                   dialog_manager)
    if not response:
        return

    homeworks = response.json()
    available_homeworks = []
    for homework in homeworks:
        available_homeworks.append(homework['task'])

    match = re.match(send_mark_pattern, text)
    if not match:
        await message.answer("Формат оценки неверен😔.\n\n"
                             "Проверь формат и отправь оценку ещё раз.\n"
                             "Пример сообщения:\n"
                             "<i>3 3.25</i>\n", parse_mode=ParseMode.HTML)
        return

    hw_num = int(match.group(1))
    if hw_num not in available_homeworks:
        await message.answer(f"Формат оценки неверен😔, <b>@{student_username}</b> "
                             f"ещё не сдавал дз {format_symbols[hw_num]}\n\n"
                             "Проверь формат и отправь оценку ещё раз.\n"
                             "Пример сообщения:\n"
                             "<i>3 3.25</i>\n", parse_mode=ParseMode.HTML)
        return

    hw_mark = float(match.group(2))
    if hw_mark < 0 or hw_mark > 10:
        await message.answer(f"Формат оценки неверен😔, значение оценки должно быть от 0 до 10.\n\n"
                             "Проверь формат и отправь оценку ещё раз.\n"
                             "Пример сообщения:\n"
                             "<i>3 3.25</i>\n", parse_mode=ParseMode.HTML)
        return

    try:
        response = requests.put(settings.BACKEND_URL + f"/{slugify(student_username)}/checkhw",
                                data={
                                    "task": hw_num,
                                    "mark": hw_mark
                                })
        response.raise_for_status()
    except ConnectionError as error:
        logging.error(error)
        await message.answer(f"Сервер временно недоступен 😔\nНапиши {settings.ADMIN}.")
        await dialog_manager.done()
        return None
    except HTTPError as error:
        logging.error(error)
        await message.answer(f"Упс, что-то пошло не так😳. Напиши {settings.ADMIN}.")
        await dialog_manager.done()
        return None

    hw_info = response.json()
    await message.answer(f"Дз {format_symbols[hw_info['task']]} от "
                         f"<b>@{stringify(hw_info['username'])}</b> успешно оценено на <b>{hw_info['mark']}</b>🥳\n",
                         parse_mode=ParseMode.HTML)


async def back_from_student_info_button_handler(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    if dialog_manager.dialog_data.get('chosen_homework') is None:
        await dialog_manager.switch_to(CheckHw.view_students)
    else:
        await dialog_manager.switch_to(CheckHw.hws_to_check)


check_hw_dialog = Dialog(
    Window(
        Const("📒 Список студентов\n\n"
              "❗️ Выбрав студента, можно увидеть\n"
              " информацию о его домашках"),

        ScrollingGroup(
            Select(
                Format("{item}"),
                id="all_students",
                item_id_getter=lambda student: student,
                items="students_list",
                on_click=on_student_chosen,
            ),
            id="students_group",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        Cancel(Const("Закончить")),
        state=CheckHw.view_students,
        getter=students_getter
    ),
    Window(
        Const("Выберите номер дз для проверки"),
        Column(
            Select(
                Format("{item[1]}, ждут проверки: {item[2]}"),
                id="homeworks_to_check",
                item_id_getter=lambda homework: homework[0],
                items="homeworks_list",
                on_click=on_homework_chosen,
            )
        ),
        Cancel(Const("Закончить")),
        state=CheckHw.homeworks_list,
        getter=homework_to_check_getter
    ),
    Window(
        Format("Студенты, у которых непроверена домашка {dialog_data[chosen_homework_format]}"),
        ScrollingGroup(
            Select(
                Format("{item}"),
                id="students_by_hw",
                item_id_getter=lambda student: student,
                items="students_list",
                on_click=on_student_chosen,
            ),
            id="students_group_by_hw",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        Row(
            Back(Const("Назад")),
            Cancel(Const("Закончить"))
        ),
        state=CheckHw.students_to_check,
        getter=students_by_hw_getter
    ),
    Window(
        Format("ℹ️ Информация о домашках от <b>@{dialog_data[chosen_student]}</b>\n"
               "Можешь нажимать на кнопки ниже, чтобы просматривать домашки.\n"),
        Const("❗️ <b>Чтобы оценить дз, в <u>следующем сообщении</u> введи оценку в следующем формате</b>:\n"
              "<i>&lt;номер дз&gt; &lt;оценка: от 0 до 10&gt;</i>\n\n"
              "❗️ <b>Оценка может быть дробной.</b>\n"
              "Пример сообщения:\n"
              "<i>3 3.25</i>\n\n"
              "❗️ <b>Также можно переоценить уже проверенную домашку</b>\n"),
        Url(Format("{hws_info[0][text]}"), Format("{hws_info[0][url]}")),
        Url(Format("{hws_info[1][text]}"), Format("{hws_info[1][url]}")),
        Url(Format("{hws_info[2][text]}"), Format("{hws_info[2][url]}")),
        Url(Format("{hws_info[3][text]}"), Format("{hws_info[3][url]}")),
        Url(Format("{hws_info[4][text]}"), Format("{hws_info[4][url]}")),
        Row(
            Button(
                Const("Назад"),
                id="back_button",
                on_click=back_from_student_info_button_handler),
            Cancel(Const("Закончить"))
        ),
        MessageInput(check_hw_handler, content_types=[ContentType.TEXT]),
        state=CheckHw.hws_to_check,
        getter=chosen_student_hw_getter,
        parse_mode=ParseMode.HTML
    ),
)

router.include_router(check_hw_dialog)


class ExpelStates(StatesGroup):
    input = State()
    confirm = State()


async def input_expel_student_handler(message: Message, message_input: MessageInput, dialog_manager: DialogManager):
    student_username = message.text
    dialog_manager.dialog_data["student_to_expel"] = student_username
    await dialog_manager.next()


async def confirm_expel(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    student_username = dialog_manager.dialog_data.get("student_to_expel")
    username = callback.from_user.username
    try:
        response = requests.delete(settings.BACKEND_URL + f"/{slugify(username)}/expel/{stringify(student_username)}")
        response.raise_for_status()
    except ConnectionError as error:
        logging.error(error)
        await callback.message.answer(f"Сервер временно недоступен 😔\nНапиши {settings.ADMIN}.")
        await dialog_manager.done()
        return
    except HTTPError as error:
        if error.response.status_code == 404:
            await callback.message.answer(f"Не вижу у тебя такого участника🤨\n\n"
                                          f"/students")
        else:
            logging.error(error)
            await callback.message.answer(f"Упс, что-то пошло не так😳. Напиши {settings.ADMIN}.")
        await dialog_manager.done()
        return

    del_from_redis(student_username)
    await callback.message.answer(f"Участник <b>@{student_username}</b> успешно исключён.",
                                  parse_mode=ParseMode.HTML)
    await dialog_manager.done()


expel_dialog = Dialog(
    Window(
        Const("⚠️<b>DANGER ZONE</b>⚠️\n\n"
              "Введи имя участника (<u><b>без @</b></u>), которого ты хочешь исключить.\n\n"
              "❗️ <b>Он будет полностью удалён без возможности вернуться.</b>"),
        MessageInput(input_expel_student_handler, content_types=[ContentType.TEXT]),
        parse_mode=ParseMode.HTML,
        state=ExpelStates.input
    ),
    Window(
        Format("Ты точно хочешь исключить этого участника из курса❓\n\n"
               "❗️ <b>Он будет полностью удалён без возможности вернуться.</b>"),
        Button(Const("Да"), id="confirm_yes", on_click=confirm_expel),
        Cancel(Const("Нет")),
        state=ExpelStates.confirm,
        parse_mode=ParseMode.HTML
    )
)

router.include_router(expel_dialog)


@router.message(Command("statistics"))
async def get_statistics(message: types.Message, dialog_manager: DialogManager, command: CommandObject):
    if command.args is None:
        limit = 5
    else:
        args = command.args.split(" ")
        if len(args) > 1:
            await message.answer("/statistics <i>&lt;число: от 1 до 20&gt;</i>", parse_mode=ParseMode.HTML)
            return

        limit = args[0]
        try:
            limit = int(limit)
            if limit < 1 or limit > 20:
                raise ValueError
        except ValueError:
            await message.answer("/statistics <i>&lt;число: от 1 до 20&gt;</i>", parse_mode=ParseMode.HTML)
            return

    tutor_username = message.from_user.username
    response = await make_request_(settings.BACKEND_URL + f"/{slugify(tutor_username)}/statistic/{limit}", message)

    if not response:
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
                                       f"<i>ср.балл</i>: <b>{round(max(statistic['average'], 0.0), 1)}</b>, "
                                       f"<i>проект</i>: <b>{project}</b>")
        num += 1

    await message.answer("🏅 Рейтинг лучших участников.\n\n"
                         "Сортировка по кол-ву <b>проверенных</b> домашек, затем по среднему баллу.\n\n" +
                         '\n'.join(students_statistics) +
                         "\n\n/students - список всех участников", parse_mode=ParseMode.HTML)


@router.message(Command("students"))
async def get_students_list(message: types.Message, dialog_manager: DialogManager):
    await dialog_manager.start(CheckHw.view_students, mode=StartMode.RESET_STACK)


@router.message(Command("checkhw"))
async def start_sending_hw_dialog(message: types.Message, dialog_manager: DialogManager):
    await dialog_manager.start(CheckHw.homeworks_list, mode=StartMode.RESET_STACK)


@router.message(Command("expel"))
async def start_sending_hw_dialog(message: types.Message, dialog_manager: DialogManager, command: CommandObject):
    await dialog_manager.start(ExpelStates.input, mode=StartMode.RESET_STACK)

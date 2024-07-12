import logging
from typing import Any

import requests
from aiogram import Bot, Router, types
from aiogram.dispatcher.middlewares.user_context import EventContext
from aiogram.enums import ParseMode
from aiogram.filters.command import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import Dialog, DialogManager, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Back, Button, Cancel, Row, Select
from aiogram_dialog.widgets.text import Const, Format
from requests import HTTPError
from requests.exceptions import ConnectionError

import settings
from shared import AccessMiddleware, Role
from utils import compare_date_str_to_now, del_from_redis, slugify

router = Router()
router.message.middleware(AccessMiddleware(Role.STUDENT))


class SendHwSG(StatesGroup):
    hw_list = State()
    send_hw = State()


async def hw_list_getter(bot: Bot, event_context: EventContext, dialog_manager: DialogManager, **kwargs):
    '''возвращает кол-во доступных дз для сдачи'''
    try:
        response = requests.get(settings.BACKEND_URL + "/timetable")
        response.raise_for_status()
    except ConnectionError as error:
        logging.error(error)
        await bot.send_message(chat_id=event_context.chat_id, text="Сервер временно недоступен 😔\n"
                                                                   "Над этим уже работают!\n\nПопробуй ещё раз позже.")
        await dialog_manager.done()
        return
    except HTTPError as error:
        logging.error(error)
        await bot.send_message(chat_id=event_context.chat_id, text=f"Упс, что-то пошло не так😳. "
                                                                   "Попробуй ещё раз позже.")
        await dialog_manager.done()
        return

    tasks = response.json()
    opened_homeworks = []
    for task in tasks:
        if compare_date_str_to_now(task['start_date']) <= 0 <= compare_date_str_to_now(task['end_date']):
            opened_homeworks.append(task['id'])

    if not opened_homeworks:
        await bot.send_message(chat_id=event_context.chat_id, text=f"Нету доступных дз для сдачи👀")
        await dialog_manager.done()
        return

    return {
        'opened_homeworks': opened_homeworks
    }


async def on_homework_chosen(callback: CallbackQuery, widget: Any, dialog_manager: DialogManager, item_id: str):
    format_symbols = {
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣"
    }
    dialog_manager.dialog_data['task_id'] = item_id
    await callback.message.answer(text=f'Выбрано дз: *{format_symbols[int(item_id)]}*', parse_mode=ParseMode.MARKDOWN_V2)
    await dialog_manager.next()


async def hw_handler(message: Message, message_input: MessageInput, dialog_manager: DialogManager):
    entities = message.entities or []
    hw_link = None
    for item in entities:
        if item.type == "url":
            hw_link = item.extract_from(message.text)
            break
    if hw_link is None:
        await message.answer(text="Сообщение не содержит ссылки😔.\n"
                                  "Отправь, пожалуйста, ещё раз.")
    else:
        try:
            response = requests.post(settings.BACKEND_URL + f"/{slugify(message.from_user.username)}/sendhw",
                                     data={
                                        'url': hw_link,
                                        'task': int(dialog_manager.dialog_data['task_id'])
                                     })
            response.raise_for_status()
        except ConnectionError as error:
            logging.error(error)
            await message.answer("Сервер временно недоступен 😔\nНад этим уже работают!\n\nПопробуй ещё раз позже.")
            await dialog_manager.done()
            return
        except HTTPError as error:
            logging.error(error)
            await message.answer(f"Упс, что-то пошло не так😳. Напиши, пожалуйста {settings.ADMIN}.")
            await dialog_manager.done()
            return

        await message.answer(text="Дз успешно отправлено🥳")
        await dialog_manager.done()


send_hw_dialog = Dialog(
    Window(
        Const("Выбери номер дз для сдачи🫴\n\n"
              "❗️ пока дз доступно, его можно пересдавать неограниченное число раз"),
        Select(
            Format("{item}"),
            id="hw_id",
            item_id_getter=lambda x: x,
            items="opened_homeworks",
            on_click=on_homework_chosen
        ),
        Cancel(Const("Отмена")),
        state=SendHwSG.hw_list,
        getter=hw_list_getter
    ),
    Window(
        Const(text=
              "Отправь ссылку🔗 на дз.\n\n"
              "❗️ Если в сообщении ты отправишь несколько ссылок,\n"
              "то на проверку будет выбрана первая\n\n"
              "Пример:\n"
              "<i>Привет! Вот ссылки на моё первое дз</i>\n"
              "<i>https://figmalink1</i> - первая ссылка пойдёт на проверку\n"
              "<i>https://figmalink2</i> - вторая канет в бездну ☹️\n"
              "<i>Вроде всё☺️</i>"
              ),
        Row(
            Back(Const("Назад")),
            Cancel(Const("Отмена"))
        ),
        MessageInput(hw_handler, content_types=[ContentType.TEXT]),
        state=SendHwSG.send_hw,
        parse_mode=ParseMode.HTML
    ),
)

router.include_router(send_hw_dialog)


class LeaveStates(StatesGroup):
    confirm = State()


async def confirm_leave(callback: CallbackQuery, button: Button, dialog_manager: DialogManager):
    username = callback.from_user.username
    try:
        response = requests.delete(settings.BACKEND_URL + f"/delmember/{slugify(username)}")
        response.raise_for_status()
    except ConnectionError as error:
        logging.error(error)
        await callback.message.answer(f"Сервер временно недоступен 😔\n\n"
                                      f"Над этим уже работают!\n\nПопробуй ещё раз позже.")
        await dialog_manager.done()
        return
    except HTTPError:
        await callback.message.answer(f"Упс, что-то пошло не так😳. Напиши, пожалуйста, {settings.ADMIN}.")
        await dialog_manager.done()
        return

    del_from_redis(username)
    await callback.message.answer(f"Ты был исключён из курса по фигме.", parse_mode=ParseMode.HTML)
    await dialog_manager.done()


leave_dialog = Dialog(
    Window(
        Format("⚠️<b>DANGER ZONE</b>⚠️\n\n"
               "Ты точно хочешь покинуть курс❓\n\n"
               "❗️ <b>Ты будет полностью удалён без\n возможности вернуться</b>😥"),
        Button(Const("Да"), id="confirm_yes", on_click=confirm_leave),
        Cancel(Const("Нет")),
        state=LeaveStates.confirm,
        parse_mode=ParseMode.HTML
    )
)


router.include_router(leave_dialog)


@router.message(Command("sendhw"))
async def start_sending_hw_dialog(message: types.Message, dialog_manager: DialogManager):
    await dialog_manager.start(SendHwSG.hw_list, mode=StartMode.RESET_STACK)


@router.message(Command("leave"))
async def leave_course(message: types.Message, dialog_manager: DialogManager):
    await dialog_manager.start(LeaveStates.confirm, mode=StartMode.RESET_STACK)

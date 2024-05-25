import re
from dataclasses import dataclass
from datetime import datetime

from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, Window, DialogManager, ShowMode
from aiogram_dialog.widgets.kbd import Cancel, Row, Button
from aiogram_dialog.widgets.text import Format, Const, List, Multi

from src.api import client
from src.api.schemas.method_input_schemas import ModifyTaskBody
from src.api.schemas.method_output_schemas import UserInfo, TaskInfoResponse
from src.bot.dialogs.dialog_communications import (
    TaskViewDialogStartData,
    ConfirmationDialogStartData,
    PromptDialogStartData,
)
from src.bot.dialogs.states import TaskViewSG, ConfirmationSG, PromptSG


class MainWindowConsts:
    TASK_VIEW_FORMAT = """Name: {task.name}
Start date: {task.start_date_repr}
Period (in days): {task.period}"""
    DESCRIPTION_FORMAT = "Description: {task.description}"
    DATE_FORMAT = "%d.%m.%Y %H:%M"
    ORDER_HEADER = "Order:"
    ORDER_ITEM_FORMAT = "{pos}) {item.fullname}"

    NAME_INPUT_PATTERN = re.compile(r".+")
    DESCRIPTION_INPUT_PATTERN = re.compile(r".+(?:\n\r?.+)*")

    @staticmethod
    def period_filter(s: str):
        return s.isdecimal() and int(s) > 0

    @staticmethod
    def start_date_filter(text: str) -> bool:
        try:
            parse_datetime(text)
        except ValueError:
            return False

    BACK_BUTTON_ID = "back_button"
    EDIT_NAME_BUTTON_ID = "edit_name_button"
    EDIT_DESCRIPTION_BUTTON_ID = "edit_description_button"
    EDIT_START_DATE_BUTTON_ID = "edit_start_date_button"
    EDIT_PERIOD_BUTTON_ID = "edit_period_button"
    EDIT_ORDER_BUTTON_ID = "edit_order_button"
    DELETE_BUTTON_ID = "delete_button"


@dataclass
class TaskRepresentation:
    name: str
    description: str
    start_date: datetime
    period: int

    @property
    def start_date_repr(self) -> str:
        return self.start_date.strftime(MainWindowConsts.DATE_FORMAT)


class Loader:
    @staticmethod
    async def load_task_info(manager: DialogManager):
        user_id = manager.event.from_user.id
        task_id = manager.dialog_data["task_id"]

        task_data: TaskInfoResponse = await client.get_task_info(task_id, user_id)
        manager.dialog_data["task"] = task_data

        if task_data.order_id is None:
            manager.dialog_data["executors"] = None
        else:
            order_data = await client.get_order_info(task_data.order_id, user_id)
            manager.dialog_data["executors"] = order_data.users


class Events:
    @staticmethod
    async def on_start(start_data: dict, manager: DialogManager):
        args: TaskViewDialogStartData = start_data["input"]
        manager.dialog_data["task_id"] = args.task_id
        await Loader.load_task_info(manager)

    @staticmethod
    async def on_delete_task(callback: CallbackQuery, widget, manager: DialogManager):
        await manager.start(
            ConfirmationSG.main,
            data={
                "intent": "delete",
                "input": ConfirmationDialogStartData("delete the task", yes_message="The task has been deleted"),
            },
            show_mode=ShowMode.SEND,
        )

    @staticmethod
    async def _prompt_string(intent: str, prompt: PromptDialogStartData, manager: DialogManager):
        await manager.start(
            PromptSG.main,
            data={"intent": intent, "input": prompt},
            show_mode=ShowMode.SEND,
        )

    @staticmethod
    async def on_edit_name(callback: CallbackQuery, widget, manager: DialogManager):
        await Events._prompt_string(
            "edit_name", PromptDialogStartData("a new name", filter=MainWindowConsts.NAME_INPUT_PATTERN), manager
        )

    @staticmethod
    async def on_edit_description(callback: CallbackQuery, widget, manager: DialogManager):
        await Events._prompt_string(
            "edit_description",
            PromptDialogStartData("a new description", filter=MainWindowConsts.DESCRIPTION_INPUT_PATTERN),
            manager,
        )

    @staticmethod
    async def on_edit_start_date(callback: CallbackQuery, widget, manager: DialogManager):
        await Events._prompt_string(
            "edit_start_date",
            PromptDialogStartData("a new start date", filter=MainWindowConsts.start_date_filter),
            manager,
        )

    @staticmethod
    async def on_edit_period(callback: CallbackQuery, widget, manager: DialogManager):
        await Events._prompt_string(
            "edit_period", PromptDialogStartData("a new period", filter=MainWindowConsts.period_filter), manager
        )

    @staticmethod
    async def on_process_result(start_data: dict, result: bool | str | None, manager: DialogManager):
        if not isinstance(start_data, dict):
            return

        task_id = manager.dialog_data["task_id"]
        user_id = manager.event.from_user.id
        if start_data["intent"] == "delete":
            if result:
                await client.delete_task(task_id, user_id)
                await manager.done(show_mode=ShowMode.SEND)
                return
        elif start_data["intent"] == "edit_name":
            if result is not None:
                await client.modify_task(ModifyTaskBody(id=task_id, name=result), user_id)
                await Loader.load_task_info(manager)
        elif start_data["intent"] == "edit_description":
            if result is not None:
                await client.modify_task(ModifyTaskBody(id=task_id, description=result), user_id)
                await Loader.load_task_info(manager)
        elif start_data["intent"] == "edit_start_date":
            if result is not None:
                await client.modify_task(ModifyTaskBody(id=task_id, start_date=parse_datetime(result)), user_id)
                await Loader.load_task_info(manager)
        elif start_data["intent"] == "edit_period":
            if result is not None:
                await client.modify_task(ModifyTaskBody(id=task_id, period=result), user_id)
                await Loader.load_task_info(manager)
        await manager.show(ShowMode.SEND)


def parse_datetime(text: str) -> datetime:
    return datetime.strptime(text, MainWindowConsts.DATE_FORMAT)


async def getter(dialog_manager: DialogManager, **kwargs):
    task: TaskInfoResponse = dialog_manager.dialog_data["task"]
    executors: list[UserInfo] = dialog_manager.dialog_data["executors"]

    return {
        "task": TaskRepresentation(task.name, task.description, task.start_date, task.period),
        "executors": executors,
    }


task_view_dialog = Dialog(
    Window(
        Format(MainWindowConsts.TASK_VIEW_FORMAT),
        Format(MainWindowConsts.DESCRIPTION_FORMAT, when=lambda data, w, m: data["task"].description),
        Multi(
            Const(MainWindowConsts.ORDER_HEADER),
            List(
                Format(MainWindowConsts.ORDER_ITEM_FORMAT),
                items="executors",
            ),
            when="executors",
        ),
        Row(
            Button(
                Const("Edit name"),
                id=MainWindowConsts.EDIT_NAME_BUTTON_ID,
                on_click=Events.on_edit_name,
            ),
            Button(
                Const("Edit description"),
                id=MainWindowConsts.EDIT_DESCRIPTION_BUTTON_ID,
                on_click=Events.on_edit_description,
            ),
        ),
        Row(
            Button(
                Const("Edit start date"),
                id=MainWindowConsts.EDIT_START_DATE_BUTTON_ID,
                on_click=Events.on_edit_start_date,
            ),
            Button(
                Const("Edit period"),
                id=MainWindowConsts.EDIT_PERIOD_BUTTON_ID,
                on_click=Events.on_edit_period,
            ),
        ),
        Row(
            Button(
                Const("Delete"),
                id=MainWindowConsts.DELETE_BUTTON_ID,
                on_click=Events.on_delete_task,
            ),
            Button(
                Const("Edit order"),
                id=MainWindowConsts.EDIT_ORDER_BUTTON_ID,
            ),
        ),
        Cancel(Const("Back"), MainWindowConsts.BACK_BUTTON_ID),
        state=TaskViewSG.main,
        getter=getter,
    ),
    on_start=Events.on_start,
    on_process_result=Events.on_process_result,
)

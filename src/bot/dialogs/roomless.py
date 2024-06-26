from aiogram.types import CallbackQuery
from aiogram_dialog import Window, Dialog, DialogManager, Data, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Row, Button, Start
from aiogram_dialog.widgets.text import Const

from src.api import client
from src.bot.dialogs.dialog_communications import (
    RoomDialogStartData,
    IncomingInvitationDialogStartData,
    PromptDialogStartData,
)
from src.bot.dialogs.states import RoomlessSG, PromptSG, RoomSG, IncomingInvitationsSG


class WelcomeWindowConsts:
    WELCOME_MESSAGE = """This is a welcome message\n
You can:
- Accept an invitation to a room
- Create a new room"""

    INVITATIONS_BUTTON_ID = "invitations_button"
    CREATE_ROOM_BUTTON_ID = "create_room_button"


class Events:
    @staticmethod
    async def on_process_result(start_data: Data, result: str | None, manager: DialogManager):
        if not isinstance(start_data, dict):
            return

        if start_data["intent"] == "create_room":
            if result is not None:
                room_id = await client.create_room(result, manager.event.from_user.id)
                await manager.start(
                    RoomSG.main,
                    data={"input": RoomDialogStartData(room_id, result)},
                    mode=StartMode.RESET_STACK,
                )
            else:
                await manager.show(ShowMode.SEND)
            return

    @staticmethod
    async def on_click_create_room(event: CallbackQuery, button: Button, dialog_manager: DialogManager):
        await dialog_manager.start(
            PromptSG.main,
            data={"intent": "create_room", "input": PromptDialogStartData("a room's name")},
            show_mode=ShowMode.SEND,
        )


roomless_dialog = Dialog(
    # Main page
    Window(
        Const(WelcomeWindowConsts.WELCOME_MESSAGE),
        Row(
            Start(
                Const("Invitations"),
                id=WelcomeWindowConsts.INVITATIONS_BUTTON_ID,
                state=IncomingInvitationsSG.list,
                data={
                    "intent": "invitations",
                    "input": IncomingInvitationDialogStartData(True),
                },
            ),
            Button(
                Const("Create"),
                WelcomeWindowConsts.CREATE_ROOM_BUTTON_ID,
                on_click=Events.on_click_create_room,
            ),
        ),
        state=RoomlessSG.welcome,
    ),
    on_process_result=Events.on_process_result,
)

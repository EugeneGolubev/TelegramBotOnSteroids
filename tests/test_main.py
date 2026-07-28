from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.main import register_bot_commands


@pytest.mark.asyncio
async def test_register_bot_commands_publishes_status_commands():
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock()

    await register_bot_commands(application)

    commands = application.bot.set_my_commands.await_args.args[0]
    assert [(command.command, command.description) for command in commands] == [
        ("status", "Show system and VPN status"),
        ("tstatus", "Show torrent progress and speed"),
        ("mediafiles", "List and delete media files"),
    ]

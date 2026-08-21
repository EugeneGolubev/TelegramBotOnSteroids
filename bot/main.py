import logging
from telegram import BotCommand
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler, filters, Defaults
from bot.handlers import (
    handle_category_selection,
    handle_media_callback,
    handle_media_files,
    handle_message,
    handle_status,
    handle_torrent_callback,
    handle_tstatus,
)
from bot.config import get_settings, validate_settings


async def register_bot_commands(application: Application) -> None:
    """Publish Telegram's command-menu suggestions at application startup."""
    await application.bot.set_my_commands([
        BotCommand("status", "Show system and VPN status"),
        BotCommand("tstatus", "Show torrent progress and speed"),
        BotCommand("mediafiles", "List and delete media files"),
    ])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    validate_settings(settings)
    app = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .defaults(Defaults(parse_mode=ParseMode.MARKDOWN))
        .post_init(register_bot_commands)
        .build()
    )
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("tstatus", handle_tstatus))
    app.add_handler(CommandHandler("mediafiles", handle_media_files))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(handle_media_callback, pattern=r"^media:"))
    app.add_handler(CallbackQueryHandler(handle_torrent_callback, pattern=r"^torrent:"))
    app.add_handler(CallbackQueryHandler(handle_category_selection))
    app.run_polling()

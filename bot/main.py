import logging
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler, filters, Defaults
from bot.handlers import handle_message, handle_category_selection, handle_status, handle_tstatus
from bot.config import get_settings, validate_settings

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    validate_settings(settings)
    app = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .defaults(Defaults(parse_mode=ParseMode.MARKDOWN))
        .build()
    )
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("tstatus", handle_tstatus))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(handle_category_selection))
    app.run_polling()

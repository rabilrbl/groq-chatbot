import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
)
from groq_chat.handlers import (
    start,
    help_command,
    message_handler,
    new_command_handler,
    model_command_handler,
    change_model_callback_handler,
    SYSTEM_PROMPT_SP,
    CANCEL_SP,
    start_system_prompt,
    get_system_prompt,
    cancelled_system_prompt,
    info_command_handler,
)
from groq_chat.filters import AuthFilter, MessageFilter
from dotenv import load_dotenv
from mongopersistence import MongoPersistence
import logging

load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

persistence = MongoPersistence(
    mongo_url=os.getenv("MONGODB_URL"),
    db_name="groq-chatbot",
    name_col_user_data="user_data",
    name_col_bot_data="bot_data",
    name_col_chat_data="chat_data",
    name_col_conversations_data="conversations_data",
    create_col_if_not_exist=True,  # optional
    ignore_general_data=["cache"],
)


def start_bot():
    logger.info("Starting bot")
    app = (
        Application.builder()
        .token(os.getenv("BOT_TOKEN"))
        .persistence(persistence)
        .build()
    )
    app.add_error_handler(
        lambda _, __: logger.error("Exception while handling an update:", exc_info=True)
    )

    app.add_handler(CommandHandler("start", start, filters=AuthFilter))
    app.add_handler(CommandHandler("help", help_command, filters=AuthFilter))
    app.add_handler(CommandHandler("new", new_command_handler, filters=AuthFilter))
    app.add_handler(CommandHandler("model", model_command_handler, filters=AuthFilter))
    app.add_handler(CommandHandler("info", info_command_handler, filters=AuthFilter))

    app.add_handler(
        ConversationHandler(
            entry_points=[
                CommandHandler("system_prompt", start_system_prompt, filters=AuthFilter)
            ],
            states={
                SYSTEM_PROMPT_SP: [MessageHandler(MessageFilter, get_system_prompt)],
                CANCEL_SP: [
                    CommandHandler(
                        "cancel", cancelled_system_prompt, filters=AuthFilter
                    )
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancelled_system_prompt, filters=AuthFilter)
            ],
        )
    )

    app.add_handler(MessageHandler(MessageFilter, message_handler))
    app.add_handler(
        CallbackQueryHandler(change_model_callback_handler, pattern="^change_model_")
    )

    # Run the bot until the user presses Ctrl-C
    app.run_polling(allowed_updates=Update.ALL_TYPES)

import html
import json
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import NetworkError, BadRequest
from telegram.constants import ChatAction, ParseMode
from groq_chat.html_format import format_message
from groq_chat.groq_chat import chatbot, generate_response
import asyncio

SYSTEM_PROMPT_SP = 1
CANCEL_SP = 2

def new_chat(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("system_prompt") is not None:
        context.user_data["messages"] = [
            {
                "role": "system",
                "content": context.user_data.get("system_prompt"),
            },
        ]
    else:
        context.user_data["messages"] = []


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}!\n\nStart sending messages with me to generate a response.\n\nSend /new to start a new chat session.",
    )


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
Basic commands:
/start - Start the bot
/help - Get help. Shows this message

Chat commands:
/new - Start a new chat session (model will forget previously generated messages)
/model - Change the model used to generate responses.
/system_prompt - Change the system prompt used for new chat sessions.
/info - Get info about the current chat session.

Send a message to the bot to generate a response.
"""
    await update.message.reply_text(help_text)


async def new_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start a new chat session"""
    new_chat(context)
    await update.message.reply_text(
        "New chat session started.\n\nSwitch models with /model."
    )


async def model_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Change the model used to generate responses"""
    models = ["llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768", "gemma-7b-it"]

    reply_markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(model, callback_data="change_model_" + model)]
            for model in models
        ]
    )

    await update.message.reply_text("Select a model:", reply_markup=reply_markup)


async def change_model_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Change the model used to generate responses"""
    query = update.callback_query
    model = query.data.replace("change_model_", "")

    context.user_data["model"] = model

    await query.edit_message_text(
        f"Model changed to `{model}`. \n\nSend /new to start a new chat session.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_system_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start a system prompt"""
    await update.message.reply_text(
        "Send me a system prompt. If you want to clear the system prompt, send `clear` now."
    )
    return SYSTEM_PROMPT_SP


async def cancelled_system_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Cancel the system prompt"""
    await update.message.reply_text("System prompt change cancelled.")
    return ConversationHandler.END


async def get_system_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the system prompt"""
    system_prompt = update.message.text
    if system_prompt.lower().strip() == "clear":
        context.user_data.pop("system_prompt", None)
        await update.message.reply_text("System prompt cleared.")
    else:
        context.user_data["system_prompt"] = system_prompt
        await update.message.reply_text(
            "System prompt changed."
        )
    new_chat(context)
    return ConversationHandler.END


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages"""
    if "model" not in context.user_data:
        context.user_data["model"] = "llama3-8b-8192"

    if "messages" not in context.user_data:
        context.user_data["messages"] = []

    init_msg = await update.message.reply_text("Generating response...")

    message = update.message.text
    if not message:
        return

    asyncio.run_coroutine_threadsafe(update.message.chat.send_action(ChatAction.TYPING), loop=asyncio.get_event_loop())
    full_output_message = ""
    for message in generate_response(message, context):
        if message:
            full_output_message += message
            send_message = format_message(full_output_message)
            init_msg = await init_msg.edit_text(
                send_message, parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
    context.user_data["messages"] = context.user_data.get("messages", []) + [
        {
            "role": "system",
            "content": full_output_message,
        }
    ]


async def info_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Get info about the bot"""
    message = f"""**__Conversation Info:__**
**Model**: `{context.user_data.get("model", "llama3-8b-8192")}`
"""
    # if context.user_data.get("system_prompt") is not None:
    #     message += f"\n**System Prompt**: \n```\n{context.user_data.get("system_prompt")}\n```"
    await update.message.reply_text(format_message(message), parse_mode=ParseMode.HTML)
    
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.getLogger(__name__).error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await update.message.reply_text(
        text=message, parse_mode=ParseMode.HTML
    )

import asyncio
from asgiref.sync import async_to_sync, sync_to_async
from telegram import Update, Bot, Message
from telegram.ext import (
    ApplicationBuilder, 
    Application,
    CallbackContext,
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    PicklePersistence,
    ExtBot
)
from telegram.constants import ParseMode
import html
import json
import logging
from dataclasses import dataclass
from http import HTTPStatus
import traceback
import os
from dotenv import load_dotenv
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

load_dotenv('.env')

ENVIRONMENT = os.getenv("ENVIRONMENT")
URL = os.getenv("URL")
PORT = int(os.getenv("PORT"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
DEVELOPER_CHAT_ID = int(os.getenv("DEVELOPER_CHAT_ID"))

logger = logging.getLogger(__name__)


@dataclass
class WebhookUpdate:
    """Simple dataclass to wrap a custom update type"""

    user_id: int
    payload: str


class CustomContext(CallbackContext[ExtBot, dict, dict, dict]):
    """
    Custom CallbackContext class that makes `user_data` available for updates of type
    `WebhookUpdate`.
    """

    @classmethod
    def from_update(
        cls,
        update: object,
        application: "Application",
    ) -> "CustomContext":
        if isinstance(update, WebhookUpdate):
            return cls(application=application, user_id=update.user_id)
        return super().from_update(update, application)

context_types = ContextTypes(context=CustomContext)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 😊 Assalom alaykum!\nUshbu telegram bot Fasahfiya telegram kanali admini bilan o'zaro anonim suhbat qurish uchun yaratilgan.
    await update.message.reply_text("📝 Fikringizni yozib qoldiring:")

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_message = update.message.text

    # Forward the message to the developer
    message: Message = await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, 
        text=f"🆕 ID #{user_id} foydalanuvchidan yangi xabar:\n\n{user_message}")
    # Forward the message to the admin
    message: Message = await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID, 
        text=f"🆕 ID {user_id} foydalanuvchidan yangi xabar:\n\n{user_message}")
    # Save message_id and user_id to chat_data
    context.bot_data[message.message_id] = user_id

    await update.message.reply_text("✅ Xabar muvaffaqiyatli yuborildi!")

async def reply_from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await forward_to_admin(update, context)
        return
    admin_message = update.message.text
    reply_to_message_id = update.message.reply_to_message.message_id
    # Get user_id from chat_data using the message_id
    user_id = context.bot_data.get(reply_to_message_id)

    if user_id:
        # Send admin's message to the user
        await context.bot.send_message(chat_id=user_id, text=f"🆕 Admin tomonidan yangi xabar:\n\n{admin_message}")
        await context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=f"🆕 Admin tomonidan yangi xabar, #{user_id} uchun:\n\n{admin_message}")
        await update.message.reply_text("✅ Xabar muvaffaqiyatli yuborildi!")
    else:
        await update.message.reply_text("User not found or message was not forwarded.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

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
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )



async def main(application: Application) -> None:
    """Set up PTB application and a web application for handling the incoming requests."""
    # Here we set updater to None because we want our custom webhook server to handle the updates
    # and hence we don't need an Updater instance
    await application.bot.set_webhook(url=f"{URL}/telegram", allowed_updates=Update.ALL_TYPES)

    # Set up webserver
    async def telegram(request: Request) -> Response:
        """Handle incoming Telegram updates by putting them into the `update_queue`"""
        await application.update_queue.put(
            Update.de_json(data=await request.json(), bot=application.bot)
        )
        return Response()

    starlette_app = Starlette(
        routes=[
            Route("/telegram", telegram, methods=["POST"]),
        ]
    )
    webserver = uvicorn.Server(
        config=uvicorn.Config(
            app=starlette_app,
            port=PORT,
            use_colors=False,
            host="127.0.0.1",
        )
    )

    # Run application and webserver together
    async with application:
        await application.start()
        await webserver.serve()
        await application.stop()


if __name__ == "__main__":
    persistence = PicklePersistence(filepath='persistence')
    application = (
        Application.builder().token(BOT_TOKEN).persistence(persistence).context_types(context_types).build()
    )

    # register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.REPLY, forward_to_admin))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, reply_from_admin))
    application.add_error_handler(error_handler)

    if ENVIRONMENT == 'production':
        asyncio.run(main(application))
    elif ENVIRONMENT == 'development':
        # async with application:
        print('Bot polling ...')
        application.run_polling()
        

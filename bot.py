from telegram import Update, Bot, Message
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    PicklePersistence
)
from telegram.constants import ParseMode
import html
import json
import logging
import traceback
import os
from dotenv import load_dotenv

load_dotenv('.env')

BOT_TOKEN = os.getenv("BOT_TOKEN")
print(BOT_TOKEN)
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
DEVELOPER_CHAT_ID = int(os.getenv("DEVELOPER_CHAT_ID"))

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Send me a message, and I'll forward it to the admin.")

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_message = update.message.text

    # Forward the message to the admin
    message: Message = await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID, 
        text=f"🆕 ID {user_id} foydalanuvchidan yangi xabar:\n\n{user_message}")
    # Save message_id and user_id to chat_data
    context.bot_data[message.message_id] = user_id

    await update.message.reply_text("✅ Xabar muvaffaqiyatli yuborildi!")

async def reply_from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(ADMIN_CHAT_ID)
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

if __name__ == "__main__":
    persistence = PicklePersistence(filepath='persistence')
    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.REPLY, forward_to_admin))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, reply_from_admin))
    app.add_error_handler(error_handler)
    app.run_polling()

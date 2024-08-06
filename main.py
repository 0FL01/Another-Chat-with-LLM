import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from handlers import start, clear, handle_message, handle_voice, change_model, add_user, remove_user, set_offline_mode
from config import TELEGRAM_TOKEN, ollama_client

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update, context):
    logger.error(f"Exception while handling an update: {context.error}")

async def shutdown():
    await ollama_client.aclose()
    logger.info("Ollama client closed.")

def main():
    logger.info("Starting the bot")
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(MessageHandler(filters.Regex('^Оффлайн режим$'), set_offline_mode))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    application.add_error_handler(error_handler)

    # Use the stop callback to gracefully shutdown the bot
    application.post_stop = shutdown

    application.run_polling()

if __name__ == '__main__':
    main()

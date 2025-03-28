import nest_asyncio
nest_asyncio.apply()

import logging
import asyncio
from logging.handlers import TimedRotatingFileHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from handlers import start, clear, handle_message, handle_voice, change_model, add_user, remove_user, healthcheck, handle_video
from config import TELEGRAM_TOKEN, MODELS
import os
import re
from database import get_db_connection, check_postgres_connection, create_chat_history_table, create_user_models_table

class SensitiveDataFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.patterns = [
            # Pattern for Telegram bot token in URLs
            (r'(https?:\/\/[^\/]+\/bot)([0-9]+:[A-Za-z0-9_-]+)(\/[^"\s]*)', r'\1[TELEGRAM_TOKEN]\3'),
            # Pattern for raw bot token
            (r'([0-9]{8,10}:[A-Za-z0-9_-]{35})', '[TELEGRAM_TOKEN]'),
            # Pattern for partial token mentions
            (r'(bot[0-9]{8,10}:)[A-Za-z0-9_-]+', r'\1[TELEGRAM_TOKEN]')
        ]

    def filter(self, record):
        if hasattr(record, 'msg'):
            if isinstance(record.msg, str):
                for pattern, replacement in self.patterns:
                    record.msg = re.sub(pattern, replacement, record.msg)

        if hasattr(record, 'args'):
            if record.args:
                args_list = list(record.args)
                for i, arg in enumerate(args_list):
                    if isinstance(arg, str):
                        for pattern, replacement in self.patterns:
                            args_list[i] = re.sub(pattern, replacement, arg)
                record.args = tuple(args_list)
        return True

class TokenMaskingFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        self.sensitive_filter = SensitiveDataFilter()

    def format(self, record):
        # Apply filter before formatting
        self.sensitive_filter.filter(record)
        return super().format(record)

def setup_logging():
    """Configure logging with secure token masking"""
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Create formatter
    formatter = TokenMaskingFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create sensitive data filter
    sensitive_filter = SensitiveDataFilter()

    # File handler setup
    file_handler = TimedRotatingFileHandler(
        'logs/acwl.log',
        when='h',
        interval=1,
        backupCount=72,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)

    # Console handler setup
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Configure httpx logger
    httpx_logger = logging.getLogger('httpx')
    httpx_logger.setLevel(logging.INFO)
    # Remove existing handlers
    for handler in httpx_logger.handlers[:]:
        httpx_logger.removeHandler(handler)
    httpx_logger.addHandler(file_handler)
    httpx_logger.propagate = False

    # Configure telegram logger
    telegram_logger = logging.getLogger('telegram')
    telegram_logger.setLevel(logging.INFO)
    # Remove existing handlers
    for handler in telegram_logger.handlers[:]:
        telegram_logger.removeHandler(handler)
    telegram_logger.addHandler(file_handler)
    telegram_logger.propagate = False

    # Configure urllib3 logger
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.INFO)
    # Remove existing handlers
    for handler in urllib3_logger.handlers[:]:
        urllib3_logger.removeHandler(handler)
    urllib3_logger.addHandler(file_handler)
    urllib3_logger.propagate = False

    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging()

async def main():
    try:
        logger.info("Starting the bot")
        
        # Проверяем подключение к PostgreSQL
        check_postgres_connection()
        
        # Создаем необходимые таблицы
        create_chat_history_table()
        create_user_models_table()
        
        # Пробуем установить тестовое подключение к БД
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()
                    logger.info(f"Connected to PostgreSQL. Version: {version[0]}")
        except Exception as e:
            logger.error(f"Failed to connect to database during startup check: {e}")
        
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("clear", clear))
        application.add_handler(CommandHandler("add_user", add_user))
        application.add_handler(CommandHandler("remove_user", remove_user))
        application.add_handler(CommandHandler("healthcheck", healthcheck))
        
        # Обработчик для кнопки "Сменить модель" и выбора модели
        application.add_handler(MessageHandler(
            filters.Regex("^Сменить модель$") | filters.Regex(f"^({'|'.join(MODELS)})$"),
            change_model
        ))

        # Обработчик для остальных текстовых сообщений
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.Regex("^Сменить модель$") & ~filters.Regex(f"^({'|'.join(MODELS)})$"),
            handle_message
        ))
        
        # Регистрируем обработчик для голосовых сообщений
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))

        # Регистрируем обработчик для видео сообщений
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        
        # Start the bot
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    asyncio.run(main())



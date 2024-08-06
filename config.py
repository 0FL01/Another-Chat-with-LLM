import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from utils import load_allowed_users, save_allowed_users, is_user_allowed, add_allowed_user, remove_allowed_user, set_user_auth_state, get_user_auth_state

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

chat_history = {}
user_settings = {}

MODELS = {
    "GPT-3.5 Turbo": {"id": "gpt-3.5-turbo", "max_tokens": 4096},
    "GPT-4": {"id": "gpt-4", "max_tokens": 8192}
}

ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Создаем клиент OpenAI
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

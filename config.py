import os
import httpx
from dotenv import load_dotenv
from utils import load_allowed_users, save_allowed_users, is_user_allowed, add_allowed_user, remove_allowed_user, set_user_auth_state, get_user_auth_state

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OLLAMA_API_URL = "http://localhost:11434/api/chat"

chat_history = {}
user_settings = {}

MODELS = {
    "Gemma 2B": {"id": "gemma2:2b", "max_tokens": 8192}
}

ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Создаем один экземпляр httpx.AsyncClient для повторного использования
ollama_client = httpx.AsyncClient()

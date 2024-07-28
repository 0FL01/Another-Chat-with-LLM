import html
import re
import os
from typing import List, Dict

# Функции форматирования

def format_html(text):
    def code_block_replacer(match):
        code = match.group(2)
        language = match.group(1) or ''
        escaped_code = html.escape(code.strip())
        return f'<pre><code class="{language}">{escaped_code}</code></pre>'

    text = re.sub(r'```(\w+)?\n(.*?)```', code_block_replacer, text, flags=re.DOTALL)
    text = re.sub(r'`(\w+)\n(.*?)`', code_block_replacer, text, flags=re.DOTALL)
    text = re.sub(r'^\* ', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', lambda m: f'<code>{html.escape(m.group(1))}</code>', text)
    
    return text

def split_long_message(message, max_length=4000):
    parts = []
    while len(message) > max_length:
        split_index = max_length
        
        newline_index = message.rfind('\n', 0, max_length)
        if newline_index > max_length * 0.8:
            split_index = newline_index
        else:
            space_index = message.rfind(' ', 0, max_length)
            if space_index > max_length * 0.8:
                split_index = space_index
        
        parts.append(message[:split_index].strip())
        message = message[split_index:].strip()
    
    if message:
        parts.append(message)
    
    return parts

# Функция поиска с использованием LangChain
def search_with_langchain(query: str) -> str:
    from config import agent  # Импортируем agent здесь, чтобы избежать циклического импорта
    try:
        result = agent.run(query)
        return result
    except Exception as e:
        return f"Произошла ошибка при поиске: {str(e)}"

# Функции авторизации

ALLOWED_USERS_FILE = "allowed_users.txt"

def load_allowed_users() -> List[int]:
    if not os.path.exists(ALLOWED_USERS_FILE):
        return []
    with open(ALLOWED_USERS_FILE, "r") as f:
        return [int(line.strip()) for line in f if line.strip().isdigit()]

def save_allowed_users(users: List[int]):
    with open(ALLOWED_USERS_FILE, "w") as f:
        for user_id in users:
            f.write(f"{user_id}\n")

def is_user_allowed(user_id: int) -> bool:
    allowed_users = load_allowed_users()
    return user_id in allowed_users

def add_allowed_user(user_id: int):
    allowed_users = load_allowed_users()
    if user_id not in allowed_users:
        allowed_users.append(user_id)
        save_allowed_users(allowed_users)

def remove_allowed_user(user_id: int):
    allowed_users = load_allowed_users()
    if user_id in allowed_users:
        allowed_users.remove(user_id)
        save_allowed_users(allowed_users)

user_auth_state: Dict[int, bool] = {}

def set_user_auth_state(user_id: int, state: bool):
    user_auth_state[user_id] = state

def get_user_auth_state(user_id: int) -> bool:
    return user_auth_state.get(user_id, False)

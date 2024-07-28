import os
from groq import AsyncGroq
from octoai.client import OctoAI
from dotenv import load_dotenv
from utils import load_allowed_users, save_allowed_users, is_user_allowed, add_allowed_user, remove_allowed_user, set_user_auth_state, get_user_auth_state
from langchain_community.llms import Groq
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import initialize_agent, AgentType

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
OCTOAI_API_KEY = os.getenv('OCTOAI_API_KEY')

groq_client = AsyncGroq(api_key=GROQ_API_KEY)
octoai_client = OctoAI(api_key=OCTOAI_API_KEY)

chat_history = {}

MODELS = {
    "Gemma 2 9B-8192": {"id": "gemma2-9b-it", "max_tokens": 8192, "provider": "groq"},
    "Llama 3 70B-8192": {"id": "llama3-70b-8192", "max_tokens": 8192, "provider": "groq"},
    "Llama 3.1 70B-8192": {"id": "llama-3.1-70b-versatile", "max_tokens": 8000, "provider": "groq"},
    "Llama 3.1 405B-65536": {"id": "meta-llama-3.1-405b-instruct", "max_tokens": 65536, "provider": "octoai"}
}

ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Инициализация LangChain и инструмента поиска
llm = Groq(model_name="llama3-70b-8192", groq_api_key=GROQ_API_KEY)
search_tool = DuckDuckGoSearchRun()
agent = initialize_agent([search_tool], llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

import os
from groq import AsyncGroq
from dotenv import load_dotenv
from database import is_user_allowed, add_allowed_user, remove_allowed_user, UserRole
from utils import process_file
from openai import OpenAI
from mistralai import Mistral
import pandas as pd
from typing import Union
import logging
import google.generativeai as genai


logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')



if OPENROUTER_API_KEY:
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
else:
    print("Warning: OPENROUTER_API_KEY is not set in the environment variables.")
    openrouter_client = None


if MISTRAL_API_KEY:
    mistral_client = Mistral(api_key=MISTRAL_API_KEY)
else:
    print("Warning: MISTRAL_API_KEY is not set in the environment variables.")
    mistral_client = None

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_client = genai
else:
    print("Warning: GEMINI_API_KEY is not set in the environment variables.")
    gemini_client = None

chat_history = {}

MODELS = {
    "Gemini 2.0 Flash": {"id": "gemini-2.0-flash", "max_tokens": 16384, "provider": "gemini", "vision": True},
    "DeepSeek-R1-Distill-Llama-70B": {"id": "DeepSeek-R1-Distill-Llama-70B", "max_tokens": 128000, "provider": "groq"},
    "Mistral Large 128K": {"id": "mistral-large-latest", "max_tokens": 128000, "provider": "mistral"},
    "Llama 3.3 70B 8K (groq)": {"id": "llama-3.3-70b-versatile", "max_tokens": 32000, "provider": "groq"}
}

DEFAULT_MODEL = "Gemini 2.0 Flash"

try:
    groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    ) if OPENROUTER_API_KEY else None
    mistral_client = Mistral(api_key=MISTRAL_API_KEY) if MISTRAL_API_KEY else None
    gemini_client = genai if GEMINI_API_KEY else None
except Exception as e:
    logger.error(f"Error initializing API clients: {str(e)}")
    # Установите значения клиентов в None в случае ошибки
    groq_client = None
    openrouter_client = None
    mistral_client = None
    gemini_client = None







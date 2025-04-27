import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import os
import sys

# Добавляем путь к корневой директории проекта, если тесты запускаются из папки tests
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Импортируем необходимые компоненты telegram
import telegram
from telegram import Update, User, Message, Chat, Voice, Video
from telegram.constants import ParseMode, ChatAction
from telegram.ext import ContextTypes

# Импортируем тестируемые хендлеры и связанные функции/классы
import handlers
from handlers import (
    start, clear, handle_message, handle_voice, handle_video, change_model,
    add_user, remove_user, process_message, get_main_keyboard,
    get_model_keyboard, get_extra_functions_keyboard, audio_to_text
)
from database import UserRole
from config import MODELS, DEFAULT_MODEL

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    update.effective_user.username = 'testuser'
    update.effective_user.first_name = 'Test'
    update.message = MagicMock(spec=Message)
    update.message.chat = MagicMock(spec=Chat)
    update.message.chat.id = 123456
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    update.message.voice = None
    update.message.video = None
    update.message.document = None
    update.message.text = ""
    update.message.caption = None
    return update

@pytest.fixture
def mock_context(mocker):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.args = []
    return context

@pytest.fixture(autouse=True)
def mock_db_functions(mocker):
    mocker.patch('handlers.is_user_allowed', return_value=True)
    mocker.patch('handlers.get_user_role', return_value=UserRole.USER)
    mocker.patch('handlers.add_allowed_user')
    mocker.patch('handlers.remove_allowed_user')
    mocker.patch('handlers.clear_chat_history')
    mocker.patch('handlers.get_chat_history', return_value=[])
    mocker.patch('handlers.save_message')
    mocker.patch('handlers.update_user_prompt')
    mocker.patch('handlers.get_user_prompt', return_value=None)
    mocker.patch('handlers.get_user_model', return_value=DEFAULT_MODEL)
    mocker.patch('handlers.update_user_model')
    mocker.patch('handlers.set_user_auth_state')

@pytest.fixture(autouse=True)
def mock_api_clients_and_io(mocker):
    # --- Моки для генерации текста ---
    mock_groq_chat_create_method = AsyncMock(return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Mocked Groq Response"))]))
    mock_groq_client_instance = mocker.patch('handlers.groq_client', new_callable=AsyncMock, create=True)
    mock_groq_client_instance.chat.completions.create = mock_groq_chat_create_method

    mock_mistral_complete_method = MagicMock(return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Mocked Mistral Response"))]))
    mock_mistral_client_instance = mocker.patch('handlers.mistral_client', new_callable=MagicMock, create=True)
    mock_mistral_client_instance.chat.complete = mock_mistral_complete_method

    mock_gemini_generate_async_method = AsyncMock(return_value=MagicMock(text="Mocked Gemini Response"))
    mock_generative_model_instance = MagicMock()
    mock_generative_model_instance.generate_content_async = mock_gemini_generate_async_method
    mocker.patch('handlers.gemini_client', new_callable=MagicMock, create=True)
    mocker.patch('handlers.gemini_client.GenerativeModel', return_value=mock_generative_model_instance, create=True)

    # --- Моки для транскрипции ---
    mocker.patch('handlers.audio_to_text', new_callable=AsyncMock, return_value="Mocked transcription text")

    # --- Моки для работы с файлами ---
    mock_download_method = AsyncMock(return_value=b'fake_file_content')
    mock_file_instance = MagicMock(spec=telegram.File)
    mock_file_instance.download_as_bytearray = mock_download_method # Присваиваем мок метода экземпляру

    mocker.patch('telegram.Voice.get_file', AsyncMock(return_value=mock_file_instance))
    mocker.patch('telegram.Video.get_file', AsyncMock(return_value=mock_file_instance))

    # --- Моки для os и open ---
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.remove')
    mocker.patch('builtins.open', mock_open())

    # --- Моки для утилит форматирования ---
    mocker.patch('handlers.format_text', side_effect=lambda x: x)
    mocker.patch('handlers.split_long_message', side_effect=lambda x: [x] if x else [])


async def test_start_unauthorized(mock_update, mock_context, mocker):
    mocker.patch('handlers.is_user_allowed', return_value=False)
    mock_set_auth_state = mocker.patch('handlers.set_user_auth_state')
    await start(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with("Пожалуйста, введите код авторизации:")
    mock_set_auth_state.assert_not_called()

async def test_start_authorized(mock_update, mock_context, mocker):
    mocker.patch('handlers.is_user_allowed', return_value=True)
    mocker.patch('handlers.get_user_model', return_value="Mistral Large 128K")
    mock_set_auth_state = mocker.patch('handlers.set_user_auth_state')
    await start(mock_update, mock_context)
    expected_text = f'<b>Привет!</b> Я бот, который может отвечать на вопросы и распознавать речь.\nТекущая модель: <b>Mistral Large 128K</b>'
    mock_update.message.reply_text.assert_called_once_with(
        expected_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )
    assert mock_context.user_data['model'] == "Mistral Large 128K"
    mock_set_auth_state.assert_called_once_with(12345, True)

async def test_handle_message_text_gemini(mock_update, mock_context, mocker):
    mocker.patch('handlers.get_user_model', return_value="Gemini 2.0 Flash")
    mock_save_message = mocker.patch('handlers.save_message')
    mock_get_history = mocker.patch('handlers.get_chat_history', return_value=[{"role": "user", "content": "previous"}])
    mock_gemini_generate_async = handlers.gemini_client.GenerativeModel.return_value.generate_content_async
    mock_update.message.text = "Привет!"
    mock_update.message.photo = None # Explicitly set photo to None for text message test
    mock_context.user_data['model'] = "Gemini 2.0 Flash"

    await handle_message(mock_update, mock_context)

    mock_get_history.assert_called_once_with(12345)
    assert mock_save_message.call_count == 2
    mock_save_message.assert_any_call(12345, "user", "Привет!")
    mock_save_message.assert_any_call(12345, "assistant", "Mocked Gemini Response")
    mock_gemini_generate_async.assert_called_once()
    call_args, _ = mock_gemini_generate_async.call_args
    assert call_args[0] == [{"role": "user", "parts": ["previous"]}, {"role": "user", "parts": ["Привет!"]}]
    mock_update.message.reply_text.assert_called_once_with("Mocked Gemini Response", parse_mode=ParseMode.HTML)
    mock_update.message.chat.send_action.assert_called_once_with(action=ChatAction.TYPING)

async def test_handle_message_text_mistral(mock_update, mock_context, mocker):
    mocker.patch('handlers.get_user_model', return_value="Mistral Large 128K")
    mock_save_message = mocker.patch('handlers.save_message')
    mock_get_history = mocker.patch('handlers.get_chat_history', return_value=[{"role": "assistant", "content": "prev bot"}])
    mock_mistral_complete = handlers.mistral_client.chat.complete
    mock_update.message.text = "Анекдот?"
    mock_context.user_data['model'] = "Mistral Large 128K"

    await handle_message(mock_update, mock_context)

    mock_get_history.assert_called_once_with(12345)
    assert mock_save_message.call_count == 2
    mock_save_message.assert_any_call(12345, "user", "Анекдот?")
    mock_save_message.assert_any_call(12345, "assistant", "Mocked Mistral Response")
    mock_mistral_complete.assert_called_once()
    _, call_kwargs = mock_mistral_complete.call_args
    assert call_kwargs['messages'][0]['role'] == 'system'
    assert call_kwargs['messages'][1] == {"role": "assistant", "content": "prev bot"}
    assert call_kwargs['messages'][2] == {"role": "user", "content": "Анекдот?"}
    mock_update.message.reply_text.assert_called_once_with("Mocked Mistral Response", parse_mode=ParseMode.HTML)
    mock_update.message.chat.send_action.assert_called_once_with(action=ChatAction.TYPING)

async def test_handle_voice_message(mock_update, mock_context, mocker):
    mock_voice = MagicMock(spec=Voice)
    mock_update.message.voice = mock_voice
    mock_update.message.text = None
    mock_process_message = mocker.patch('handlers.process_message', new_callable=AsyncMock)
    mock_audio_to_text = handlers.audio_to_text # Мок из фикстуры

    await handle_voice(mock_update, mock_context)

    mock_voice.get_file.assert_called_once()
    # Получаем мок экземпляра файла и проверяем вызов download_as_bytearray на нем
    mock_file_returned = await mock_voice.get_file()
    mock_file_returned.download_as_bytearray.assert_called_once()

    expected_filename = f"tempvoice_{mock_update.effective_user.id}.ogg"
    mock_audio_to_text.assert_called_once_with(expected_filename, 'audio/ogg')
    mock_update.message.chat.send_action.assert_called_once_with(action=ChatAction.TYPING)
    mock_update.message.reply_text.assert_called_once_with(
        f"Распознано: \"Mocked transcription text\"\n\nОбрабатываю запрос..."
    )
    mock_process_message.assert_called_once_with(mock_update, mock_context, "Mocked transcription text")
    handlers.os.remove.assert_called_once_with(expected_filename)

async def test_handle_video_message(mock_update, mock_context, mocker):
    mock_video = MagicMock(spec=Video)
    mock_update.message.video = mock_video
    mock_update.message.text = None
    mock_update.message.caption = None
    mock_process_message = mocker.patch('handlers.process_message', new_callable=AsyncMock)
    mock_audio_to_text = handlers.audio_to_text # Мок из фикстуры

    await handle_video(mock_update, mock_context)

    mock_video.get_file.assert_called_once()
    # Получаем мок экземпляра файла и проверяем вызов download_as_bytearray на нем
    mock_file_returned = await mock_video.get_file()
    mock_file_returned.download_as_bytearray.assert_called_once()

    expected_filename = f"tempvideo_{mock_update.effective_user.id}.mp4"
    mock_audio_to_text.assert_called_once_with(expected_filename, 'video/mp4')
    mock_update.message.chat.send_action.assert_called_once_with(action=ChatAction.TYPING)
    mock_update.message.reply_text.assert_called_once_with(
        f"Распознано из видео: \"Mocked transcription text\"\n\nОбрабатываю запрос..."
    )
    mock_process_message.assert_called_once_with(mock_update, mock_context, "Mocked transcription text")
    handlers.os.remove.assert_called_once_with(expected_filename)

async def test_clear_context(mock_update, mock_context, mocker):
    mock_clear_history = mocker.patch('handlers.clear_chat_history')
    mocker.patch('handlers.get_user_model', return_value="Llama 3.3 70B 8K (groq)")
    mock_update.message.text = "Очистить контекст"
    await handle_message(mock_update, mock_context)
    mock_clear_history.assert_called_once_with(12345)
    mock_update.message.reply_text.assert_called_once_with(
        '<b>История чата очищена.</b>',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )

async def test_change_model_show_options(mock_update, mock_context, mocker):
    mock_update.message.text = "Сменить модель"
    await handle_message(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with(
        'Выберите модель:',
        reply_markup=get_model_keyboard()
    )

async def test_change_model_select_valid(mock_update, mock_context, mocker):
    selected_model = "Mistral Large 128K"
    mock_update_model_db = mocker.patch('handlers.update_user_model')
    mock_update.message.text = selected_model
    await handle_message(mock_update, mock_context)
    mock_update_model_db.assert_called_once_with(12345, selected_model)
    assert mock_context.user_data['model'] == selected_model
    mock_update.message.reply_text.assert_called_once_with(
        f'Модель изменена на <b>{selected_model}</b>',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )

async def test_change_model_direct_call(mock_update, mock_context, mocker):
    selected_model = "Llama 3.3 70B 8K (groq)"
    mock_update_model_db = mocker.patch('handlers.update_user_model')
    mock_update.message.text = selected_model
    await change_model(mock_update, mock_context)
    mock_update_model_db.assert_called_once_with(12345, selected_model)
    assert mock_context.user_data['model'] == selected_model
    mock_update.message.reply_text.assert_called_once_with(
        f'Модель изменена на <b>{selected_model}</b>',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )

async def test_admin_add_user_success(mock_update, mock_context, mocker):
    mocker.patch('handlers.get_user_role', return_value=UserRole.ADMIN)
    mock_add_db = mocker.patch('handlers.add_allowed_user')
    mock_context.args = ["54321", "USER"]
    await add_user(mock_update, mock_context)
    mock_add_db.assert_called_once_with(54321, UserRole.USER)
    mock_update.message.reply_text.assert_called_once_with("Пользователь 54321 успешно добавлен с ролью USER.")

async def test_admin_add_user_invalid_args(mock_update, mock_context, mocker):
    mocker.patch('handlers.get_user_role', return_value=UserRole.ADMIN)
    mock_add_db = mocker.patch('handlers.add_allowed_user')
    mock_context.args = ["invalid_id"]
    await add_user(mock_update, mock_context)
    mock_add_db.assert_not_called()
    mock_update.message.reply_text.assert_called_once_with("Пожалуйста, укажите корректный ID пользователя и роль (ADMIN или USER). Пример: /add_user 123456789 USER")

async def test_admin_add_user_not_admin(mock_update, mock_context, mocker):
    mocker.patch('handlers.get_user_role', return_value=UserRole.USER)
    mock_add_db = mocker.patch('handlers.add_allowed_user')
    mock_context.args = ["54321", "USER"]
    await add_user(mock_update, mock_context)
    mock_add_db.assert_not_called()
    mock_update.message.reply_text.assert_called_once_with("У вас нет прав для выполнения этой команды.")

async def test_admin_remove_user_success(mock_update, mock_context, mocker):
    mocker.patch('handlers.get_user_role', return_value=UserRole.ADMIN)
    mock_remove_db = mocker.patch('handlers.remove_allowed_user')
    mock_context.args = ["54321"]
    await remove_user(mock_update, mock_context)
    mock_remove_db.assert_called_once_with(54321)
    mock_update.message.reply_text.assert_called_once_with("Пользователь 54321 успешно удален.")

async def test_admin_remove_user_invalid_args(mock_update, mock_context, mocker):
    mocker.patch('handlers.get_user_role', return_value=UserRole.ADMIN)
    mock_remove_db = mocker.patch('handlers.remove_allowed_user')
    mock_context.args = []
    await remove_user(mock_update, mock_context)
    mock_remove_db.assert_not_called()
    mock_update.message.reply_text.assert_called_once_with("Пожалуйста, укажите корректный ID пользователя. Пример: /remove_user 123456789")

async def test_admin_remove_user_not_admin(mock_update, mock_context, mocker):
    mocker.patch('handlers.get_user_role', return_value=UserRole.USER)
    mock_remove_db = mocker.patch('handlers.remove_allowed_user')
    mock_context.args = ["54321"]
    await remove_user(mock_update, mock_context)
    mock_remove_db.assert_not_called()
    mock_update.message.reply_text.assert_called_once_with("У вас нет прав для выполнения этой команды.")

async def test_handle_message_edit_prompt_start(mock_update, mock_context, mocker):
    mock_update.message.text = "Изменить промпт"
    await handle_message(mock_update, mock_context)
    assert mock_context.user_data.get('editing_prompt') is True
    mock_update.message.reply_text.assert_called_once_with(
        "Введите новый системный промпт. Для отмены введите 'Назад':",
        reply_markup=get_extra_functions_keyboard()
    )

async def test_handle_message_edit_prompt_submit(mock_update, mock_context, mocker):
    mock_update_prompt_db = mocker.patch('handlers.update_user_prompt')
    mock_context.user_data['editing_prompt'] = True
    mock_update.message.text = "Новый системный промпт"
    await handle_message(mock_update, mock_context)
    mock_update_prompt_db.assert_called_once_with(12345, "Новый системный промпт")
    assert mock_context.user_data.get('editing_prompt') is False
    mock_update.message.reply_text.assert_called_once_with(
        "Системный промпт обновлен.",
        reply_markup=get_main_keyboard()
    )

async def test_handle_message_edit_prompt_cancel(mock_update, mock_context, mocker):
    mock_update_prompt_db = mocker.patch('handlers.update_user_prompt')
    mock_context.user_data['editing_prompt'] = True
    mock_update.message.text = "Назад"
    await handle_message(mock_update, mock_context)
    mock_update_prompt_db.assert_not_called()
    assert mock_context.user_data.get('editing_prompt') is False
    mock_update.message.reply_text.assert_called_once_with(
        "Отмена обновления системного промпта.",
        reply_markup=get_main_keyboard()
    )

async def test_handle_message_extra_functions(mock_update, mock_context, mocker):
    mock_update.message.text = "Доп функции"
    await handle_message(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with(
        "Выберите действие:",
        reply_markup=get_extra_functions_keyboard()
    )

async def test_handle_message_back_from_extra(mock_update, mock_context, mocker):
    mock_update.message.text = "Назад"
    mock_context.user_data['editing_prompt'] = False
    await handle_message(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with(
        'Выберите действие: (Или начните диалог)',
        reply_markup=get_main_keyboard()
    )

async def test_handle_unsupported_document(mock_update, mock_context, mocker):
    mock_update.message.document = MagicMock()
    mock_update.message.document.file_name = "test.zip"
    mock_update.message.text = None
    mock_process_message = mocker.patch('handlers.process_message', new_callable=AsyncMock)
    await handle_message(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with("Данный файл не поддерживается.")
    mock_process_message.assert_not_called()

async def test_handle_voice_transcription_error(mock_update, mock_context, mocker):
    mock_voice = MagicMock(spec=Voice)
    mock_update.message.voice = mock_voice
    mock_update.message.text = None
    error_message = "Ошибка Gemini API: Квота"
    mocker.patch('handlers.audio_to_text', new_callable=AsyncMock, side_effect=Exception(error_message))
    mock_process_message = mocker.patch('handlers.process_message', new_callable=AsyncMock)

    # Мокируем download_as_bytearray, чтобы он не мешал проверке ошибки транскрипции
    mock_download_method = mocker.patch('telegram.File.download_as_bytearray', new_callable=AsyncMock, return_value=b'fake_file_content')

    await handle_voice(mock_update, mock_context)

    mock_process_message.assert_not_called()
    mock_update.message.reply_text.assert_called_once_with(
        f"Произошла ошибка при обработке голосового сообщения: {error_message}"
    )
    expected_filename = f"tempvoice_{mock_update.effective_user.id}.ogg"
    handlers.os.remove.assert_called_once_with(expected_filename)
    # Проверяем, что скачивание все равно было вызвано до ошибки
    mock_voice.get_file.assert_called_once()
    mock_file_returned = await mock_voice.get_file()
    mock_file_returned.download_as_bytearray.assert_called_once()
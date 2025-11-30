"""Главный файл Telegram бота WOWsilizing."""
import asyncio
import logging
import os
import sys
from typing import Optional, Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database import db
from video_processor import VideoProcessor
from ai_processor import ai_processor
from utils import (
    parse_batch_timecodes,
    apply_padding_to_timecodes,
    check_overlapping_segments,
    is_youtube_url,
    download_youtube_video,
    validate_file_size,
    cleanup_temp_files,
    extract_frame,
    get_video_info,
    get_video_duration,
    format_duration,
    format_file_size,
    create_zip_archive,
    generate_temp_filename
)

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Очереди задач для каждого пользователя
user_queues: Dict[int, asyncio.Queue] = {}
user_current_video: Dict[int, str] = {}


# FSM состояния
class VideoStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_timecodes = State()
    waiting_for_template_name = State()
    processing = State()


# Утилиты для клавиатур
def get_main_keyboard(is_premium: bool = False) -> InlineKeyboardMarkup:
    """Создание главной клавиатуры."""
    buttons = [
        [InlineKeyboardButton(text="✂️ Нарезка видео", callback_data="cut")],
        [InlineKeyboardButton(text="🎵 Извлечь аудио", callback_data="audio")],
        [InlineKeyboardButton(text="📱 В вертикальный формат", callback_data="vertical")],
        [InlineKeyboardButton(text="🗜 Сжать видео", callback_data="compress")],
        [InlineKeyboardButton(text="🔇 Убрать шум", callback_data="noise")],
        [InlineKeyboardButton(text="🔊 Нормализовать звук", callback_data="normalize")],
        [InlineKeyboardButton(text="🔗 Склеить видео", callback_data="merge")],
    ]
    
    if is_premium:
        buttons.extend([
            [InlineKeyboardButton(text="📝 Субтитры (AI)", callback_data="subtitles")],
            [InlineKeyboardButton(text="🌐 Перевести субтитры", callback_data="translate")],
            [InlineKeyboardButton(text="🎤 Озвучка текста (TTS)", callback_data="tts")],
            [InlineKeyboardButton(text="⭐ Авто-хайлайты", callback_data="highlights")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        ])
    
    buttons.append([InlineKeyboardButton(text="📜 История", callback_data="history")])
    buttons.append([InlineKeyboardButton(text="📁 Шаблоны", callback_data="templates")])
    buttons.append([InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_audio_format_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора формата аудио."""
    buttons = [
        [
            InlineKeyboardButton(text="MP3", callback_data="audio_mp3"),
            InlineKeyboardButton(text="WAV", callback_data="audio_wav"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tts_provider_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора провайдера TTS."""
    buttons = [
        [InlineKeyboardButton(text="OpenAI TTS", callback_data="tts_openai")],
        [InlineKeyboardButton(text="Google AI Studio", callback_data="tts_google")],
        [InlineKeyboardButton(text="11Labs", callback_data="tts_elevenlabs")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Обработчики команд
@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start."""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    is_premium = await db.is_premium(username)
    
    await db.add_user(user_id, username, is_premium)
    
    keyboard = get_main_keyboard(is_premium)
    await message.answer(config.MESSAGES["start"], reply_markup=keyboard)


@dp.message(Command("cut"))
async def cmd_cut(message: Message, state: FSMContext):
    """Команда для нарезки видео."""
    await message.answer(
        "✂️ Отправьте видео или YouTube ссылку, затем укажите таймкоды для нарезки.\n\n"
        "Форматы таймкодов:\n"
        "• 00:00-01:30\n"
        "• 1:30-3:45\n"
        "• Несколько сегментов (по одному на строку)"
    )
    await state.set_state(VideoStates.waiting_for_video)


@dp.message(Command("audio"))
async def cmd_audio(message: Message):
    """Команда для извлечения аудио."""
    await message.answer(
        "🎵 Отправьте видео для извлечения аудио:",
        reply_markup=get_audio_format_keyboard()
    )


@dp.message(Command("vertical"))
async def cmd_vertical(message: Message):
    """Команда для конвертации в вертикальный формат."""
    await message.answer("📱 Отправьте видео для конвертации в вертикальный формат 9:16")


@dp.message(Command("subtitles"))
async def cmd_subtitles(message: Message):
    """Команда для генерации субтитров (премиум)."""
    username = message.from_user.username or ""
    is_premium = await db.is_premium(username)
    
    if not is_premium:
        await message.answer(config.MESSAGES["premium_only"])
        return
    
    await message.answer("📝 Отправьте видео для генерации субтитров")


@dp.message(Command("history"))
async def cmd_history(message: Message):
    """Показать историю операций."""
    user_id = message.from_user.id
    history = await db.get_history(user_id, limit=10)
    
    if not history:
        await message.answer("📜 История пуста")
        return
    
    text = "📜 Ваша история операций:\n\n"
    for item in history:
        timestamp = item['timestamp']
        video_name = item['video_name']
        operation = item['operation']
        duration = item.get('duration', 0)
        
        duration_str = format_duration(duration) if duration else "N/A"
        text += f"• {timestamp}\n  📹 {video_name}\n  ⚙️ {operation}\n  ⏱ {duration_str}\n\n"
    
    await message.answer(text)


@dp.message(Command("templates"))
async def cmd_templates(message: Message):
    """Управление шаблонами."""
    user_id = message.from_user.id
    templates = await db.get_user_templates(user_id)
    
    if not templates:
        await message.answer("⚙️ У вас нет сохраненных шаблонов")
        return
    
    text = "⚙️ Ваши шаблоны:\n\n"
    for template_name in templates:
        text += f"• {template_name}\n"
    
    text += "\nИспользуйте: /use_template <название>"
    await message.answer(text)


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика использования (премиум)."""
    username = message.from_user.username or ""
    is_premium = await db.is_premium(username)
    
    if not is_premium:
        await message.answer(config.MESSAGES["premium_only"])
        return
    
    user_id = message.from_user.id
    stats = await db.get_usage_stats(user_id)
    
    text = f"""📊 Ваша статистика:

🔢 API запросов: {stats['api_calls']}
⏱ Минут обработано: {stats['minutes_processed']:.1f}
📅 Последний сброс: {stats.get('last_reset', 'N/A')}
"""
    
    await message.answer(text)


@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    """Настройки бота."""
    user_id = message.from_user.id
    padding_settings = await db.get_padding_settings(user_id)
    
    start_padding = padding_settings['start_padding']
    end_padding = padding_settings['end_padding']
    
    text = "⚙️ Настройки нарезки\n\n"
    text += "Запас времени (чтобы не обрезать речь):\n\n"
    
    # Кнопки для выбора начального запаса
    text += f"Начало: "
    start_buttons = []
    for sec in [0, 1, 2, 3, 5]:
        mark = "✅" if sec == start_padding else ""
        start_buttons.append(
            InlineKeyboardButton(
                text=f"{mark} {sec} сек" if mark else f"{sec} сек",
                callback_data=f"padding_start_{sec}"
            )
        )
    
    # Кнопки для выбора конечного запаса
    text += f"\nКонец: "
    end_buttons = []
    for sec in [0, 1, 2, 3, 5]:
        mark = "✅" if sec == end_padding else ""
        end_buttons.append(
            InlineKeyboardButton(
                text=f"{mark} {sec} сек" if mark else f"{sec} сек",
                callback_data=f"padding_end_{sec}"
            )
        )
    
    text += f"\n\n💡 Рекомендуется 2-3 секунды для сохранения речи\n"
    text += f"\n📊 Текущие настройки:\n"
    text += f"Начало: {start_padding} сек\n"
    text += f"Конец: {end_padding} сек"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        start_buttons[:3],  # Первая строка: 0, 1, 2
        start_buttons[3:],  # Вторая строка: 3, 5
        end_buttons[:3],    # Третья строка: 0, 1, 2
        end_buttons[3:],    # Четвертая строка: 3, 5
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])
    
    # Добавляем подписи для строк
    text = "⚙️ Настройки нарезки\n\n"
    text += "Запас времени (чтобы не обрезать речь):\n\n"
    text += f"💡 Рекомендуется 2-3 секунды для сохранения речи\n\n"
    text += f"📊 Текущие настройки:\n"
    text += f"Начало: {start_padding} сек\n"
    text += f"Конец: {end_padding} сек\n\n"
    text += "Выберите новое значение:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начало:", callback_data="padding_label_start")],
        start_buttons[:3],
        start_buttons[3:],
        [InlineKeyboardButton(text="Конец:", callback_data="padding_label_end")],
        end_buttons[:3],
        end_buttons[3:],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


# Обработчики callback запросов
@dp.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery):
    """Возврат в главное меню."""
    username = callback.from_user.username or ""
    is_premium = await db.is_premium(username)
    
    keyboard = get_main_keyboard(is_premium)
    await callback.message.edit_text(config.MESSAGES["start"], reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("padding_"))
async def callback_padding(callback: CallbackQuery):
    """Callback для настройки padding."""
    user_id = callback.from_user.id
    data_parts = callback.data.split("_")
    
    # Игнорируем callback для меток (label)
    if len(data_parts) == 3 and data_parts[1] == "label":
        await callback.answer()
        return
    
    if len(data_parts) != 3:
        await callback.answer()
        return
    
    padding_type = data_parts[1]  # "start" или "end"
    padding_value = int(data_parts[2])
    
    # Получаем текущие настройки
    padding_settings = await db.get_padding_settings(user_id)
    
    # Обновляем нужное значение
    if padding_type == "start":
        await db.set_padding_settings(user_id, padding_value, padding_settings['end_padding'])
    elif padding_type == "end":
        await db.set_padding_settings(user_id, padding_settings['start_padding'], padding_value)
    
    # Обновляем сообщение
    padding_settings = await db.get_padding_settings(user_id)
    start_padding = padding_settings['start_padding']
    end_padding = padding_settings['end_padding']
    
    # Кнопки для выбора начального запаса
    start_buttons = []
    for sec in [0, 1, 2, 3, 5]:
        mark = "✅" if sec == start_padding else ""
        start_buttons.append(
            InlineKeyboardButton(
                text=f"{mark} {sec} сек" if mark else f"{sec} сек",
                callback_data=f"padding_start_{sec}"
            )
        )
    
    # Кнопки для выбора конечного запаса
    end_buttons = []
    for sec in [0, 1, 2, 3, 5]:
        mark = "✅" if sec == end_padding else ""
        end_buttons.append(
            InlineKeyboardButton(
                text=f"{mark} {sec} сек" if mark else f"{sec} сек",
                callback_data=f"padding_end_{sec}"
            )
        )
    
    text = "⚙️ Настройки нарезки\n\n"
    text += "Запас времени (чтобы не обрезать речь):\n\n"
    text += f"💡 Рекомендуется 2-3 секунды для сохранения речи\n\n"
    text += f"📊 Текущие настройки:\n"
    text += f"Начало: {start_padding} сек\n"
    text += f"Конец: {end_padding} сек\n\n"
    text += "Выберите новое значение:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начало:", callback_data="padding_label_start")],
        start_buttons[:3],
        start_buttons[3:],
        [InlineKeyboardButton(text="Конец:", callback_data="padding_label_end")],
        end_buttons[:3],
        end_buttons[3:],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer("✅ Настройки обновлены")


@dp.callback_query(F.data == "settings")
async def callback_settings(callback: CallbackQuery):
    """Callback для настроек."""
    user_id = callback.from_user.id
    padding_settings = await db.get_padding_settings(user_id)
    
    start_padding = padding_settings['start_padding']
    end_padding = padding_settings['end_padding']
    
    # Кнопки для выбора начального запаса
    start_buttons = []
    for sec in [0, 1, 2, 3, 5]:
        mark = "✅" if sec == start_padding else ""
        start_buttons.append(
            InlineKeyboardButton(
                text=f"{mark} {sec} сек" if mark else f"{sec} сек",
                callback_data=f"padding_start_{sec}"
            )
        )
    
    # Кнопки для выбора конечного запаса
    end_buttons = []
    for sec in [0, 1, 2, 3, 5]:
        mark = "✅" if sec == end_padding else ""
        end_buttons.append(
            InlineKeyboardButton(
                text=f"{mark} {sec} сек" if mark else f"{sec} сек",
                callback_data=f"padding_end_{sec}"
            )
        )
    
    text = "⚙️ Настройки нарезки\n\n"
    text += "Запас времени (чтобы не обрезать речь):\n\n"
    text += f"💡 Рекомендуется 2-3 секунды для сохранения речи\n\n"
    text += f"📊 Текущие настройки:\n"
    text += f"Начало: {start_padding} сек\n"
    text += f"Конец: {end_padding} сек\n\n"
    text += "Выберите новое значение:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начало:", callback_data="padding_label_start")],
        start_buttons[:3],
        start_buttons[3:],
        [InlineKeyboardButton(text="Конец:", callback_data="padding_label_end")],
        end_buttons[:3],
        end_buttons[3:],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "cut")
async def callback_cut(callback: CallbackQuery, state: FSMContext):
    """Callback для нарезки видео."""
    await callback.message.answer(
        "✂️ Отправьте видео или YouTube ссылку для нарезки"
    )
    await state.set_state(VideoStates.waiting_for_video)
    await callback.answer()


@dp.callback_query(F.data.startswith("audio_"))
async def callback_audio(callback: CallbackQuery):
    """Callback для извлечения аудио."""
    audio_format = callback.data.split("_")[1]  # mp3 или wav
    
    user_id = callback.from_user.id
    video_path = user_current_video.get(user_id)
    
    if not video_path:
        await callback.message.answer(config.MESSAGES["no_video"])
        await callback.answer()
        return
    
    progress_msg = await callback.message.answer("⏳ Извлекаю аудио...")
    
    try:
        output_path = await VideoProcessor.extract_audio(
            video_path,
            output_format=audio_format
        )
        
        if output_path:
            await progress_msg.edit_text("✅ Аудио извлечено!")
            
            # Отправляем файл
            audio_file = FSInputFile(output_path)
            await callback.message.answer_audio(audio_file)
            
            # Сохраняем в историю
            await db.add_history(
                user_id,
                os.path.basename(video_path),
                f"extract_audio_{audio_format}"
            )
            
            # Очищаем временные файлы
            cleanup_temp_files(output_path)
        else:
            await progress_msg.edit_text("❌ Ошибка при извлечении аудио")
    
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()


@dp.callback_query(F.data == "vertical")
async def callback_vertical(callback: CallbackQuery):
    """Callback для конвертации в вертикальный формат."""
    user_id = callback.from_user.id
    video_path = user_current_video.get(user_id)
    
    if not video_path:
        await callback.message.answer(config.MESSAGES["no_video"])
        await callback.answer()
        return
    
    progress_msg = await callback.message.answer("⏳ Конвертирую в вертикальный формат...")
    
    try:
        output_path = await VideoProcessor.convert_to_vertical(video_path)
        
        if output_path:
            await progress_msg.edit_text("✅ Видео конвертировано!")
            
            video_file = FSInputFile(output_path)
            await callback.message.answer_video(video_file)
            
            await db.add_history(user_id, os.path.basename(video_path), "vertical")
            
            cleanup_temp_files(output_path)
        else:
            await progress_msg.edit_text("❌ Ошибка при конвертации")
    
    except Exception as e:
        logger.error(f"Error converting to vertical: {e}")
        await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()


@dp.callback_query(F.data == "compress")
async def callback_compress(callback: CallbackQuery):
    """Callback для сжатия видео."""
    user_id = callback.from_user.id
    video_path = user_current_video.get(user_id)
    
    if not video_path:
        await callback.message.answer(config.MESSAGES["no_video"])
        await callback.answer()
        return
    
    progress_msg = await callback.message.answer("⏳ Сжимаю видео (CRF=23)...")
    
    try:
        output_path = await VideoProcessor.compress_video(video_path, crf=23)
        
        if output_path:
            # Получаем информацию о размерах файлов
            original_size = os.path.getsize(video_path)
            compressed_size = os.path.getsize(output_path)
            savings = (1 - compressed_size / original_size) * 100
            
            await progress_msg.edit_text(
                f"✅ Видео сжато!\n\n"
                f"Оригинал: {format_file_size(original_size)}\n"
                f"Сжатое: {format_file_size(compressed_size)}\n"
                f"Экономия: {savings:.1f}%"
            )
            
            video_file = FSInputFile(output_path)
            await callback.message.answer_video(video_file)
            
            await db.add_history(user_id, os.path.basename(video_path), "compress")
            
            cleanup_temp_files(output_path)
        else:
            await progress_msg.edit_text("❌ Ошибка при сжатии")
    
    except Exception as e:
        logger.error(f"Error compressing video: {e}")
        await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()


@dp.callback_query(F.data == "noise")
async def callback_noise(callback: CallbackQuery):
    """Callback для шумоподавления."""
    user_id = callback.from_user.id
    video_path = user_current_video.get(user_id)
    
    if not video_path:
        await callback.message.answer(config.MESSAGES["no_video"])
        await callback.answer()
        return
    
    progress_msg = await callback.message.answer("⏳ Применяю шумоподавление...")
    
    try:
        output_path = await VideoProcessor.reduce_noise(video_path)
        
        if output_path:
            await progress_msg.edit_text("✅ Шумоподавление применено!")
            
            video_file = FSInputFile(output_path)
            await callback.message.answer_video(video_file)
            
            await db.add_history(user_id, os.path.basename(video_path), "noise_reduction")
            
            cleanup_temp_files(output_path)
        else:
            await progress_msg.edit_text("❌ Ошибка при шумоподавлении")
    
    except Exception as e:
        logger.error(f"Error reducing noise: {e}")
        await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()


@dp.callback_query(F.data == "normalize")
async def callback_normalize(callback: CallbackQuery):
    """Callback для нормализации звука."""
    user_id = callback.from_user.id
    video_path = user_current_video.get(user_id)
    
    if not video_path:
        await callback.message.answer(config.MESSAGES["no_video"])
        await callback.answer()
        return
    
    progress_msg = await callback.message.answer("⏳ Нормализую звук...")
    
    try:
        output_path = await VideoProcessor.normalize_audio(video_path)
        
        if output_path:
            await progress_msg.edit_text("✅ Звук нормализован!")
            
            video_file = FSInputFile(output_path)
            await callback.message.answer_video(video_file)
            
            await db.add_history(user_id, os.path.basename(video_path), "normalize")
            
            cleanup_temp_files(output_path)
        else:
            await progress_msg.edit_text("❌ Ошибка при нормализации")
    
    except Exception as e:
        logger.error(f"Error normalizing audio: {e}")
        await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()


@dp.callback_query(F.data == "subtitles")
async def callback_subtitles(callback: CallbackQuery):
    """Callback для генерации субтитров (премиум)."""
    username = callback.from_user.username or ""
    is_premium = await db.is_premium(username)
    
    if not is_premium:
        await callback.message.answer(config.MESSAGES["premium_only"])
        await callback.answer()
        return
    
    user_id = callback.from_user.id
    video_path = user_current_video.get(user_id)
    
    if not video_path:
        await callback.message.answer(config.MESSAGES["no_video"])
        await callback.answer()
        return
    
    progress_msg = await callback.message.answer("⏳ Генерирую субтитры с помощью Whisper AI...")
    
    try:
        subtitles_path = await ai_processor.generate_subtitles(video_path, language="auto")
        
        if subtitles_path:
            await progress_msg.edit_text("✅ Субтитры сгенерированы!")
            
            srt_file = FSInputFile(subtitles_path)
            await callback.message.answer_document(srt_file, caption="📝 Субтитры готовы")
            
            await db.add_history(user_id, os.path.basename(video_path), "subtitles")
            await db.add_api_usage(user_id, api_calls=1)
            
            cleanup_temp_files(subtitles_path)
        else:
            await progress_msg.edit_text("❌ Ошибка при генерации субтитров")
    
    except Exception as e:
        logger.error(f"Error generating subtitles: {e}")
        await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()


@dp.callback_query(F.data == "highlights")
async def callback_highlights(callback: CallbackQuery):
    """Callback для автоматических хайлайтов (премиум)."""
    username = callback.from_user.username or ""
    is_premium = await db.is_premium(username)
    
    if not is_premium:
        await callback.message.answer(config.MESSAGES["premium_only"])
        await callback.answer()
        return
    
    user_id = callback.from_user.id
    video_path = user_current_video.get(user_id)
    
    if not video_path:
        await callback.message.answer(config.MESSAGES["no_video"])
        await callback.answer()
        return
    
    progress_msg = await callback.message.answer("⏳ Анализирую видео для поиска интересных моментов...")
    
    try:
        highlights = await ai_processor.analyze_video_for_highlights(video_path, target_duration=60)
        
        if highlights:
            text = "⭐ Найденные хайлайты:\n\n"
            for i, highlight in enumerate(highlights[:5], 1):  # Показываем топ-5
                text += f"{i}. {highlight['start']}-{highlight['end']}\n"
                text += f"   📝 {highlight['description']}\n"
                text += f"   ⭐ Оценка: {highlight['score']}/10\n\n"
            
            await progress_msg.edit_text(text)
            
            await db.add_history(user_id, os.path.basename(video_path), "highlights")
            await db.add_api_usage(user_id, api_calls=1)
        else:
            await progress_msg.edit_text("❌ Не удалось найти хайлайты")
    
    except Exception as e:
        logger.error(f"Error finding highlights: {e}")
        await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()


# Обработчик видео файлов
@dp.message(F.video)
async def handle_video(message: Message, state: FSMContext):
    """Обработка видео файлов."""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    is_premium = await db.is_premium(username)
    
    # Проверка размера файла
    file_size = message.video.file_size
    is_valid, error_msg = validate_file_size(file_size)
    
    if not is_valid:
        await message.answer(error_msg)
        return
    
    progress_msg = await message.answer(config.MESSAGES["downloading"])
    
    try:
        # Скачиваем видео
        file = await bot.get_file(message.video.file_id)
        file_path = generate_temp_filename()
        
        await bot.download_file(file.file_path, file_path)
        
        # Сохраняем путь к видео
        user_current_video[user_id] = file_path
        
        # Получаем информацию о видео
        video_info = await get_video_info(file_path)
        
        info_text = f"✅ Видео загружено!\n\n"
        info_text += f"📐 Разрешение: {video_info['width']}x{video_info['height']}\n"
        info_text += f"⏱ Длительность: {format_duration(video_info['duration'])}\n"
        info_text += f"💾 Размер: {format_file_size(file_size)}\n\n"
        info_text += "Выберите действие:"
        
        await progress_msg.edit_text(info_text, reply_markup=get_main_keyboard(is_premium))
        
        # Создаем превью
        preview_path = await extract_frame(file_path, time_seconds=1)
        if preview_path:
            photo = FSInputFile(preview_path)
            await message.answer_photo(photo, caption="🎬 Превью видео")
            cleanup_temp_files(preview_path)
    
    except Exception as e:
        logger.error(f"Error handling video: {e}")
        await progress_msg.edit_text(f"❌ Ошибка при загрузке видео: {str(e)}")


# Обработчик текстовых сообщений (таймкоды, YouTube ссылки)
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    """Обработка текстовых сообщений."""
    text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or ""
    is_premium = await db.is_premium(username)
    
    # Проверяем, является ли текст YouTube ссылкой
    if is_youtube_url(text):
        progress_msg = await message.answer(config.MESSAGES["downloading"])
        
        try:
            video_path = await download_youtube_video(text)
            
            if video_path:
                user_current_video[user_id] = video_path
                
                await progress_msg.edit_text(
                    "✅ Видео скачано с YouTube!\n\nВыберите действие:",
                    reply_markup=get_main_keyboard(is_premium)
                )
            else:
                await progress_msg.edit_text("❌ Ошибка при скачивании видео с YouTube")
        
        except Exception as e:
            logger.error(f"Error downloading YouTube video: {e}")
            await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
        
        return
    
    # Проверяем, содержит ли текст таймкоды
    timecodes = parse_batch_timecodes(text)
    
    if timecodes:
        video_path = user_current_video.get(user_id)
        
        if not video_path:
            await message.answer(config.MESSAGES["no_video"])
            return
        
        # Подтверждение нарезки
        count = len(timecodes)
        
        if count > config.MAX_BATCH_SEGMENTS:
            await message.answer(
                f"❌ Слишком много сегментов ({count}). "
                f"Максимум: {config.MAX_BATCH_SEGMENTS}"
            )
            return
        
        # Получаем настройки padding
        padding_settings = await db.get_padding_settings(user_id)
        start_padding = padding_settings['start_padding']
        end_padding = padding_settings['end_padding']
        
        # Получаем длительность видео для проверки границ
        video_duration = await get_video_duration(video_path)
        
        # Применяем padding к таймкодам
        padded_timecodes = apply_padding_to_timecodes(
            timecodes, 
            start_padding, 
            end_padding, 
            video_duration
        )
        
        confirmation_text = f"✂️ Найдено {count} отрезков\n"
        
        # Показываем информацию о padding
        if start_padding > 0 or end_padding > 0:
            confirmation_text += f"С запасом: +{start_padding} сек в начале, +{end_padding} сек в конце\n\n"
            
            # Показываем пример с padding
            if len(timecodes) > 0:
                orig_start, orig_end = timecodes[0]
                padded_start, padded_end = padded_timecodes[0]
                confirmation_text += f"Пример: {format_duration(orig_start)}-{format_duration(orig_end)} → "
                confirmation_text += f"{format_duration(padded_start)}-{format_duration(padded_end)}\n\n"
        else:
            confirmation_text += "Без запаса времени (точная нарезка)\n\n"
        
        # Проверяем на пересечения
        overlaps = check_overlapping_segments(padded_timecodes)
        if overlaps:
            confirmation_text += f"⚠️ Внимание: {len(overlaps)} сегментов пересекаются!\n\n"
        
        # Показываем первые 5 сегментов для проверки
        confirmation_text += "Первые сегменты:\n"
        for i, (start, end) in enumerate(padded_timecodes[:5], 1):
            confirmation_text += f"{i}. {format_duration(start)} - {format_duration(end)}\n"
        
        if count > 5:
            confirmation_text += f"... и еще {count - 5}\n"
        
        # Кнопки подтверждения
        confirm_buttons = [
            [
                InlineKeyboardButton(text="✅ Да, начать", callback_data=f"batch_cut_{count}"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Изменить запас", callback_data="settings"),
                InlineKeyboardButton(text="🚫 Без запаса", callback_data=f"batch_cut_nopad_{count}")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")
            ]
        ]
        
        # Сохраняем таймкоды в state (и оригинальные, и с padding)
        await state.update_data(
            timecodes=timecodes,
            padded_timecodes=padded_timecodes,
            video_duration=video_duration
        )
        
        await message.answer(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=confirm_buttons)
        )
        
        return
    
    # Если премиум, пробуем распарсить как естественный язык
    if is_premium:
        command = await ai_processor.parse_natural_language_command(text)
        
        if command:
            await message.answer(
                f"🤖 Распознана команда: {command['operation']}\n"
                f"Параметры: {command.get('parameters', {})}"
            )
            # TODO: Выполнить команду
            return
    
    # Если ничего не подошло
    await message.answer(
        "❓ Не удалось распознать команду.\n\n"
        "Отправьте видео или используйте команды:\n"
        "/start - главное меню\n"
        "/cut - нарезка видео\n"
        "/audio - извлечь аудио"
    )


@dp.callback_query(F.data.startswith("batch_cut_"))
async def callback_batch_cut(callback: CallbackQuery, state: FSMContext):
    """Callback для подтверждения пакетной нарезки."""
    user_id = callback.from_user.id
    video_path = user_current_video.get(user_id)
    
    if not video_path:
        await callback.message.answer(config.MESSAGES["no_video"])
        await callback.answer()
        return
    
    # Получаем таймкоды из state
    data = await state.get_data()
    
    # Определяем, нужно ли использовать padding
    use_padding = "nopad" not in callback.data
    
    if use_padding:
        # Используем таймкоды с padding
        timecodes = data.get('padded_timecodes', [])
        if not timecodes:
            # Fallback на оригинальные таймкоды, если padded отсутствуют
            timecodes = data.get('timecodes', [])
    else:
        # Используем оригинальные таймкоды без padding
        timecodes = data.get('timecodes', [])
    
    if not timecodes:
        await callback.message.answer("❌ Таймкоды не найдены")
        await callback.answer()
        return
    
    padding_info = " (с запасом)" if use_padding else " (без запаса)"
    progress_msg = await callback.message.answer(f"⏳ Начинаю пакетную нарезку{padding_info}...")
    
    try:
        output_files = []
        total = len(timecodes)
        
        # Функция для обновления прогресса
        async def update_progress(current, total):
            await progress_msg.edit_text(
                config.MESSAGES["processing_segment"].format(current=current, total=total)
            )
        
        # Нарезаем все сегменты
        output_files = await VideoProcessor.batch_cut_video(
            video_path,
            timecodes,
            progress_callback=update_progress
        )
        
        if output_files:
            await progress_msg.edit_text(
                f"✅ Нарезка завершена! Создано {len(output_files)} сегментов.\n\n"
                f"Отправляю файлы..."
            )
            
            # Если сегментов много, создаем ZIP архив
            if len(output_files) > 10:
                zip_path = generate_temp_filename("zip")
                if create_zip_archive(output_files, zip_path):
                    zip_file = FSInputFile(zip_path)
                    await callback.message.answer_document(
                        zip_file,
                        caption=f"📦 Все {len(output_files)} сегментов в архиве"
                    )
                    cleanup_temp_files(zip_path)
            else:
                # Отправляем каждый сегмент
                for i, file_path in enumerate(output_files, 1):
                    video_file = FSInputFile(file_path)
                    await callback.message.answer_video(
                        video_file,
                        caption=f"Сегмент {i}/{len(output_files)}"
                    )
            
            # Сохраняем в историю
            await db.add_history(
                user_id,
                os.path.basename(video_path),
                f"batch_cut_{len(output_files)}_segments{padding_info}"
            )
            
            # Очищаем временные файлы
            for file_path in output_files:
                cleanup_temp_files(file_path)
        else:
            await progress_msg.edit_text("❌ Ошибка при нарезке видео")
    
    except Exception as e:
        logger.error(f"Error batch cutting video: {e}")
        await progress_msg.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()


async def main():
    """Запуск бота."""
    logger.info("Starting WOWsilizing Bot...")
    
    # Инициализация базы данных
    await db.init_db()
    logger.info("Database initialized")
    
    # Очистка старого кеша при запуске
    await db.clean_old_cache()
    logger.info("Old cache cleaned")
    
    # Запуск polling
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")

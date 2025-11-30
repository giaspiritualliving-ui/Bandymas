"""AI обработка для премиум пользователей (Whisper, GPT, TTS)."""
import os
from typing import Optional, List, Dict, Any
import config
from utils import generate_temp_filename


class AIProcessor:
    """Класс для AI обработки видео и аудио (только для премиум)."""
    
    def __init__(self):
        self.openai_available = bool(config.OPENAI_API_KEY)
        self.google_available = bool(config.GOOGLE_API_KEY)
        self.elevenlabs_available = bool(config.ELEVENLABS_API_KEY)
    
    async def generate_subtitles(
        self,
        video_path: str,
        language: str = "auto",
        output_format: str = "srt"
    ) -> Optional[str]:
        """
        Генерация субтитров с помощью OpenAI Whisper.
        
        Args:
            video_path: Путь к видео
            language: Код языка (lt, ru, en, uk) или "auto"
            output_format: Формат субтитров (srt, vtt, txt)
        
        Returns:
            Путь к файлу субтитров или None
        """
        if not self.openai_available:
            print("OpenAI API key not configured")
            return None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            
            # Извлекаем аудио из видео
            from video_processor import VideoProcessor
            audio_path = await VideoProcessor.extract_audio(video_path, output_format="mp3")
            
            if not audio_path:
                return None
            
            # Отправляем на транскрибацию
            with open(audio_path, 'rb') as audio_file:
                if language == "auto":
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format=output_format
                    )
                else:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language,
                        response_format=output_format
                    )
            
            # Сохраняем субтитры
            subtitles_path = generate_temp_filename(output_format)
            with open(subtitles_path, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            # Удаляем временный аудио файл
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            return subtitles_path
        
        except Exception as e:
            print(f"Error generating subtitles: {e}")
            return None
    
    async def detect_language(self, video_path: str) -> Optional[str]:
        """
        Определение языка видео с помощью Whisper.
        
        Returns:
            Код языка (lt, ru, en, uk и т.д.) или None
        """
        if not self.openai_available:
            return None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            
            # Извлекаем первые 30 секунд аудио
            from video_processor import VideoProcessor
            audio_path = await VideoProcessor.extract_audio(video_path, output_format="mp3")
            
            if not audio_path:
                return None
            
            # Используем Whisper для определения языка
            with open(audio_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="json"
                )
            
            # Удаляем временный файл
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            # Возвращаем определенный язык
            if hasattr(transcript, 'language'):
                return transcript.language
            
            return None
        
        except Exception as e:
            print(f"Error detecting language: {e}")
            return None
    
    async def translate_subtitles(
        self,
        subtitles_text: str,
        target_language: str,
        source_language: str = "auto"
    ) -> Optional[str]:
        """
        Перевод субтитров с помощью GPT.
        
        Args:
            subtitles_text: Текст субтитров
            target_language: Целевой язык (ru, en, lt, uk)
            source_language: Исходный язык или "auto"
        
        Returns:
            Переведенный текст субтитров
        """
        if not self.openai_available:
            return None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            
            language_names = {
                "ru": "русский",
                "en": "английский",
                "lt": "литовский",
                "uk": "украинский"
            }
            
            target_lang_name = language_names.get(target_language, target_language)
            
            prompt = f"Переведи следующие субтитры на {target_lang_name} язык, сохраняя временные метки и форматирование:\n\n{subtitles_text}"
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты профессиональный переводчик субтитров. Переводи точно, сохраняя тайминг и форматирование."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            print(f"Error translating subtitles: {e}")
            return None
    
    async def text_to_speech_openai(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1"
    ) -> Optional[str]:
        """
        Преобразование текста в речь с помощью OpenAI TTS.
        
        Args:
            text: Текст для озвучки
            voice: Голос (alloy, echo, fable, onyx, nova, shimmer)
            model: Модель (tts-1, tts-1-hd)
        
        Returns:
            Путь к аудио файлу
        """
        if not self.openai_available:
            return None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            
            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text
            )
            
            output_path = generate_temp_filename("mp3")
            response.stream_to_file(output_path)
            
            return output_path
        
        except Exception as e:
            print(f"Error with OpenAI TTS: {e}")
            return None
    
    async def text_to_speech_google(
        self,
        text: str,
        language: str = "ru-RU",
        voice_name: str = None
    ) -> Optional[str]:
        """
        Преобразование текста в речь с помощью Google AI Studio TTS.
        
        Args:
            text: Текст для озвучки
            language: Код языка (ru-RU, en-US, lt-LT, uk-UA)
            voice_name: Имя голоса (если None, используется по умолчанию)
        
        Returns:
            Путь к аудио файлу
        """
        if not self.google_available:
            return None
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=config.GOOGLE_API_KEY)
            
            # Используем Google Text-to-Speech API
            from google.cloud import texttospeech
            
            client = texttospeech.TextToSpeechClient()
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code=language,
                name=voice_name if voice_name else None
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            output_path = generate_temp_filename("mp3")
            with open(output_path, 'wb') as out:
                out.write(response.audio_content)
            
            return output_path
        
        except Exception as e:
            print(f"Error with Google TTS: {e}")
            return None
    
    async def text_to_speech_elevenlabs(
        self,
        text: str,
        voice_id: str = None,
        model_id: str = "eleven_multilingual_v2"
    ) -> Optional[str]:
        """
        Преобразование текста в речь с помощью 11Labs.
        
        Args:
            text: Текст для озвучки
            voice_id: ID голоса из библиотеки 11Labs
            model_id: ID модели
        
        Returns:
            Путь к аудио файлу
        """
        if not self.elevenlabs_available:
            return None
        
        try:
            from elevenlabs.client import ElevenLabs
            from elevenlabs import save
            
            client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
            
            # Если voice_id не указан, используем первый доступный голос
            if not voice_id:
                voices = client.voices.get_all()
                if voices and len(voices.voices) > 0:
                    voice_id = voices.voices[0].voice_id
            
            audio = client.generate(
                text=text,
                voice=voice_id,
                model=model_id
            )
            
            output_path = generate_temp_filename("mp3")
            save(audio, output_path)
            
            return output_path
        
        except Exception as e:
            print(f"Error with 11Labs TTS: {e}")
            return None
    
    async def get_available_voices_elevenlabs(self) -> List[Dict[str, str]]:
        """
        Получение списка доступных голосов из 11Labs.
        
        Returns:
            Список словарей с информацией о голосах
        """
        if not self.elevenlabs_available:
            return []
        
        try:
            from elevenlabs.client import ElevenLabs
            
            client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
            voices = client.voices.get_all()
            
            result = []
            for voice in voices.voices:
                result.append({
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": voice.category if hasattr(voice, 'category') else "unknown"
                })
            
            return result
        
        except Exception as e:
            print(f"Error getting 11Labs voices: {e}")
            return []
    
    async def analyze_video_for_highlights(
        self,
        video_path: str,
        target_duration: int = 60
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Анализ видео для определения интересных моментов (для shorts).
        Использует GPT для анализа транскрипта.
        
        Args:
            video_path: Путь к видео
            target_duration: Целевая длительность каждого хайлайта (сек)
        
        Returns:
            Список сегментов с временными метками и описаниями
        """
        if not self.openai_available:
            return None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            
            # Сначала получаем транскрипт
            subtitles_path = await self.generate_subtitles(video_path, output_format="srt")
            if not subtitles_path:
                return None
            
            with open(subtitles_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
            
            # Анализируем транскрипт с помощью GPT
            prompt = f"""Проанализируй следующий транскрипт видео и найди самые интересные моменты для создания коротких видео (shorts) длительностью около {target_duration} секунд каждое.

Для каждого момента укажи:
1. Временные метки начала и конца (в формате MM:SS)
2. Краткое описание момента (почему он интересен)
3. Оценку интересности от 1 до 10

Транскрипт:
{transcript}

Верни результат в формате JSON:
[
  {{
    "start": "00:15",
    "end": "01:10",
    "description": "Описание момента",
    "score": 8
  }}
]
"""
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты эксперт по созданию вирусного контента. Находи самые интересные моменты в видео."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            # Парсим JSON ответ
            import json
            result_text = response.choices[0].message.content
            
            # Извлекаем JSON из ответа
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                highlights = json.loads(json_match.group())
                
                # Конвертируем временные метки в секунды
                for highlight in highlights:
                    from utils import parse_timecode
                    highlight['start_seconds'] = parse_timecode(highlight['start'])
                    highlight['end_seconds'] = parse_timecode(highlight['end'])
                
                # Сортируем по оценке
                highlights.sort(key=lambda x: x.get('score', 0), reverse=True)
                
                return highlights
            
            return None
        
        except Exception as e:
            print(f"Error analyzing video for highlights: {e}")
            return None
    
    async def generate_video_summary(self, video_path: str) -> Optional[str]:
        """
        Генерация краткого резюме видео с помощью GPT.
        
        Args:
            video_path: Путь к видео
        
        Returns:
            Текст резюме
        """
        if not self.openai_available:
            return None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            
            # Получаем транскрипт
            subtitles_path = await self.generate_subtitles(video_path, output_format="txt")
            if not subtitles_path:
                return None
            
            with open(subtitles_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
            
            prompt = f"Создай краткое резюме следующего видео на русском языке:\n\n{transcript}"
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты помощник, который создает краткие и информативные резюме видео."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            print(f"Error generating video summary: {e}")
            return None
    
    async def parse_natural_language_command(self, command: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг команды на естественном языке с помощью GPT.
        
        Args:
            command: Команда на естественном языке (например, "вырежи с 1:30 до 3:45 и сожми")
        
        Returns:
            Словарь с распознанной операцией и параметрами
        """
        if not self.openai_available:
            return None
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            
            prompt = f"""Распознай команду обработки видео и верни результат в JSON формате.

Доступные операции:
- cut: вырезать сегмент (параметры: start, end)
- extract_audio: извлечь аудио (параметры: format)
- compress: сжать видео (параметры: quality)
- vertical: конвертировать в вертикальный формат
- noise_reduction: шумоподавление
- normalize: нормализация звука
- merge: склеить видео

Команда: "{command}"

Верни JSON:
{{
  "operation": "название_операции",
  "parameters": {{параметры}}
}}
"""
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты помощник, который распознает команды обработки видео."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            import json
            import re
            result_text = response.choices[0].message.content
            
            # Извлекаем JSON
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return None
        
        except Exception as e:
            print(f"Error parsing natural language command: {e}")
            return None


# Глобальный экземпляр AI процессора
ai_processor = AIProcessor()

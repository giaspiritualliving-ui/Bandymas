"""Вспомогательные функции для бота."""
import re
import os
import asyncio
import subprocess
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import config


def parse_timecode(timecode: str) -> Optional[float]:
    """
    Парсинг таймкода в секунды.
    Поддерживаемые форматы: HH:MM:SS, MM:SS, SS, H:M:S
    """
    try:
        # Удаляем пробелы
        timecode = timecode.strip()
        
        # Разделяем по ":"
        parts = timecode.split(":")
        
        if len(parts) == 3:  # HH:MM:SS
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:  # MM:SS
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        elif len(parts) == 1:  # SS
            return float(parts[0])
        else:
            return None
    except (ValueError, AttributeError):
        return None


def parse_timecode_range(range_str: str) -> Optional[Tuple[float, float]]:
    """
    Парсинг диапазона таймкодов.
    Поддерживаемые форматы:
    - "00:00-01:59"
    - "0:0-1:59"
    - "00:00 - 01:59"
    - "00:00 to 01:59"
    - "от 00:00 до 01:59"
    """
    # Замена различных разделителей на "-"
    range_str = range_str.strip()
    range_str = re.sub(r'\s*(?:to|-|до)\s*', '-', range_str, flags=re.IGNORECASE)
    range_str = re.sub(r'от\s*', '', range_str, flags=re.IGNORECASE)
    
    # Разделение на начало и конец
    parts = range_str.split("-")
    if len(parts) != 2:
        return None
    
    start = parse_timecode(parts[0])
    end = parse_timecode(parts[1])
    
    if start is not None and end is not None and start < end:
        return (start, end)
    
    return None


def parse_batch_timecodes(text: str) -> List[Tuple[float, float]]:
    """
    Парсинг множественных таймкодов из текста.
    Поддерживает разделение по: новой строке, запятой, точке с запятой.
    """
    # Разделяем текст на строки
    lines = text.split('\n')
    
    timecodes = []
    for line in lines:
        # Также разделяем по запятым и точкам с запятой
        segments = re.split(r'[,;]', line)
        
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            
            # Пробуем распарсить как диапазон
            tc_range = parse_timecode_range(segment)
            if tc_range:
                timecodes.append(tc_range)
    
    return timecodes


def apply_padding_to_timecodes(
    timecodes: List[Tuple[float, float]],
    start_padding: float,
    end_padding: float,
    video_duration: Optional[float] = None
) -> List[Tuple[float, float]]:
    """
    Применение запаса времени (padding) к таймкодам.
    
    Args:
        timecodes: Список кортежей (начало, конец) в секундах
        start_padding: Запас в начале (секунды)
        end_padding: Запас в конце (секунды)
        video_duration: Длительность видео для проверки границ
    
    Returns:
        Список таймкодов с примененным padding
    """
    padded_timecodes = []
    
    for start, end in timecodes:
        # Применяем padding
        padded_start = start - start_padding
        padded_end = end + end_padding
        
        # Проверяем границы
        if padded_start < 0:
            padded_start = 0
        
        if video_duration and padded_end > video_duration:
            padded_end = video_duration
        
        # Убеждаемся, что начало все еще меньше конца
        if padded_start < padded_end:
            padded_timecodes.append((padded_start, padded_end))
    
    return padded_timecodes


def check_overlapping_segments(timecodes: List[Tuple[float, float]]) -> List[Tuple[int, int]]:
    """
    Проверка на пересечение сегментов после применения padding.
    
    Returns:
        Список индексов пересекающихся пар сегментов [(i, j), ...]
    """
    overlaps = []
    
    for i in range(len(timecodes)):
        for j in range(i + 1, len(timecodes)):
            start1, end1 = timecodes[i]
            start2, end2 = timecodes[j]
            
            # Проверяем пересечение
            if not (end1 <= start2 or end2 <= start1):
                overlaps.append((i, j))
    
    return overlaps


def format_duration(seconds: float) -> str:
    """Форматирование длительности в человекочитаемый формат."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_file_size(size_bytes: int) -> str:
    """Форматирование размера файла."""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} ТБ"


async def get_video_duration(file_path: str) -> Optional[float]:
    """Получение длительности видео с помощью ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, _ = await process.communicate()
        
        if process.returncode == 0:
            return float(stdout.decode().strip())
        
        return None
    except Exception as e:
        print(f"Error getting video duration: {e}")
        return None


async def get_video_info(file_path: str) -> Dict[str, Any]:
    """Получение информации о видео (разрешение, длительность, кодеки)."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,codec_name,duration',
            '-show_entries', 'format=duration,size',
            '-of', 'json',
            file_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, _ = await process.communicate()
        
        if process.returncode == 0:
            import json
            data = json.loads(stdout.decode())
            
            info = {
                'duration': 0,
                'width': 0,
                'height': 0,
                'codec': 'unknown',
                'size': 0
            }
            
            if 'format' in data:
                info['duration'] = float(data['format'].get('duration', 0))
                info['size'] = int(data['format'].get('size', 0))
            
            if 'streams' in data and len(data['streams']) > 0:
                stream = data['streams'][0]
                info['width'] = int(stream.get('width', 0))
                info['height'] = int(stream.get('height', 0))
                info['codec'] = stream.get('codec_name', 'unknown')
            
            return info
        
        return None
    except Exception as e:
        print(f"Error getting video info: {e}")
        return None


def cleanup_temp_files(*file_paths: str):
    """Удаление временных файлов."""
    for file_path in file_paths:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error cleaning up {file_path}: {e}")


def generate_temp_filename(extension: str = "mp4") -> str:
    """Генерация уникального имени для временного файла."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_str = os.urandom(4).hex()
    return os.path.join(config.TEMP_DIR, f"{timestamp}_{random_str}.{extension}")


async def download_youtube_video(url: str, output_path: str = None) -> Optional[str]:
    """
    Скачивание видео с YouTube используя yt-dlp.
    Возвращает путь к скачанному файлу.
    """
    try:
        if output_path is None:
            output_path = generate_temp_filename()
        
        cmd = [
            'yt-dlp',
            '-f', 'best[ext=mp4]/best',
            '-o', output_path,
            url
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        if process.returncode == 0 and os.path.exists(output_path):
            return output_path
        
        return None
    except Exception as e:
        print(f"Error downloading YouTube video: {e}")
        return None


def is_youtube_url(text: str) -> bool:
    """Проверка, является ли текст ссылкой на YouTube."""
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+',
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, text.strip()):
            return True
    
    return False


def validate_file_size(file_size: int) -> Tuple[bool, str]:
    """Проверка размера файла."""
    max_size_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
    
    if file_size > max_size_bytes:
        return False, f"Файл слишком большой ({format_file_size(file_size)}). Максимальный размер: {config.MAX_FILE_SIZE_MB} МБ"
    
    return True, ""


async def extract_frame(video_path: str, time_seconds: float = 0, output_path: str = None) -> Optional[str]:
    """Извлечение кадра из видео для предпросмотра."""
    try:
        if output_path is None:
            output_path = generate_temp_filename("jpg")
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', str(time_seconds),
            '-vframes', '1',
            '-y',
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        if process.returncode == 0 and os.path.exists(output_path):
            return output_path
        
        return None
    except Exception as e:
        print(f"Error extracting frame: {e}")
        return None


class ProgressCallback:
    """Колбэк для отслеживания прогресса обработки."""
    
    def __init__(self, total_duration: float, update_callback=None):
        self.total_duration = total_duration
        self.update_callback = update_callback
        self.last_progress = 0
    
    async def update(self, current_time: float):
        """Обновление прогресса."""
        if self.total_duration <= 0:
            return
        
        progress = int((current_time / self.total_duration) * 100)
        
        # Обновляем только если прогресс изменился на 10% или больше
        if progress >= self.last_progress + 10:
            self.last_progress = progress
            if self.update_callback:
                await self.update_callback(progress)
    
    def parse_ffmpeg_progress(self, line: str) -> Optional[float]:
        """Парсинг прогресса из вывода ffmpeg."""
        # Ищем строку с временем: "time=00:01:23.45"
        match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
        if match:
            hours = float(match.group(1))
            minutes = float(match.group(2))
            seconds = float(match.group(3))
            return hours * 3600 + minutes * 60 + seconds
        return None


def create_zip_archive(files: List[str], archive_path: str) -> bool:
    """Создание ZIP архива с файлами."""
    try:
        import zipfile
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                if os.path.exists(file_path):
                    # Добавляем файл в архив с его именем (без пути)
                    zipf.write(file_path, os.path.basename(file_path))
        
        return True
    except Exception as e:
        print(f"Error creating zip archive: {e}")
        return False


def detect_silence_periods(video_path: str, noise_threshold: str = "-30dB", 
                          min_silence_duration: float = 0.5) -> List[Tuple[float, float]]:
    """
    Определение периодов тишины в видео.
    Возвращает список (начало, конец) тихих сегментов.
    """
    try:
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-af', f'silencedetect=noise={noise_threshold}:d={min_silence_duration}',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.STDOUT)
        output = result.stdout
        
        # Парсинг вывода ffmpeg для определения тишины
        silence_start = None
        silence_periods = []
        
        for line in output.split('\n'):
            if 'silence_start' in line:
                match = re.search(r'silence_start: ([\d.]+)', line)
                if match:
                    silence_start = float(match.group(1))
            elif 'silence_end' in line and silence_start is not None:
                match = re.search(r'silence_end: ([\d.]+)', line)
                if match:
                    silence_end = float(match.group(1))
                    silence_periods.append((silence_start, silence_end))
                    silence_start = None
        
        return silence_periods
    except Exception as e:
        print(f"Error detecting silence: {e}")
        return []

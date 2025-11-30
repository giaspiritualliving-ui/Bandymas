"""Обработка видео с помощью ffmpeg (бесплатный уровень)."""
import asyncio
import os
import re
from typing import List, Optional, Callable, Tuple
import config
from utils import (
    generate_temp_filename, 
    get_video_duration, 
    format_duration,
    parse_batch_timecodes,
    ProgressCallback
)


class VideoProcessor:
    """Класс для обработки видео с помощью ffmpeg."""
    
    @staticmethod
    async def cut_video_segment(
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Нарезка видео по таймкодам.
        
        Args:
            input_path: Путь к входному видео
            output_path: Путь для сохранения результата
            start_time: Время начала в секундах
            end_time: Время конца в секундах
            progress_callback: Колбэк для обновления прогресса
        """
        try:
            duration = end_time - start_time
            
            cmd = [
                'ffmpeg',
                '-ss', str(start_time),
                '-i', input_path,
                '-t', str(duration),
                '-c', 'copy',  # Быстрая нарезка без перекодирования
                '-y',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            return process.returncode == 0 and os.path.exists(output_path)
        
        except Exception as e:
            print(f"Error cutting video: {e}")
            return False
    
    @staticmethod
    async def batch_cut_video(
        input_path: str,
        timecodes: List[Tuple[float, float]],
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """
        Пакетная нарезка видео по множественным таймкодам.
        ПРИОРИТЕТНАЯ ФУНКЦИЯ.
        
        Args:
            input_path: Путь к входному видео
            timecodes: Список кортежей (начало, конец) в секундах
            progress_callback: Колбэк для обновления прогресса (current, total)
        
        Returns:
            Список путей к созданным сегментам
        """
        output_files = []
        total_segments = len(timecodes)
        
        for idx, (start, end) in enumerate(timecodes, 1):
            output_path = generate_temp_filename()
            
            # Обновляем прогресс
            if progress_callback:
                await progress_callback(idx, total_segments)
            
            # Нарезаем сегмент
            success = await VideoProcessor.cut_video_segment(
                input_path, output_path, start, end
            )
            
            if success:
                output_files.append(output_path)
            else:
                print(f"Failed to cut segment {idx}: {start}-{end}")
        
        return output_files
    
    @staticmethod
    async def extract_audio(
        input_path: str,
        output_format: str = "mp3",
        bitrate: str = config.DEFAULT_AUDIO_BITRATE,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Извлечение аудио из видео.
        
        Args:
            input_path: Путь к видео
            output_format: Формат аудио (mp3, wav, m4a)
            bitrate: Битрейт аудио (например, "192k")
            progress_callback: Колбэк для прогресса
        """
        try:
            output_path = generate_temp_filename(output_format)
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-vn',  # Без видео
                '-acodec', 'libmp3lame' if output_format == 'mp3' else 'pcm_s16le',
                '-ab', bitrate,
                '-y',
                output_path
            ]
            
            if output_format == 'wav':
                cmd = [
                    'ffmpeg',
                    '-i', input_path,
                    '-vn',
                    '-acodec', 'pcm_s16le',
                    '-ar', str(config.DEFAULT_SAMPLE_RATE),
                    '-ac', '2',
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
            print(f"Error extracting audio: {e}")
            return None
    
    @staticmethod
    async def reduce_noise(
        input_path: str,
        output_path: str = None,
        noise_reduction: str = "afftdn",
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Шумоподавление в аудио/видео.
        
        Args:
            input_path: Путь к входному файлу
            output_path: Путь для сохранения (если None, создается автоматически)
            noise_reduction: Тип фильтра (afftdn, anlmdn)
        """
        try:
            if output_path is None:
                output_path = generate_temp_filename()
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-af', f'{noise_reduction}',
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
            print(f"Error reducing noise: {e}")
            return None
    
    @staticmethod
    async def normalize_audio(
        input_path: str,
        output_path: str = None,
        target_level: int = config.LOUDNESS_TARGET,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Нормализация громкости аудио.
        
        Args:
            input_path: Путь к входному файлу
            output_path: Путь для сохранения
            target_level: Целевой уровень громкости в LUFS
        """
        try:
            if output_path is None:
                output_path = generate_temp_filename()
            
            # Двухпроходная нормализация с loudnorm
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-af', f'loudnorm=I={target_level}:TP={config.LOUDNESS_TRUE_PEAK}:LRA={config.LOUDNESS_RANGE}',
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
            print(f"Error normalizing audio: {e}")
            return None
    
    @staticmethod
    async def compress_video(
        input_path: str,
        output_path: str = None,
        crf: int = config.DEFAULT_CRF,
        preset: str = config.DEFAULT_PRESET,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Сжатие видео с настраиваемым качеством.
        
        Args:
            input_path: Путь к видео
            output_path: Путь для сохранения
            crf: Constant Rate Factor (18-28, ниже = лучше качество)
            preset: Скорость кодирования (ultrafast, fast, medium, slow)
        """
        try:
            if output_path is None:
                output_path = generate_temp_filename()
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', config.DEFAULT_VIDEO_CODEC,
                '-crf', str(crf),
                '-preset', preset,
                '-c:a', config.DEFAULT_AUDIO_CODEC,
                '-b:a', config.DEFAULT_AUDIO_BITRATE,
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
            print(f"Error compressing video: {e}")
            return None
    
    @staticmethod
    async def convert_format(
        input_path: str,
        output_format: str,
        output_path: str = None,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Конвертация видео в другой формат.
        
        Args:
            input_path: Путь к видео
            output_format: Целевой формат (mp4, mov, webm, avi, mkv)
            output_path: Путь для сохранения
        """
        try:
            if output_path is None:
                output_path = generate_temp_filename(output_format)
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', config.DEFAULT_VIDEO_CODEC,
                '-c:a', config.DEFAULT_AUDIO_CODEC,
                '-y',
                output_path
            ]
            
            # Специальные настройки для некоторых форматов
            if output_format == 'webm':
                cmd = [
                    'ffmpeg',
                    '-i', input_path,
                    '-c:v', 'libvpx-vp9',
                    '-c:a', 'libopus',
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
            print(f"Error converting format: {e}")
            return None
    
    @staticmethod
    async def convert_to_vertical(
        input_path: str,
        output_path: str = None,
        target_aspect: str = "9:16",
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Конвертация видео в вертикальный формат 9:16 (для stories/reels).
        Обрезает центральную часть видео.
        
        Args:
            input_path: Путь к видео
            output_path: Путь для сохранения
            target_aspect: Целевое соотношение сторон
        """
        try:
            if output_path is None:
                output_path = generate_temp_filename()
            
            # Для 9:16 (вертикальное видео)
            # Формула: crop=in_h*9/16:in_h (обрезать ширину до высоты*9/16)
            crop_filter = "crop=ih*9/16:ih"
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-vf', crop_filter,
                '-c:v', config.DEFAULT_VIDEO_CODEC,
                '-c:a', 'copy',  # Копируем аудио без изменений
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
            print(f"Error converting to vertical: {e}")
            return None
    
    @staticmethod
    async def auto_segment_video(
        input_path: str,
        segment_duration: float = 60,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """
        Автоматическая сегментация видео на части заданной длительности.
        
        Args:
            input_path: Путь к видео
            segment_duration: Длительность каждого сегмента в секундах
        
        Returns:
            Список путей к созданным сегментам
        """
        try:
            # Получаем общую длительность видео
            total_duration = await get_video_duration(input_path)
            if not total_duration:
                return []
            
            # Вычисляем количество сегментов
            num_segments = int(total_duration / segment_duration) + 1
            
            output_files = []
            
            for i in range(num_segments):
                start_time = i * segment_duration
                if start_time >= total_duration:
                    break
                
                end_time = min((i + 1) * segment_duration, total_duration)
                output_path = generate_temp_filename()
                
                if progress_callback:
                    await progress_callback(i + 1, num_segments)
                
                success = await VideoProcessor.cut_video_segment(
                    input_path, output_path, start_time, end_time
                )
                
                if success:
                    output_files.append(output_path)
            
            return output_files
        
        except Exception as e:
            print(f"Error auto-segmenting video: {e}")
            return []
    
    @staticmethod
    async def remove_silence(
        input_path: str,
        output_path: str = None,
        silence_threshold: str = "-30dB",
        min_silence_duration: float = 0.5,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Удаление тишины из видео.
        
        Args:
            input_path: Путь к видео
            output_path: Путь для сохранения
            silence_threshold: Порог тишины
            min_silence_duration: Минимальная длительность тишины для удаления (сек)
        """
        try:
            if output_path is None:
                output_path = generate_temp_filename()
            
            # Используем фильтр silenceremove
            silence_filter = f"silenceremove=stop_periods=-1:stop_duration={min_silence_duration}:stop_threshold={silence_threshold}"
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-af', silence_filter,
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
            print(f"Error removing silence: {e}")
            return None
    
    @staticmethod
    async def merge_videos(
        input_paths: List[str],
        output_path: str = None,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Склейка нескольких видео в одно.
        
        Args:
            input_paths: Список путей к видео для склейки
            output_path: Путь для сохранения
        """
        try:
            if not input_paths:
                return None
            
            if output_path is None:
                output_path = generate_temp_filename()
            
            # Создаем временный файл со списком видео для concat
            concat_file = generate_temp_filename("txt")
            
            with open(concat_file, 'w') as f:
                for video_path in input_paths:
                    f.write(f"file '{os.path.abspath(video_path)}'\n")
            
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c', 'copy',
                '-y',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            # Удаляем временный файл
            if os.path.exists(concat_file):
                os.remove(concat_file)
            
            if process.returncode == 0 and os.path.exists(output_path):
                return output_path
            
            return None
        
        except Exception as e:
            print(f"Error merging videos: {e}")
            return None

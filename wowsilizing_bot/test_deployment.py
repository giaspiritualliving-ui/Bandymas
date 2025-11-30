#!/usr/bin/env python3
"""
Тест готовности к развертыванию WOWsilizing Bot
Проверяет все необходимые компоненты перед деплоем на Railway
"""

import os
import sys
import asyncio
from pathlib import Path

# Цвета для вывода
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    """Печать заголовка"""
    print(f"\n{BLUE}{'=' * 60}")
    print(f"{text}")
    print(f"{'=' * 60}{RESET}\n")

def print_success(text):
    """Печать успеха"""
    print(f"{GREEN}✓{RESET} {text}")

def print_error(text):
    """Печать ошибки"""
    print(f"{RED}✗{RESET} {text}")

def print_warning(text):
    """Печать предупреждения"""
    print(f"{YELLOW}⚠{RESET} {text}")

def print_info(text):
    """Печать информации"""
    print(f"{BLUE}ℹ{RESET} {text}")

class DeploymentTester:
    """Тестировщик готовности к развертыванию"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.errors = []
        self.warnings = []
        
    def check_file_exists(self, filename):
        """Проверка существования файла"""
        filepath = self.base_dir / filename
        if filepath.exists():
            print_success(f"Файл найден: {filename}")
            return True
        else:
            self.errors.append(f"Отсутствует файл: {filename}")
            print_error(f"Файл НЕ найден: {filename}")
            return False
    
    def check_required_files(self):
        """Проверка обязательных файлов"""
        print_header("1. ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ ФАЙЛОВ")
        
        required_files = [
            "bot.py",
            "config.py",
            "database.py",
            "video_processor.py",
            "ai_processor.py",
            "utils.py",
            "requirements.txt",
            "Dockerfile",
            ".dockerignore",
            "railway.json",
            ".env.example",
            "README.md",
            "DEPLOYMENT.md",
            "QUICK_START.md",
            "ENV_VARIABLES.md",
            "CHECKLIST.md",
            "POST_DEPLOYMENT.md"
        ]
        
        all_found = True
        for filename in required_files:
            if not self.check_file_exists(filename):
                all_found = False
        
        return all_found
    
    def check_python_syntax(self):
        """Проверка синтаксиса Python файлов"""
        print_header("2. ПРОВЕРКА СИНТАКСИСА PYTHON")
        
        python_files = [
            "bot.py",
            "config.py",
            "database.py",
            "video_processor.py",
            "ai_processor.py",
            "utils.py"
        ]
        
        all_valid = True
        for filename in python_files:
            filepath = self.base_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        compile(f.read(), filename, 'exec')
                    print_success(f"Синтаксис корректен: {filename}")
                except SyntaxError as e:
                    self.errors.append(f"Ошибка синтаксиса в {filename}: {e}")
                    print_error(f"Ошибка синтаксиса в {filename}: {e}")
                    all_valid = False
        
        return all_valid
    
    def check_imports(self):
        """Проверка импортов"""
        print_header("3. ПРОВЕРКА ИМПОРТОВ")
        
        required_modules = [
            "aiogram",
            "dotenv",
            "aiosqlite",
            "aiohttp",
            "aiofiles"
        ]
        
        optional_modules = [
            "openai",
            "google.generativeai",
            "elevenlabs"
        ]
        
        all_required = True
        for module in required_modules:
            try:
                __import__(module)
                print_success(f"Модуль установлен: {module}")
            except ImportError:
                self.errors.append(f"Отсутствует обязательный модуль: {module}")
                print_error(f"Модуль НЕ установлен: {module}")
                all_required = False
        
        for module in optional_modules:
            try:
                __import__(module)
                print_success(f"Опциональный модуль установлен: {module}")
            except ImportError:
                self.warnings.append(f"Отсутствует опциональный модуль: {module}")
                print_warning(f"Опциональный модуль НЕ установлен: {module}")
        
        return all_required
    
    def check_requirements(self):
        """Проверка requirements.txt"""
        print_header("4. ПРОВЕРКА REQUIREMENTS.TXT")
        
        filepath = self.base_dir / "requirements.txt"
        if not filepath.exists():
            print_error("requirements.txt не найден")
            return False
        
        with open(filepath, 'r') as f:
            requirements = f.read().strip().split('\n')
        
        required_packages = ['aiogram', 'python-dotenv', 'aiosqlite']
        found = []
        
        for package in required_packages:
            for req in requirements:
                if package in req.lower():
                    found.append(package)
                    break
        
        if len(found) == len(required_packages):
            print_success(f"Все обязательные пакеты найдены ({len(found)}/{len(required_packages)})")
            return True
        else:
            missing = set(required_packages) - set(found)
            self.errors.append(f"Отсутствуют пакеты в requirements.txt: {', '.join(missing)}")
            print_error(f"Отсутствуют пакеты: {', '.join(missing)}")
            return False
    
    def check_dockerfile(self):
        """Проверка Dockerfile"""
        print_header("5. ПРОВЕРКА DOCKERFILE")
        
        filepath = self.base_dir / "Dockerfile"
        if not filepath.exists():
            print_error("Dockerfile не найден")
            return False
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        checks = {
            "FROM python:": "Базовый образ Python",
            "RUN apt-get": "Установка системных зависимостей",
            "COPY requirements.txt": "Копирование requirements.txt",
            "RUN pip install": "Установка Python пакетов",
            "CMD": "Команда запуска"
        }
        
        all_found = True
        for check, description in checks.items():
            if check in content:
                print_success(f"{description}")
            else:
                self.warnings.append(f"Отсутствует в Dockerfile: {description}")
                print_warning(f"Не найдено: {description}")
        
        return all_found
    
    def check_env_variables(self):
        """Проверка переменных окружения"""
        print_header("6. ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
        
        # Проверка .env.example
        example_file = self.base_dir / ".env.example"
        if example_file.exists():
            print_success(".env.example найден")
            
            with open(example_file, 'r') as f:
                content = f.read()
            
            required_vars = ['BOT_TOKEN', 'PREMIUM_USERNAME']
            for var in required_vars:
                if var in content:
                    print_success(f"Переменная описана: {var}")
                else:
                    self.warnings.append(f"Переменная не описана в .env.example: {var}")
                    print_warning(f"Переменная не описана: {var}")
        else:
            self.warnings.append(".env.example не найден")
            print_warning(".env.example не найден")
        
        # Проверка .env (не должен существовать в репозитории)
        env_file = self.base_dir / ".env"
        if env_file.exists():
            self.warnings.append(".env файл найден! Убедитесь, что он в .gitignore")
            print_warning(".env файл найден! Убедитесь, что он в .gitignore")
        else:
            print_success(".env файл отсутствует (хорошо)")
        
        return True
    
    def check_gitignore(self):
        """Проверка .gitignore"""
        print_header("7. ПРОВЕРКА .GITIGNORE")
        
        gitignore_file = self.base_dir / ".gitignore"
        if not gitignore_file.exists():
            self.warnings.append(".gitignore не найден")
            print_warning(".gitignore не найден")
            return False
        
        with open(gitignore_file, 'r') as f:
            content = f.read()
        
        important_ignores = ['.env', '__pycache__', '*.pyc', 'temp/', 'data/', 'logs/']
        for ignore in important_ignores:
            if ignore in content:
                print_success(f"Игнорируется: {ignore}")
            else:
                self.warnings.append(f"Не игнорируется: {ignore}")
                print_warning(f"Не игнорируется: {ignore}")
        
        return True
    
    def check_directories(self):
        """Проверка необходимых директорий"""
        print_header("8. ПРОВЕРКА СТРУКТУРЫ ДИРЕКТОРИЙ")
        
        # Директории будут созданы автоматически при запуске
        print_info("Директории (temp/, data/, logs/) будут созданы автоматически")
        print_success("Структура директорий OK")
        
        return True
    
    async def test_database_init(self):
        """Тест инициализации базы данных"""
        print_header("9. ТЕСТ ИНИЦИАЛИЗАЦИИ БАЗЫ ДАННЫХ")
        
        try:
            # Импортируем модуль базы данных
            sys.path.insert(0, str(self.base_dir))
            from database import Database
            
            # Создаем временную базу данных
            test_db_path = self.base_dir / "data" / "test_bot.db"
            test_db_path.parent.mkdir(parents=True, exist_ok=True)
            
            db = Database(str(test_db_path))
            await db.init_db()
            
            # Проверяем, что база создана
            if test_db_path.exists():
                print_success("База данных инициализирована успешно")
                
                # Удаляем тестовую базу
                test_db_path.unlink()
                print_info("Тестовая база данных удалена")
                
                return True
            else:
                self.errors.append("База данных не была создана")
                print_error("База данных не была создана")
                return False
                
        except Exception as e:
            self.errors.append(f"Ошибка инициализации базы данных: {e}")
            print_error(f"Ошибка инициализации: {e}")
            return False
    
    def check_config(self):
        """Проверка config.py"""
        print_header("10. ПРОВЕРКА КОНФИГУРАЦИИ")
        
        try:
            sys.path.insert(0, str(self.base_dir))
            import config
            
            # Проверка обязательных констант
            required_attrs = ['BOT_TOKEN', 'PREMIUM_USERNAME', 'DATABASE_PATH']
            for attr in required_attrs:
                if hasattr(config, attr):
                    print_success(f"Конфигурация найдена: {attr}")
                else:
                    self.warnings.append(f"Отсутствует в config.py: {attr}")
                    print_warning(f"Отсутствует: {attr}")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Ошибка импорта config: {e}")
            print_error(f"Ошибка импорта config: {e}")
            return False
    
    def check_documentation(self):
        """Проверка документации"""
        print_header("11. ПРОВЕРКА ДОКУМЕНТАЦИИ")
        
        doc_files = {
            "README.md": "Основная документация",
            "DEPLOYMENT.md": "Руководство по развертыванию",
            "QUICK_START.md": "Быстрый старт",
            "ENV_VARIABLES.md": "Описание переменных окружения",
            "CHECKLIST.md": "Чеклист развертывания",
            "POST_DEPLOYMENT.md": "Пост-развертывание"
        }
        
        all_found = True
        for filename, description in doc_files.items():
            filepath = self.base_dir / filename
            if filepath.exists():
                # Проверяем, что файл не пустой
                if filepath.stat().st_size > 100:
                    print_success(f"{description}: {filename}")
                else:
                    self.warnings.append(f"Файл слишком короткий: {filename}")
                    print_warning(f"Файл слишком короткий: {filename}")
            else:
                self.warnings.append(f"Отсутствует документация: {filename}")
                print_warning(f"Отсутствует: {filename}")
                all_found = False
        
        return all_found
    
    def print_summary(self):
        """Печать итогового отчета"""
        print_header("ИТОГОВЫЙ ОТЧЕТ")
        
        if not self.errors and not self.warnings:
            print_success("✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
            print_success("✓ Бот готов к развертыванию на Railway")
            print()
            print_info("Следующие шаги:")
            print_info("1. Загрузите код на GitHub")
            print_info("2. Создайте проект в Railway")
            print_info("3. Добавьте переменные окружения")
            print_info("4. Проверьте логи после развертывания")
            print()
            return True
        
        if self.errors:
            print_error(f"\n✗ Найдено {len(self.errors)} критических ошибок:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
        
        if self.warnings:
            print_warning(f"\n⚠ Найдено {len(self.warnings)} предупреждений:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        print()
        if self.errors:
            print_error("✗ ИСПРАВЬТЕ ОШИБКИ ПЕРЕД РАЗВЕРТЫВАНИЕМ")
            return False
        else:
            print_warning("⚠ Устраните предупреждения для лучшей надежности")
            print_success("✓ Критических проблем не обнаружено")
            return True
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print(f"{BLUE}")
        print("╔══════════════════════════════════════════════════════════╗")
        print("║     ТЕСТ ГОТОВНОСТИ К РАЗВЕРТЫВАНИЮ - WOWsilizing Bot   ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"{RESET}")
        
        # Запуск всех проверок
        self.check_required_files()
        self.check_python_syntax()
        self.check_imports()
        self.check_requirements()
        self.check_dockerfile()
        self.check_env_variables()
        self.check_gitignore()
        self.check_directories()
        await self.test_database_init()
        self.check_config()
        self.check_documentation()
        
        # Итоговый отчет
        success = self.print_summary()
        
        return success

async def main():
    """Главная функция"""
    tester = DeploymentTester()
    success = await tester.run_all_tests()
    
    # Возвращаем код выхода
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())

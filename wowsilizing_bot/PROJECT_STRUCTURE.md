# WOWsilizing Bot - Project Structure

## 📁 Project Overview

```
wowsilizing_bot/
├── 🤖 Core Bot Files
│   ├── bot.py                  # Main bot handler (commands, callbacks, FSM)
│   ├── config.py               # Configuration and environment variables
│   ├── database.py             # SQLite database operations
│   └── utils.py                # Helper functions (timecode parsing, file ops)
│
├── 🎬 Video Processing
│   ├── video_processor.py      # FREE tier ffmpeg functions
│   └── ai_processor.py         # PREMIUM tier AI features
│
├── 🚀 Deployment Files
│   ├── Dockerfile              # Docker image for Railway
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example            # Environment variables template
│   └── .gitignore              # Git ignore rules
│
├── 📚 Documentation
│   ├── README.md               # Project documentation (Russian)
│   ├── DEPLOYMENT.md           # Deployment guide (Russian)
│   └── PROJECT_STRUCTURE.md    # This file
│
└── 📂 Data Directories
    ├── temp/                   # Temporary files during processing
    ├── data/                   # SQLite database and persistent data
    │   └── cache/              # Cached processed videos
    └── logs/                   # Bot logs
```

## 🎯 Core Modules

### bot.py (Main Entry Point)
- Telegram bot initialization with aiogram
- Command handlers (/start, /cut, /audio, etc.)
- Callback query handlers
- FSM (Finite State Machine) for workflows
- Video/text message handlers
- Progress tracking and user notifications

### config.py (Configuration)
- Bot token: 8314895069:AAG1P9oozBOHv1pMaIPy-uzGQhayu6Fz9c8
- Premium user: @WowFUX
- API keys for OpenAI, Google, 11Labs
- All settings via environment variables
- Russian language messages

### database.py (Data Persistence)
- SQLite database management
- Tables: users, history, templates, cache, usage_stats
- Async operations with aiosqlite
- Premium status checking
- Cache management

### utils.py (Utilities)
- Timecode parsing (supports multiple formats)
- Batch timecode extraction
- Video info extraction (ffprobe)
- YouTube URL detection
- File cleanup and temp file management
- Progress callback system

### video_processor.py (FREE Tier)
**Priority Feature: Batch Timecode Cutting**
- Process up to 100 segments at once
- Progress tracking "Обрабатываю 5/38..."
- Support for various timecode formats

**Other Features:**
- Audio extraction (MP3/WAV)
- Noise reduction (afftdn filter)
- Audio normalization (loudnorm)
- Video compression (CRF control)
- Format conversion
- Vertical 9:16 conversion
- Auto-segmentation
- Silence removal
- Video merging

### ai_processor.py (PREMIUM Tier - @WowFUX only)
- **Subtitle generation** - OpenAI Whisper API
- **Language detection** - Auto-detect video language
- **Subtitle translation** - GPT-4 powered
- **TTS providers:**
  - OpenAI TTS (6 voices)
  - Google AI Studio TTS
  - 11Labs TTS (professional voices)
- **Auto highlights** - GPT-4 video analysis
- **Video summarization** - GPT-4
- **Natural language commands** - GPT parsing

## 📊 Database Schema

### users table
- user_id (PRIMARY KEY)
- username
- is_premium
- created_at
- last_active

### history table
- id (AUTOINCREMENT)
- user_id
- video_name
- operation
- timestamp
- file_size
- duration

### templates table
- id (AUTOINCREMENT)
- user_id
- name (UNIQUE per user)
- settings_json
- created_at

### cache table
- hash (PRIMARY KEY)
- file_path
- operation
- created_at
- file_size
- access_count

### usage_stats table (premium)
- user_id (PRIMARY KEY)
- api_calls
- minutes_processed
- last_reset

## 🔄 Processing Flow

### 1. Video Upload
```
User sends video → Bot downloads → Saves to temp/
                 ↓
         Extracts preview frame
                 ↓
         Shows main menu (FREE or PREMIUM)
```

### 2. Batch Cutting (Priority Feature)
```
User sends timecodes → Parse multiple segments
                     ↓
              Validate all timecodes
                     ↓
              Show confirmation
                     ↓
          User confirms → Process each segment
                     ↓
              Track progress: "5/38..."
                     ↓
          Send files OR create ZIP archive
```

### 3. Premium AI Features
```
Check if user is @WowFUX → Extract audio → Send to API
                         ↓
                 Process with AI
                         ↓
                 Save to history & stats
                         ↓
                 Return result
```

## 🚀 Deployment Process

### Railway Deployment Steps:
1. Push code to GitHub
2. Create Railway project
3. Connect GitHub repo
4. Set environment variables:
   - BOT_TOKEN
   - PREMIUM_USERNAME
   - (Optional) AI API keys
5. Railway builds Docker image
6. Bot starts automatically

### Docker Build Process:
```
Base image (python:3.11-slim)
    ↓
Install ffmpeg & yt-dlp
    ↓
Copy requirements.txt
    ↓
Install Python dependencies
    ↓
Copy bot code
    ↓
Create data directories
    ↓
Run bot.py
```

## 🎨 User Interface (Russian)

### Commands:
- `/start` - Главное меню
- `/cut` - Нарезка видео
- `/audio` - Извлечь аудио
- `/vertical` - Вертикальный формат
- `/subtitles` - Субтитры (премиум)
- `/translate` - Перевод (премиум)
- `/tts` - Озвучка (премиум)
- `/highlights` - Хайлайты (премиум)
- `/history` - История операций
- `/templates` - Шаблоны
- `/stats` - Статистика (премиум)

### Inline Buttons:
- ✂️ Нарезка видео
- 🎵 Извлечь аудио
- 📱 В вертикальный формат
- 🗜 Сжать видео
- 🔇 Убрать шум
- 🔊 Нормализовать звук
- 🔗 Склеить видео
- 📝 Субтитры (AI) - премиум
- 🌐 Перевести субтитры - премиум
- 🎤 Озвучка текста (TTS) - премиум
- ⭐ Авто-хайлайты - премиум
- 📜 История
- ⚙️ Шаблоны
- 📊 Статистика - премиум

## 💾 File Management

### Temporary Files:
- Created in `temp/` directory
- Cleaned up after sending to user
- Named with timestamp + random string

### Cached Files:
- Stored in `data/cache/`
- Keyed by hash(file + operation + params)
- Auto-cleaned after 7 days
- Reused if same operation requested

### Database:
- SQLite file: `data/bot.db`
- Stores user data, history, templates
- Persistent across restarts

## 🔐 Security

### Access Control:
- Premium features locked to @WowFUX
- Case-insensitive username check
- Stored in config.PREMIUM_USERNAME

### API Keys:
- Never committed to git (.gitignore)
- Stored in Railway environment variables
- Loaded via python-dotenv

### Rate Limiting:
- Max queue size per user: 10
- Max batch segments: 100
- Max file size: 50 MB

## 📈 Monitoring

### Logs:
- Location: `logs/bot.log`
- Level: INFO (configurable)
- Includes: errors, operations, API calls

### Metrics (in Railway):
- CPU usage
- Memory usage
- Active users
- Processing time

## 🧪 Testing Checklist

- [ ] Bot responds to /start
- [ ] Video upload works
- [ ] Batch cutting works (priority)
- [ ] Audio extraction works
- [ ] Vertical conversion works
- [ ] History saves correctly
- [ ] Premium check works for @WowFUX
- [ ] AI features work (with API keys)
- [ ] YouTube download works
- [ ] Progress updates show correctly

## 🎯 Key Features

### ⭐ PRIORITY: Batch Timecode Cutting
This is the most important feature:
- Parse multiple timecodes from text
- Support formats: "00:00-01:59", "0:0-1:59", "00:00 - 01:59"
- Process up to 100 segments
- Show progress: "Обрабатываю 5/38..."
- Send as separate files or ZIP archive

### 🆓 FREE Features (All Users)
All ffmpeg-based, no API costs

### 👑 PREMIUM Features (@WowFUX Only)
All AI-powered features requiring API keys

## 📝 Development Notes

- Language: All user-facing text in RUSSIAN
- Framework: aiogram 3.4 (async)
- Video processing: ffmpeg
- Database: SQLite with aiosqlite
- Deployment: Docker on Railway
- Version control: Git

## 🔄 Update Process

1. Make changes locally
2. Test locally
3. Commit to git
4. Push to GitHub
5. Railway auto-deploys

## ✅ Production Ready

This bot is production-ready with:
- ✅ Error handling
- ✅ Logging
- ✅ Database persistence
- ✅ Caching
- ✅ Progress tracking
- ✅ Clean code structure
- ✅ Russian documentation
- ✅ Deployment guide
- ✅ Version control

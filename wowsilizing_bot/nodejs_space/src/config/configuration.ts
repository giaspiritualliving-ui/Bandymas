export default () => ({
  port: parseInt(process.env.PORT, 10) || 3000,
  nodeEnv: process.env.NODE_ENV || 'development',
  bot: {
    token: process.env.BOT_TOKEN || '8314895069:AAG1P9oozBOHv1pMaIPy-uzGQhayu6Fz9c8',
    premiumUsername: (process.env.PREMIUM_USERNAME || '@WowFUX').toLowerCase().replace('@', ''),
  },
  api: {
    openai: process.env.OPENAI_API_KEY || '',
    google: process.env.GOOGLE_API_KEY || '',
    elevenlabs: process.env.ELEVENLABS_API_KEY || '',
  },
  languages: {
    priority: (process.env.PRIORITY_LANGS || 'lt,ru,en,uk').split(',').map(l => l.trim()),
  },
  rateLimit: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS, 10) || 60000,
    maxRequests: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS, 10) || 10,
  },
  video: {
    maxSizeMb: parseInt(process.env.MAX_VIDEO_SIZE_MB, 10) || 100,
    tempDir: process.env.TEMP_DIR || '/tmp/telegram-bot',
  },
});

const { Telegraf } = require('telegraf');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const { kv } = require('@vercel/kv');

const bot = new Telegraf(process.env.BOT_TOKEN);
const ai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = ai.getGenerativeModel({ model: "gemini-1.5-flash" });

const SYSTEM_PROMPT = `
Ты — токсичный ИИ-аналитик чата StatBoy. Отвечай СТРОГО по запрошенным командам. Используй HTML для форматирования (<b>жирный</b>, <i>курсив</i>, <code>код</code>). Без Markdown!
`;

function escapeHTML(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 1. КРАСИВЫЙ ОТВЕТ НА /help
bot.command('help', async (ctx) => {
  const helpText = `
<b>🤖 StatBoy ИИ. Список команд:</b>
• <code>/help</code> — Меню
• <code>/summary</code> — Выжимка за 24 часа
• <code>/rating</code> — Диагнозы чата
• <code>/rateme</code> — Табель позора
• <code>/psycho</code> — Психопортрет всех
  `;
  try {
    await ctx.reply(helpText, { parse_mode: 'HTML' });
  } catch (err) {
    console.error('Ошибка /help:', err);
  }
});

// 2. УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТПРАВКИ КОМАНД В GEMINI
async function handleAiCommand(ctx, commandName) {
  try {
    await ctx.sendChatAction('typing');
    const chatId = ctx.message.chat.id;
    const args = ctx.message.text.split(' ').slice(1).join(' ');

    // Тянем историю чата из Redis
    const historyArray = await kv.lrange(`chat_history:${chatId}`, 0, -1);
    const logContext = historyArray.length > 0 ? historyArray.join('\n') : 'Чат пуст.';

    const prompt = `КОНТЕКСТ ЧАТА:\n${logContext}\n\nКОМАНДА: !sb ${commandName} ${args}`;

    const result = await model.generateContent({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      systemInstruction: SYSTEM_PROMPT,
    });

    await ctx.reply(escapeHTML(result.response.text()), { 
      reply_to_message_id: ctx.message.message_id,
      parse_mode: 'HTML'
    });
  } catch (e) {
    console.error('Ошибка ИИ:', e);
    await ctx.reply('Бот сломался от твоего кринжа.');
  }
}

// РЕГИСТРИРУЕМ ИИ-КОМАНДЫ ЧЕРЕЗ ВСТРОЕННЫЕ МЕТОДЫ TELEGRAF
bot.command('summary', (ctx) => handleAiCommand(ctx, 'summary'));
bot.command('rating', (ctx) => handleAiCommand(ctx, 'rating'));
bot.command('rateme', (ctx) => handleAiCommand(ctx, 'rateme'));
bot.command('psycho', (ctx) => handleAiCommand(ctx, 'psycho'));

// 3. ПАССИВНОЕ ЛОГИРОВАНИЕ ОБЫЧНЫХ СООБЩЕНИЙ
bot.on('message', async (ctx) => {
  const text = ctx.message.text;
  if (!text) return;

  // Если это любая слэш-команда — Telegraf обработал её выше. Игнорируем и не пишем в логи.
  if (text.startsWith('/')) return;

  const chatId = ctx.message.chat.id;
  const username = ctx.message.from.username || ctx.message.from.first_name || 'Аноним';

  try {
    await kv.rpush(`chat_history:${chatId}`, `[${username}]: ${text}`);
    await kv.ltrim(`chat_history:${chatId}`, -150, -1);
  } catch (err) {
    console.error('Ошибка KV:', err);
  }
});

// ОБРАБОТЧИК ВЕБХУКА ДЛЯ VERCEL
module.exports = async (req, res) => {
  try {
    if (req.method === 'POST') {
      const update = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
      await bot.handleUpdate(update);
      res.status(200).end();
    } else {
      res.status(200).send('<h1>StatBoy работает</h1>');
    }
  } catch (err) {
    console.error('Ошибка вебхука:', err);
    res.status(200).end();
  }
};const { Telegraf } = require('telegraf');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const { kv } = require('@vercel/kv');

const bot = new Telegraf(process.env.BOT_TOKEN);
const ai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = ai.getGenerativeModel({ model: "gemini-1.5-flash" });

const SYSTEM_PROMPT = `
Ты — токсичный ИИ-аналитик чата StatBoy. Отвечай СТРОГО по запрошенным командам. Используй HTML для форматирования (<b>жирный</b>, <i>курсив</i>, <code>код</code>). Без Markdown!
`;

function escapeHTML(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 1. КРАСИВЫЙ ОТВЕТ НА /help
bot.command('help', async (ctx) => {
  const helpText = `
<b>🤖 StatBoy ИИ. Список команд:</b>
• <code>/help</code> — Меню
• <code>/summary</code> — Выжимка за 24 часа
• <code>/rating</code> — Диагнозы чата
• <code>/rateme</code> — Табель позора
• <code>/psycho</code> — Психопортрет всех
  `;
  try {
    await ctx.reply(helpText, { parse_mode: 'HTML' });
  } catch (err) {
    console.error('Ошибка /help:', err);
  }
});

// 2. УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТПРАВКИ КОМАНД В GEMINI
async function handleAiCommand(ctx, commandName) {
  try {
    await ctx.sendChatAction('typing');
    const chatId = ctx.message.chat.id;
    const args = ctx.message.text.split(' ').slice(1).join(' ');

    // Тянем историю чата из Redis
    const historyArray = await kv.lrange(`chat_history:${chatId}`, 0, -1);
    const logContext = historyArray.length > 0 ? historyArray.join('\n') : 'Чат пуст.';

    const prompt = `КОНТЕКСТ ЧАТА:\n${logContext}\n\nКОМАНДА: !sb ${commandName} ${args}`;

    const result = await model.generateContent({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      systemInstruction: SYSTEM_PROMPT,
    });

    await ctx.reply(escapeHTML(result.response.text()), { 
      reply_to_message_id: ctx.message.message_id,
      parse_mode: 'HTML'
    });
  } catch (e) {
    console.error('Ошибка ИИ:', e);
    await ctx.reply('Бот сломался от твоего кринжа.');
  }
}

// РЕГИСТРИРУЕМ ИИ-КОМАНДЫ ЧЕРЕЗ ВСТРОЕННЫЕ МЕТОДЫ TELEGRAF
bot.command('summary', (ctx) => handleAiCommand(ctx, 'summary'));
bot.command('rating', (ctx) => handleAiCommand(ctx, 'rating'));
bot.command('rateme', (ctx) => handleAiCommand(ctx, 'rateme'));
bot.command('psycho', (ctx) => handleAiCommand(ctx, 'psycho'));

// 3. ПАССИВНОЕ ЛОГИРОВАНИЕ ОБЫЧНЫХ СООБЩЕНИЙ
bot.on('message', async (ctx) => {
  const text = ctx.message.text;
  if (!text) return;

  // Если это любая слэш-команда — Telegraf обработал её выше. Игнорируем и не пишем в логи.
  if (text.startsWith('/')) return;

  const chatId = ctx.message.chat.id;
  const username = ctx.message.from.username || ctx.message.from.first_name || 'Аноним';

  try {
    await kv.rpush(`chat_history:${chatId}`, `[${username}]: ${text}`);
    await kv.ltrim(`chat_history:${chatId}`, -150, -1);
  } catch (err) {
    console.error('Ошибка KV:', err);
  }
});

// ОБРАБОТЧИК ВЕБХУКА ДЛЯ VERCEL
module.exports = async (req, res) => {
  try {
    if (req.method === 'POST') {
      const update = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
      await bot.handleUpdate(update);
      res.status(200).end();
    } else {
      res.status(200).send('<h1>StatBoy работает</h1>');
    }
  } catch (err) {
    console.error('Ошибка вебхука:', err);
    res.status(200).end();
  }
};

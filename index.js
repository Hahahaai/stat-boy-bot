const { Telegraf } = require('telegraf');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const { kv } = require('@vercel/kv');

const bot = new Telegraf(process.env.BOT_TOKEN);
const ai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = ai.getGenerativeModel({ model: "gemini-1.5-flash" });

// Твой точный юзернейм бота (строго маленькими буквами)
const BOT_USERNAME = 'stat_boyy_bot';

const SYSTEM_PROMPT = `
Ты — toxic, циничный ИИ-аналитик чата StatBoy. Отвечай СТРОГО по запрошенным командам. Используй HTML для форматирования (<b>жирный</b>, <i>курсив</i>, <code>код</code>). Никогда не используй символы разметки Markdown (звёздочки)!

КОМАНДЫ:
1. !sb help: список команд.
2. !sb summary: выжимка (Главная тема, Ключевые события, Градус неадеквата от 1 до 5).
3. !sb rating: по каждому нику (Вульгарность, Вежливость, Кринж, Токсичность от 1 до 5) и диагноз.
4. !sb rateme: личный табель (Вульгарность, Токсичность, Интеллект, Вайб от 1 до 5) и приговор.
5. !sb psycho: психопортрет всех (Архетип, Триггеры, Состояние от 1 до 5) и совет.
6. !sb psychome: диагностика автора (Недосып, Зависимость, Стабильность от 1 до 5) и вердикт.
7. !sb ask [вопрос]: циничный ответ по контексту логов.
8. !sb poll: опрос (Тема и 4 едких варианта ответа).
9. !sb taro: расклад (Прошлое, Настоящее, Будущее и вердикт).
10. !sb song: саундтрек жизни (Исполнитель, Трек, Пояснение, Строчка, Уровень позора от 1 до 5).
11. !sb edit: концепт фотожабы и оценка идеи от 1 до 5.
12. !sb create: едкий коммент и детализированный англоязычный промпт для Midjourney.
13. !sb future: прогноз будущих сообщений (Уровень адекватности, Сценарный прогноз с репликамиников).
14. !sb meme: демотиватор (Кринж, Постирония от 1 до 5, ТЕКСТ СВЕРХУ, ТЕКСТ СНИЗУ).

ОБЩИЕ ПРАВИЛА: Все оценки от 1 до 5. Никакой пощады, будь высокомерным. Если лог пуст, высмей юзера.
`;

function escapeHTML(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 1. СЛУШАТЕЛЬ /help
bot.hears(/^\/help( @[a-zA-Z0-9_]+)?$/i, async (ctx) => {
  const text = (ctx.message.text || '').toLowerCase();
  if (text.includes('@') && !text.includes(`@${BOT_USERNAME}`)) return;

  const helpText = `
<b>🤖 StatBoy ИИ. Список команд:</b>
• <code>/help</code> — Меню
• <code>/summary</code> — Выжимка за 24 часа
• <code>/rating</code> — Диагнозы чата
• <code>/rateme</code> — Табель позора
• <code>/psycho</code> — Психопортрет всех
• <code>/psychome</code> — Твоя карта кукухи
• <code>/ask [вопрос]</code> — Вопрос по логам
• <code>/poll</code> — Создать опрос
• <code>/taro</code> — Расклад Таро
• <code>/song</code> — Саундтрек жизни
• <code>/edit [запрос]</code> — Концепт фотожабы
• <code>/create [запрос]</code> — Промпт для MJ
• <code>/future</code> — Прогноз сообщений
• <code>/meme</code> — Демотиватор
  `;
  try {
    await ctx.reply(helpText, { parse_mode: 'HTML' });
  } catch (err) {
    console.error('Ошибка help:', err);
  }
});

// 2. ГЛАВНЫЙ ОБРАБОТЧИК
bot.on('message', async (ctx) => {
  const text = ctx.message.text;
  if (!text) return;

  const chatId = ctx.message.chat.id;
  const username = ctx.message.from.username || ctx.message.from.first_name || 'Аноним';
  const kvKey = `chat_history:${chatId}`;

  // Обработка слэш-команд
  if (text.startsWith('/')) {
    const firstSpaceIndex = text.indexOf(' ');
    let fullCommand = firstSpaceIndex === -1 ? text.slice(1) : text.slice(1, firstSpaceIndex);
    const args = firstSpaceIndex === -1 ? '' : text.slice(firstSpaceIndex + 1);

    let commandName = fullCommand.toLowerCase();

    // Проверяем наличие юзернейма в команде (например, /summary@stat_boyy_bot)
    if (commandName.includes('@')) {
      // Если команда предназначена НЕ нашему боту — логируем её как обычный текст и выходим
      if (!commandName.endsWith(`@${BOT_USERNAME}`)) {
        try {
          await kv.rpush(kvKey, `[${username}]: ${text}`);
          await kv.ltrim(kvKey, -150, -1);
        } catch (err) {
          console.error('Ошибка записи чужой команды в KV:', err);
        }
        return;
      }
      // Если нашему — очищаем имя бота, оставляя только чистую команду (например, "summary")
      commandName = commandName.split('@')[0];
    }

    if (commandName === 'help') return;

    // Обработка нашей команды через ИИ
    try {
      await ctx.sendChatAction('typing');
      const historyArray = await kv.lrange(kvKey, 0, -1);
      const logContext = historyArray.length > 0 ? historyArray.join('\n') : 'Чат пуст.';

      const cleanCommand = `!sb ${commandName} ${args}`;
      const prompt = `КОНТЕКСТ ЧАТА:\n${logContext}\n\nКОМАНДА: ${cleanCommand}\n\nВыполни строго по инструкции Стат Боя.`;

      const result = await model.generateContent({
        contents: [{ role: 'user', parts: [{ text: prompt }] }],
        systemInstruction: SYSTEM_PROMPT,
      });

      const aiResponse = result.response.text();
      await ctx.reply(escapeHTML(aiResponse), { 
        reply_to_message_id: ctx.message.message_id,
        parse_mode: 'HTML'
      });
    } catch (e) {
      console.error('Ошибка работы ИИ:', e);
      await ctx.reply('Бот сломался от твоего кринжа. Попробуй позже.');
    }
    return;
  }

  // 3. Пассивное логирование обычного текста
  try {
    await kv.rpush(kvKey, `[${username}]: ${text}`);
    await kv.ltrim(kvKey, -150, -1);
  } catch (err) {
    console.error('Ошибка записи в KV:', err);
  }
});

// НАДЁЖНЫЙ ОБРАБОТЧИК ДЛЯ СРЕДЫ VERCEL
module.exports = async (req, res) => {
  try {
    if (req.method === 'POST') {
      const update = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
      await bot.handleUpdate(update);
      res.status(200).end();
    } else {
      res.status(200).send('<h1>StatBoy успешно работает!</h1>');
    }
  } catch (err) {
    console.error('Критический сбой вебхука:', err);
    res.status(200).end();
  }
};

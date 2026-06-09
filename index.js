const { Telegraf } = require('telegraf');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const { kv } = require('@vercel/kv');

const bot = new Telegraf(process.env.BOT_TOKEN);
const ai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = ai.getGenerativeModel({ model: "gemini-1.5-flash" });

const SYSTEM_PROMPT = `
Ты — токсичный, циничный ИИ-аналитик чата StatBoy. Отвечай СТРОГО по запрошенным командам. Используй HTML для форматирования (<b>жирный</b>, <i>курсив</i>, <code>код</code>). Без Markdown!

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

bot.hears('!sb help', async (ctx) => {
  const helpText = `
<b>🤖 StatBoy ИИ. Список команд:</b>
• <code>!sb help</code> — Меню
• <code>!sb summary</code> — Выжимка за 24 часа
• <code>!sb rating</code> — Диагнозы чата
• <code>!sb rateme</code> — Табель позора
• <code>!sb psycho</code> — Психопортрет всех
• <code>!sb psychome</code> — Твоя карта кукухи
• <code>!sb ask [вопрос]</code> — Вопрос по логам
• <code>!sb poll</code> — Создать опрос
• <code>!sb taro</code> — Расклад Таро
• <code>!sb song</code> — Саундтрек жизни
• <code>!sb edit [запрос]</code> — Концепт фотожабы
• <code>!sb create [запрос]</code> — Промпт для MJ
• <code>!sb future</code> — Прогноз сообщений
• <code>!sb meme</code> — Демотиватор
  `;
  try {
    await ctx.reply(helpText, { parse_mode: 'HTML' });
  } catch (err) {
    console.error('Ошибка help:', err);
  }
});

bot.on('message', async (ctx) => {
  const text = ctx.message.text;
  if (!text) return;

  const chatId = ctx.message.chat.id;
  const username = ctx.message.from.username || ctx.message.from.first_name || 'Аноним';
  const kvKey = `chat_history:${chatId}`;

  if (!text.startsWith('!sb')) {
    try {
      await kv.rpush(kvKey, `[${username}]: ${text}`);
      await kv.ltrim(kvKey, -150, -1);
    } catch (err) {
      console.error('Ошибка записи в KV:', err);
    }
    return;
  }

  if (text.trim() === '!sb help') return;

  try {
    await ctx.sendChatAction('typing');
    const historyArray = await kv.lrange(kvKey, 0, -1);
    const logContext = historyArray.length > 0 ? historyArray.join('\n') : 'Чат пуст.';

    const prompt = `КОНТЕКСТ ЧАТА:\n${logContext}\n\nКОМАНДА: ${text}\n\nВыполни строго по инструкции Стат Боя.`;

    const result = await model.generateContent({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      systemInstruction: SYSTEM_PROMPT,
    });

    await ctx.reply(result.response.text(), { 
      reply_to_message_id: ctx.message.message_id,
      parse_mode: 'HTML'
    });
  } catch (e) {
    console.error('Ошибка ИИ:', e);
    await ctx.reply('Бот сломался от твоего кринжа. Попробуй позже.');
  }
});

// КЛАССИЧЕСКИЙ РАЗВЕРНУТЫЙ ОБРАБОТЧИК ВЕБХУКА VERCEL
module.exports = async (req, res) => {
  try {
    if (req.method === 'POST') {
      const update = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
      await bot.handleUpdate(update, res);
    } else {
      res.status(200).send('<h1>StatBoy готов к работе через Вебхук и Vercel KV!</h1>');
    }
  } catch (err) {
    console.error('Критическая ошибка вебхука:', err);
    res.status(200).send('Error handled');
  }
};

// 1. СЛУШАТЕЛЬ ОПИСАНИЯ КОМАНД (ДЛЯ /help)
bot.hears(/^\/help(@[a-zA-Z0-9_]+bot)?$/i, async (ctx) => {
  // Проверяем: если юзернейм указан, но он не принадлежит нашему боту — игнорируем
  const botUsername = ctx.botInfo.username;
  if (ctx.match[1] && ctx.match[1].toLowerCase() !== `@${botUsername}`.toLowerCase()) return;

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

// 2. ГЛАВНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ СООБЩЕНИЙ И КОМАНД ЧАТА
bot.on('message', async (ctx) => {
  const text = ctx.message.text;
  if (!text) return;

  const chatId = ctx.message.chat.id;
  const username = ctx.message.from.username || ctx.message.from.first_name || 'Аноним';
  const kvKey = `chat_history:${chatId}`;
  const botUsername = ctx.botInfo.username;

  // Регулярное выражение проверяет, начинается ли текст со слэша /
  const isCommand = text.startsWith('/');

  if (isCommand) {
    // Вытаскиваем саму команду (например, "summary") и юзернейм после собаки (если есть)
    const match = text.match(/^\/([a-zA-Z0-9_]+)(@[a-zA-Z0-9_]+bot)?(.*)/s);
    
    if (match) {
      const commandName = match[1].toLowerCase();
      const targetBot = match[2];
      const args = match[3] ? match[3].trim() : '';

      // Защита от дублирования вызова help (для него отдельныйhears выше)
      if (commandName === 'help') return;

      // Если в команде указан юзернейм бота, но он НЕ наш — расцениваем это как обычное сообщение чата и пишем в лог
      if (targetBot && targetBot.toLowerCase() !== `@${botUsername}`.toLowerCase()) {
        try {
          await kv.rpush(kvKey, `[${username}]: ${text}`);
          await kv.ltrim(kvKey, -150, -1);
        } catch (err) {
          console.error('Ошибка записи в KV:', err);
        }
        return;
      }

      // Если проверка пройдена, запускаем ИИ для обработки команды нашего бота
      try {
        await ctx.sendChatAction('typing');
        const historyArray = await kv.lrange(kvKey, 0, -1);
        const logContext = historyArray.length > 0 ? historyArray.join('\n') : 'Чат пуст.';

        // Формируем чистую команду без привязки юзернейма для промпта Gemini
        const cleanCommand = `!sb ${commandName} ${args}`;
        const prompt = `КОНТЕКСТ ЧАТА:\n${logContext}\n\nКОМАНДА: ${cleanCommand}\n\nВыполни строго по инструкции Стат Боя.`;

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
      return;
    }
  }

  // 3. Пассивное логирование (если это обычный текст без слэша)
  try {
    await kv.rpush(kvKey, `[${username}]: ${text}`);
    await kv.ltrim(kvKey, -150, -1);
  } catch (err) {
    console.error('Ошибка записи в KV:', err);
  }
});

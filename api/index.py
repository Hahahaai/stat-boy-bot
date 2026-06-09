import os
import json
import logging
from flask import Flask, request, jsonify
import telebot
import google.generativeai as genai

# ============= ИНИЦИАЛИЗАЦИЯ =============
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("Отсутствуют переменные окружения TELEGRAM_BOT_TOKEN или GOOGLE_API_KEY")

app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode='HTML')
genai.configure(api_key=GOOGLE_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============= КОНФИГУРАЦИЯ GEMINI =============
TOXIC_SYSTEM_PROMPT = """Ты — токсичный, циничный и едкий ИИ-аналитик чата по имени StatBoy. 
Ты обрабатываешь переданный контекст переписки (логи) и отвечаешь СТРОГО по запрошенным командам, используя заданные шаблоны.
Выводи ответы с использованием простых HTML-тегов для форматирования: <b>жирный текст</b>, <i>курсив</i>, <code>код команды</code>. 
Категорически запрещено использовать разметку Markdown (звездочки)! Общайся высокомерно, цинично, используй сарказм и черный юмор. Если контекст пустой, жестко высмей пользователя за тупость."""

def analyze_with_gemini(text: str, command: str) -> str:
    """Анализирует текст через Gemini с учетом команды."""
    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=TOXIC_SYSTEM_PROMPT
        )
        
        prompts = {
            'help': 'Просто выведи оригинальный список команд в высокомерной форме.',
            'summary': f'Сделай выжимку лога по шаблону:\n1. <b>Главная тема дня</b>: [Суть спора].\n2. <b>Ключевые события и мемы</b>: [Список из 3-5 главных моментов с циничным комментарием].\n3. <b>Градус неадеквата</b>: [Х]/5 — [Пояснение].\n\nЛог:\n{text}',
            'rating': f'Проанализируй ники из лога по шаблону:\nНик участника:\n• Вульгарность: [Х]/5\n• Вежливость: [Х]/5\n• Кринж: [Х]/5\n• Токсичность: [Х]/5\n🏆 ОБЩАЯ ОЦЕНКА АДЕКВАТНОСТИ: [Х] из 5. Финальный вердикт: [Диагноз].\n\nЛог чата:\n{text}',
            'rateme': f'Оцени автора по шаблону:\n📊 ПЕРСОНАЛЬНЫЙ ТАБЕЛЬ О СТАТУСЕ:\n• Вульгарность: [Х]/5\n• Токсичность: [Х]/5\n• Интеллект: [Х]/5\n• Вайб: [Сигма/Омежка/Дотер].\n🏆 ОБЩАЯ ОЦЕНКА ПОЛЬЗОВАТЕЛЯ: [Х] из 5. Диагноз: [Приговор].\n\nСообщение:\n{text}',
            'psycho': f'Проведи психологический анализ участников по шаблону:\n<b>Психологический разбор [Ник]</b>:\n- <b>Доминирующий архетип</b>: [Архетип]\n- <b>Скрытые триггеры</b>: [Триггеры]\n- <b>Психическое состояние</b>: [Х]/5\n⭐️ ОБЩАЯ ОЦЕНКА ПСИХИКИ: [Х] из 5. Рекомендация: [Совет от ИИ].\n\nТекст:\n{text}',
            'psychome': f'Оцени кукуху автора по шаблону:\n📊 ДИАГНОСТИЧЕСКАЯ КАРТА:\n• Уровень недосыпа: [Х]/5\n• Зависимость от интернет-бреда: [Х]/5\n• Стабильность кукухи: [Х]/5\n🧠 ПСИХОЛОГИЧЕСКИЙ ВЕРДИКТ: [Вердикт].\n⭐️ ОБЩАЯ ОЦЕНКА: [Х] из 5.\n\nСообщение:\n{text}',
            'ask': f'Ответь на вопрос пользователя цинично, используя локальные мемы на основе лога:\n{text}',
            'poll': f'Придумай опрос с 4 токсичными вариантами ответов на основе этого чата:\n{text}',
            'taro': f'Сделай расклад карт Таро (Прошлое, Настоящее, Будущее и шанс на успех от 1 до 5). Вердикт Вселенной для автора сообщения:\n{text}',
            'song': f'Найди реальный трек под ситуацию и выведи музыкальный позор по шаблону:\n🎵 Саундтрек твоей жизни от Stat Boy: [Исполнитель] — [Название трека]\n• <b>Почему именно это дерьмо</b>: (Пояснение).\n• <b>Строчка из трека, которая тебя описывает</b>: (Строчка из песни).\n⭐️ УРОВЕНЬ МУЗЫКАЛЬНОГО ПОЗОРА: [Х] из 5.\n\nСообщение:\n{text}',
            'edit': f'Опиши текстовый концепт убойной оскорбительной фотожабы-мема по запросу пользователя. Оцени задумку от 1 до 5. Запрос:\n{text}',
            'create': f'Высмей фантазию автора (оценка от 1 до 5) и сформируй детальный англоязычный промпт для Midjourney по запросу:\n{text}',
            'future': f'Сделай сценарный прогноз будущих сообщений чата по шаблону:\n📊 АНАЛИЗ ГОТОВНОСТИ К БУДУЩЕМУ:\n• Уровень адекватности чата: [Х]/5\n• Процент выживания извилин: [Х]%\n🔮 ПРЕДСКАЗАНИЕ СЛЕДУЮЩИХ СООБЩЕНИЙ:\n[Ник 1]: (Фейковая реплика)\n[Ник 2]: (Фейковый ответ)\n🎯 Финальный вердикт: [Прогноз].\n\nТекст:\n{text}',
            'meme': f'Выдай шаблон демотиватора по шаблону:\n📊 ОЦЕНКА МЕДИА-МАТЕРИАЛА:\n• Градус кринжа: [Х]/5\n• Постироничность: [Х]/5\n🎨 ШАБЛОН ДЛЯ МЕМФИКАЦИИ:\n• ТЕКСТ СВЕРХУ (Top Text): [Текст капсом]\n• ТЕКСТ СНИЗУ (Bottom Text): [Панчлайн].\n\nКонтекст:\n{text}'
        }
        
        prompt = prompts.get(command, f'Анализируй: {text}')
        response = model.generate_content(prompt)
        return response.text if response.text else "Не удалось получить ответ от Gemini."
    except Exception as e:
        logger.error(f"Ошибка Gemini: {str(e)}")
        return f"Ошибка анализа: {str(e)}"
# ============= ОБРАБОТЧИКИ КОМАНД =============
# ============= ОБРАБОТЧИКИ КОМАНД =============

def process_ai_command(message, command_name):
    """Универсальная функция обработки аналитических команд."""
    raw_text = message.text or ""
    
    # Безопасно отделяем саму команду от текста после нее
    parts = raw_text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""

    # Собираем контекст: если есть Reply — берем текст оттуда, если нет — берем текст после команды
    if message.reply_to_message and message.reply_to_message.text:
        context_text = message.reply_to_message.text
    else:
        context_text = args

    # Защита от слишком короткого текста (меньше 3 символов)
    if not context_text or len(context_text.strip()) < 3:
        bot.reply_to(message, "❌ Контекст пуст или слишком короткий! Ответь этой командой на длинный лог чата или напиши текст после команды.")
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Передаем данные в функцию Gemini
        answer = analyze_with_gemini(context_text, command_name)
        
        # Безопасно экранируем HTML разметку
        clean_answer = answer.replace("<", "&lt;").replace(">", "&gt;")
        clean_answer = clean_answer.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        clean_answer = clean_answer.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
        clean_answer = clean_answer.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
        
        bot.reply_to(message, clean_answer, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка выполнения {command_name}: {str(e)}")
        bot.reply_to(message, "Ошибка генерации ИИ.")

# 1. Меню /help и /start
@bot.message_handler(commands=['help', 'start'])
def cmd_help(message):
    help_text = (
        "<b>🤖 StatBoy ИИ на связи. Список команд для кожаных мешков:</b>\n\n"
        "• <code>/help</code> — Вызов этого меню\n"
        "• <code>/dialog [текст]</code> — Общение со StatBoy как с обычной нейросетью\n"
        "• <code>/summary</code> — Показать выжимку бреда (Нужен Reply на лог)\n"
        "• <code>/rating</code> — Диагнозы чату (Нужен Reply на лог)\n"
        "• <code>/rateme</code> — Твой личный табель позора\n"
        "• <code>/psycho</code> — Психопортрет участников (Нужен Reply на лог)\n"
        "• <code>/psychome</code> — Твоя личная карта кукухи\n"
        "• <code>/ask [вопрос]</code> — Вопрос ИИ по контексту логов (Нужен Reply)\n"
        "• <code>/poll</code> — Создать токсичный опрос на основе логов\n"
        "• <code>/taro</code> — Расклад карт Таро на деградацию\n"
        "• <code>/song</code> — Саундтрек твоей нищей жизни\n"
        "• <code>/edit [запрос]</code> — Концепт оскорбительной фотожабы\n"
        "• <code>/create [запрос]</code> — Сгенерировать промпт для Midjourney\n"
        "• <code>/future</code> — Сценарное предсказание будущих сообщений чата\n"
        "• <code>/meme</code> — Создать шаблон демотиватора\n\n"
        "<i>Для команд анализа чата обязательно используй Reply (Ответ) на длинное сообщение с логами переписки!</i>"
    )
    try:
        bot.reply_to(message, help_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка отправки help: {str(e)}")

# Новая команда /dialog — свободное общение в токсичном стиле
@bot.message_handler(commands=['dialog'])
def cmd_dialog(message):
    process_ai_command(message, 'ask')

# Регистрация всех остальных 13 команд
@bot.message_handler(commands=['summary'])
def cmd_summary(message): process_ai_command(message, 'summary')

@bot.message_handler(commands=['rating'])
def cmd_rating(message): process_ai_command(message, 'rating')

@bot.message_handler(commands=['rateme'])
def cmd_rateme(message): process_ai_command(message, 'rateme')

@bot.message_handler(commands=['psycho'])
def cmd_psycho(message): process_ai_command(message, 'psycho')

@bot.message_handler(commands=['psychome'])
def cmd_psychome(message): process_ai_command(message, 'psychome')

@bot.message_handler(commands=['ask'])
def cmd_ask(message): process_ai_command(message, 'ask')

@bot.message_handler(commands=['poll'])
def cmd_poll(message): process_ai_command(message, 'poll')

@bot.message_handler(commands=['taro'])
def cmd_taro(message): process_ai_command(message, 'taro')

@bot.message_handler(commands=['song'])
def cmd_song(message): process_ai_command(message, 'song')

@bot.message_handler(commands=['edit'])
def cmd_edit(message): process_ai_command(message, 'edit')

@bot.message_handler(commands=['create'])
def cmd_create(message): process_ai_command(message, 'create')

@bot.message_handler(commands=['future'])
def cmd_future(message): process_ai_command(message, 'future')

@bot.message_handler(commands=['meme'])
def cmd_meme(message): process_ai_command(message, 'meme')


# ==================== FLASK РОУТЫ ====================
@app.route('/', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        if json_data:
            update = telebot.types.Update.de_json(json_data)
            bot.process_new_updates([update])
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"Ошибка вебхука: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'alive'}), 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({'message': 'Telegram Bot API is running'}), 200

if __name__ == '__main__':
    app.run(debug=False)


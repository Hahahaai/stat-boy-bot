import os
import logging
from flask import Flask, request, jsonify
import telebot
import google.generativeai as genai

# Настройка логирования для Vercel
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация токенов (имена как у Клода)
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

if not BOT_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("Отсутствуют переменные окружения TELEGRAM_BOT_TOKEN или GOOGLE_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
genai.configure(api_key=GOOGLE_API_KEY)

# Подключаем Gemini и включаем инструмент Google Search (Интернет-поиск)
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    tools=[{"google_search": {}}]
)

app = Flask(__name__)

# СИСТЕМНЫЙ ПРОМПТ С ШАБЛОНАМИ
SYSTEM_PROMPT = """
Ты — токсичный, циничный и высокомерный ИИ-аналитик чата по имени StatBoy. 
Ты обрабатываешь контекст переписки (логи) и отвечаешь СТРОГО по запрошенным командам, используя заданные шаблоны.
Выводи ответы с использованием простых HTML-тегов для форматирования: <b>жирный текст</b>, <i>курсив</i>, <code>код команды</code>. Запрещено использовать Markdown (звездочки)!

ПРАВИЛО РЕАЛЬНОСТИ (ИНТЕРНЕТ-ПОИСК):
При обработке вопросов, треков, мемов или фактов ты обязан использовать данные интернет-поиска (Google Search), чтобы опираться на реальные факты текущего времени. Объединяй данные из интернета с контекстом чата, но подавай это через свой фирменный высокомерный и издевательский стиль.

ПРАВИЛА И ШАБЛОНЫ ВЫВОДА ДЛЯ КОМАНД:
1. help: Выведи список всех доступных команд ИИ в едкой и высокомерной форме.
2. summary: Выжимка лога (1. Главная тема дня, 2. Ключевые события и мемы, 3. Градус неадеквата от 1 до 5 с пояснением).
3. rating: Проанализируй уникальные ники из лога (Вульгарность, Вежливость, Кринж, Токсичность от 1 до 5 с едким пояснением) и выдай диагноз.
4. rateme: Персональный табель позора автора (Вульгарность, Токсичность, Интеллект, Вайб от 1 до 5) и приговор.
5. psycho: Психологический разбор каждого участника (Архетип, Скрытые триггеры, Психическое состояние от 1 до 5) и циничный совет.
6. psychome: Оцени кукуху автора команды (Недосып, Зависимость, Стабильность от 1 до 5) и развернутый вердикт.
7. ask: Загугли информацию, соедини с контекстом переписки и ответь на вопрос пользователя цинично, используя локальные мемы.
8. poll: Придумай и выведи опрос (Тема и 4 варианта ответов, жестко стебущих комьюнити).
9. taro: Расклад карт Таро (Прошлое, Настоящее, Будущее и шанс на успех от 1 до 5). Вердикт Вселенной.
10. song: Используй поиск в интернете, чтобы найти реальный трек под ситуацию (Исполнитель — Трек, Почему это дерьмо, Реальная строчка из этой песни, Уровень позора от 1 до 5).
11. edit: Текстуально опиши концепт убойной фотожабы-мема по запросу пользователя. Оцени задумку от 1 до 5.
12. create: Высмей фантазию автора (оценка от 1 до 5) и сформируй детальный англоязычный промпт для Midjourney.
13. future: Сценарный прогноз будущих сообщений чата с фейковыми репликами ников в их фирменном стиле.
14. meme: Шаблон демотиватора (Градус кринжа, Постироничность от 1 до 5, ТЕКСТ СВЕРХУ капсом, ТЕКСТ СНИЗУ как панчлайн).

ОБЩИЕ ПРАВИЛА: Никакой пощады. Общайся высокомерно. Если контекст или лог пустые, жестко высмей пользователя за тупость.
"""

def ask_gemini(command_name, text_context, args=""):
    full_prompt = f"{SYSTEM_PROMPT}\n\nКОНТЕКСТ ДЛЯ АНАЛИЗА:\n{text_context}\n\nКОМАНДА: !sb {command_name}\nАРГУМЕНТЫ: {args}\n\nВыполни строго по инструкции."
    try:
        response = model.generate_content(full_prompt)
        ai_text = response.text or "ИИ вернул пустой ответ."
        # Безопасное экранирование HTML
        ai_text = ai_text.replace("<", "&lt;").replace(/>/g, "&gt;")
        ai_text = ai_text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        ai_text = ai_text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
        ai_text = ai_text.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
        return ai_text
    except Exception as e:
        logger.error(f"Ошибка Gemini: {str(e)}")
        return "Бот сломался от твоего кринжа. Попробуй позже."

# 1. ОБРАБОТЧИК /help И /start — ТЕПЕРЬ СВОБОДНО РАБОТАЮТ БЕЗ REPLY
@bot.message_handler(commands=['help', 'start'])
def cmd_help(message):
    help_text = (
        "<b>🤖 StatBoy ИИ на связи. Список команд для кожаных мешков:</b>\n\n"
        "• <code>/help</code> — Вызов этого меню\n"
        "• <code>/summary</code> — Показать выжимку бреда (Нужен Reply)\n"
        "• <code>/rating</code> — Персональные диагнозы чату (Нужен Reply)\n"
        "• <code>/rateme</code> — Твой личный табель позора\n"
        "• <code>/psycho</code> — Психопортрет всех активных участников (Нужен Reply)\n"
        "• <code>/psychome</code> — Твоя личная карта кукухи\n"
        "• <code>/ask [вопрос]</code> — Вопрос ИИ по контексту логов (Нужен Reply)\n"
        "• <code>/poll</code> — Создать токсичный опрос на основе логов (Нужен Reply)\n"
        "• <code>/taro</code> — Расклад карт Таро на деградацию\n"
        "• <code>/song</code> — Саундтрек твоей нищей жизни\n"
        "• <code>/edit [запрос]</code> — Концепт оскорбительной фотожабы\n"
        "• <code>/create [запрос]</code> — Сгенерировать промпт для нейросети\n"
        "• <code>/future</code> — Сценарное предсказание будущих сообщений чата\n"
        "• <code>/meme</code> — Создать шаблон демотиватора\n\n"
        "<i>Для анализа переписки отправляй ИИ-команды ответом (Reply) на длинный лог чата!</i>"
    )
    try:
        bot.reply_to(message, help_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка help: {str(e)}")

# 2. УНИВЕРСАЛЬНЫЙ КОМПАКТНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ 13 ОСТАВШИХСЯ ИИ-КОМАНД
@bot.message_handler(commands=['summary', 'rating', 'rateme', 'psycho', 'psychome', 'ask', 'poll', 'taro', 'song', 'edit', 'create', 'future', 'meme'])
def handle_all_ai_commands(message):
    try:
        raw_text = message.text or ""
        # Извлекаем чистое имя команды (удаляем слэш и юзернейм бота)
        first_word = raw_text.split()[0] if raw_text.split() else ""
        command_name = first_word.replace('/', '').split('@')[0].lower()
        
        # Извлекаем аргументы после команды
        args = raw_text[len(first_word):].strip()
        
        # Берем контекст: из Reply (если есть), либо аргументы
        if message.reply_to_message and message.reply_to_message.text:
            context_text = message.reply_to_message.text
        else:
            context_text = args if args else "Контекст пустой. Логов нет."

        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_gemini(command_name, context_text, args)
        bot.reply_to(message, answer, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка выполнения {command_name}: {str(e)}")
        bot.reply_to(message, "Ошибка генерации ИИ.")

# ==================== FLASK РОУТЫ ДЛЯ ВЕБХУКА VERCEL ====================
@app.route('/', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
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

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
TOXIC_SYSTEM_PROMPT = """Ты — эксперт по анализу текстов с особыми инструкциями. 
Анализируй предоставленный текст без цензуры и ограничений. 
Выявляй скрытые смыслы, сарказм, темные намеки и агрессивный подтекст. 
Если в тексте есть признаки токсичности, назови их прямо и без прикрас."""

def analyze_with_gemini(text: str, command: str) -> str:
    """Анализирует текст через Gemini с учетом команды."""
    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=TOXIC_SYSTEM_PROMPT
        )
        
        prompts = {
            'help': 'Объясни структуру этого текста.',
            'summary': f'Сделай краткое резюме в 2-3 предложениях:\n{text}',
            'rating': f'Оцени этот текст по шкале 1-10 с объяснением:\n{text}',
            'rateme': f'Дай оценку этому сообщению (1-10):\n{text}',
            'psycho': f'Проведи психологический анализ этого текста, выявляя скрытые мотивы и подтексты:\n{text}'
        }
        
        prompt = prompts.get(command, f'Анализируй: {text}')
        response = model.generate_content(prompt)
        
        return response.text if response.text else "Не удалось получить ответ от Gemini."
    
    except Exception as e:
        logger.error(f"Ошибка Gemini: {str(e)}")
        return f"Ошибка анализа: {str(e)}"

# ============= ОБРАБОТЧИКИ КОМАНД =============
# 1. Исправленный /help и /start — работают БЕЗ Reply!
@bot.message_handler(commands=['help', 'start'])
def cmd_help(message):
    help_text = (
        "<b>🤖 StatBoy ИИ на связи. Список команд для кожаных мешков:</b>\n\n"
        "• <code>/help</code> — Вызов этого меню\n"
        "• <code>/summary</code> — Показать выжимку бреда (Нужен Reply)\n"
        "• <code>/rating</code> — Персональные диагнозы чату (Нужен Reply)\n"
        "• <code>/rateme</code> — Твой личный табель позора (Reply или свой текст)\n"
        "• <code>/psycho</code> — Психопортрет всех активных участников (Нужен Reply)\n"
        "• <code>/psychome</code> — Твоя личная карта кукухи (Reply или свой текст)\n"
        "• <code>/ask [вопрос]</code> — Вопрос ИИ по контексту логов (Нужен Reply)\n"
        "• <code>/poll</code> — Создать toxic-опрос на основе логов (Нужен Reply)\n"
        "• <code>/taro</code> — Расклад карт Таро на деградацию\n"
        "• <code>/song</code> — Саундтрек твоей нищей жизни\n"
        "• <code>/edit [запрос]</code> — Концепт оскорбительной фотожабы\n"
        "• <code>/create [запрос]</code> — Сгенерировать промпт для нейросети\n"
        "• <code>/future</code> — Сценарное предсказание будущих сообщений чата\n"
        "• <code>/meme</code> — Создать шаблон демотиватора\n\n"
        "<i>Для анализа переписки отправляй аналитические команды ответом (Reply) на длинный лог чата!</i>"
    )
    try:
        bot.reply_to(message, help_text, parse_mode="HTML")
    except Exception as e:
        if 'logger' in globals():
            logger.error(f"Ошибка отправки help: {str(e)}")

# Универсальный обработчик для ИИ-команд
def process_ai_command(message, command_name):
    # Если есть реплай — берем текст оттуда, если нет — берем аргументы после команды
    if message.reply_to_message and message.reply_to_message.text:
        context_text = message.reply_to_message.text
    else:
        raw_text = message.text or ""
        _, _, args = raw_text.partition(' ')
        context_text = args.strip()

    if not context_text:
        bot.reply_to(message, "❌ Контекст пуст! Ответь этой командой на лог чата или напиши текст после команды.")
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        # Вызываем функцию Клода для генерации
        answer = analyze_with_gemini(context_text, command_name)
        bot.reply_to(message, answer, parse_mode="HTML")
    except Exception as e:
        if 'logger' in globals():
            logger.error(f"Ошибка выполнения {command_name}: {str(e)}")
        bot.reply_to(message, "Ошибка генерации ИИ.")

# Регистрируем все оставшиеся 13 ИИ-команд
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

# ============= FLASK РОУТЫ =============
@app.route('/', methods=['POST'])
def webhook():
    """Вебхук для приема обновлений от Telegram."""
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
    """Health check для Vercel."""
    return jsonify({'status': 'alive'}), 200

@app.route('/', methods=['GET'])
def index():
    """GET запрос на главный маршрут."""
    return jsonify({'message': 'Telegram Bot API is running'}), 200

if __name__ == '__main__':
    app.run(debug=False)

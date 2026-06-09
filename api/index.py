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
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Приветственное сообщение."""
    text = (
        "🤖 <b>Привет!</b>\n\n"
        "Я бот для анализа текстов через AI.\n\n"
        "<b>Команды:</b>\n"
        "/help — Объяснить структуру текста\n"
        "/summary — Краткое резюме\n"
        "/rating — Оценка текста\n"
        "/rateme — Рейтинг сообщения\n"
        "/psycho — Психоанализ\n\n"
        "<i>Используй как reply на сообщение!</i>"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    """Команда /help — объяснение структуры."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text
    if not reply_text:
        bot.reply_to(message, "❌ В reply-сообщении нет текста!")
        return
    
    result = analyze_with_gemini(reply_text, 'help')
    bot.reply_to(message, f"📝 <b>Анализ структуры:</b>\n\n{result}")

@bot.message_handler(commands=['summary'])
def cmd_summary(message):
    """Команда /summary — резюме."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text
    if not reply_text:
        bot.reply_to(message, "❌ В reply-сообщении нет текста!")
        return
    
    result = analyze_with_gemini(reply_text, 'summary')
    bot.reply_to(message, f"📌 <b>Резюме:</b>\n\n{result}")

@bot.message_handler(commands=['rating'])
def cmd_rating(message):
    """Команда /rating — оценка текста."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text
    if not reply_text:
        bot.reply_to(message, "❌ В reply-сообщении нет текста!")
        return
    
    result = analyze_with_gemini(reply_text, 'rating')
    bot.reply_to(message, f"⭐ <b>Оценка:</b>\n\n{result}")

@bot.message_handler(commands=['rateme'])
def cmd_rateme(message):
    """Команда /rateme — рейтинг."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text
    if not reply_text:
        bot.reply_to(message, "❌ В reply-сообщении нет текста!")
        return
    
    result = analyze_with_gemini(reply_text, 'rateme')
    bot.reply_to(message, f"🎯 <b>Рейтинг:</b>\n\n{result}")

@bot.message_handler(commands=['psycho'])
def cmd_psycho(message):
    """Команда /psycho — психологический анализ."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text
    if not reply_text:
        bot.reply_to(message, "❌ В reply-сообщении нет текста!")
        return
    
    result = analyze_with_gemini(reply_text, 'psycho')
    bot.reply_to(message, f"🧠 <b>Психоанализ:</b>\n\n{result}")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """Обработка остальных сообщений."""
    bot.reply_to(message, "ℹ️ Используй команды: /start, /help, /summary, /rating, /rateme, /psycho")

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

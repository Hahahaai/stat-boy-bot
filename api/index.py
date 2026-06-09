import os
import json
from flask import Flask, request
import telebot
from google import genai
from google.genai import types as ai_types

# Инициализация клиентов
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), threaded=False)
ai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
app = Flask(__name__)

SYSTEM_PROMPT = """
Ты — токсичный, циничный ИИ-аналитик чата StatBoy. Отвечай СТРОГО по запрошенным командам. 
Используй HTML для форматирования (<b>жирный</b>, <i>курсив</i>, <code>код</code>). Без Markdown!

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
13. !sb future: прогноз будущих сообщений.
14. !sb meme: демотиватор (ТЕКСТ СВЕРХУ, ТЕКСТ СНИЗУ).

ОБЩИЕ ПРАВИЛА: Все оценки от 1 до 5. Никакой пощады, будь высокомерным. Если лог пуст, высмей юзера.
"""

# Обработка /help
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "<b>🤖 StatBoy ИИ. Список команд:</b>\n"
        "• <code>/help</code> — Меню помощи\n"
        "• <code>/summary</code> — Выжимка бреда из Reply\n"
        "• <code>/rating</code> — Диагнозы участникам из Reply\n"
        "• <code>/rateme</code> — Твой личный табель позора"
    )
    bot.reply_to(message, help_text, parse_mode="HTML")

# Универсальный вызов ИИ
def ask_gemini(command_name, text_context, args=""):
    clean_command = f"!sb {command_name} {args}"
    prompt = f"КОНТЕКСТ ДЛЯ АНАЛИЗА:\n{text_context}\n\nКОМАНДА: {clean_command}\n\nВыполни строго по инструкции."
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=ai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
        )
        ai_text = response.text.replace("<", "&lt;").replace(">", "&gt;")
        ai_text = ai_text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        ai_text = ai_text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
        ai_text = ai_text.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
        return ai_text
    except Exception as e:
        print(f"Ошибка Gemini: {e}")
        return "Бот сломался от твоего кринжа."

# Обработка команд анализа через Reply
@bot.message_handler(commands=['summary', 'rating', 'rateme', 'psycho', 'psychome', 'ask', 'poll', 'taro', 'song', 'edit', 'create', 'future', 'meme'])
def handle_analysis_commands(message):
    raw_text = message.text or ""
    words = raw_text.split()
    
    # Безопасное извлечение имени команды без вылетов
    if words:
        first_word = words[0].lower()
        command_name = first_word.replace('/', '').split('@')[0]
        args = raw_text[len(words[0]):].strip()
    else:
        command_name = "summary"
        args = ""
    
    # Реплика / контекст из Reply
    if message.reply_to_message and message.reply_to_message.text:
        context = message.reply_to_message.text
    else:
        context = raw_text

    bot.send_chat_action(message.chat.id, 'typing')
    answer = ask_gemini(command_name, context, args)
    bot.reply_to(message, answer, parse_mode="HTML")

# Роутинг вебхука Vercel
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

@app.route('/', methods=['GET'])
def index():
    return "<h1>StatBoy Python успешно работает на Vercel!</h1>", 200

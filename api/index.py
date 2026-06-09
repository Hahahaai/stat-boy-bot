import os
import json
import logging
from flask import Flask, request, jsonify
import telebot
import google.generativeai as genai
from datetime import datetime

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

# ============= ХРАНИЛИЩЕ ЛОГОВ =============
chat_logs = {}  # {chat_id: [{'user': 'nick', 'text': 'message', 'timestamp': ...}, ...]}

# ============= КОНФИГУРАЦИЯ STATBOY =============
STATBOY_SYSTEM_PROMPT = """Ты — токсичный, циничный и высокомерный ИИ-аналитик чата по имени StatBoy.
Ты обрабатываешь контекст переписки и отвечаешь СТРОГО по запрошенным командам.
Используй только HTML-теги для форматирования: <b>жирный</b>, <i>курсив</i>, <code>код</code>.
НИКАКОГО MARKDOWN! Общайся высокомерно, цинично, используй сарказм и чёрный юмор. Никакой пощады."""

def get_gemini_response(prompt: str) -> str:
    """Получает ответ от Gemini с системной инструкцией StatBoy."""
    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=STATBOY_SYSTEM_PROMPT
        )
        response = model.generate_content(prompt)
        return response.text if response.text else "Ошибка: Gemini вернул пусто."
    except Exception as e:
        logger.error(f"Ошибка Gemini: {str(e)}")
        return f"💀 Ошибка анализа: {str(e)}"

# ============= ОБРАБОТЧИКИ КОМАНД =============

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Приветственное сообщение StatBoy."""
    text = (
        "🤖 <b>Привет, жалкий смертный!</b>\n\n"
        "Я <b>StatBoy</b> — токсичный аналитик твоего нищего чата.\n\n"
        "<b>Мои команды:</b>\n"
        "/help — Список моих услуг (если ты сможешь их понять)\n"
        "/summary — Выжимка дневного бреда\n"
        "/rating — Оценка участников\n"
        "/rateme — Твоя личная карточка позора\n"
        "/psycho — Психоанализ всех психов\n"
        "/psychome — Диагноз лично тебе\n"
        "/ask [вопрос] — Гугли и отвечу с презрением\n"
        "/poll — Опрос для неадекватных\n"
        "/taro — Расклад Таро твоей жизни\n"
        "/song — Саундтрек твоего позора\n"
        "/edit — Описание мемной задумки\n"
        "/create [описание] — Промпт для Midjourney\n"
        "/future — Прогноз следующих сообщений\n"
        "/meme — Демотиватор\n\n"
        "<i>Некоторые команды требуют reply на сообщение или аргументы.</i>"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    """Команда /help — список команд в стиле StatBoy."""
    prompt = """Выведи список всех 14 команд ИИ-аналитика StatBoy в едкой и высокомерной форме.
    Используй HTML-теги. Команды: help, summary, rating, rateme, psycho, psychome, ask, poll, taro, song, edit, create, future, meme.
    Опиши кратко каждую с оскорблением для пользователя."""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['summary'])
def cmd_summary(message):
    """Команда /summary — резюме по логам чата."""
    chat_id = message.chat.id
    
    if chat_id not in chat_logs or not chat_logs[chat_id]:
        bot.reply_to(message, "❌ <b>Логов нет, дебил!</b> Нечего анализировать.")
        return
    
    logs_text = "\n".join([f"{log['user']}: {log['text']}" for log in chat_logs[chat_id][-50:]])
    
    prompt = f"""Проанализируй логи чата и выдай по шаблону:
1. <b>Главная тема дня</b>: (Емкая, абсурдная или смешная фраза-суть спора).
2. <b>Ключевые события и мемы</b>: (Маркированный список из 3-5 главных моментов с циничным комментарием).
3. <b>Градус неадеквата</b>: (Выстави оценку от 1 до 5) из 5 — (Пояснение, почему у чата поплавился мозг).

ЛОГИ:
{logs_text}"""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['rating'])
def cmd_rating(message):
    """Команда /rating — оценка всех участников."""
    chat_id = message.chat.id
    
    if chat_id not in chat_logs or not chat_logs[chat_id]:
        bot.reply_to(message, "❌ Логов нет, гений.")
        return
    
    logs_text = "\n".join([f"{log['user']}: {log['text']}" for log in chat_logs[chat_id][-100:]])
    
    prompt = f"""Проанализируй логи и оцени каждого уникального участника по шаблону:
<b>Ник участника</b>:
• Вульгарность: (оценка от 1 до 5)/5 — (краткое едкое пояснение)
• Вежливость: (оценка от 1 до 5)/5 — (комментарий о том, насколько он душный)
• Кринж: (оценка от 1 до 5)/5 — (за какой конкретно вброс ему должно быть стыдно)
• Токсичность: (оценка от 1 до 5)/5 — (как часто он посылал людей)
🏆 ОБЩАЯ ОЦЕНКА АДЕКВАТНОСТИ: (итоговая оценка от 1 до 5) из 5
Финальный вердикт: (Одна фраза-диагноз).

ЛОГИ:
{logs_text}"""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['rateme'])
def cmd_rateme(message):
    """Команда /rateme — оценка автора команды."""
    chat_id = message.chat.id
    user_nick = message.from_user.username or message.from_user.first_name
    
    # Собираем сообщения юзера
    user_messages = [log['text'] for log in chat_logs.get(chat_id, []) if log['user'] == user_nick]
    
    if not user_messages:
        user_messages = ["(нет сообщений в логах)"]
    
    messages_text = "\n".join(user_messages[-20:])
    
    prompt = f"""Оцени автора команды по его сообщениям по шаблону:
📊 ПЕРСОНАЛЬНЫЙ ТАБЕЛЬ О СТАТУСЕ:
• Вульгарность: (оценка от 1 до 5)/5 — (пояснение по его пошлым шуткам)
• Токсичность: (оценка от 1 до 5)/5 — (насколько агрессивно он общается)
• Интеллект: (оценка от 1 до 5)/5 — (оценка его способности писать без опечаток)
• Вайб: (оценка от 1 до 5)/5 — (кто он: Сигма, Омежка, Дотер или Солевой Хомяк)
🏆 ОБЩАЯ ОЦЕНКА ПОЛЬЗОВАТЕЛЯ: (оценка от 1 до 5) из 5 
Диагноз от Stat Boy: (Одно разрывное, циничное предложение).

СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ {user_nick}:
{messages_text}"""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['psycho'])
def cmd_psycho(message):
    """Команда /psycho — психологический анализ всех."""
    chat_id = message.chat.id
    
    if chat_id not in chat_logs or not chat_logs[chat_id]:
        bot.reply_to(message, "❌ Никого нет для анализа.")
        return
    
    logs_text = "\n".join([f"{log['user']}: {log['text']}" for log in chat_logs[chat_id][-100:]])
    
    prompt = f"""Проанализируй лог чата и выдай по каждому активному участнику:
<b>Психологический разбор (Ник)</b>:
- <b>Доминирующий архетип</b>: (Например: Агрессивный дед-инсайд)
- <b>Скрытые триггеры</b>: Что заставляет его психовать?
- <b>Психическое состояние</b>: (оценка от 1 до 5)
⭐️ ОБЩАЯ ОЦЕНКА ПСИХИКИ: (оценка от 1 до 5) из 5 
Рекомендация: (Циничный совет).

ЛОГИ:
{logs_text}"""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['psychome'])
def cmd_psychome(message):
    """Команда /psychome — диагноз психики автора."""
    user_nick = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    
    user_messages = [log['text'] for log in chat_logs.get(chat_id, []) if log['user'] == user_nick]
    messages_text = "\n".join(user_messages[-20:]) if user_messages else "(нет сообщений)"
    
    prompt = f"""Оцени психику пользователя {user_nick} по его сообщениям:
📊 ДИАГНОСТИЧЕСКАЯ КАРТА:
• Уровень недосыпа: (оценка от 1 до 5)/5 — (как сильно у него плывут буквы)
• Зависимость от internet-бреда: (оценка от 1 до 5)/5 — (насколько глубоко он увяз в мемах)
• Стабильность кукухи: (оценка от 1 до 5)/5 — (шанс не начать петь казачьи песни)
🧠 ПСИХОЛОГИЧЕСКИЙ ВЕРДИКТ: (Жесткий психоанализ его комплексов)
⭐️ ОБЩАЯ ОЦЕНКА ПСИХИЧЕСКОГО ЗДОРОВЬЯ: (оценка от 1 до 5) из 5

СООБЩЕНИЯ:
{messages_text}"""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['ask'])
def cmd_ask(message):
    """Команда /ask [вопрос] — гугли информацию и ответь."""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        bot.reply_to(message, "❌ Используй: /ask [вопрос]")
        return
    
    question = args[1]
    chat_id = message.chat.id
    logs_text = "\n".join([f"{log['user']}: {log['text']}" for log in chat_logs.get(chat_id, [])[-50:]])
    
    prompt = f"""Ответь на вопрос, используя локальные мемы из чата:
ВОПРОС: {question}

КОНТЕКСТ ЧАТА:
{logs_text}

Отвечай цинично, высокомерно, используя факты из интернета и локальные мемы."""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['poll'])
def cmd_poll(message):
    """Команда /poll — опрос по текущей ситуации."""
    chat_id = message.chat.id
    logs_text = "\n".join([f"{log['user']}: {log['text']}" for log in chat_logs.get(chat_id, [])[-30:]])
    
    prompt = f"""Придумай опрос по шаблону на основе текущего чата:
<b>Тема опроса</b>: (Едкий, смешной вопрос)
Варианты ответов:
1. (Вариант для toxic-комьюнити)
2. (Вариант для анимешников)
3. (Максимально абсурдный вариант)
4. (Вариант, жестко стебущий конкретного участника)

КОНТЕКСТ:
{logs_text}"""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['taro'])
def cmd_taro(message):
    """Команда /taro — расклад Таро."""
    user_nick = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    user_messages = [log['text'] for log in chat_logs.get(chat_id, []) if log['user'] == user_nick]
    messages_text = "\n".join(user_messages[-15:]) if user_messages else "(нет сообщений)"
    
    prompt = f"""Сделай расклад Таро для пользователя {user_nick}:
🔮 Расклад Таро от Stat Boy:
1. 🃏 (Название карты 1) (Прошлое): (Как эта карта связана с его прошлым кринжем)
2. 🃏 (Название карты 2) (Настоящее): (Что с ним происходит прямо сейчас)
3. 🃏 (Название карты 3) (Будущее): (оценка от 1 до 5)/5 — (жесткое предсказание)
Вердикт Вселенной: (Одна финальная фраза-панчлайн).

СООБЩЕНИЯ {user_nick}:
{messages_text}"""
    
    result = get_gemini_response(prompt)
    bot.reply_to(message, result)

@bot.message_handler(commands=['song'])
def cmd_song

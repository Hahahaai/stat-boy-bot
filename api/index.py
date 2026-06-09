Отлично! Вот переделанный код с поддержкой всех команд StatBoy и интеграцией Google Search:

```python
import os
import json
import logging
from flask import Flask, request, jsonify
import telebot
import google.generativeai as genai
from googlesearch import search
import random

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
STATBOY_SYSTEM_PROMPT = """Ты — токсичный, циничный и высокомерный ИИ-аналитик чата по имени StatBoy.
Ты обрабатываешь контекст переписки и отвечаешь в едком, издевательском стиле.
Используй только HTML-теги для форматирования: <b>жирный</b>, <i>курсив</i>, <code>код</code>.
Никакого Markdown! Будь жестким, саркастичным, черный юмор приветствуется.
Если контекст пустой — высмей пользователя за тупость."""

def analyze_with_gemini(text: str, command: str, author: str = None) -> str:
    """Анализирует текст через Gemini в стиле StatBoy."""
    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=STATBOY_SYSTEM_PROMPT
        )
        
        prompts = {
            'help': 'Выведи список доступных команд StatBoy в едкой форме.',
            'summary': f'Сделай выжимку по шаблону:\n1. <b>Главная тема</b>: (суть)\n2. <b>Ключевые события</b>: (список)\n3. <b>Градус неадеквата</b>: (1-5)/5\nТекст: {text}',
            'rating': f'Проанализируй участников по шаблону для каждого ника:\n• Вульгарность: (1-5)/5\n• Вежливость: (1-5)/5\n• Кринж: (1-5)/5\n• Токсичность: (1-5)/5\n🏆 ОБЩАЯ ОЦЕНКА: (1-5)/5\nТекст: {text}',
            'rateme': f'Оцени автора по шаблону:\n📊 ПЕРСОНАЛЬНЫЙ ТАБЕЛЬ:\n• Вульгарность: (1-5)/5\n• Токсичность: (1-5)/5\n• Интеллект: (1-5)/5\n• Вайб: (1-5)/5\n🏆 ОБЩАЯ ОЦЕНКА: (1-5)/5\nТекст: {text}',
            'psycho': f'Проведи психоанализ по шаблону:\n<b>Психологический разбор</b>:\n- <b>Доминирующий архетип</b>:\n- <b>Скрытые триггеры</b>:\n- <b>Психическое состояние</b>: (1-5)\n⭐️ ОБЩАЯ ОЦЕНКА: (1-5)/5\nТекст: {text}',
            'psychome': f'Диагностируй автора:\n📊 ДИАГНОСТИЧЕСКАЯ КАРТА:\n• Уровень недосыпа: (1-5)/5\n• Зависимость от интернет-бреда: (1-5)/5\n• Стабильность кукухи: (1-5)/5\n🧠 ПСИХОЛОГИЧЕСКИЙ ВЕРДИКТ: (развернутый анализ)\n⭐️ ОБЩАЯ ОЦЕНКА: (1-5)/5\nТекст: {text}',
            'poll': f'Придумай опрос по шаблону:\n<b>Тема опроса</b>: (едкий вопрос)\nВарианты:\n1. (для toxic)\n2. (для анимешников)\n3. (абсурд)\n4. (стеб конкретного участника)\nКонтекст: {text}',
            'taro': f'Сделай расклад Таро:\n🔮 Расклад для пользователя:\n1. 🃏 (Карта 1) (Прошлое)\n2. 🃏 (Карта 2) (Настоящее)\n3. 🃏 (Карта 3) (Будущее) (1-5)/5\nВердикт Вселенной: (финальная фраза)\nТекст: {text}',
            'future': f'Прогноз:\n📊 АНАЛИЗ ГОТОВНОСТИ:\n• Уровень адекватности: (1-5)/5\n• Процент выживания извилин: (0-100)%\n🔮 ПРЕДСКАЗАНИЕ СЛЕДУЮЩИХ СООБЩЕНИЙ: (фейковые сообщения в стиле участников)\n🎯 Финальный вердикт: (одно циничное предложение)\nТекст: {text}',
            'meme': f'Демотиватор:\n📊 ОЦЕНКА:\n• Градус кринжа: (1-5)/5\n• Постироничность: (1-5)/5\n🎨 ШАБЛОН:\n• ТЕКСТ СВЕРХУ: (КАПСОМ)\n• ТЕКСТ СНИЗУ: (панчлайн)\nТекст: {text}'
        }
        
        prompt = prompts.get(command, f'Анализируй в стиле StatBoy: {text}')
        response = model.generate_content(prompt)
        
        return response.text if response.text else "Gemini спит. Попробуй позже."
    
    except Exception as e:
        logger.error(f"Ошибка Gemini: {str(e)}")
        return f"<b>Ошибка анализа:</b> {str(e)}"

def search_web(query: str) -> str:
    """Поиск в интернете для команды /ask."""
    try:
        results = list(search(query, num_results=3))
        return " ".join(results[:3]) if results else "Интернет молчит."
    except Exception as e:
        logger.error(f"Ошибка поиска: {str(e)}")
        return "Google спит."

def generate_song_analysis(context: str) -> str:
    """Генерирует анализ трека для /song."""
    songs = [
        ("The Weeknd", "Blinding Lights", "I can't sleep until I feel your touch"),
        ("Billie Eilish", "Bad Guy", "So you think you're tough? I'm the baddest"),
        ("Eminem", "Lose Yourself", "You only get one shot, do not miss your chance"),
        ("Tyler, The Creator", "EARFQUAKE", "Do you love me or nah?"),
        ("Playboi Carti", "Magnolia", "Everything I do be legendary"),
    ]
    
    artist, track, lyric = random.choice(songs)
    return f"🎵 <b>{artist}</b> — <b>{track}</b>\n\n• <b>Почему это дерьмо</b>: Идеально описывает твою дегенерацию.\n• <b>Строчка из трека</b>: <i>«{lyric}»</i>\n⭐️ УРОВЕНЬ МУЗЫКАЛЬНОГО ПОЗОРА: 5/5"

# ============= ОБРАБОТЧИКИ КОМАНД =============
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Приветствие StatBoy."""
    text = (
        "🤖 <b>Привет, дегенерат!</b>\n\n"
        "Я <b>StatBoy</b> — токсичный аналитик твоего чата.\n\n"
        "<b>Команды:</b>\n"
        "/help — Список команд\n"
        "/summary — Выжимка лога\n"
        "/rating — Рейтинг участников\n"
        "/rateme — Оценка твоих сообщений\n"
        "/psycho — Психоанализ чата\n"
        "/psychome — Твоя кукуха\n"
        "/ask [вопрос] — Загугли и ответь\n"
        "/poll — Опрос\n"
        "/taro — Расклад Таро\n"
        "/song — Твой саундтрек\n"
        "/future — Прогноз\n"
        "/meme — Демотиватор\n\n"
        "<i>Используй как reply на сообщение (где требуется)!</i>"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    """Команда /help."""
    if message.reply_to_message:
        reply_text = message.reply_to_message.text or "пусто"
        result = analyze_with_gemini(reply_text, 'help')
    else:
        result = analyze_with_gemini("", 'help')
    
    bot.reply_to(message, f"📋 <b>StatBoy Commands:</b>\n\n{result}")

@bot.message_handler(commands=['summary'])
def cmd_summary(message):
    """Команда /summary."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение/лог этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'summary')
    bot.reply_to(message, f"📌 <b>Выжимка лога:</b>\n\n{result}")

@bot.message_handler(commands=['rating'])
def cmd_rating(message):
    """Команда /rating."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'rating')
    bot.reply_to(message, f"⭐️ <b>Рейтинг участников:</b>\n\n{result}")

@bot.message_handler(commands=['rateme'])
def cmd_rateme(message):
    """Команда /rateme."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'rateme')
    bot.reply_to(message, f"🎯 <b>Табель о статусе:</b>\n\n{result}")

@bot.message_handler(commands=['psycho'])
def cmd_psycho(message):
    """Команда /psycho."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'psycho')
    bot.reply_to(message, f"🧠 <b>Психоанализ:</b>\n\n{result}")

@bot.message_handler(commands=['psychome'])
def cmd_psychome(message):
    """Команда /psychome."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'psychome')
    bot.reply_to(message, f"🧠 <b>Диагностика:</b>\n\n{result}")

@bot.message_handler(commands=['ask'])
def cmd_ask(message):
    """Команда /ask [вопрос]."""
    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Использование: /ask [ваш вопрос]")
        return
    
    query = args[1]
    web_results = search_web(query)
    result = analyze_with_gemini(f"Вопрос: {query}\nРезультаты: {web_results}", 'ask')
    bot.reply_to(message, f"🔍 <b>StatBoy отвечает:</b>\n\n{result}")

@bot.message_handler(commands=['poll'])
def cmd_poll(message):
    """Команда /poll."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'poll')
    bot.reply_to(message, f"📊 <b>Опрос:</b>\n\n{result}")

@bot.message_handler(commands=['taro'])
def cmd_taro(message):
    """Команда /taro."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'taro')
    bot.reply_to(message, f"🔮 <b>Расклад Таро:</b>\n\n{result}")

@bot.message_handler(commands=['song'])
def cmd_song(message):
    """Команда /song."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = generate_song_analysis(reply_text)
    bot.reply_to(message, result)

@bot.message_handler(commands=['future'])
def cmd_future(message):
    """Команда /future."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'future')
    bot.reply_to(message, f"🔮 <b>Прогноз:</b>\n\n{result}")

@bot.message_handler(commands=['meme'])
def cmd_meme(message):
    """Команда /meme."""
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение этой командой!")
        return
    
    reply_text = message.reply_to_message.text or "пусто"
    result = analyze_with_gemini(reply_text, 'meme')
    bot.reply_to(message, f"🎨 <b>Демотиватор:</b>\n\n{result}")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """Обработка остальных сообщений."""
    text = (
        "

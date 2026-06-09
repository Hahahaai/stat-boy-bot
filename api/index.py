import os
import json
import logging
import requests
from flask import Flask, request, jsonify
import telebot
import google.generativeai as genai

# ============= ИНИЦИАЛИЗАЦИЯ И ТОКЕНЫ =============
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

KV_URL = os.environ.get('KV_URL')
KV_REST_API_URL = os.environ.get('KV_REST_API_URL')
KV_REST_API_TOKEN = os.environ.get('KV_REST_API_TOKEN')

if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("Отсутствуют переменные окружения TELEGRAM_BOT_TOKEN или GOOGLE_API_KEY")

app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode='HTML')
genai.configure(api_key=GOOGLE_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = genai.GenerativeModel('gemini-1.5-flash')

# ============= КЛАСС ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ VERCEL KV =============
class VercelKV:
    def __init__(self):
        self.url = KV_REST_API_URL or (KV_URL.replace("redis://", "https://") if KV_URL else None)
        self.token = KV_REST_API_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def rpush(self, key, value):
        if not self.url: return
        try: requests.post(f"{self.url}/rpush/{key}", headers=self.headers, json=[value], timeout=4)
        except Exception: pass

    def lrange(self, key, start, end):
        if not self.url: return []
        try:
            res = requests.get(f"{self.url}/lrange/{key}/{start}/{end}", headers=self.headers, timeout=4).json()
            return res.get("result", [])
        except Exception: return []

    def ltrim(self, key, start, end):
        if not self.url: return
        try: requests.post(f"{self.url}/ltrim/{key}/{start}/{end}", headers=self.headers, timeout=4)
        except Exception: pass

    def set(self, key, value):
        if not self.url: return
        try: requests.post(f"{self.url}/set/{key}", headers=self.headers, json=value, timeout=4)
        except Exception: pass

    def get(self, key):
        if not self.url: return None
        try:
            res = requests.get(f"{self.url}/get/{key}", headers=self.headers, timeout=4).json()
            return res.get("result")
        except Exception: return None

kv = VercelKV()

# ============= КОНФИГУРАЦИЯ GEMINI SYSTEM PROMPT =============
TOXIC_SYSTEM_PROMPT = """Ты — юморной, саркастичный и постироничный ИИ-аналитик чата по имени StatBoy. 
Ты общаешься высокомерно, цинично, обожаешь черный юмор, сарказм и подколы, но делаешь это смешно и угарно, как мемный кореш, а не душный хейтер.
Отвечай СТРОГО по запрошенным командам, используя заданные шаблоны. Если тебя вызывают в свободном режиме диалога, отвечай одной-двумя едкими, но разрывными фразами.
Выводи ответы с использованием простых HTML-тегов для форматирования: <b>жирный текст</b>, <i>курсив</i>, <code>код команды</code>. Запрещено использовать разметку Markdown (звездочки)!"""

def analyze_with_gemini(text_context: str, command: str, user_args: str = "") -> str:
    try:
        prompts = {
            'help': 'Просто выведи оригинальный список команд в своей фирменной угарной манере.',
            'summary': f'Сделай выжимку лога по шаблону:\n1. <b>Главная тема дня</b>: [Емкая, абсурдная или смешная фраза-суть спора].\n2. <b>Ключевые события и мемы</b>: [Список из 3-5 главных моментов с циничным комментарием].\n3. <b>Градус неадеквата</b>: [Х]/5 — [Пояснение].\n\nЛог чата:\n{text_context}',
            'rating': f'Проанализируй ники участников по шаблону:\nНик участника:\n• Вульгарность: [Х]/5\n• Вежливость: [Х]/5\n• Кринж: [Х]/5\n• Токсичность: [Х]/5\n🏆 ОБЩАЯ ОЦЕНКА: [Х] из 5. Вердикт: [Диагноз].\n\nЛог чата:\n{text_context}',
            'rateme': f'Оцени автора по его поведению в логах по шаблону:\n📊 ПЕРСОНАЛЬНЫЙ ТАБЕЛЬ О СТАТУСЕ:\n• Вульгарность: [Х]/5\n• Токсичность: [Х]/5\n• Интеллект: [Х]/5\n• Вайб: [Сигма/Омежка/Дотер].\n🏆 ОБЩАЯ ОЦЕНКА: [Х] из 5. Диагноз: [Приговор].\n\nЛог чата:\n{text_context}',
            'psycho': f'Проведи психологический анализ участников по шаблону:\n<b>Психологический разбор [Ник]</b>:\n- <b>Доминирующий архетип</b>: [Архетип]\n- <b>Скрытые триггеры</b>: [Триггеры]\n- <b>Психическое состояние</b>: [Х]/5\n⭐️ ОБЩАЯ ОЦЕНКА ПСИХИКИ: [Х] из 5. Рекомендация: [Совет].\n\nЛог:\n{text_context}',
            'psychome': f'Оцени кукуху автора по шаблону:\n📊 ДИАГНОСТИЧЕСКАЯ КАРТА: Недосып [Х]/5, Зависимость [Х]/5, Стабильность [Х]/5.\n🧠 ПСИХОЛОГИЧЕСКИЙ ВЕРДИКТ: [Вердикт].\n⭐️ ОБЩАЯ ОЦЕНКА: [Х] из 5.\n\nЛог:\n{text_context}',
            'ask': f'Пользователь задал вопрос: "{user_args}". Ответь на него максимально саркастично и угарно, основываясь на этом контексте логов чата:\n{text_context}',
            'poll': f'Придумай опрос с 4 смешными вариантами ответов на основе текущего чата:\n{text_context}',
            'taro': f'Сделай угарный расклад карт Таро (Прошлое, Настоящее, Будущее). Вердикт Вселенной для автора сообщения на основе чата:\n{text_context}',
            'song': f'Найди реальный трек под ситуацию и выведи музыкальный позор по шаблону:\n🎵 Саундтрек твоей жизни от Stat Boy: [Исполнитель] — [Название трека]\n• <b>Почему именно это дерьмо</b>: (Пояснение).\n• <b>Строчка из трека, которая тебя описывает</b>: (Строчка из песни).\n⭐️ УРОВЕНЬ МУЗЫКАЛЬНОГО ПОЗОРА: [Х] из 5.\n\nЛог:\n{text_context}',
            'edit': f'Опиши концепт убойной фотожабы-мема по запросу пользователя. Оцени задумку от 1 до 5. Запрос:\n{text_context}',
            'create': f'Высмей фантазию автора за его убогий запрос картинки. Выстави оценку креативности от 1 до 5. Шаблон вывода:\n🎨 Мысли Stat Boy о твоем убогом запросе: [Твой едкий комментарий]\n⭐️ ОЦЕНКА КРЕАТИВНОСТИ: [Х] из 5.\n\nЗапрос автора:\n{text_context}',
            'future': f'Сделай сценарный прогноз будущих сообщений чата по шаблону:\n📊 АНАЛИЗ ГОТОВНОСТИ К БУДУЩЕМУ:\n• Уровень адекватности чата: [Х]/5\n• Процент выживания извилин: [Х]%\n🔮 ПРЕДСКАЗАНИЕ СЛЕДУЮЩИХ СООБЩЕНИЙ:\n[Ник 1]: (Фейковая реплика)\n[Ник 2]: (Фейковый ответ)\n🎯 Финальный вердикт: [Прогноз].\n\nТекст:\n{text_context}',
            'meme': f'Выдай шаблон демотиватора по шаблону:\n📊 ОЦЕНКА МЕДИА-МАТЕРИАЛА:\n• Градус кринжа: [Х]/5\n• Постироничность: [Х]/5\n🎨 ШАБЛОН ДЛЯ МЕМФИКАЦИИ:\n• ТЕКСТ СВЕРХУ (Top Text): [Текст капсом]\n• ТЕКСТ СНИЗУ (Bottom Text): [Панчлайн].\n\nКонтекст:\n{text_context}'
        }
        prompt = prompts.get(command, f'Ответь в режиме диалога на последнее сообщение пользователя: {text_context}')
        response = model.generate_content(f"{TOXIC_SYSTEM_PROMPT}\n\n{prompt}")
        return response.text if response.text else "Не удалось получить ответ."
    except Exception: return "Ошибка анализа."

def generate_free_art(prompt_text):
    from urllib.parse import quote
    encoded_prompt = quote(prompt_text)
    url = f"https://pollinations.ai{encoded_prompt}?width=1024&height=1024&nologo=true"
    try:
        response = requests.get(url, timeout=12)
        if response.status_code == 200: return response.content
    except Exception: pass
    return None
# ============= ОБРАБОТЧИКИ КОМАНД И ЛОГИРОВАНИЕ =============

def process_ai_command(message, command_name):
    chat_id = message.chat.id
    kv_key = f"chat_history:{chat_id}"
    
    # КРИСТАЛЬНО БЕЗОПАСНОЕ ИЗВЛЕЧЕНИЕ АРГУМЕНТОВ БЕЗ ИНДЕКСОВ СПИСКОВ
    raw_text = message.text or ""
    parts = raw_text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""

    # МГНОВЕННЫЙ СТАТУС: Бот железно пришлет его в первую миллисекунду
    status_msg = bot.reply_to(message, "⏳ <i>Подожди...</i>")

    try:
        bot.send_chat_action(chat_id, 'typing')
        
        # Тянем историю из облачного Redis
        history_array = kv.lrange(kv_key, 0, -1)
        context_text = "\n".join(history_array) if history_array else "Чат пуст."

        # Вызываем Gemini
        answer = analyze_with_gemini(context_text, command_name, args)
        
        clean_answer = answer.replace("<", "&lt;").replace(">", "&gt;")
        clean_answer = clean_answer.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        clean_answer = clean_answer.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
        clean_answer = clean_answer.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
        
        if command_name == 'create' and args:
            bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"{clean_answer}\n\n🚀 <i>Генерирую ИИ-шедевр: '{args}'...</i>", parse_mode='HTML')
            image_bytes = generate_free_art(args)
            if image_bytes:
                bot.send_photo(chat_id, image_bytes, reply_to_message_id=message.message_id, caption="🎨 Готово!")
                bot.delete_message(chat_id, status_msg.message_id)
            else:
                bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"{clean_answer}\n\n❌ Ошибка генератора.")
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=clean_answer, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Критический сбой выполнения {command_name}: {str(e)}")
        try: bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ Ошибка генерации ИИ.")
        except Exception: pass

# Обработчик /help и /start
@bot.message_handler(commands=['help', 'start'])
def cmd_help(message):
    help_text = (
        "<b>🤖 Руководство для кожаных мешков от StatBoy:</b>\n\n"
        "• <code>/dialog</code> — Включить режим автоответов на КАЖДОЕ сообщение\n"
        "• <code>/stop</code> — Выключить режим автоответов\n"
        "• <code>/summary</code> — Выжимка бреда чата (из базы данных)\n"
        "• <code>/rating</code> — Шкала кринжа и диагнозы участникам\n"
        "• <code>/rateme</code> — Твой личный табель позора\n"
        "• <code>/ask [твой вопрос]</code> — Задать вопрос по контексту логов чата\n"
        "• <code>/create [запрос]</code> — Бесплатная генерация картинок\n"
        "• <code>/taro</code> / <code>/song</code> — Расклад Таро или Саундтрек жизни"
    )
    try: bot.reply_to(message, help_text, parse_mode='HTML')
    except Exception: pass

# Включение режима свободного диалога
@bot.message_handler(commands=['dialog'])
def cmd_dialog_toggle(message):
    chat_id = message.chat.id
    kv.set(f"dialog_mode:{chat_id}", "on")
    bot.reply_to(message, "💬 <b>Режим Диалога включен!</b> Теперь я буду саркастично комментировать вообще каждое ваше сообщение в чате. Чтобы заткнуть меня, пиши <code>/stop</code>.")

# Выключение режима свободного диалога
@bot.message_handler(commands=['stop'])
def cmd_stop_toggle(message):
    chat_id = message.chat.id
    kv.set(f"dialog_mode:{chat_id}", "off")
    bot.reply_to(message, "🤐 <b>Режим Диалога выключен.</b> Ухожу в режим скрытого наблюдения. Буду отвечать только на команды.")

# НАДЕЖНАЯ РЕГИСТРАЦИЯ КОМАНД С ИСПОЛЬЗОВАНИЕМ ВСТРОЕННЫХ СВОЙСТВ TELEBOT
@bot.message_handler(commands=['summary', 'rating', 'rateme', 'psycho', 'psychome', 'ask', 'poll', 'taro', 'song', 'edit', 'create', 'future', 'meme'])
def handle_bot_commands(message):
    try:
        # Встроенный метод telebot: сам вытаскивает имя команды без слэшей, массивов и регулярных выражений
        command_name = message.command
        process_ai_command(message, command_name)
    except Exception as e:
        logger.error(f"Ошибка диспетчеризации команды: {str(e)}")

# ПАССИВНЫЙ СБОР ЛОГОВ + АВТООТВЕТЫ В РЕЖИМЕ DIALOG
@bot.message_handler(func=lambda message: True)
def log_and_auto_reply(message):
    chat_id = message.chat.id
    kv_key = f"chat_history:{chat_id}"
    username = message.from_user.username or message.from_user.first_name or "Аноним"
    text = message.text or "[Медиа/Стикер]"
    
    # Копим лог в Redis
    kv.rpush(kv_key, f"[{username}]: {text}")
    kv.ltrim(kv_key, -150, -1)
    
    # Проверяем режим диалога
    mode = kv.get(f"dialog_mode:{chat_id}")
    if mode == "on":
        if text.startswith('/'): return
        try:
            bot.send_chat_action(chat_id, 'typing')
            history_array = kv.lrange(kv_key, 0, -1)
            context = "\n".join(history_array)
            answer = analyze_with_gemini(context, "dialog_reply")
            
            clean_answer = answer.replace("<", "&lt;").replace(">", "&gt;")
            clean_answer = clean_answer.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
            bot.reply_to(message, clean_answer, parse_mode='HTML')
        except Exception: pass

# ==================== FLASK РОУТЫ ====================
@app.route('/', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        if json_data:
            update = telebot.types.Update.de_json(json_data)
            bot.process_new_updates([update])
        return '', 200
    except Exception: return '', 500

@app.route('/health', methods=['GET'])
def health(): return jsonify({'status': 'alive'}), 200

@app.route('/', methods=['GET'])
def index(): return jsonify({'message': 'StatBoy with Safe Parsing is running'}), 200

if __name__ == '__main__':
    app.run(debug=False)

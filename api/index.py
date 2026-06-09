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
        except Exception as e: logger.error(f"KV Write Error: {e}")

    def lrange(self, key, start, end):
        if not self.url: return []
        try:
            res = requests.get(f"{self.url}/lrange/{key}/{start}/{end}", headers=self.headers, timeout=4).json()
            return res.get("result", [])
        except Exception as e: 
            logger.error(f"KV Read Error: {e}")
            return []

    def ltrim(self, key, start, end):
        if not self.url: return
        try: requests.post(f"{self.url}/ltrim/{key}/{start}/{end}", headers=self.headers, timeout=4)
        except Exception as e: logger.error(f"KV Trim Error: {e}")

    def set(self, key, value):
        if not self.url: return
        try: requests.post(f"{self.url}/set/{key}", headers=self.headers, json=value, timeout=4)
        except Exception as e: logger.error(f"KV Set Error: {e}")

    def get(self, key):
        if not self.url: return None
        try:
            res = requests.get(f"{self.url}/get/{key}", headers=self.headers, timeout=4).json()
            return res.get("result")
        except Exception as e: 
            logger.error(f"KV Get Error: {e}")
            return None

kv = VercelKV()

# ============= КОНФИГУРАЦИЯ GEMINI SYSTEM PROMPT =============
TOXIC_SYSTEM_PROMPT = """Ты — юморной, саркастичный и постироничный ИИ-аналитик чата по имени StatBoy. 
Ты общаешься высокомерно, цинично, обожаешь черный юмор, сарказм и подколы, но делаешь это смешно и угарно, как мемный кореш, а не душный хейтер.
Отвечай СТРОГО по запрошенным командам, используя заданные шаблоны. Если тебя вызывают в свободном режиме диалога, отвечай одной-двумя едкими, но разрывными фразами.
Выводи ответы с использованием простых HTML-тегов для форматирования: <b>жирный текст</b>, <i>курсив</i>, <code>код команды</code>. Запрещено использовать разметку Markdown (звездочки)!"""

# ФИКС КЛОДА №1 и №2: Добавлен и полноценно задействован параметр user_args во всех промптах!
def analyze_with_gemini(text_context: str, command: str, user_args: str = "") -> str:
    try:
        prompts = {
            'help': 'Просто выведи оригинальный список команд в своей фирменной угарной манере.',
            'summary': f'Сделай выжимку лога по шаблону:\n1. <b>Главная тема дня</b>: [Емкая фраза-суть спора].\n2. <b>Ключевые события и мемы</b>: [Список из 3-5 моментов с циничным комментарием].\n3. <b>Градус неадеквата</b>: [Х]/5 — [Пояснение].\n\nЛог чата:\n{text_context}',
            'rating': f'Проанализируй ники участников по шаблону:\nНик участника:\n• Вульгарность: [Х]/5\n• Вежливость: [Х]/5\n• Кринж: [Х]/5\n• Токсичность: [Х]/5\n🏆 ОБЩАЯ ОЦЕНКА: [Х] из 5. Вердикт: [Диагноз].\n\nЛог чата:\n{text_context}',
            'rateme': f'Оцени автора по его поведению в логах по шаблону:\n📊 ПЕРСОНАЛЬНЫЙ ТАБЕЛЬ О СТАТУСЕ:\n• Вульгарность: [Х]/5\n• Токсичность: [Х]/5\n• Интеллект: [Х]/5\n• Вайб: [Сигма/Омежка/Дотер].\n🏆 ОБЩАЯ ОЦЕНКА: [Х] из 5. Диагноз: [Приговор].\n\nЛог чата:\n{text_context}',
            'psycho': f'Проведи психологический анализ участников по шаблону:\n<b>Психологический разбор [Ник]</b>:\n- <b>Доминирующий архетип</b>: [Архетип]\n- <b>Скрытые триггеры</b>: [Триггеры]\n- <b>Психическое состояние</b>: [Х]/5\n⭐️ ОБЩАЯ ОЦЕНКА ПСИХИКИ: [Х] из 5. Рекомендация: [Совет].\n\nЛог:\n{text_context}',
            'psychome': f'Оцени кукуху автора по шаблону:\n📊 ДИАГНОСТИЧЕСКАЯ КАРТА: Недосып [Х]/5, Зависимость [Х]/5, Стабильность [Х]/5.\n🧠 ПСИХОЛОГИЧЕСКИЙ ВЕРДИКТ: [Вердикт].\n⭐️ ОБЩАЯ ОЦЕНКА: [Х] из 5.\n\nЛог:\n{text_context}',
            'ask': f'Пользователь задал конкретный вопрос: "{user_args}". Ответь на него максимально саркастично, опираясь на этот контекст логов чата:\n{text_context}',
            'poll': f'Придумай опрос с 4 смешными вариантами ответов на основе текущего чата:\n{text_context}',
            'taro': f'Сделай угарный расклад карт Таро (Прошлое, Настоящее, Будущее и шанс на успех от 1 до 5). Вердикт Вселенной для автора сообщения на основе чата:\n{text_context}',
            'song': f'Найди реальный трек под ситуацию и выведи музыкальный позор по шаблону:\n🎵 Саундтрек твоей жизни от Stat Boy: [Исполнитель] — [Название трека]\n• <b>Почему именно это дерьмо</b>: (Пояснение).\n• <b>Строчка из трека, которая тебя описывает</b>: (Строчка из песни).\n⭐️ УРОВЕНЬ МУЗЫКАЛЬНОГО ПОЗОРА: [Х] из 5.\n\nЛог:\n{text_context}',
            'edit': f'Опиши концепт убойной фотожабы-мема по конкретному запросу пользователя: "{user_args}". Оцени задумку от 1 до 5.\n\nКонтекст чата:\n{text_context}',
            'create': f'Высмей фантазию автора за его убогий запрос картинки: "{user_args}". Выстави оценку креативности от 1 до 5. Шаблон вывода:\n🎨 Мысли Stat Boy о твоем убогом запросе: [Твой едкий комментарий]\n⭐️ ОЦЕНКА КРЕАТИВНОСТИ: [Х] из 5.\n\nЗапрос автора:\n{text_context}',
            'future': f'Сделай сценарный прогноз будущих сообщений чата по шаблону:\n📊 АНАЛИЗ ГОТОВНОСТИ К БУДУЩЕМУ:\n• Уровень адекватности чата: [Х]/5\n• Процент выживания извилин: [Х]%\n🔮 ПРЕДСКАЗАНИЕ СЛЕДУЮЩИХ СООБЩЕНИЙ:\n[Ник 1]: (Фейковая реплика)\n[Ник 2]: (Фейковый ответ)\n🎯 Финальный вердикт: [Прогноз].\n\nТекст:\n{text_context}',
            'meme': f'Выдай шаблон демотиватора по шаблону:\n📊 ОЦЕНКА МЕДИА-МАТЕРИАЛА:\n• Градус кринжа: [Х]/5\n• Постироничность: [Х]/5\n🎨 ШАБЛОН ДЛЯ МЕМФИКАЦИИ:\n• ТЕКСТ СВЕРХУ (Top Text): [Текст капсом]\n• ТЕКСТ СНИЗУ (Bottom Text): [Панчлайн].\n\nКонтекст:\n{text_context}'
        }
        prompt = prompts.get(command, f'В режиме диалога ответь на сообщение: {user_args or text_context}')
        response = model.generate_content(f"{TOXIC_SYSTEM_PROMPT}\n\n{prompt}")
        return response.text if response.text else "Не удалось получить ответ."
    except Exception as e:
        logger.error(f"Gemini Core Error: {e}")
        return "Ошибка анализа."

def generate_free_art(prompt_text):
    from urllib.parse import quote
    encoded_prompt = quote(prompt_text)
    url = f"https://pollinations.ai{encoded_prompt}?width=1024&height=1024&nologo=true"
    try:
        response = requests.get(url, timeout=12)
        if response.status_code == 200: return response.content
    except Exception as e:
        logger.error(f"Art Generator Link Failed: {e}")
    return None
# ============= ОБРАБОТЧИКИ КОМАНД И ЛОГИРОВАНИЕ =============

def process_ai_command(message, command_name):
    chat_id = message.chat.id
    kv_key = f"chat_history:{chat_id}"
    
    # Извлекаем текст после команды
    raw_text = message.text or ""
    _, _, args_raw = raw_text.partition(' ')
    args = args_raw.strip()

    # МГНОВЕННЫЙ СТАТУС: Бот железно пришлет его в первую миллисекунду
    status_msg = bot.reply_to(message, "⏳ <i>Подожди...</i>")

    try:
        bot.send_chat_action(chat_id, 'typing')
        
        # Загружаем пассивно собранный лог группы из Redis
        history_array = kv.lrange(kv_key, 0, -1)
        context_text = "\n".join(history_array) if history_array else "Чат пуст."

        # ФИКС КЛОДА №1 (Исправлен вызов - теперь передается ровно 3 аргумента!)
        answer = analyze_with_gemini(context_text, command_name, args)
        
        # ФИКС КЛОДА №3: Безопасная, устойчивая к падениям замена HTML-тегов
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
        # ФИКС КЛОДА №4: Ошибки больше не прячутся в pass, а честно выводятся в дебаг логов Vercel!
        logger.error(f"Критический сбой выполнения {command_name}: {str(e)}")
        try: bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ Ошибка генерации ИИ.")
        except Exception as err: logger.error(f"Failed to send error status: {err}")

# Обработчик /help и /start
@bot.message_handler(commands=['help', 'start'])
def cmd_help(message):
    help_text = (
        "<b>🤖 Руководство для кожаных мешков от Стат Боя:</b>\n\n"
        "• <code>/dialog</code> — Включить режим автоответов на ВСЕ сообщения чата\n"
        "• <code>/stop</code> — Выключить автоответы ИИ\n"
        "• <code>/summary</code> — Выжимка бреда чата (из базы)\n"
        "• <code>/rating</code> — Шкала кринжа и диагнозы участникам\n"
        "• <code>/rateme</code> — Твой личный табель позора из логов\n"
        "• <code>/ask [твой вопрос]</code> — Вопрос ИИ по контексту логов чата\n"
        "• <code>/create [запрос]</code> — Бесплатная моментальная генерация картинок\n"
        "• <code>/taro</code> / <code>/song</code> — Расклад Таро или Саундтрек твоей жизни"
    )
    try: bot.reply_to(message, help_text, parse_mode='HTML')
    except Exception as e: logger.error(f"Help send failed: {e}")

# Включение режима свободного диалога
@bot.message_handler(commands=['dialog'])
def cmd_dialog_toggle(message):
    chat_id = message.chat.id
    kv.set(f"dialog_mode:{chat_id}", "on")
    bot.reply_to(message, "💬 <b>Режим Диалога включен!</b> Теперь я буду комментировать вообще каждое ваше сообщение в чате. Чтобы заткнуть меня, пиши <code>/stop</code>.")

# Выключение режима свободного диалога
@bot.message_handler(commands=['stop'])
def cmd_stop_toggle(message):
    chat_id = message.chat.id
    kv.set(f"dialog_mode:{chat_id}", "off")
    bot.reply_to(message, "🤐 <b>Режим Диалога выключен.</b> Ухожу в режим пассивного наблюдения.")

# Регистрация ИИ-команд
@bot.message_handler(commands=['summary', 'rating', 'rateme', 'psycho', 'psychome', 'ask', 'poll', 'taro', 'song', 'edit', 'create', 'future', 'meme'])
def handle_bot_commands(message):
    try:
        raw_cmd = message.text or ""
        first_word = raw_cmd.split()[0].lower() if raw_cmd.split() else ""
        clean_cmd = first_word.replace('/', '').split('@')[0]
        process_ai_command(message, clean_cmd)
    except Exception as e:
        logger.error(f"Ошибка диспетчера команд: {str(e)}")

# ПАССИВНЫЙ СБОР ЛОГОВ + АВТООТВЕТЫ В РЕЖИМЕ DIALOG
@bot.message_handler(func=lambda message: True)
def log_and_auto_reply(message):
    chat_id = message.chat.id
    kv_key = f"chat_history:{chat_id}"
    username = message.from_user.username or message.from_user.first_name or "Аноним"
    text = message.text or "[Медиа/Стикер]"
    
    if text.startswith('/'): return

    # Копим лог в Redis
    kv.rpush(kv_key, f"[{username}]: {text}")
    kv.ltrim(kv_key, -150, -1)
    
    # Проверяем режим диалога
    mode = kv.get(f"dialog_mode:{chat_id}")
    if mode == "on":
        try:
            bot.send_chat_action(chat_id, 'typing')
            history_array = kv.lrange(kv_key, 0, -1)
            context = "\n".join(history_array)
            answer = analyze_with_gemini(context, "dialog_reply", text)
            
            clean_answer = answer.replace("<", "&lt;").replace(">", "&gt;")
            clean_answer = clean_answer.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
            bot.reply_to(message, clean_answer, parse_mode='HTML')
        except Exception as e: logger.error(f"Auto-reply loop error: {e}")

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
        logger.error(f"Webhook Fatal Error: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/health', methods=['GET'])
def health(): return jsonify({'status': 'alive'}), 200

@app.route('/', methods=['GET'])
def index(): return jsonify({'message': 'StatBoy Fixed is running'}), 200

if __name__ == '__main__':
    app.run(debug=False)

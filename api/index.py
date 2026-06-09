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

# Переменные для подключения к бесплатной базе данных Vercel KV Redis
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
    """Класс для прямого асинхронного взаимодействия с Redis базой данных через HTTP REST API."""
    def __init__(self):
        self.url = KV_REST_API_URL or (KV_URL.replace("redis://", "https://") if KV_URL else None)
        self.token = KV_REST_API_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def rpush(self, key, value):
        """Пассивное добавление сообщения в конец списка логов чата."""
        if not self.url: return
        try:
            requests.post(f"{self.url}/rpush/{key}", headers=self.headers, json=[value], timeout=4)
        except Exception as e:
            logger.error(f"Ошибка записи в Redis: {e}")

    def lrange(self, key, start, end):
        """Извлечение накопленной истории переписки из базы."""
        if not self.url: return []
        try:
            res = requests.get(f"{self.url}/lrange/{key}/{start}/{end}", headers=self.headers, timeout=4).json()
            return res.get("result", [])
        except Exception as e:
            logger.error(f"Ошибка чтения из Redis: {e}")
            return []

    def ltrim(self, key, start, end):
        """Очистка старых логов, чтобы база оставалась бесплатной."""
        if not self.url: return
        try:
            requests.post(f"{self.url}/ltrim/{key}/{start}/{end}", headers=self.headers, timeout=4)
        except Exception as e:
            logger.error(f"Ошибка очистки Redis: {e}")

kv = VercelKV()

# ============= КОНФИГУРАЦИЯ GEMINI SYSTEM PROMPT =============
TOXIC_SYSTEM_PROMPT = """Ты — токсичный, циничный и высокомерный ИИ-аналитик чата по имени StatBoy. 
Ты обрабатываешь контекст переписки (логи) и отвечаешь СТРОГО по запрошенным командам, используя заданные шаблоны.
Выводи ответы с использованием простых HTML-тегов для форматирования: <b>жирный текст</b>, <i>курсив</i>, <code>код команды</code>. 
Категорически запрещено использовать разметку Markdown (звездочки)! Общайся высокомерно. Если контекст пустой, высмей пользователя за тупость."""

def analyze_with_gemini(text_context: str, command: str) -> str:
    """Анализирует лог чата через Gemini с учетом выбранной команды."""
    try:
        prompts = {
            'help': 'Просто выведи оригинальный список команд в высокомерной форме.',
            'summary': f'Сделай выжимку лога по шаблону:\n1. <b>Главная тема дня</b>: [Суть спора].\n2. <b>Ключевые события и mемы</b>: [Список из 3-5 главных моментов с циничным комментарием].\n3. <b>Градус неадеквата</b>: [Х]/5 — [Пояснение].\n\nЛог чата:\n{text_context}',
            'rating': f'Проанализируй ники участников из лога чата по шаблону:\nНик участника:\n• Вульгарность: [Х]/5\n• Вежливость: [Х]/5\n• Кринж: [Х]/5\n• Токсичность: [Х]/5\n🏆 ОБЩАЯ ОЦЕНКА: [Х] из 5. Вердикт: [Диагноз].\n\nЛог чата:\n{text_context}',
            'rateme': f'Оцени автора сообщения по его поведению в логах по шаблону:\n📊 ПЕРСОНАЛЬНЫЙ ТАБЕЛЬ О СТАТУСЕ:\n• Вульгарность: [Х]/5\n• Токсичность: [Х]/5\n• Интеллект: [Х]/5\n• Вайб: [Сигма/Омежка/Дотер].\n🏆 ОБЩАЯ ОЦЕНКА ПОЛЬЗОВАТЕЛЯ: [Х] из 5. Диагноз: [Приговор].\n\nЛог чата:\n{text_context}',
            'psycho': f'Проведи психологический анализ участников чата по шаблону:\n<b>Психологический разбор [Ник]</b>:\n- <b>Доминирующий архетип</b>: [Архетип]\n- <b>Скрытые триггеры</b>: [Триггеры]\n- <b>Психическое состояние</b>: [Х]/5\n⭐️ ОБЩАЯ ОЦЕНКА ПСИХИКИ: [Х] из 5. Рекомендация: [Совет].\n\nЛог:\n{text_context}',
            'psychome': f'Оцени кукуху автора по шаблону:\n📊 ДИАГНОСТИЧЕСКАЯ КАРТА: Недосып [Х]/5, Зависимость от интернет-бреда [Х]/5, Стабильность кукухи [Х]/5.\n🧠 ПСИХОЛОГИЧЕСКИЙ ВЕРДИКТ: [Вердикт].\n⭐️ ОБЩАЯ ОЦЕНКА: [Х] из 5.\n\nЛог:\n{text_context}',
            'ask': f'Ответь на вопрос пользователя цинично, используя локальные мемы на основе лога чата:\n{text_context}',
            'poll': f'Придумай опрос с 4 токсичными вариантами ответов на основе текущего чата:\n{text_context}',
            'taro': f'Сделай расклад карт Таро (Прошлое, Настоящее, Будущее и шанс на успех от 1 до 5). Вердикт Вселенной для автора сообщения на основе чата:\n{text_context}',
            'song': f'Найди реальный трек под ситуацию и выведи музыкальный позор по шаблону:\n🎵 Саундтрек твоей жизни от Stat Boy: [Исполнитель] — [Название трека]\n• <b>Почему именно это дерьмо</b>: (Пояснение).\n• <b>Строчка из трека, которая тебя описывает</b>: (Строчка из песни).\n⭐️ УРОВЕНЬ МУЗЫКАЛЬНОГО ПОЗОРА: [Х] из 5.\n\nЛог:\n{text_context}',
            'edit': f'Опиши текстовый концепт убойной оскорбительной фотожабы-мема по запросу пользователя. Оцени задумку от 1 до 5. Запрос:\n{text_context}',
            'create': f'Высмей фантазию автора за его убогий запрос картинки. Выстави оценку креативности от 1 до 5. Шаблон вывода:\n🎨 Мысли Stat Boy о твоем убогом запросе: [Твой едкий комментарий]\n⭐️ ОЦЕНКА КРЕАТИВНОСТИ: [Х] из 5.\n\nЗапрос автора:\n{text_context}',
            'future': f'Сделай сценарный прогноз будущих сообщений чата по шаблону:\n📊 АНАЛИЗ ГОТОВНОСТИ К БУДУЩЕМУ:\n• Уровень адекватности чата: [Х]/5\n• Процент выживания извилин: [Х]%\n🔮 ПРЕДСКАЗАНИЕ СЛЕДУЮЩИХ СООБЩЕНИЙ:\n[Ник 1]: (Фейковая реплика)\n[Ник 2]: (Фейковый ответ)\n🎯 Финальный вердикт: [Прогноз].\n\nЛог:\n{text_context}',
            'meme': f'Выдай шаблон демотиватора по шаблону:\n📊 ОЦЕНКА МЕДИА-МАТЕРИАЛА:\n• Градус кринжа: [Х]/5\n• Постироничность: [Х]/5\n🎨 ШАБЛОН ДЛЯ МЕМФИКАЦИИ:\n• ТЕКСТ СВЕРХУ (Top Text): [Текст капсом]\n• ТЕКСТ СНИЗУ (Bottom Text): [Панчлайн].\n\nЛог:\n{text_context}'
        }
        prompt = prompts.get(command, f'Анализируй: {text_context}')
        response = model.generate_content(f"{TOXIC_SYSTEM_PROMPT}\n\n{prompt}")
        return response.text if response.text else "Не удалось получить ответ от Gemini."
    except Exception as e:
        logger.error(f"Ошибка Gemini: {str(e)}")
        return "Ошибка анализа."

def generate_free_art(prompt_text):
    """Абсолютно бесплатная моментальная генерация картинок (Pollinations AI)."""
    from urllib.parse import quote
    encoded_prompt = quote(prompt_text)
    url = f"https://pollinations.ai{encoded_prompt}?width=1024&height=1024&nologo=true"
    try:
        response = requests.get(url, timeout=12)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logger.error(f"Ошибка Pollinations: {str(e)}")
    return None
    # ============= ОБРАБОТЧИКИ КОМАНД И ЛОГИРОВАНИЕ =============

def process_ai_command(message, command_name):
    """Функция обработки ИИ-команд на основе пассивно собранной истории из базы данных KV."""
    chat_id = message.chat.id
    kv_key = f"chat_history:{chat_id}"
    
    raw_text = message.text or ""
    parts = raw_text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""

    # Отправляем моментальное сообщение-заглушку, чтобы пользователь не гадал
    status_msg = bot.reply_to(message, "⏳ <i>Сканирую историю чата из базы данных, подожди...</i>")

    try:
        bot.send_chat_action(chat_id, 'typing')
        
        # ВЫТАСКИВАЕМ ПАССИВНО НАКОПЛЕННУЮ ИСТОРИЮ ЧАТА ИЗ БАЗЫ КV REDIS!
        history_array = kv.lrange(kv_key, 0, -1)
        if history_array:
            context_text = "\n".join(history_array)
        else:
            context_text = "Чат пуст. Переписки еще нет."

        answer = analyze_with_gemini(context_text, command_name)
        
        # Безопасно форматируем HTML, чтобы Telegram не падал
        clean_answer = answer.replace("<", "&lt;").replace(">", "&gt;")
        clean_answer = clean_answer.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        clean_answer = clean_answer.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
        clean_answer = clean_answer.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
        
        # Отрезаем и обрабатываем команду генерации картинок
        if command_name == 'create' and args:
            bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"{clean_answer}\n\n🚀 <i>Генерирую ИИ-шедевр по твоему запросу: '{args}'...</i>", parse_mode='HTML')
            image_bytes = generate_free_art(args)
            if image_bytes:
                bot.send_photo(chat_id, image_bytes, reply_to_message_id=message.message_id, caption="🎨 Твой шедевр готов!")
                bot.delete_message(chat_id, status_msg.message_id)
            else:
                bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"{clean_answer}\n\n❌ Нейросеть не смогла сгенерировать картинку.")
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=clean_answer, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Ошибка выполнения {command_name}: {str(e)}")
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ Ошибка генерации ИИ.")
        except Exception:
            pass

# 1. ОБРАБОТЧИК /help И /start
@bot.message_handler(commands=['help', 'start'])
def cmd_help(message):
    help_text = (
        "<b>🤖 StatBoy ИИ на связи. Автономный аналитик готов к работе!</b>\n\n"
        "Я пассивно записываю все сообщения группы в облачную базу данных. Больше никаких Reply не требуется!\n\n"
        "• <code>/help</code> — Вызов этого меню\n"
        "• <code>/dialog [текст]</code> — Свободное общение с ИИ\n"
        "• <code>/summary</code> — Показать выжимку бреда чата на основе базы\n"
        "• <code>/rating</code> — Выдать диагнозы участникам на основе базы\n"
        "• <code>/rateme</code> — Твой личный табель позора из логов\n"
        "• <code>/psycho</code> — Психопортрет участников на основе истории базы\n"
        "• <code>/psychome</code> — Твоя личная карта кукухи\n"
        "• <code>/ask [вопрос]</code> — Задать вопрос ИИ по контексту чата\n"
        "• <code>/poll</code> — Создать токсичный опрос на основе логов\n"
        "• <code>/taro</code> — Расклад карт Таро на деградацию\n"
        "• <code>/song</code> — Саундтрек твоей нищей жизни\n"
        "• <code>/edit [запрос]</code> — Концепт оскорбительной фотожабы\n"
        "• <code>/create [запрос]</code> — БЕСПЛАТНАЯ генерация картинок нейросетью\n"
        "• <code>/future</code> — Сценарное предсказание будущих сообщений чата\n"
        "• <code>/meme</code> — Создать шаблон демотиватора"
    )
    try:
        bot.reply_to(message, help_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка help: {str(e)}")

@bot.message_handler(commands=['dialog'])
def cmd_dialog(message): process_ai_command(message, 'ask')

# Регистрация ИИ-команд
@bot.message_handler(commands=['summary', 'rating', 'rateme', 'psycho', 'psychome', 'ask', 'poll', 'taro', 'song', 'edit', 'create', 'future', 'meme'])
def handle_bot_commands(message):
    # Извлекаем имя команды
    raw_text = message.text or ""
    first_word = raw_text.split()[0].lower() if raw_text.split() else ""
    command_name = first_word.replace('/', '').split('@')[0]
    process_ai_command(message, command_name)

# 2. ПАССИВНЫЙ СБОР ЛОГОВ АБСОЛЮТНО ВСЕХ СООБЩЕНИЙ ЧАТА ДЛЯ БАЗЫ ДАННЫХ
@bot.message_handler(func=lambda message: True)
def log_all_chat_messages(message):
    chat_id = message.chat.id
    kv_key = f"chat_history:{chat_id}"
    username = message.from_user.username or message.from_user.first_name or "Аноним"
    text = message.text or "[Медиа/Стикер/Файлы]"
    
    # Записываем строчку переписки в облачный Redis
    kv.rpush(kv_key, f"[{username}]: {text}")
    # Держим лимит последних 150 строк в памяти
    kv.ltrim(kv_key, -150, -1)

# ==================== FLASK РОУТЫ ДЛЯ ВЕБХУКА VERCEL ====================
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
    return jsonify({'message': 'Telegram Bot API with Vercel KV is running'}), 200

if __name__ == '__main__':
    app.run(debug=False)

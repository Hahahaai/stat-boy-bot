import re
from collections import defaultdict
import time
from urllib.parse import quote  # Перенести наверх из функции!

# --- Утилиты ---
_rate_limits = defaultdict(float)

def is_rate_limited(user_id: int, cooldown: int = 10) -> bool:
    now = time.time()
    if now - _rate_limits[user_id] < cooldown:
        return True
    _rate_limits[user_id] = now
    return False

def sanitize_html(text: str) -> str:
    allowed = {'b', 'i', 'code', 'pre'}
    def replace_tag(m):
        tag = m.group(1).lstrip('/')
        return m.group(0) if tag in allowed else m.group(0).replace('<','&lt;').replace('>','&gt;')
    return re.sub(r'</?(\w+)[^>]*>', replace_tag, text)

# --- Генерация изображений ---
def generate_free_art(prompt_text: str) -> bytes | None:
    encoded_prompt = quote(prompt_text)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
    try:
        response = requests.get(url, timeout=20)  # Увеличен таймаут!
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logger.error(f"Art Generator Error: {e}")
    return None

# --- Обработчик команд с защитой ---
@bot.message_handler(commands=['summary','rating','rateme','psycho',
                                'psychome','ask','poll','taro','song',
                                'edit','create','future','meme'])
def handle_bot_commands(message):
    try:
        if is_rate_limited(message.from_user.id):
            bot.reply_to(message, "⏱ <i>Притормози, 

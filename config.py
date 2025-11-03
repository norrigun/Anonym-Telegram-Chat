import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Настройки безопасности
MAX_MESSAGE_LENGTH = 2000
MAX_SESSIONS_PER_USER = 5
SESSION_TIMEOUT_HOURS = 24
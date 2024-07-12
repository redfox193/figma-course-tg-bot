import os

from dotenv import load_dotenv

load_dotenv()

FAQ_URL = os.environ.get("FAQ_URL", "https://google.com")
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://google.com")
CHAT_LINK = os.environ.get("CHAT_LINK", "https://google.com")
TABLE_LINK = os.environ.get("TABLE_LINK", "https://google.com")

TOCKEN = os.environ.get("TOCKEN", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "")
ADMIN = os.environ.get("ADMIN", "админ")
TASKS = int(os.environ.get("TASKS", 0))

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

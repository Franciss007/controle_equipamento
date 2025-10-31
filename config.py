import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

SECRET_KEY = os.environ.get("APP_SECRET_KEY", "supersecret-change-me")

from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    SERVER_NAME = os.environ.get("SERVER_NAME")
    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    if not DATABASE_URL:
        DATABASE_URL = "sqlite:///./quests.db"

    SECRET_KEY = os.environ.get("SECRET_KEY")
    HASH_ALGORITHM = os.environ.get("HASH_ALGORITHM")

    ADMIN_EMAILS = (os.environ.get("FROM_EMAIL"),)

    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    FROM_EMAIL = os.getenv("FROM_EMAIL")

    ADMIN_NAME = os.getenv("ADMIN_NAME")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


config = Config()

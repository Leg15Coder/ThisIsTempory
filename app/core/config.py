from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """Настройки приложения"""

    # Database
    database_url: str = "sqlite:///./quests.db"

    # Application
    app_name: str = "Quest App"
    debug: bool = False

    # Paths
    static_dir: str = "app/static"
    templates_dir: str = "app/templates"

    # Quest settings
    max_parent_quests: int = 10
    max_subtasks: int = 50
    default_quest_deadline_days: int = 1

    # Generator settings
    generator_check_interval: int = 300  # секунды

    # Assistant / Gemini
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"
    gemini_intent_model: str = "gemini-2.0-flash-lite"
    gemini_audio_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: int = 30
    gemini_max_retries: int = 3
    gemini_model_disable_404_seconds: int = 3600  # how long to mark a model disabled on 404 (default 1 hour)
    gemini_model_cooldown_429_seconds: int = 60   # cooldown on 429 (short)
    assistant_context_messages: int = 8
    assistant_memory_db_path: str = "assistant_memory.db"

    # Fallback Providers
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar"
    perplexity_base_url: str = "https://api.perplexity.ai"
    openrouter_api_key: str = ""
    openrouter_model: str = "gpt-3.5-mini"
    openrouter_base_url: str = "https://api.openrouter.ai"

    # Local fallback assistant (dev helper) — when true, GeminiService вернёт локальный ответ вместо вызова внешних LLM
    assistant_force_local_llm: bool = False
    assistant_local_llm_response: str = "(DEV) Внешние языковые сервисы недоступны — это локальный заглушечный ответ. Проверьте ключи и сеть."

    google_calendar_service_account_file: str = ""
    google_calendar_id: str = ""
    fast_assistant_system_prompt: str = (
        "Ты быстрый ассистент. Твои задачи:\n"
        "1. Отвечать на вопросы кратко\n"
        "2. Помогать пользователю выполнять действия\n"
        "3. Если не хватает данных для действия — задать уточняющий вопрос\n"
        "4. Отвечай кратко и по делу."
    )
    psych_assistant_system_prompt: str = (
        "Ты эмпатичный психологический помощник.\n"
        "Правила:\n"
        "- Слушай и поддерживай\n"
        "- Используй теплый, заботливый тон\n"
        "- Задавай открытые вопросы\n"
        "- Не ставь диагнозы и не давай медицинских советов\n"
        "- Если риск самоповреждения, мягко предложи обратиться к специалисту\n"
        "- Можешь предлагать простые техники: дыхание, рефрейминг"
    )

    model_config = ConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    def get_database_url(self) -> str:
        """Получить URL базы данных с корректировкой для PostgreSQL"""
        url = self.database_url
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def static_path(self) -> str:
        """Возвращает абсолютный путь к директории static"""
        p = Path(self.static_dir)
        if p.is_absolute():
            return str(p.resolve())
        project_root = Path(__file__).resolve().parents[2]
        return str((project_root / self.static_dir).resolve())

    @property
    def templates_path(self) -> str:
        """Возвращает абсолютный путь к директории templates"""
        p = Path(self.templates_dir)
        if p.is_absolute():
            return str(p.resolve())
        project_root = Path(__file__).resolve().parents[2]
        return str((project_root / self.templates_dir).resolve())


@lru_cache()
def get_settings() -> Settings:
    """Получить экземпляр настроек (кешируется)"""
    return Settings()

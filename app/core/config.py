from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


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


@lru_cache()
def get_settings() -> Settings:
    """Получить экземпляр настроек (кешируется)"""
    return Settings()

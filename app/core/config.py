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

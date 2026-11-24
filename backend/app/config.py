from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения (см. .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/nedro"
    jwt_secret: str = "dev-secret-change-me-dev-secret-change-me"
    jwt_hours: int = 12  # срок действия токена = длительность смены
    seed_password: str | None = None
    # стоянка самосвалов у карьеров (пос. Свень, Брянский район) — точка отсчёта расстояний
    base_lat: float = 53.105
    base_lon: float = 34.303


settings = Settings()

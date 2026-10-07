from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/certgen"
    REDIS_URL: str = "redis://redis:6379/0"
    GENERATED_DIR: str = "app/generated"
    TEMPLATES_DIR: str = "app/templates"
    CELERY_ALWAYS_EAGER: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()

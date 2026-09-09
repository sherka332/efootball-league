import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./efootball.db"
    secret_key: str = "change-this-secret"
    telegram_bot_token: str = ""
    telegram_admin_id: str = ""
    cors_origins: str = "*"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

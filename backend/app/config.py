import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Telecom AI Agent Backend"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./telecom.db")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    class Config:
        env_file = ".env"

settings = Settings()
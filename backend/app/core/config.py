import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field

class Settings(BaseSettings):
    # API Config
    API_PORT: int = Field(default=8000, validation_alias="API_PORT")
    FRONTEND_URL: str = Field(default="http://localhost:5173", validation_alias="FRONTEND_URL")
    
    # MongoDB Config
    MONGODB_HOST: str = Field(default="127.0.0.1", validation_alias="MONGODB_HOST")
    MONGODB_PORT: int = Field(default=27017, validation_alias="MONGODB_PORT")
    MONGODB_DATABASE: str = Field(default="mes_db", validation_alias="MONGODB_DATABASE")
    
    # Redis Config
    REDIS_HOST: str = Field(default="127.0.0.1", validation_alias="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, validation_alias="REDIS_PORT")
    REDIS_DB: int = Field(default=0, validation_alias="REDIS_DB")

    # AI Config
    GEMINI_API_KEY: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    GEMINI_MODEL: Optional[str] = Field(default=None, validation_alias="GEMINI_MODEL")
    OLLAMA_BASE_URL: Optional[str] = Field(default=None, validation_alias="OLLAMA_BASE_URL")
    OLLAMA_MODEL: Optional[str] = Field(default=None, validation_alias="OLLAMA_MODEL")

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @computed_field
    @property
    def mongodb_uri(self) -> str:
        return f"mongodb://{self.MONGODB_HOST}:{self.MONGODB_PORT}/"

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

# Global settings instance
settings = Settings()

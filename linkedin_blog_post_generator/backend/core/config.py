from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str    = ""
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"


# single instance — import this everywhere instead of re-creating
settings: Settings = Settings()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    redis_url: str
    log_level: str = "INFO"
    max_response_size: int = 2 * 1024 * 1024  # 2 MB

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings() # pyright: ignore[reportCallIssue]
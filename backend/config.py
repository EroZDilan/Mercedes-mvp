from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jwt_secret_key: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_hours: int = 8

    groq_api_key: str = ""

    warehouse_a_id: str = "ALM-A"
    warehouse_a_name: str = "Almacén Norte"
    warehouse_b_id: str = "ALM-B"
    warehouse_b_name: str = "Almacén Sur"

    sync_interval_minutes: int = 30
    max_login_attempts: int = 5
    allowed_origin: str = "http://localhost:3000"
    login_rate_limit: str = "10/minute"

    database_url: str = "sqlite:///./stock_chatbot.db"

    class Config:
        env_file = ".env"


settings = Settings()

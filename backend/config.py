from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret_key: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_hours: int = 8

    groq_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    openrouter_api_key: str = ""

    ollama_base_url: str = ""
    ollama_model: str = "qwen2.5:7b"

    warehouse_a_id: str = "ALM-A"
    warehouse_a_name: str = "Almacén Norte"
    warehouse_b_id: str = "ALM-B"
    warehouse_b_name: str = "Almacén Sur"

    sync_interval_minutes: int = 30
    max_login_attempts: int = 5
    # Orígenes permitidos en CORS — separados por coma para multi-PC
    # Ejemplo: "https://localhost:3000,https://192.168.1.50:3000"
    allowed_origins: str = "https://localhost:3000"
    login_rate_limit: str = "10/minute"

    action_token_ttl_seconds: int = 60

    whisper_model: str = "base"
    whisper_language: str = "es"

    database_url: str = "sqlite:///./stock_chatbot.db"

    inventree_url: str = "http://localhost:8080/api/"
    inventree_token: str = ""

    # Multi-PC: rol de este nodo y conexión al servidor central
    node_role: str = "server"          # "server" | "client"
    node_id: str = "node-1"            # identificador único de este nodo
    central_server_url: str = ""       # solo en clientes: URL del servidor central

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

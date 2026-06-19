from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://sistemaxml:devpassword@localhost:5433/sistemaxml"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 480
    jwt_algorithm: str = "HS256"

settings = Settings()

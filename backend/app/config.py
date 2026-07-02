from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    env: str = "dev"  # "production" activa el enforcement de secretos
    database_url: str = "postgresql+psycopg://sistemaxml:devpassword@localhost:5433/sistemaxml"
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_expire_minutes: int = 480  # 8 h; acortar cuando se implemente refresh tokens.
    jwt_algorithm: str = "HS256"

    @model_validator(mode="after")
    def _exigir_secreto_en_prod(self):
        if self.env == "production" and (
            self.jwt_secret == _DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "En producción (ENV=production), JWT_SECRET debe ser propio y de al menos 32 caracteres."
            )
        return self


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRACAO_MINUTOS: int = 60
    REFRESH_TOKEN_EXPIRACAO_DIAS: int = 30
    XP_BONUS_VITORIA: int = 20
    AMBIENTE: str = "desenvolvimento"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


configuracoes = Configuracoes()

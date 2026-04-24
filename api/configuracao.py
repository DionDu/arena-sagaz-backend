from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    AMBIENTE: str = "desenvolvimento"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


configuracoes = Configuracoes()

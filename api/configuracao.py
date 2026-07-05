from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    """Configurações da API, lidas de variáveis de ambiente (ou de um `.env`
    local, não versionado). Em produção, vêm das Variables do Railway.
    """

    AMBIENTE: str = "desenvolvimento"

    # URL do PostgreSQL. Em produção vem das Variables do Railway (que injeta a
    # URL interna). O placeholder local permite importar a app sem um banco
    # configurado — a conexão real só acontece quando uma rota usa o banco.
    # Aceita tanto `postgresql://` quanto `postgresql+asyncpg://` (a camada de
    # banco normaliza para o driver async).
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/arena_sagaz"

    # Firebase Admin SDK (verificação do ID token enviado pelo app) — usados a
    # partir da US2. Ficam vazios até lá.
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS: str = ""

    # Origens extras permitidas no CORS, separadas por vírgula (ex.: o domínio de
    # um eventual build web em produção). O dev (Flutter web em localhost, com
    # porta aleatória) já é liberado por regex no `main.py`. Mobile não usa CORS.
    CORS_ORIGINS: str = ""

    # Segredo que autoriza o disparo de **broadcast** de notificações
    # (`POST /v1/notificacoes/broadcast`). Quem chamar precisa enviar este valor
    # no cabeçalho `X-Admin-Token`. VAZIO = endpoint **desabilitado** (default
    # seguro: sem segredo configurado, ninguém consegue disparar para todos).
    # Em produção, definir nas Variables do Railway.
    ADMIN_BROADCAST_TOKEN: str = ""

    # ── Rate limiting (SEG-04) ───────────────────────────────────────────────
    # Limites por IP, por minuto (janela deslizante). `RATE_LIMIT_ENABLED=false`
    # desliga tudo (usado nos testes). Leituras (GET) usam o limite geral; escritas
    # (POST/PUT/PATCH/DELETE) usam o limite mais apertado. Ajuste nas Variables do
    # Railway conforme o tráfego real.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_POR_MINUTO: int = 120          # geral (leituras)
    RATE_LIMIT_ESCRITA_POR_MINUTO: int = 30   # escritas (mais sensíveis)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def eh_producao(self) -> bool:
        """`True` em produção. Aceita 'producao'/'production'/'prod' (case-insensitive)
        para o valor de `AMBIENTE` — usado, por ex., para NÃO liberar `localhost` no
        CORS em produção (SEG-02)."""
        return self.AMBIENTE.strip().lower() in {"producao", "production", "prod"}


configuracoes = Configuracoes()

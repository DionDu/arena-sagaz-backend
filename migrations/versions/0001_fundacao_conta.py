"""Fundação de conta: schema `conta` com 6 tabelas + 6 views (spec 005)

Cria o schema `conta` e as tabelas/views aprovadas em
`arena-sagaz-frontend/specs/005-fundacao-cadastro-login/data-model.md`.
Convenção: leitura via VIEW `vwNNN_*`, escrita na tabela `tbNNN_*`.

Revision ID: 0001_fundacao_conta
Revises:
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op

# Identificadores da revisão.
revision: str = "0001_fundacao_conta"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema transversal de conta (não é de um jogo específico).
    op.execute("CREATE SCHEMA IF NOT EXISTS conta")

    # ── tb001_usuario — o usuário (núcleo) ──────────────────────────────────
    # `gen_random_uuid()` é nativo do Postgres 13+ (sem extensão). Vários campos
    # de PII são anuláveis porque viram NULL na anonimização (exclusão de conta).
    op.execute(
        """
        CREATE TABLE conta.tb001_usuario (
            id_usuario             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            co_usuario             VARCHAR(8)  NOT NULL UNIQUE,
            co_identidade_externa  TEXT        UNIQUE,
            no_exibicao            VARCHAR(40),
            no_email               TEXT,
            dt_nascimento          DATE,
            co_provedor_principal  VARCHAR(20) NOT NULL,
            co_idioma_preferido    CHAR(2)     NOT NULL DEFAULT 'pt',
            ic_convidado           BOOLEAN     NOT NULL DEFAULT FALSE,
            ic_anonimizado         BOOLEAN     NOT NULL DEFAULT FALSE,
            co_anonimo             UUID,
            dh_criacao             TIMESTAMPTZ NOT NULL DEFAULT now(),
            dh_atualizacao         TIMESTAMPTZ NOT NULL DEFAULT now(),
            dh_ultimo_acesso       TIMESTAMPTZ
        )
        """
    )

    # ── tb002_provedor_login — provedores vinculados (vínculo explícito) ─────
    op.execute(
        """
        CREATE TABLE conta.tb002_provedor_login (
            id_provedor_login      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_usuario             UUID NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario) ON DELETE CASCADE,
            co_provedor            VARCHAR(20) NOT NULL,
            co_identidade_provedor TEXT        NOT NULL,
            dh_vinculo             TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_provedor_identidade
                UNIQUE (co_provedor, co_identidade_provedor)
        )
        """
    )

    # ── tb003_aceite_legal — aceites de documentos legais ───────────────────
    op.execute(
        """
        CREATE TABLE conta.tb003_aceite_legal (
            id_aceite_legal UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_usuario      UUID NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario) ON DELETE CASCADE,
            co_documento    VARCHAR(20) NOT NULL,
            co_versao       VARCHAR(20) NOT NULL,
            co_idioma       CHAR(2)     NOT NULL,
            dh_aceite       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # ── tb004_consentimento — rastreamento + opt-in de marketing ────────────
    # ("menor de idade" NÃO é coluna: é derivado de dt_nascimento em runtime.)
    op.execute(
        """
        CREATE TABLE conta.tb004_consentimento (
            id_consentimento UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_usuario       UUID NOT NULL UNIQUE
                REFERENCES conta.tb001_usuario(id_usuario) ON DELETE CASCADE,
            ic_rastreamento  BOOLEAN     NOT NULL DEFAULT FALSE,
            ic_marketing     BOOLEAN     NOT NULL DEFAULT FALSE,
            dh_atualizacao   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # ── tb005_dispositivo_notificacao — token FCM por aparelho ──────────────
    # id_usuario é ANULÁVEL (token de sessão de convidado, sem conta).
    op.execute(
        """
        CREATE TABLE conta.tb005_dispositivo_notificacao (
            id_dispositivo UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_usuario     UUID
                REFERENCES conta.tb001_usuario(id_usuario) ON DELETE CASCADE,
            co_token_fcm   TEXT        NOT NULL UNIQUE,
            sg_plataforma  VARCHAR(10) NOT NULL,
            co_idioma      CHAR(2)     NOT NULL,
            dh_criacao     TIMESTAMPTZ NOT NULL DEFAULT now(),
            dh_atualizacao TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # ── tb006_preferencia_notificacao — preferências por categoria ──────────
    op.execute(
        """
        CREATE TABLE conta.tb006_preferencia_notificacao (
            id_preferencia UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_usuario     UUID NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario) ON DELETE CASCADE,
            co_categoria   VARCHAR(20) NOT NULL,
            ic_ativo       BOOLEAN     NOT NULL DEFAULT TRUE,
            dh_atualizacao TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_usuario_categoria UNIQUE (id_usuario, co_categoria)
        )
        """
    )

    # ── VIEWs (uma por tabela — regra de acesso do projeto) ─────────────────
    # A app/serviços leem das VIEWs; escrevem nas tabelas.
    for n, nome in (
        (1, "usuario"),
        (2, "provedor_login"),
        (3, "aceite_legal"),
        (4, "consentimento"),
        (5, "dispositivo_notificacao"),
        (6, "preferencia_notificacao"),
    ):
        op.execute(
            f"CREATE VIEW conta.vw{n:03d}_{nome} AS "
            f"SELECT * FROM conta.tb{n:03d}_{nome}"
        )


def downgrade() -> None:
    # Derruba na ordem inversa (views, depois tabelas; o CASCADE no schema
    # resolveria, mas explicitamos para clareza). Por fim, o schema.
    for n, nome in (
        (6, "preferencia_notificacao"),
        (5, "dispositivo_notificacao"),
        (4, "consentimento"),
        (3, "aceite_legal"),
        (2, "provedor_login"),
        (1, "usuario"),
    ):
        op.execute(f"DROP VIEW IF EXISTS conta.vw{n:03d}_{nome}")
        op.execute(f"DROP TABLE IF EXISTS conta.tb{n:03d}_{nome} CASCADE")
    op.execute("DROP SCHEMA IF EXISTS conta CASCADE")

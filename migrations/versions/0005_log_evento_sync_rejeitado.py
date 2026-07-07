"""Log de eventos de sync não aplicados (rejeitados/falha de processamento)

Cria o schema `log` e a tabela `log.tb001_evento_sync_rejeitado`, onde o
`POST /v1/sincronizacao/eventos` ARQUIVA o payload de todo evento que NÃO pôde
ser aplicado, em vez de descartá-lo. Dois motivos (`co_motivo`):

- `rejeitado_contrato`  — reprovado na validação (payload malformado / fora dos
  tetos anti-fraude). O servidor já tinha o payload em mãos ao rejeitar.
- `falha_processamento` — passou na validação mas EXPLODIU ao gravar (um erro
  inesperado no SQL que, sem blindagem, viraria 500 e derrubaria o lote). A rota
  agora envolve cada evento num SAVEPOINT e, ao capturar a exceção, arquiva aqui
  o payload cru para diagnóstico — sem re-rodar a lógica que falhou.

Motivação: em campo, uma partida cujo XP batia no teto diário era rejeitada e o
app a marcava `abandonado` — o log detalhado sumia sem deixar rastro no servidor.
Com esta tabela, toda falha fica VISÍVEL no backend (dá para detectar um bug de
contrato acontecendo em N dispositivos) e o app pode EXPURGAR o evento local com
segurança (o servidor guarda a evidência).

O `js_payload` é TEXT (não JSONB) de propósito: é um dump de dado NÃO-CONFIÁVEL
(pode estar malformado); guardá-lo como texto cru evita qualquer erro de parse na
própria gravação do log. O app trunca antes de enviar; ainda assim não há FK para
`conta.tb001_usuario` (o log deve sobreviver mesmo a um id inesperado).

Revision ID: 0005_log_evento_sync_rejeitado
Revises: 0004_aceite_legal_idempotente
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_log_evento_sync_rejeitado"
down_revision: Union[str, None] = "0004_aceite_legal_idempotente"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS log")

    # tb001_evento_sync_rejeitado — arquivo de eventos de sync não aplicados.
    # SEM FK e SEM UNIQUE em co_evento: é um LOG append-only de diagnóstico; o
    # mesmo co_evento pode reincidir (o app reenvia até receber o veredicto), e
    # cada ocorrência é um registro válido de que a falha aconteceu de novo.
    op.execute(
        """
        CREATE TABLE log.tb001_evento_sync_rejeitado (
            id_log       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_usuario   UUID,
            co_anonimo   UUID,
            co_evento    VARCHAR(64),
            co_tipo      VARCHAR(30),
            co_motivo    VARCHAR(30)  NOT NULL,
            de_codigo    VARCHAR(200),
            js_payload   TEXT,
            dh_registro  TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
        """
    )
    # Índices para as consultas de diagnóstico mais prováveis: "quais motivos
    # estão bombando agora?" (motivo + data) e "as falhas deste usuário".
    op.execute(
        "CREATE INDEX ix_log_evt_rejeitado_motivo_data "
        "ON log.tb001_evento_sync_rejeitado (co_motivo, dh_registro)"
    )
    op.execute(
        "CREATE INDEX ix_log_evt_rejeitado_usuario "
        "ON log.tb001_evento_sync_rejeitado (id_usuario)"
    )

    # Convenção do projeto: serviços LEEM pela VIEW e ESCREVEM na tabela.
    op.execute(
        "CREATE VIEW log.vw001_evento_sync_rejeitado AS "
        "SELECT * FROM log.tb001_evento_sync_rejeitado"
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS log.vw001_evento_sync_rejeitado")
    op.execute("DROP TABLE IF EXISTS log.tb001_evento_sync_rejeitado CASCADE")
    op.execute("DROP SCHEMA IF EXISTS log CASCADE")

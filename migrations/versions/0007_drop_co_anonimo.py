"""Remove a coluna morta `co_anonimo` das tabelas-filhas (mantém em conta.tb001)

CONTEXTO — descoberto no teste de exclusão de conta (13/07/2026): depois de excluir
a conta, `co_anonimo` continuava **NULL** em `partida.tb001_partida`,
`partida.tb003_xp_partida` e `progressao.tb001_progressao_usuario`.

Não é bug de exclusão: a coluna é **impossível de preencher** e **ninguém a lê**.

TRÊS FATOS QUE CONDENAM A COLUNA
────────────────────────────────
1. **Dois `co_anonimo` homônimos e DIFERENTES.** No app, `ProvedorIdentidade.coAnonimo`
   é um UUID **do APARELHO** (nasce no `shared_preferences`, na 1ª abertura). No banco,
   `conta.tb001_usuario.co_anonimo` é o rótulo **da CONTA EXTINTA** (nasce no UPDATE da
   anonimização). O sync misturava os dois.

2. **É logicamente IMPOSSÍVEL preencher a coluna nas filhas.** O sync grava
   `co_anonimo = payload.co_anonimo or usuario.co_anonimo`. Mas `usuario.co_anonimo` só
   existe DEPOIS da anonimização — e a anonimização **zera o `co_identidade_externa`**,
   que é justamente por onde `usuario_autenticado` acha a conta a partir do token.
   ⇒ conta anonimizada **nunca mais autentica ⇒ nunca mais sincroniza ⇒ a coluna jamais
   é preenchida**. (O `payload.co_anonimo` também chegava `null`: o app chamava
   `registrarPartidaConcluida()` sem passar o parâmetro, que é opcional.)

3. **Zero consumidores.** Nenhum `SELECT`, `WHERE`, `JOIN`, `GROUP BY` ou `ORDER BY` toca
   `co_anonimo` — em toda a API, nos notebooks e no gerador de dataset. Era write-only.

POR QUE NÃO "CONSERTAR" EM VEZ DE REMOVER
─────────────────────────────────────────
O propósito (FR-024) era "uma âncora que sobrevive à exclusão". Mas **`id_usuario` já faz
isso**: a conta é **anonimizada, não deletada** — as FKs continuam válidas e a
`tb001_usuario` já não tem nome, e-mail, nascimento nem uid. **O `id_usuario` já É o
pseudônimo.**

⚠️ E preenchê-la seria PIOR: o `coAnonimo` do app é **por APARELHO**, não por conta.
Ele ligaria a **conta excluída** à **conta nova criada depois no mesmo celular** — um
identificador que atravessa a exclusão e permite **re-identificação por vínculo**. É o
oposto do que a LGPD quer. Removê-la não enfraquece a anonimização: **fortalece**.

Precedente no próprio schema: `progressao.tb002_conquista_usuario` sempre viveu só com
`id_usuario`, e nunca fez falta.

O QUE MUDA
──────────
DROP da coluna em 4 tabelas:
  • partida.tb001_partida
  • partida.tb003_xp_partida
  • progressao.tb001_progressao_usuario
  • log.tb001_evento_sync_rejeitado

**MANTIDA** em `conta.tb001_usuario` — ali ela tem uso real: é o carimbo do ato de
anonimização (rótulo opaco divulgável em suporte/auditoria sem expor a PK).

⚠️ Pegadinha do Postgres (a mesma da 0006): uma VIEW criada com `SELECT *` **congela** a
lista de colunas. Toda view que projeta a coluna (via `*`) impede o DROP e precisa ser
derrubada e recriada. As 4 afetadas estão tratadas abaixo.
NÃO precisam ser tocadas: `partida.vw002_jogada` (só usa `p.co_modo`) e
`progressao.vw101_ranking_global_geral` (colunas explícitas) — não referenciam a coluna.

NÃO destrutiva para os dados: só some uma coluna que era 100% NULL.

Revision ID: 0007_drop_co_anonimo
Revises: 0006_redesenho_log_treino
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op

# ⚠️ Máximo 32 caracteres: `alembic_version.version_num` é VARCHAR(32).
revision: str = "0007_drop_co_anonimo"
down_revision: Union[str, None] = "0006_redesenho_log_treino"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# As 4 views que projetam `co_anonimo` (via `*`) e por isso travam o DROP COLUMN.
VIEWS_AFETADAS = (
    "partida.vw001_partida",
    "partida.vw003_xp_partida",
    "progressao.vw001_progressao_usuario",
    "log.vw001_evento_sync_rejeitado",
)

# (schema.tabela) de onde a coluna sai. `conta.tb001_usuario` NÃO está aqui — de propósito.
TABELAS_AFETADAS = (
    "partida.tb001_partida",
    "partida.tb003_xp_partida",
    "progressao.tb001_progressao_usuario",
    "log.tb001_evento_sync_rejeitado",
)


def _recriar_views() -> None:
    """Recria as 4 views com a MESMA semântica de antes — sem a coluna morta.

    Definições copiadas das migrações que as criaram (0003, 0005 e 0006), para que a
    única diferença seja a ausência de `co_anonimo`.
    """
    # partida.vw001_partida (0006) — `p.*` + o resultado derivado do placar.
    op.execute(
        """
        CREATE VIEW partida.vw001_partida AS
        SELECT p.*,
               CASE
                 WHEN p.nu_placar_j1 > p.nu_placar_j2 THEN 'venceu_j1'
                 WHEN p.nu_placar_j2 > p.nu_placar_j1 THEN 'venceu_j2'
                 ELSE 'empate'
               END AS co_resultado
        FROM partida.tb001_partida p
        """
    )
    # partida.vw003_xp_partida (0006) — pass-through.
    op.execute(
        "CREATE VIEW partida.vw003_xp_partida AS "
        "SELECT * FROM partida.tb003_xp_partida"
    )
    # progressao.vw001_progressao_usuario (0003) — nível derivado do XP + patente.
    op.execute(
        """
        CREATE VIEW progressao.vw001_progressao_usuario AS
        SELECT sub.*,
               CASE
                 WHEN sub.nu_nivel >= 80 THEN 'lendario'
                 WHEN sub.nu_nivel >= 55 THEN 'sagaz'
                 WHEN sub.nu_nivel >= 35 THEN 'sabio'
                 WHEN sub.nu_nivel >= 20 THEN 'mestre'
                 WHEN sub.nu_nivel >= 10 THEN 'tatico'
                 WHEN sub.nu_nivel >= 5  THEN 'estrategista'
                 ELSE 'aprendiz'
               END AS co_patente
        FROM (
            SELECT g.*,
                   GREATEST(1, FLOOR(
                       (-5 + sqrt(49 + (4.0 * g.nu_xp_total / 15.0))) / 2.0
                   ))::int AS nu_nivel
            FROM progressao.tb001_progressao_usuario g
        ) sub
        """
    )
    # log.vw001_evento_sync_rejeitado (0005) — pass-through.
    op.execute(
        "CREATE VIEW log.vw001_evento_sync_rejeitado AS "
        "SELECT * FROM log.tb001_evento_sync_rejeitado"
    )


def upgrade() -> None:
    # 1) Derruba as views que CONGELARAM a coluna (senão o DROP COLUMN falha).
    for view in VIEWS_AFETADAS:
        op.execute(f"DROP VIEW IF EXISTS {view}")

    # 2) Some com a coluna morta. IF EXISTS: torna a migração re-executável sem susto.
    for tabela in TABELAS_AFETADAS:
        op.execute(f"ALTER TABLE {tabela} DROP COLUMN IF EXISTS co_anonimo")

    # 3) Recria as views (agora sem a coluna).
    _recriar_views()


def downgrade() -> None:
    # Devolve a coluna (sempre NULL — nunca houve dado nela) e recria as views.
    for view in VIEWS_AFETADAS:
        op.execute(f"DROP VIEW IF EXISTS {view}")

    for tabela in TABELAS_AFETADAS:
        op.execute(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS co_anonimo UUID")

    _recriar_views()

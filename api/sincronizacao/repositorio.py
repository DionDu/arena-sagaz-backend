"""Repositório de sincronização (spec 006 / US1 — T032/T033).

Escrita nas tabelas ``partida.*``/``jogo_pontinhos.*``/``progressao.*`` e leitura
pelas VIEWs, com ``sqlalchemy.text(...)`` e parâmetros nomeados (nunca
interpolação — anti-SQL-injection). Segue o mesmo estilo de ``api/conta/repositorio.py``.

⚠️ TESTES DE INTEGRAÇÃO PENDENTES: este SQL só roda contra o Postgres com a
migração ``0003_conta_nuvem`` aplicada. Os testes de CONTRATO (T023/T024) usam um
repositório FALSO e validam o serviço/rotas sem banco. A validação do SQL real
depende de aplicar a migração (Railway des) e rodar os testes de integração.

Idempotência:
 • ingestão de partida → ``INSERT ... ON CONFLICT (co_evento) DO NOTHING RETURNING``;
 • merge convidado → ``INSERT ... ON CONFLICT (co_lote_migracao) DO NOTHING RETURNING``.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _data(valor: Any) -> date | None:
    """Converte para ``date`` (coluna ``dt_ultimo_dia_jogado`` é DATE, e o
    asyncpg é estrito: DATE quer ``date``, não ``datetime`` nem ``str``). Aceita
    ``date``/``datetime``/ISO-string; qualquer coisa inválida vira ``None``."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    dt = _dt(valor)
    return dt.date() if dt else None


def _dt(valor: Any) -> datetime | None:
    """Converte uma string ISO-8601 (como o app envia, ex.:
    ``2026-07-04T11:38:00.000``) em ``datetime``.

    ⚠️ CRÍTICO: o ``asyncpg`` é ESTRITO com tipos — ele NÃO aceita ``str`` para
    colunas ``TIMESTAMPTZ`` (espera um ``datetime``), e lança ``DataError`` se
    receber uma string. Sem esta conversão, gravar uma partida estoura com 500 e
    o evento fica "pendente" para sempre no app. ``None`` e ``datetime`` passam
    direto; string inválida vira ``None`` (a coluna NOT NULL então acusa o
    problema de forma clara)."""
    if valor is None or isinstance(valor, datetime):
        return valor
    try:
        # `Z` (UTC) → offset explícito, que o fromisoformat entende.
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


class RepositorioSincronizacao:
    """Acesso a partidas/jogadas/XP/progressão para a sincronização.

    Recebe a [AsyncSession] da requisição. Faz `flush` (para o RETURNING) mas
    NÃO faz `commit` — quem orquestra a transação é a rota (tudo atômico).
    """

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    # ── Ingestão de um evento de partida (idempotente por co_evento) ──────────

    async def gravar_evento(
        self,
        *,
        id_usuario: str,
        co_anonimo: str | None,
        co_evento: str,
        payload: dict[str, Any],
    ) -> bool:
        """Grava a partida + jogadas + extensão Pontinhos + XP e incrementa a
        progressão, tudo na transação da requisição. Idempotente: se o
        ``co_evento`` já existe, não faz nada e devolve ``False``."""
        partida = payload.get("partida") or {}

        # 1) Partida (raiz do evento). ON CONFLICT no co_evento garante o dedupe.
        #    O id_usuario é SEMPRE o do token (ignora qualquer valor do cliente).
        sql_partida = text(
            """
            INSERT INTO partida.tb001_partida
              (id_partida, co_evento, co_jogo, co_variante, co_modo, id_usuario,
               co_anonimo, id_usuario_j2, co_dificuldade, nu_placar_j1,
               nu_placar_j2, ic_pontua, co_status, co_lote_migracao,
               dh_inicio, dh_fim)
            VALUES
              (:id_partida, :co_evento, :co_jogo, :co_variante, :co_modo,
               :id_usuario, :co_anonimo, :id_usuario_j2, :co_dificuldade,
               :nu_placar_j1, :nu_placar_j2, :ic_pontua, :co_status,
               :co_lote_migracao, :dh_inicio, :dh_fim)
            ON CONFLICT (co_evento) DO NOTHING
            RETURNING id_partida
            """
        )
        resultado = await self.sessao.execute(
            sql_partida,
            {
                "id_partida": partida.get("id_partida"),
                "co_evento": co_evento,
                "co_jogo": partida.get("co_jogo"),
                "co_variante": partida.get("co_variante"),
                "co_modo": partida.get("co_modo"),
                "id_usuario": id_usuario,
                # co_anonimo do J1 sobrevive à anonimização (LGPD, FR-024).
                "co_anonimo": partida.get("co_anonimo") or co_anonimo,
                "id_usuario_j2": partida.get("id_usuario_j2"),
                "co_dificuldade": partida.get("co_dificuldade"),
                "nu_placar_j1": partida.get("nu_placar_j1", 0),
                "nu_placar_j2": partida.get("nu_placar_j2", 0),
                "ic_pontua": partida.get("ic_pontua", False),
                "co_status": partida.get("co_status", "concluida"),
                "co_lote_migracao": partida.get("co_lote_migracao"),
                # asyncpg exige datetime (não string ISO) para timestamptz.
                "dh_inicio": _dt(partida.get("dh_inicio")),
                "dh_fim": _dt(partida.get("dh_fim")),
            },
        )
        if resultado.first() is None:
            return False  # co_evento já existia → retry no-op

        id_partida = partida.get("id_partida")

        # 2) Jogadas (genéricas) + extensão do Pontinhos, na ordem recebida.
        for jogada in payload.get("jogadas", []):
            await self._gravar_jogada(id_partida, jogada)

        # 3) Parcelas de XP da partida.
        for parcela in payload.get("xp", []):
            await self._gravar_xp(id_partida, id_usuario, co_anonimo, parcela)

        # 4) Incrementa a progressão (só se a partida pontua).
        await self._incrementar_progressao(
            id_usuario, co_anonimo, partida, payload.get("xp", [])
        )
        return True

    async def _gravar_jogada(self, id_partida: str, jogada: dict[str, Any]) -> None:
        await self.sessao.execute(
            text(
                """
                INSERT INTO partida.tb002_jogada
                  (id_jogada, id_partida, nu_ordem, nu_jogador, dh_jogada,
                   nu_timer_ms, nu_tempo_decisao_ms, co_origem_decisao)
                VALUES
                  (:id_jogada, :id_partida, :nu_ordem, :nu_jogador, :dh_jogada,
                   :nu_timer_ms, :nu_tempo_decisao_ms, :co_origem_decisao)
                """
            ),
            {
                "id_jogada": jogada.get("id_jogada"),
                "id_partida": id_partida,
                "nu_ordem": jogada.get("nu_ordem"),
                "nu_jogador": jogada.get("nu_jogador"),
                "dh_jogada": _dt(jogada.get("dh_jogada")),
                "nu_timer_ms": jogada.get("nu_timer_ms"),
                "nu_tempo_decisao_ms": jogada.get("nu_tempo_decisao_ms", 0),
                "co_origem_decisao": jogada.get("co_origem_decisao", "humano"),
            },
        )
        # Extensão específica do Pontinhos (1:1), quando presente no payload.
        pontinhos = jogada.get("pontinhos")
        if pontinhos:
            await self.sessao.execute(
                text(
                    """
                    INSERT INTO jogo_pontinhos.tb002_jogada
                      (id_jogada, co_jogador, co_aresta, ar_tabuleiro_antes,
                       ar_tabuleiro_apos, nu_caixas_fechadas, co_acao,
                       co_situacao, ar_probabilidade_cnn, ar_score_busca,
                       nu_profundidade, js_extra)
                    VALUES
                      (:id_jogada, :co_jogador, :co_aresta, :ar_antes, :ar_apos,
                       :nu_caixas, :co_acao, :co_situacao, :ar_prob, :ar_score,
                       :nu_prof, :js_extra)
                    """
                ),
                {
                    "id_jogada": jogada.get("id_jogada"),
                    "co_jogador": pontinhos.get("co_jogador"),
                    "co_aresta": pontinhos.get("co_aresta"),
                    "ar_antes": pontinhos.get("ar_tabuleiro_antes"),
                    "ar_apos": pontinhos.get("ar_tabuleiro_apos"),
                    "nu_caixas": pontinhos.get("nu_caixas_fechadas", 0),
                    "co_acao": pontinhos.get("co_acao"),
                    "co_situacao": pontinhos.get("co_situacao"),
                    "ar_prob": pontinhos.get("ar_probabilidade_cnn"),
                    "ar_score": pontinhos.get("ar_score_busca"),
                    "nu_prof": pontinhos.get("nu_profundidade"),
                    "js_extra": pontinhos.get("js_extra"),
                },
            )

    async def _gravar_xp(
        self,
        id_partida: str,
        id_usuario: str,
        co_anonimo: str | None,
        parcela: dict[str, Any],
    ) -> None:
        await self.sessao.execute(
            text(
                """
                INSERT INTO partida.tb003_xp_partida
                  (id_xp_partida, id_partida, id_usuario, co_anonimo, co_tipo_xp,
                   nu_xp, co_referencia, dh_registro)
                VALUES
                  (gen_random_uuid(), :id_partida, :id_usuario, :co_anonimo,
                   :co_tipo_xp, :nu_xp, :co_referencia, now())
                """
            ),
            {
                "id_partida": id_partida,
                "id_usuario": id_usuario,
                "co_anonimo": co_anonimo,
                "co_tipo_xp": parcela.get("co_tipo_xp"),
                "nu_xp": parcela.get("nu_xp", 0),
                "co_referencia": parcela.get("co_referencia"),
            },
        )

    async def _incrementar_progressao(
        self,
        id_usuario: str,
        co_anonimo: str | None,
        partida: dict[str, Any],
        xp: list[dict[str, Any]],
    ) -> None:
        # Partidas que NÃO pontuam (pvp_local) não mexem em XP/contadores.
        if not partida.get("ic_pontua"):
            return
        xp_ganho = sum(int(p.get("nu_xp", 0)) for p in xp)
        j1 = int(partida.get("nu_placar_j1", 0))
        j2 = int(partida.get("nu_placar_j2", 0))
        vit = 1 if j1 > j2 else 0
        der = 1 if j1 < j2 else 0
        emp = 1 if j1 == j2 else 0
        # Dia da partida (da data de fim, ou início): avança dt_ultimo_dia_jogado
        # sem nunca retroceder (GREATEST). Mantém a coluna "fresca" a cada partida
        # sincronizada, mesmo sem a reconciliação rodar.
        dia = _data(partida.get("dh_fim") or partida.get("dh_inicio"))
        # Upsert por id_usuario (única). NOTA: a "chama" (nu_sequencia_atual) NÃO
        # é recomputada aqui (depende de datas) — fica para o merge/reconciliação;
        # o app é a fonte da sequência até lá.
        # `AS prog`: alias do alvo para referenciar o valor ANTIGO no DO UPDATE
        # (o Postgres não aceita schema.tabela.coluna nesse contexto — precisa do
        # nome/alias da tabela).
        await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb001_progressao_usuario AS prog
                  (id_progressao, id_usuario, co_anonimo, nu_xp_total,
                   nu_partidas, nu_vitorias, nu_derrotas, nu_empates,
                   dt_ultimo_dia_jogado, dh_atualizacao)
                VALUES
                  (gen_random_uuid(), :id_usuario, :co_anonimo, :xp, 1, :vit,
                   :der, :emp, :dia, now())
                ON CONFLICT (id_usuario) DO UPDATE SET
                  nu_xp_total = prog.nu_xp_total + EXCLUDED.nu_xp_total,
                  nu_partidas = prog.nu_partidas + 1,
                  nu_vitorias = prog.nu_vitorias + EXCLUDED.nu_vitorias,
                  nu_derrotas = prog.nu_derrotas + EXCLUDED.nu_derrotas,
                  nu_empates = prog.nu_empates + EXCLUDED.nu_empates,
                  -- GREATEST ignora NULL: nunca regride a última data jogada.
                  dt_ultimo_dia_jogado = GREATEST(
                      prog.dt_ultimo_dia_jogado, EXCLUDED.dt_ultimo_dia_jogado),
                  dh_atualizacao = now()
                """
            ),
            {
                "id_usuario": id_usuario,
                "co_anonimo": co_anonimo,
                "xp": xp_ganho,
                "vit": vit,
                "der": der,
                "emp": emp,
                "dia": dia,
            },
        )

    # ── Merge convidado→conta (idempotente por co_lote_migracao) ──────────────

    async def aplicar_merge_se_novo(
        self,
        *,
        id_usuario: str,
        co_anonimo: str | None,
        co_lote_migracao: str,
        progressao_convidado: dict[str, Any],
    ) -> bool:
        """Carimba o lote e, se for novo, soma a progressão do convidado à conta
        (XP/contadores somam; sequência fica a MAIOR; conquistas união)."""
        # 1) Registra o lote (idempotência). Se já existia, não aplica de novo.
        lote = await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb003_lote_migracao
                  (co_lote_migracao, id_usuario, dh_aplicado)
                VALUES (:lote, :id_usuario, now())
                ON CONFLICT (co_lote_migracao) DO NOTHING
                RETURNING co_lote_migracao
                """
            ),
            {"lote": co_lote_migracao, "id_usuario": id_usuario},
        )
        if lote.first() is None:
            return False  # lote já aplicado → no-op

        r = progressao_convidado
        await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb001_progressao_usuario AS prog
                  (id_progressao, id_usuario, co_anonimo, nu_xp_total,
                   nu_partidas, nu_vitorias, nu_derrotas, nu_empates,
                   nu_sequencia_atual, dh_atualizacao)
                VALUES
                  (gen_random_uuid(), :id_usuario, :co_anonimo, :xp, :part, :vit,
                   :der, :emp, :seq, now())
                ON CONFLICT (id_usuario) DO UPDATE SET
                  nu_xp_total = prog.nu_xp_total + EXCLUDED.nu_xp_total,
                  nu_partidas = prog.nu_partidas + EXCLUDED.nu_partidas,
                  nu_vitorias = prog.nu_vitorias + EXCLUDED.nu_vitorias,
                  nu_derrotas = prog.nu_derrotas + EXCLUDED.nu_derrotas,
                  nu_empates = prog.nu_empates + EXCLUDED.nu_empates,
                  -- a "chama" não soma: fica a MAIOR das duas.
                  nu_sequencia_atual = GREATEST(
                      prog.nu_sequencia_atual, EXCLUDED.nu_sequencia_atual),
                  dh_atualizacao = now()
                """
            ),
            {
                "id_usuario": id_usuario,
                "co_anonimo": co_anonimo,
                "xp": int(r.get("nu_xp_total", 0)),
                "part": int(r.get("nu_partidas", 0)),
                "vit": int(r.get("nu_vitorias", 0)),
                "der": int(r.get("nu_derrotas", 0)),
                "emp": int(r.get("nu_empates", 0)),
                "seq": int(r.get("nu_sequencia_atual", 0)),
            },
        )

        # Conquistas: união (a chave única id_usuario+co_conquista evita duplicar).
        for co_conquista in r.get("conquistas", []) or []:
            await self.sessao.execute(
                text(
                    """
                    INSERT INTO progressao.tb002_conquista_usuario
                      (id_conquista_usuario, id_usuario, co_conquista,
                       dh_desbloqueio)
                    VALUES (gen_random_uuid(), :id_usuario, :co_conquista, now())
                    ON CONFLICT (id_usuario, co_conquista) DO NOTHING
                    """
                ),
                {"id_usuario": id_usuario, "co_conquista": co_conquista},
            )
        return True

    # ── Evento de CONQUISTA (idempotente por id_usuario + co_conquista) ───────

    async def gravar_conquista(
        self,
        *,
        id_usuario: str,
        co_anonimo: str | None,
        co_evento: str,
        payload: dict[str, Any],
    ) -> bool:
        """Grava UMA conquista desbloqueada. Idempotente pela chave natural
        ``(id_usuario, co_conquista)`` — reenviar o mesmo desbloqueio não duplica.
        O XP da conquista NÃO entra aqui (já sobe nas parcelas de XP da partida);
        esta linha é só o REGISTRO do desbloqueio. Devolve ``True`` se inseriu."""
        conquista = payload.get("conquista") or {}
        # Conflito: mantém a MENOR data de desbloqueio (a PRIMEIRA vez que o humano
        # a atingiu, em qualquer aparelho) — não a primeira a CHEGAR ao servidor.
        # `RETURNING (xmax = 0)`: xmax=0 só numa INSERÇÃO nova → distingue
        # "inseriu agora" (aceito) de "já existia/atualizou a data" (ignorado).
        resultado = await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb002_conquista_usuario AS tb
                  (id_conquista_usuario, id_usuario, co_conquista, dh_desbloqueio)
                VALUES
                  (gen_random_uuid(), :id_usuario, :co_conquista,
                   COALESCE(:dh, now()))
                ON CONFLICT (id_usuario, co_conquista) DO UPDATE SET
                  dh_desbloqueio = LEAST(tb.dh_desbloqueio, EXCLUDED.dh_desbloqueio)
                RETURNING (xmax = 0) AS inserido
                """
            ),
            {
                "id_usuario": id_usuario,
                "co_conquista": conquista.get("co_conquista"),
                "dh": _dt(conquista.get("dh_desbloqueio")),
            },
        )
        return bool(resultado.scalar())

    # ── Reconciliação de progressão (fallback autoritativo — app é a verdade) ──

    async def reconciliar_progressao(
        self,
        *,
        id_usuario: str,
        co_anonimo: str | None,
        snapshot: dict[str, Any],
    ) -> None:
        """Aplica o snapshot AUTORITATIVO do app como REPARO: contadores sobem por
        ``GREATEST`` (nunca regridem — fecham o buraco de eventos perdidos sem
        duplicar), a "chama"/última data idem, e as conquistas entram por união.
        Roda quando a outbox está sem pendências, então o servidor já tem os
        eventos confirmados e o ``GREATEST`` é no-op quando nada se perdeu."""
        r = snapshot
        await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb001_progressao_usuario AS prog
                  (id_progressao, id_usuario, co_anonimo, nu_xp_total,
                   nu_partidas, nu_vitorias, nu_derrotas, nu_empates,
                   nu_sequencia_atual, dt_ultimo_dia_jogado, dh_atualizacao)
                VALUES
                  (gen_random_uuid(), :id_usuario, :co_anonimo, :xp, :part, :vit,
                   :der, :emp, :seq, :dia, now())
                ON CONFLICT (id_usuario) DO UPDATE SET
                  nu_xp_total = GREATEST(prog.nu_xp_total, EXCLUDED.nu_xp_total),
                  nu_partidas = GREATEST(prog.nu_partidas, EXCLUDED.nu_partidas),
                  nu_vitorias = GREATEST(prog.nu_vitorias, EXCLUDED.nu_vitorias),
                  nu_derrotas = GREATEST(prog.nu_derrotas, EXCLUDED.nu_derrotas),
                  nu_empates = GREATEST(prog.nu_empates, EXCLUDED.nu_empates),
                  nu_sequencia_atual = GREATEST(
                      prog.nu_sequencia_atual, EXCLUDED.nu_sequencia_atual),
                  dt_ultimo_dia_jogado = GREATEST(
                      prog.dt_ultimo_dia_jogado, EXCLUDED.dt_ultimo_dia_jogado),
                  dh_atualizacao = now()
                """
            ),
            {
                "id_usuario": id_usuario,
                "co_anonimo": co_anonimo,
                "xp": int(r.get("nu_xp_total", 0)),
                "part": int(r.get("nu_partidas", 0)),
                "vit": int(r.get("nu_vitorias", 0)),
                "der": int(r.get("nu_derrotas", 0)),
                "emp": int(r.get("nu_empates", 0)),
                "seq": int(r.get("nu_sequencia_atual", 0)),
                "dia": _data(r.get("dt_ultimo_dia_jogado")),
            },
        )
        # Conquistas: união idempotente (mesma chave do merge).
        for co_conquista in r.get("conquistas", []) or []:
            await self.sessao.execute(
                text(
                    """
                    INSERT INTO progressao.tb002_conquista_usuario
                      (id_conquista_usuario, id_usuario, co_conquista,
                       dh_desbloqueio)
                    VALUES (gen_random_uuid(), :id_usuario, :co_conquista, now())
                    ON CONFLICT (id_usuario, co_conquista) DO NOTHING
                    """
                ),
                {"id_usuario": id_usuario, "co_conquista": co_conquista},
            )

    # ── Leitura (pela VIEW) ───────────────────────────────────────────────────

    async def obter_progressao(self, id_usuario: str) -> dict[str, Any]:
        """Progressão atual (com nu_nivel/co_patente calculados pela VIEW) +
        a lista de conquistas. É o que o app PUXA para reconciliar o banco local
        (convergência multi-dispositivo). Se o usuário ainda não tem linha,
        devolve zeros (mas ainda lê as conquistas, que podem existir sem linha)."""
        conquistas = await self._conquistas_de(id_usuario)
        resultado = await self.sessao.execute(
            text(
                "SELECT * FROM progressao.vw001_progressao_usuario "
                "WHERE id_usuario = :id"
            ),
            {"id": id_usuario},
        )
        linha = resultado.mappings().first()
        if linha is None:
            return {
                "nu_xp_total": 0,
                "nu_partidas": 0,
                "nu_vitorias": 0,
                "nu_derrotas": 0,
                "nu_empates": 0,
                "nu_sequencia_atual": 0,
                "dt_ultimo_dia_jogado": None,
                "nu_nivel": 1,
                "co_patente": "aprendiz",
                "conquistas": conquistas,
            }
        saida = dict(linha)
        saida["conquistas"] = conquistas
        return saida

    async def _conquistas_de(self, id_usuario: str) -> list[str]:
        """Ids das conquistas do usuário (ordenados, para resposta estável)."""
        resultado = await self.sessao.execute(
            text(
                "SELECT co_conquista FROM progressao.tb002_conquista_usuario "
                "WHERE id_usuario = :id ORDER BY co_conquista"
            ),
            {"id": id_usuario},
        )
        return [r[0] for r in resultado]

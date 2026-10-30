"""Testes da junção em BLOCO dos contadores na reconciliação do servidor (T170).

O defeito que esta suíte trava (descoberto em 30/10/2026 no banco de produção):
duas contas (``c1d497ac``: 56 + 90 + 8 = 154 em 152 partidas; ``1ca98aad``:
16 + 14 + 10 = 40 em 39 partidas) estavam com ``V + D + E > partidas`` na
própria linha de ``progressao.tb001_progressao_usuario`` no servidor. Quem as
fabricou foi ``RepositorioSincronizacao.reconciliar_progressao``, que aplicava
``GREATEST`` campo a campo sobre dois retratos que fechavam a soma sozinhos:

  * servidor (deduzido do placar de damas): ``152 / 56 / 90 / 6`` (soma 152);
  * aparelho 1.3.1 (empates reais de damas): ``152 / 54 / 90 / 8`` (soma 152);
  * ``GREATEST`` campo a campo: ``152 / 56 / 90 / 8`` (soma **154 > 152**).

E ao devolver esse ``152 / 56 / 90 / 8`` para o app, o servidor contaminava o
aparelho também, trancando as reconciliações futuras em 422 para sempre.

Cobertura desta suíte:
  1. Cadeado sobre ``validacao.py``: continua intacta (422 ``progressao_inconsistente``
     na linha local antiga da Conta A ``157 / 47 / 97 / 19`` e na Conta B
     contaminada ``157 / 47 / 97 / 17``), com controle consistente aceito;
  2. Funções puras ``bloco_contadores_consistente`` e
     ``escolher_bloco_contadores_reconciliacao``;
  3. SQL real de ``RepositorioSincronizacao.reconciliar_progressao`` executado
     num SQLite em memória (com ``ATTACH DATABASE ':memory:' AS progressao`` e
     funções compatíveis com o Postgres):
       - corpo exato da **1.3.1 das lojas** com distribuições V/D/E diferentes e
         mesmo nº de partidas (zero nova inconsistência, XP/chama/data/conquistas
         seguem subindo por GREATEST/união);
       - segundo aparelho atrasado em partidas, mas com um contador individual
         maior (ex.: mais empates): mantém o bloco do servidor inteiro;
       - aparelho à frente em partidas (evento perdido): adota o bloco inteiro
         do aparelho;
       - auto-reparo das 2 linhas já inconsistentes no servidor (``c1d497ac`` e
         ``1ca98aad``) quando chega um snapshot válido com igual ou menor nº de
         partidas;
       - Conta A depois de o app ``1.4.0+18`` consertar a linha local
         (``5.960 / 157 / 47 / 97 / 13`` + 30 conquistas): reconcilia com 200,
         sobe o XP de 5.660 para 5.960 sem pagar bônus duplicado e fecha a soma;
  4. Paridade entre ``FakeRepoSincronizacao`` e o SQL real na rota HTTP
     ``POST /v1/sincronizacao/reconciliar``.
"""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.main import app
from api.nucleo.dependencias import ContextoRequisicao
from api.nucleo.dependencias_conta_nuvem import (
    UsuarioAutenticado,
    usuario_autenticado,
)
from api.sincronizacao.repositorio import (
    RepositorioSincronizacao,
    bloco_contadores_consistente,
    escolher_bloco_contadores_reconciliacao,
)
from api.sincronizacao.rotas import obter_servico_sync
from api.sincronizacao.servico import ServicoSincronizacao
from api.sincronizacao.validacao import (
    validar_progressao_convidado,
    validar_reconciliacao,
)
from tests.contratos.fakes_sync import FakeRepoSincronizacao

ID_CONTA_A = "3fc7be86-c396-4167-ad30-8d7048521ad9"
ID_CONTA_B = "8fb58b48-15ad-4a2b-b8c8-52eae54aa7a2"
ID_C1D497AC = "c1d497ac-76d8-4273-a743-a1356de6b64a"
ID_1CA98AAD = "1ca98aad-afe0-4352-8594-79fd4459039c"

# Retrato real da Conta A no iPhone antes da T170 (RETOMADA §0): 47+97+19 = 163 > 157.
RETRATO_CONTA_A_INCONSISTENTE = {
    "nu_xp_total": 5960,
    "nu_partidas": 157,
    "nu_vitorias": 47,
    "nu_derrotas": 97,
    "nu_empates": 19,
    "nu_sequencia_atual": 7,
    "dt_ultimo_dia_jogado": "2026-10-30",
    "conquistas": ["damas_derrotar_tex_com_poder", "damas_segurou_magno_com_poder", "sequencia_7"],
}

# Retrato real da Conta A depois da adoção em bloco no app +18: 47+97+13 = 157 == 157.
RETRATO_CONTA_A_CONSERTADO = {
    "nu_xp_total": 5960,
    "nu_partidas": 157,
    "nu_vitorias": 47,
    "nu_derrotas": 97,
    "nu_empates": 13,
    "nu_sequencia_atual": 7,
    "dt_ultimo_dia_jogado": "2026-10-30",
    "conquistas": ["damas_derrotar_tex_com_poder", "damas_segurou_magno_com_poder", "sequencia_7"],
}

# Retrato real da Conta B contaminada no iPhone (RETOMADA §0): 47+97+17 = 161 > 157.
RETRATO_CONTA_B_CONTAMINADA = {
    "nu_xp_total": 5690,
    "nu_partidas": 157,
    "nu_vitorias": 47,
    "nu_derrotas": 97,
    "nu_empates": 17,
    "nu_sequencia_atual": 7,
    "dt_ultimo_dia_jogado": "2026-10-30",
    "conquistas": ["velha_derrotar_tex", "sequencia_7"],
}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Cadeado sobre validacao.py — nunca afrouxar
# ═══════════════════════════════════════════════════════════════════════════


def test_validacao_continua_recusando_conta_a_inconsistente_e_conta_b_contaminada():
    """validacao.py é a rede que impediu a contaminação de subir: ela NÃO pode
    ser afrouxada na T170."""
    assert validar_reconciliacao(RETRATO_CONTA_A_INCONSISTENTE) == "progressao_inconsistente"
    assert validar_reconciliacao(RETRATO_CONTA_B_CONTAMINADA) == "progressao_inconsistente"
    assert (
        validar_progressao_convidado(RETRATO_CONTA_A_INCONSISTENTE)
        == "progressao_inconsistente"
    )
    # CONTROLE: quando o bloco fecha a soma (157 == 157), a mesma Conta A passa.
    assert validar_reconciliacao(RETRATO_CONTA_A_CONSERTADO) is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. Funções puras de consistência e escolha do bloco
# ═══════════════════════════════════════════════════════════════════════════


def test_bloco_contadores_consistente_fronteiras_e_negativos():
    assert bloco_contadores_consistente(0, 0, 0, 0) is True
    assert bloco_contadores_consistente(157, 47, 97, 13) is True
    # Soma menor que partidas é permitida por validacao.py (<=).
    assert bloco_contadores_consistente(10, 3, 3, 2) is True
    # Soma maior por 1 unidade já é inconsistente (caso 1ca98aad: 40 em 39).
    assert bloco_contadores_consistente(39, 16, 14, 10) is False
    # Negativo em qualquer campo é inválido.
    assert bloco_contadores_consistente(-1, 0, 0, 0) is False
    assert bloco_contadores_consistente(10, -1, 5, 5) is False
    assert bloco_contadores_consistente(10, 5, -1, 5) is False
    assert bloco_contadores_consistente(10, 5, 5, -1) is False


def test_escolher_bloco_reconciliacao_empate_em_partidas_mantem_servidor():
    """Corpo da 1.3.1 com mesmo nº de partidas e distribuição diferente: mantém
    o bloco inteiro do servidor em vez de fabricar 154 > 152."""
    escolhido = escolher_bloco_contadores_reconciliacao(
        atual=(152, 56, 90, 6),
        recebido=(152, 54, 90, 8),
    )
    assert escolhido == (152, 56, 90, 6)
    assert sum(escolhido[1:]) <= escolhido[0]


def test_escolher_bloco_reconciliacao_servidor_a_frente_mantem_servidor():
    """Segundo aparelho atrasado em partidas (150 < 157), mas com mais empates
    (15 > 13): o 15 NÃO vaza para o bloco do servidor."""
    escolhido = escolher_bloco_contadores_reconciliacao(
        atual=(157, 47, 97, 13),
        recebido=(150, 45, 90, 15),
    )
    assert escolhido == (157, 47, 97, 13)


def test_escolher_bloco_reconciliacao_app_a_frente_adota_bloco_do_app():
    """CONTROLE: quando o app tem MAIS partidas (evento perdido), o bloco
    inteiro do app substitui o do servidor — inclusive reduzindo um contador
    individual se a distribuição real era outra."""
    escolhido = escolher_bloco_contadores_reconciliacao(
        atual=(152, 56, 90, 6),
        recebido=(153, 54, 90, 9),
    )
    assert escolhido == (153, 54, 90, 9)
    assert sum(escolhido[1:]) == 153


def test_escolher_bloco_reconciliacao_conserta_linha_inconsistente_do_servidor():
    """Auto-reparo das 2 contas quebradas no servidor (c1d497ac e 1ca98aad):
    mesmo com igual ou MENOS partidas no snapshot válido, a linha quebrada cede
    lugar ao bloco consistente."""
    # c1d497ac com mesmo nº de partidas (152 == 152):
    assert escolher_bloco_contadores_reconciliacao(
        atual=(152, 56, 90, 8),
        recebido=(152, 56, 90, 6),
    ) == (152, 56, 90, 6)
    # 1ca98aad com menos partidas no snapshot (38 < 39):
    assert escolher_bloco_contadores_reconciliacao(
        atual=(39, 16, 14, 10),
        recebido=(38, 16, 13, 9),
    ) == (38, 16, 13, 9)


# ═══════════════════════════════════════════════════════════════════════════
# 3. SQL real de RepositorioSincronizacao.reconciliar_progressao em SQLite
# ═══════════════════════════════════════════════════════════════════════════

SQL_CRIAR_PROGRESSAO = """
CREATE TABLE progressao.tb001_progressao_usuario (
    id_progressao TEXT PRIMARY KEY,
    id_usuario TEXT NOT NULL UNIQUE,
    nu_xp_total INTEGER NOT NULL DEFAULT 0,
    nu_partidas INTEGER NOT NULL DEFAULT 0,
    nu_vitorias INTEGER NOT NULL DEFAULT 0,
    nu_derrotas INTEGER NOT NULL DEFAULT 0,
    nu_empates INTEGER NOT NULL DEFAULT 0,
    nu_sequencia_atual INTEGER NOT NULL DEFAULT 0,
    dt_ultimo_dia_jogado TEXT NULL,
    dh_atualizacao TEXT NOT NULL
);
"""

SQL_CRIAR_CONQUISTAS = """
CREATE TABLE progressao.tb002_conquista_usuario (
    id_conquista_usuario TEXT PRIMARY KEY,
    id_usuario TEXT NOT NULL,
    co_conquista TEXT NOT NULL,
    dh_desbloqueio TEXT NOT NULL,
    UNIQUE (id_usuario, co_conquista)
);
"""


def _greatest_compat_postgres(a: Any, b: Any) -> Any:
    """No PostgreSQL, ``GREATEST(x, NULL)`` devolve ``x`` (ignora NULLs, só
    devolvendo NULL se ambos forem NULL). Emula exatamente essa semântica no
    SQLite para executar o SQL literal de ``reconciliar_progressao``."""
    if a is None:
        return b
    if b is None:
        return a
    # Datas podem chegar como datetime.date de um lado e str ISO do outro no SQLite.
    sa = a.isoformat() if isinstance(a, date) else a
    sb = b.isoformat() if isinstance(b, date) else b
    if type(sa) is type(sb):
        return sa if sa >= sb else sb
    return str(sa) if str(sa) >= str(sb) else str(sb)


@pytest_asyncio.fixture
async def fabrica_progressao_sqlite():
    """Banco SQLite em memória com o schema ``progressao`` anexado para rodar o
    ``INSERT ... ON CONFLICT (id_usuario) DO UPDATE`` real do repositório."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _registrar_funcoes_pg(conexao_dbapi, _registro):
        conexao_dbapi.create_function("gen_random_uuid", 0, lambda: str(uuid4()))
        conexao_dbapi.create_function("now", 0, lambda: "2026-10-30T20:00:00Z")
        conexao_dbapi.create_function("greatest", 2, _greatest_compat_postgres)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        await s.execute(text("ATTACH DATABASE ':memory:' AS progressao"))
        await s.execute(text(SQL_CRIAR_PROGRESSAO))
        await s.execute(text(SQL_CRIAR_CONQUISTAS))
        await s.commit()
    yield fabrica
    await engine.dispose()


async def _semear_linha_servidor(
    fabrica,
    *,
    id_usuario: str,
    xp: int,
    partidas: int,
    vitorias: int,
    derrotas: int,
    empates: int,
    sequencia: int = 1,
    ultimo_dia: str | None = "2026-10-20",
    conquistas: list[str] | None = None,
) -> None:
    async with fabrica() as s:
        await s.execute(
            text(
                """
                INSERT INTO progressao.tb001_progressao_usuario
                  (id_progressao, id_usuario, nu_xp_total, nu_partidas,
                   nu_vitorias, nu_derrotas, nu_empates, nu_sequencia_atual,
                   dt_ultimo_dia_jogado, dh_atualizacao)
                VALUES
                  (gen_random_uuid(), :u, :xp, :p, :v, :d, :e, :seq, :dia, now())
                """
            ),
            {
                "u": id_usuario,
                "xp": xp,
                "p": partidas,
                "v": vitorias,
                "d": derrotas,
                "e": empates,
                "seq": sequencia,
                "dia": ultimo_dia,
            },
        )
        for co in conquistas or []:
            await s.execute(
                text(
                    """
                    INSERT INTO progressao.tb002_conquista_usuario
                      (id_conquista_usuario, id_usuario, co_conquista, dh_desbloqueio)
                    VALUES (gen_random_uuid(), :u, :co, now())
                    """
                ),
                {"u": id_usuario, "co": co},
            )
        await s.commit()


async def _ler_estado_servidor(fabrica, id_usuario: str) -> dict[str, Any]:
    async with fabrica() as s:
        linha = (
            await s.execute(
                text(
                    """
                    SELECT nu_xp_total, nu_partidas, nu_vitorias, nu_derrotas,
                           nu_empates, nu_sequencia_atual, dt_ultimo_dia_jogado
                      FROM progressao.tb001_progressao_usuario
                     WHERE id_usuario = :u
                    """
                ),
                {"u": id_usuario},
            )
        ).mappings().one()
        conqs = [
            r[0]
            for r in (
                await s.execute(
                    text(
                        """
                        SELECT co_conquista
                          FROM progressao.tb002_conquista_usuario
                         WHERE id_usuario = :u
                         ORDER BY co_conquista
                        """
                    ),
                    {"u": id_usuario},
                )
            ).all()
        ]
        saida = dict(linha)
        saida["conquistas"] = conqs
        return saida


@pytest.mark.asyncio
async def test_sql_real_app_1_3_1_com_empate_de_damas_nao_fabrica_linha_inconsistente(
    fabrica_progressao_sqlite,
):
    """Compatibilidade 1.3.1 (§8zzzz10): o corpo exato que a 1.3.1 manda quando
    dois empates de damas viraram vitórias no servidor (152/54/90/8 vs
    152/56/90/6) sobe XP, chama, data e conquistas, mas NÃO mistura V=56 com
    E=8 para criar 154 > 152."""
    await _semear_linha_servidor(
        fabrica_progressao_sqlite,
        id_usuario=ID_C1D497AC,
        xp=2500,
        partidas=152,
        vitorias=56,
        derrotas=90,
        empates=6,
        sequencia=3,
        ultimo_dia="2026-10-20",
        conquistas=["primeira_vitoria"],
    )

    # Corpo exato enviado por ServicoSync.reconciliarProgressao na 1.3.1:
    corpo_1_3_1 = {
        "nu_xp_total": 2720,
        "nu_partidas": 152,
        "nu_vitorias": 54,
        "nu_derrotas": 90,
        "nu_empates": 8,
        "nu_sequencia_atual": 5,
        "dt_ultimo_dia_jogado": "2026-10-21",
        "conquistas": ["primeira_vitoria", "damas_vitorias_10"],
    }

    async with fabrica_progressao_sqlite() as s:
        repo = RepositorioSincronizacao(s)
        await repo.reconciliar_progressao(
            id_usuario=ID_C1D497AC, snapshot=corpo_1_3_1
        )
        await s.commit()

    estado = await _ler_estado_servidor(fabrica_progressao_sqlite, ID_C1D497AC)
    # XP, sequência, data e conquistas subiram normalmente:
    assert estado["nu_xp_total"] == 2720
    assert estado["nu_sequencia_atual"] == 5
    assert str(estado["dt_ultimo_dia_jogado"]) == "2026-10-21"
    assert estado["conquistas"] == ["damas_vitorias_10", "primeira_vitoria"]
    # O bloco de contadores permaneceu o do servidor (soma = 152 == 152):
    assert (
        estado["nu_partidas"],
        estado["nu_vitorias"],
        estado["nu_derrotas"],
        estado["nu_empates"],
    ) == (152, 56, 90, 6)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bloco_atrasado",
    [
        # Mais vitórias (55 > 47), mas menos partidas (150 < 157):
        (150, 55, 85, 10),
        # Mais derrotas (99 > 97), mas menos partidas (150 < 157):
        (150, 36, 99, 15),
        # Mais empates (25 > 13), mas menos partidas (150 < 157):
        (150, 40, 85, 25),
    ],
)
async def test_sql_real_segundo_aparelho_atrasado_nao_vaza_contador_individual(
    fabrica_progressao_sqlite,
    bloco_atrasado: tuple[int, int, int, int],
):
    """Se um segundo aparelho está atrás em partidas (150 < 157), mas tem um
    contador individual maior (vitórias, derrotas ou empates), nenhum campo do
    bloco atrasado entra no servidor."""
    await _semear_linha_servidor(
        fabrica_progressao_sqlite,
        id_usuario=ID_CONTA_A,
        xp=5660,
        partidas=157,
        vitorias=47,
        derrotas=97,
        empates=13,
        sequencia=7,
    )

    async with fabrica_progressao_sqlite() as s:
        repo = RepositorioSincronizacao(s)
        await repo.reconciliar_progressao(
            id_usuario=ID_CONTA_A,
            snapshot={
                "nu_xp_total": 5100,
                "nu_partidas": bloco_atrasado[0],
                "nu_vitorias": bloco_atrasado[1],
                "nu_derrotas": bloco_atrasado[2],
                "nu_empates": bloco_atrasado[3],
                "nu_sequencia_atual": 2,
                "conquistas": [],
            },
        )
        await s.commit()

    estado = await _ler_estado_servidor(fabrica_progressao_sqlite, ID_CONTA_A)
    assert estado["nu_xp_total"] == 5660
    assert (
        estado["nu_partidas"],
        estado["nu_vitorias"],
        estado["nu_derrotas"],
        estado["nu_empates"],
    ) == (157, 47, 97, 13)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bloco_servidor", "bloco_app"),
    [
        # App com mais partidas (158 > 157), mas V e D menores que no servidor:
        ((157, 50, 97, 10), (158, 48, 95, 15)),
        # App com mais partidas (158 > 157), mas E menor que no servidor:
        ((157, 47, 90, 20), (158, 50, 95, 13)),
    ],
)
async def test_sql_real_app_com_mais_partidas_substitui_o_bloco_inteiro(
    fabrica_progressao_sqlite,
    bloco_servidor: tuple[int, int, int, int],
    bloco_app: tuple[int, int, int, int],
):
    """CONTROLE: quando o app tem mais partidas (158 > 157), TODAS as quatro
    colunas vêm do snapshot — inclusive quando V, D ou E são numericamente
    menores que os que estavam no servidor, para o bloco nunca quebrar a soma."""
    await _semear_linha_servidor(
        fabrica_progressao_sqlite,
        id_usuario=ID_CONTA_A,
        xp=5660,
        partidas=bloco_servidor[0],
        vitorias=bloco_servidor[1],
        derrotas=bloco_servidor[2],
        empates=bloco_servidor[3],
    )

    async with fabrica_progressao_sqlite() as s:
        repo = RepositorioSincronizacao(s)
        await repo.reconciliar_progressao(
            id_usuario=ID_CONTA_A,
            snapshot={
                "nu_xp_total": 6000,
                "nu_partidas": bloco_app[0],
                "nu_vitorias": bloco_app[1],
                "nu_derrotas": bloco_app[2],
                "nu_empates": bloco_app[3],
                "nu_sequencia_atual": 8,
                "conquistas": ["sequencia_7"],
            },
        )
        await s.commit()

    estado = await _ler_estado_servidor(fabrica_progressao_sqlite, ID_CONTA_A)
    assert estado["nu_xp_total"] == 6000
    assert (
        estado["nu_partidas"],
        estado["nu_vitorias"],
        estado["nu_derrotas"],
        estado["nu_empates"],
    ) == bloco_app
    assert (
        estado["nu_vitorias"] + estado["nu_derrotas"] + estado["nu_empates"]
        == estado["nu_partidas"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("id_conta", "quebrado", "reparo"),
    [
        # As 2 contas reais que estavam inconsistentes no prd em 30/10/2026:
        (ID_C1D497AC, (152, 56, 90, 8), (152, 56, 90, 6)),
        (ID_1CA98AAD, (39, 16, 14, 10), (39, 16, 14, 9)),
        # Mesmo se o snapshot válido tiver menos partidas que a linha quebrada:
        ("conta-quebrada-3", (40, 20, 15, 10), (38, 18, 14, 6)),
    ],
)
async def test_sql_real_auto_repara_linha_inconsistente_no_servidor(
    fabrica_progressao_sqlite,
    id_conta: str,
    quebrado: tuple[int, int, int, int],
    reparo: tuple[int, int, int, int],
):
    """Se a linha atual do servidor já está com ``V + D + E > partidas``, um
    snapshot consistente substitui as 4 colunas juntas mesmo sem ter mais
    partidas."""
    await _semear_linha_servidor(
        fabrica_progressao_sqlite,
        id_usuario=id_conta,
        xp=2180,
        partidas=quebrado[0],
        vitorias=quebrado[1],
        derrotas=quebrado[2],
        empates=quebrado[3],
    )

    async with fabrica_progressao_sqlite() as s:
        repo = RepositorioSincronizacao(s)
        await repo.reconciliar_progressao(
            id_usuario=id_conta,
            snapshot={
                "nu_xp_total": 2400,
                "nu_partidas": reparo[0],
                "nu_vitorias": reparo[1],
                "nu_derrotas": reparo[2],
                "nu_empates": reparo[3],
                "nu_sequencia_atual": 4,
                "conquistas": [],
            },
        )
        await s.commit()

    estado = await _ler_estado_servidor(fabrica_progressao_sqlite, id_conta)
    assert estado["nu_xp_total"] == 2400
    assert (
        estado["nu_partidas"],
        estado["nu_vitorias"],
        estado["nu_derrotas"],
        estado["nu_empates"],
    ) == reparo
    assert (
        estado["nu_vitorias"] + estado["nu_derrotas"] + estado["nu_empates"]
        <= estado["nu_partidas"]
    )


@pytest.mark.asyncio
async def test_sql_real_conta_a_consertada_sobe_xp_5960_e_conquistas_sem_dobrar_bonus(
    fabrica_progressao_sqlite,
):
    """Cenário completo da Conta A (dono): no servidor tem 5.660 / 157 / 47 / 97 / 13;
    depois que o app +18 adota o bloco consistente do servidor, ele reconcilia
    ``5.960 / 157 / 47 / 97 / 13`` com as 3 conquistas que faltavam. O servidor
    aceita, grava 5.960 (sem somar bônus outra vez!) e une as conquistas."""
    await _semear_linha_servidor(
        fabrica_progressao_sqlite,
        id_usuario=ID_CONTA_A,
        xp=5660,
        partidas=157,
        vitorias=47,
        derrotas=97,
        empates=13,
        sequencia=7,
        ultimo_dia="2026-10-30",
        conquistas=["primeira_vitoria"],
    )

    async with fabrica_progressao_sqlite() as s:
        repo = RepositorioSincronizacao(s)
        await repo.reconciliar_progressao(
            id_usuario=ID_CONTA_A, snapshot=RETRATO_CONTA_A_CONSERTADO
        )
        await s.commit()

    estado = await _ler_estado_servidor(fabrica_progressao_sqlite, ID_CONTA_A)
    assert estado["nu_xp_total"] == 5960
    assert (
        estado["nu_partidas"],
        estado["nu_vitorias"],
        estado["nu_derrotas"],
        estado["nu_empates"],
    ) == (157, 47, 97, 13)
    assert set(estado["conquistas"]) == {
        "primeira_vitoria",
        "damas_derrotar_tex_com_poder",
        "damas_segurou_magno_com_poder",
        "sequencia_7",
    }


@pytest.mark.asyncio
async def test_sql_real_primeira_reconciliacao_cria_linha_nova(
    fabrica_progressao_sqlite,
):
    """Quando o usuário ainda não tem linha em tb001_progressao_usuario, o
    INSERT grava o bloco inteiro diretamente."""
    async with fabrica_progressao_sqlite() as s:
        repo = RepositorioSincronizacao(s)
        await repo.reconciliar_progressao(
            id_usuario="usuario-novo",
            snapshot={
                "nu_xp_total": 180,
                "nu_partidas": 4,
                "nu_vitorias": 2,
                "nu_derrotas": 1,
                "nu_empates": 1,
                "nu_sequencia_atual": 2,
                "dt_ultimo_dia_jogado": "2026-10-30",
                "conquistas": ["primeira_vitoria"],
            },
        )
        await s.commit()

    estado = await _ler_estado_servidor(fabrica_progressao_sqlite, "usuario-novo")
    assert estado["nu_xp_total"] == 180
    assert (
        estado["nu_partidas"],
        estado["nu_vitorias"],
        estado["nu_derrotas"],
        estado["nu_empates"],
    ) == (4, 2, 1, 1)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Rota HTTP POST /v1/sincronizacao/reconciliar e FakeRepoSincronizacao
# ═══════════════════════════════════════════════════════════════════════════


class _SessaoFalsa:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def test_rota_http_fake_repo_segue_mesma_regra_em_bloco_e_recusa_inconsistente():
    """Garante paridade entre FakeRepoSincronizacao e o repositório real na
    rota HTTP: não fabrica 154 > 152 no empate de partidas, auto-repara linha
    quebrada, substitui quando o app tem mais partidas, e continua devolvendo
    422 quando o próprio snapshot enviado não fecha."""
    fake_repo = FakeRepoSincronizacao()
    fake_sessao = _SessaoFalsa()
    fake_repo._progressao[ID_C1D497AC] = {
        "nu_xp_total": 2500,
        "nu_partidas": 152,
        "nu_vitorias": 56,
        "nu_derrotas": 90,
        "nu_empates": 6,
        "nu_sequencia_atual": 3,
        "dt_ultimo_dia_jogado": "2026-10-20",
        "conquistas": set(),
    }

    app.dependency_overrides[usuario_autenticado] = lambda: UsuarioAutenticado(
        id_usuario=ID_C1D497AC,
        co_usuario="C1D497AC",
        contexto=ContextoRequisicao(
            versao_app="1.3.1", plataforma="android", idioma="pt"
        ),
    )
    app.dependency_overrides[obter_servico_sync] = (
        lambda: ServicoSincronizacao(fake_repo, fake_sessao)
    )
    try:
        client = TestClient(app)

        # 1) 1.3.1 manda 152/54/90/8 sobre 152/56/90/6 -> mantém bloco 152/56/90/6:
        r1 = client.post(
            "/v1/sincronizacao/reconciliar",
            json={
                "progressao": {
                    "nu_xp_total": 2720,
                    "nu_partidas": 152,
                    "nu_vitorias": 54,
                    "nu_derrotas": 90,
                    "nu_empates": 8,
                    "nu_sequencia_atual": 4,
                }
            },
        )
        assert r1.status_code == 200
        p1 = r1.json()["progressao"]
        assert p1["nu_xp_total"] == 2720
        assert (
            p1["nu_partidas"],
            p1["nu_vitorias"],
            p1["nu_derrotas"],
            p1["nu_empates"],
        ) == (152, 56, 90, 6)

        # 2) Se a linha do servidor estava quebrada (152/56/90/8), auto-repara:
        fake_repo._progressao[ID_C1D497AC]["nu_empates"] = 8
        r2 = client.post(
            "/v1/sincronizacao/reconciliar",
            json={
                "progressao": {
                    "nu_xp_total": 2720,
                    "nu_partidas": 152,
                    "nu_vitorias": 56,
                    "nu_derrotas": 90,
                    "nu_empates": 6,
                    "nu_sequencia_atual": 4,
                }
            },
        )
        assert r2.status_code == 200
        p2 = r2.json()["progressao"]
        assert (
            p2["nu_partidas"],
            p2["nu_vitorias"],
            p2["nu_derrotas"],
            p2["nu_empates"],
        ) == (152, 56, 90, 6)

        # 3) CONTROLE: snapshot inconsistente continua barrado com 422 e arquivado:
        r3 = client.post(
            "/v1/sincronizacao/reconciliar",
            json={"progressao": RETRATO_CONTA_A_INCONSISTENTE},
        )
        assert r3.status_code == 422
        assert len(fake_repo.arquivados_completos) == 1
        assert fake_repo.arquivados_completos[0]["de_codigo"] == "progressao_inconsistente"
    finally:
        app.dependency_overrides.clear()

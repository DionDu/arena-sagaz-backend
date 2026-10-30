"""O BÔNUS DAS CONQUISTAS creditado pelo SERVIDOR (T167 da spec 010, 30/10/2026).

═══════════════════════════════════════════════════════════════════════════
O DEFEITO, E A REGRA QUE O CONSERTA
═══════════════════════════════════════════════════════════════════════════

O bônus de XP das conquistas dos JOGOS só chegava ao servidor pela
reconciliação, e em 9 contas do ``prd`` ela é recusada com 422 - o bônus nunca
chegava ao ranking (2º defeito de progressão da 1.4.0,
``arena-sagaz-frontend/specs/010-jogo-quatro-em-linha/RETOMADA-progressao-1.4.0.md``).
Desde a T167 o servidor credita o bônus de TODA conquista ao inseri-la, como já
fazia com as do Desafio do Dia desde 05/10/2026:

* **o evento ``conquista`` e o merge do convidado creditam, e só na inserção**
  (o reenvio e o segundo aparelho não pagam de novo);
* ⛔ **a reconciliação nunca credita** - o total dela já é o ``GREATEST`` com o
  total do aparelho, que inclui o bônus (risco R2).

⚠️ **E nada pode ficar pior para quem não atualizar** (decisão do dono,
30/10/2026, ``DECISOES-do-dono.md`` §8zzzz10). O app antigo soma o bônus que o
catálogo DELE diz; por isso o valor de uma conquista publicada não muda mais, e
um cadeado congela os números (o último grupo deste arquivo).

═══════════════════════════════════════════════════════════════════════════
COMO CADA PARTE É PROVADA
═══════════════════════════════════════════════════════════════════════════

* O crédito usa SQL do Postgres (``xmax``, ``gen_random_uuid()``) que o SQLite
  não roda. Aqui uma sessão que ANOTA cada comando prova a regra no repositório
  real: credita na inserção nova, só nela, e só pelos dois caminhos certos.
* As duas ordens (evento antes e depois da reconciliação), o reenvio e o merge
  com o SQL de verdade são provados contra o ``des`` numa transação desfeita:
  ``scripts/conferir_bonus_das_conquistas_t167.py``.
* Os cadeados finais: a tabela = o arquivo comum com o app, e os valores
  publicados congelados.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from api.desafios.repositorio_envio import SQL_CREDITAR_NA_CONTA
from api.sincronizacao.bonus_das_conquistas import (
    BONUS_DAS_CONQUISTAS,
    bonus_da_conquista,
)
from api.sincronizacao.repositorio import RepositorioSincronizacao

DONO = "63385354-1e03-44bc-b2a3-82fdb8e34547"


# ═══════════════════════════════════════════════════════════════════════════
# A sessão que anota (veio de test_conquistas_do_desafio.py)
# ═══════════════════════════════════════════════════════════════════════════


class _Resultado:
    """O que ``sessao.execute`` devolve: só o que o repositório lê dele."""

    def __init__(self, valor: Any) -> None:
        self._valor = valor

    def scalar(self) -> Any:
        return self._valor

    def first(self) -> Any:
        return self._valor


class _SessaoQueAnota:
    """Anota cada comando e responde à INSERÇÃO da conquista com [inserido].

    ``gravar_conquista`` lê ``scalar()`` (o ``xmax = 0``); a migração do
    convidado lê ``first()`` (uma linha no ``RETURNING`` = inseriu). A mesma
    resposta serve aos dois: ``True``/uma linha quando inseriu, ``None`` quando
    a conquista já estava lá. [lote_novo] diz se o lote da migração é novo.
    """

    def __init__(self, *, inserido: bool, lote_novo: bool = True) -> None:
        self.inserido = inserido
        self.lote_novo = lote_novo
        self.comandos: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, comando: Any, parametros: dict[str, Any]) -> _Resultado:
        sql = str(comando)
        self.comandos.append((sql, parametros))
        if "tb002_conquista_usuario" in sql:
            return _Resultado(True if self.inserido else None)
        if "tb003_lote_migracao" in sql:
            return _Resultado(("lote",) if self.lote_novo else None)
        return _Resultado(None)

    def creditos(self) -> list[int]:
        """Os XP somados à conta pelo crédito do bônus, na ordem.

        ⚠️ É o SQL do crédito, e não "qualquer soma de XP": o merge e a partida
        também somam ``nu_xp_total``, e por isso o filtro é pelo texto exato.
        """
        return [p["xp"] for sql, p in self.comandos if sql == SQL_CREDITAR_NA_CONTA]

    def conquistas_gravadas(self) -> list[str]:
        """Os códigos que passaram pelo ``INSERT`` da conquista - a prova de que
        o caminho rodou, nos casos em que o crédito NÃO deve acontecer."""
        return [
            p["co_conquista"]
            for sql, p in self.comandos
            if "INSERT INTO progressao.tb002_conquista_usuario" in sql
        ]


def _evento(co_conquista: Any) -> dict[str, Any]:
    """O payload do evento de conquista, como o app o monta
    (``ServicoLogPartida.registrarConquista``, igual na 1.3.1 e na 1.4.0)."""
    return {
        "conquista": {
            "co_conquista": co_conquista,
            "dh_desbloqueio": "2026-10-30T11:25:00.000Z",
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. O evento ``conquista``
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_conquista_do_desafio_continua_pagando_ao_ser_inserida():
    """CONTROLE de regressão: o que já funcionava desde 05/10/2026."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    inserido = await repo.gravar_conquista(
        id_usuario=DONO, co_evento="e1", payload=_evento("desafio_resolvidos_10")
    )

    assert inserido is True
    assert sessao.creditos() == [100]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("co_conquista", "bonus"),
    [
        # As três da conta A que não chegaram (RETOMADA §2).
        ("damas_derrotar_tex_com_poder", 80),
        ("damas_segurou_magno_com_poder", 100),
        ("sequencia_7", 120),
        # Uma de conta e uma de cada jogo.
        ("nivel_5", 80),
        ("pontinhos_vitorias_10", 100),
        ("velha_partida_perfeita", 300),
        ("quatro_folego_longo", 120),
    ],
)
async def test_a_conquista_de_JOGO_agora_paga_ao_ser_inserida(co_conquista, bonus):
    """O coração da T167. Antes este caso dizia o contrário ("conquista de jogo
    não paga por este caminho"), na crença de que o bônus vinha na partida."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    await repo.gravar_conquista(
        id_usuario=DONO, co_evento="e1", payload=_evento(co_conquista)
    )

    assert sessao.creditos() == [bonus]


@pytest.mark.asyncio
@pytest.mark.parametrize("co_conquista", sorted(BONUS_DAS_CONQUISTAS))
async def test_toda_conquista_da_tabela_paga_o_seu_valor(co_conquista):
    """As 91: cada uma credita exatamente o número da tabela, uma vez, para o
    dono do token."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    await repo.gravar_conquista(
        id_usuario=DONO, co_evento="e1", payload=_evento(co_conquista)
    )

    creditos = [
        (p["id_usuario"], p["xp"])
        for sql, p in sessao.comandos
        if sql == SQL_CREDITAR_NA_CONTA
    ]
    assert creditos == [(DONO, BONUS_DAS_CONQUISTAS[co_conquista])]


@pytest.mark.asyncio
@pytest.mark.parametrize("co_conquista", ["desafio_primeiro", "sequencia_7"])
async def test_o_reenvio_nao_paga_de_novo(co_conquista):
    """O mesmo evento duas vezes, ou a mesma conquista de um segundo aparelho:
    a linha já existe, ``xmax`` não é zero, e o bônus fica onde estava."""
    sessao = _SessaoQueAnota(inserido=False)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    inserido = await repo.gravar_conquista(
        id_usuario=DONO, co_evento="e1", payload=_evento(co_conquista)
    )

    assert inserido is False
    # O caminho rodou (a conquista passou pelo INSERT), e mesmo assim não pagou.
    assert sessao.conquistas_gravadas() == [co_conquista]
    assert sessao.creditos() == []


@pytest.mark.asyncio
async def test_conquista_que_o_servidor_nao_conhece_grava_e_nao_paga():
    """Um app mais novo que o servidor: a conquista fica gravada, e o bônus
    dela chega pela reconciliação, como chegava antes da T167."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    inserido = await repo.gravar_conquista(
        id_usuario=DONO, co_evento="e1", payload=_evento("xadrez_vitorias_1")
    )

    assert inserido is True
    assert sessao.conquistas_gravadas() == ["xadrez_vitorias_1"]
    # Nenhum comando de crédito, nem de zero: "zero não chega a ir ao banco".
    assert sessao.creditos() == []


def test_codigo_que_nao_e_texto_da_zero():
    """O código sai de um payload JSON: um número ou ``None`` ali não pode
    estourar a ingestão nem pagar nada."""
    assert bonus_da_conquista(None) == 0
    assert bonus_da_conquista(42) == 0
    assert bonus_da_conquista(["sequencia_7"]) == 0
    assert bonus_da_conquista("sequencia_7") == 120
    assert bonus_da_conquista("desafio_primeiro") == 40


# ═══════════════════════════════════════════════════════════════════════════
# 2. O merge do convidado
# ═══════════════════════════════════════════════════════════════════════════


def _merge(conquistas: list[str]) -> dict[str, Any]:
    """O retrato que o app manda no merge (``ServicoSync.mergeConvidado``,
    igual na 1.3.1): os contadores em ZERO de propósito (sobem pelos eventos),
    e só a chama e as conquistas."""
    return {
        "nu_xp_total": 0,
        "nu_partidas": 0,
        "nu_vitorias": 0,
        "nu_derrotas": 0,
        "nu_empates": 0,
        "nu_sequencia_atual": 3,
        "conquistas": conquistas,
    }


@pytest.mark.asyncio
async def test_a_migracao_do_convidado_paga_as_de_jogo_e_as_do_desafio():
    """O merge grava as conquistas do convidado ANTES de a fila dele subir; se
    só o evento pagasse, ele acharia a linha pronta e o bônus se perderia.
    Desde a T167 o ``nivel_5`` (de conta) também paga."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    aplicado = await repo.aplicar_merge_se_novo(
        id_usuario=DONO,
        co_lote_migracao="lote-1",
        progressao_convidado=_merge(
            ["desafio_primeiro", "nivel_5", "desafio_semana_completa"]
        ),
    )

    assert aplicado is True
    assert sessao.creditos() == [40, 80, 120]


@pytest.mark.asyncio
async def test_a_migracao_nao_paga_o_que_a_conta_ja_tinha():
    """Conquista que a conta já tinha no servidor: ``DO NOTHING``, sem linha no
    ``RETURNING``, e sem crédito - o app também não a soma duas vezes."""
    sessao = _SessaoQueAnota(inserido=False)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    await repo.aplicar_merge_se_novo(
        id_usuario=DONO,
        co_lote_migracao="lote-1",
        progressao_convidado=_merge(["desafio_mes_completo", "sequencia_7"]),
    )

    assert sessao.conquistas_gravadas() == ["desafio_mes_completo", "sequencia_7"]
    assert sessao.creditos() == []


@pytest.mark.asyncio
async def test_o_lote_ja_aplicado_nao_paga_nada():
    """O retry do mesmo lote (o app reenvia até o servidor confirmar) para no
    carimbo do lote: nem soma, nem grava conquista, nem credita."""
    sessao = _SessaoQueAnota(inserido=True, lote_novo=False)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    aplicado = await repo.aplicar_merge_se_novo(
        id_usuario=DONO,
        co_lote_migracao="lote-1",
        progressao_convidado=_merge(["sequencia_7"]),
    )

    assert aplicado is False
    assert sessao.conquistas_gravadas() == []
    assert sessao.creditos() == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. A reconciliação - nunca paga
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_reconciliacao_nunca_paga_o_bonus():
    """⚠️ A reconciliação aplica ``GREATEST`` com o total do APARELHO, que já
    inclui o bônus. Somar depois disso passaria do número certo - por isso ela,
    de propósito, não chama o crédito, nem quando a conquista é nova (aqui a
    sessão responde "inseriu" para as três)."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    await repo.reconciliar_progressao(
        id_usuario=DONO,
        snapshot={
            "nu_xp_total": 5660,
            "nu_partidas": 157,
            "conquistas": ["desafio_primeiro", "sequencia_7", "nivel_5"],
        },
    )

    # CONTROLE: o caminho rodou - as três passaram pelo INSERT da união.
    assert sessao.conquistas_gravadas() == [
        "desafio_primeiro",
        "sequencia_7",
        "nivel_5",
    ]
    assert sessao.creditos() == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. Os cadeados da tabela
# ═══════════════════════════════════════════════════════════════════════════

#: O arquivo comum com o app. `parents[3]` sobe de `tests/unitarios/` até a raiz
#: do ecossistema (`arena-sagaz/`).
_ARQUIVO_COMUM = (
    Path(__file__).resolve().parents[3]
    / "arena-sagaz-frontend"
    / "test"
    / "core"
    / "progressao"
    / "bonus_das_conquistas.json"
)


def test_a_tabela_bate_com_o_arquivo_comum_do_app():
    """O app soma o bônus na celebração; o servidor, quando o evento chega. Se
    os números divergirem, o total do aparelho e o do ranking param de bater - e
    ninguém vê, porque cada lado está "certo" sozinho.

    O app confere o catálogo dele com o MESMO arquivo
    (``test/core/progressao/bonus_das_conquistas_test.dart``). ⚠️ Pula (e diz
    por quê) quando o repositório irmão não está ao lado - é o caso de uma
    máquina que só clonou o backend.
    """
    if not _ARQUIVO_COMUM.exists():
        pytest.skip(f"arquivo comum do app não encontrado em {_ARQUIVO_COMUM}")

    no_app = json.loads(_ARQUIVO_COMUM.read_text(encoding="utf-8"))["bonus"]

    assert BONUS_DAS_CONQUISTAS == no_app


def test_todo_codigo_cabe_na_coluna_e_todo_bonus_e_positivo():
    """``co_conquista`` é ``VARCHAR(40)``: um código maior seria recusado na
    sincronização. E um bônus zero ou negativo não tem sentido como prêmio."""
    for codigo, bonus in BONUS_DAS_CONQUISTAS.items():
        assert len(codigo) <= 40, codigo
        assert bonus > 0, codigo


#: ⛔ **Os valores PUBLICADOS, congelados** (30/10/2026). A 1.3.1 das lojas (e as
#: anteriores) soma o bônus que o catálogo dela diz, e o servidor agora credita o
#: desta tabela: se um dia os dois mudassem juntos, o cadeado do arquivo comum
#: continuaria verde e o app antigo passaria a mostrar um número diferente do
#: ranking - um problema NOVO para quem não atualizou, que o dono proibiu
#: (``DECISOES-do-dono.md`` §8zzzz10). Conferido em 30/10/2026: nenhum valor
#: mudou no histórico de ``conquistas.dart``. Escritos à mão de propósito (um
#: teste que lesse a tabela que devia conferir passaria com qualquer valor).
PUBLICADOS_ATE_A_1_3_1: dict[str, int] = {
    "nivel_5": 80,
    "nivel_10": 120,
    "nivel_20": 200,
    "nivel_35": 320,
    "nivel_55": 480,
    "nivel_80": 680,
    "primeira_vitoria": 40,
    "vitorias_10": 100,
    "vitorias_50": 200,
    "vitorias_100": 350,
    "vitorias_500": 800,
    "sequencia_3": 60,
    "sequencia_7": 120,
    "sequencia_14": 220,
    "sequencia_30": 400,
    "dias_10": 100,
    "dias_30": 250,
    "dias_100": 600,
    "pontinhos_vitorias_1": 40,
    "pontinhos_vitorias_10": 100,
    "pontinhos_vitorias_50": 200,
    "pontinhos_vitorias_100": 350,
    "pontinhos_derrotar_cacau": 80,
    "pontinhos_derrotar_pita": 140,
    "pontinhos_derrotar_tex": 180,
    "pontinhos_derrotar_magno": 220,
    "pontinhos_derrotar_cacau_com_poder": 30,
    "pontinhos_derrotar_pita_com_poder": 50,
    "pontinhos_derrotar_tex_com_poder": 70,
    "pontinhos_derrotar_magno_com_poder": 90,
    "pontinhos_lenda": 300,
    "pontinhos_lenda_com_poder": 120,
    "velha_vitorias_1": 30,
    "velha_vitorias_10": 70,
    "velha_vitorias_50": 140,
    "velha_vitorias_100": 240,
    "velha_derrotar_cacau": 40,
    "velha_derrotar_pita": 90,
    "velha_derrotar_tex": 200,
    "velha_derrotar_magno": 500,
    "velha_lenda": 400,
    "velha_segurou_magno": 250,
    "velha_partida_perfeita": 300,
    "damas_vitorias_1": 80,
    "damas_vitorias_10": 200,
    "damas_vitorias_50": 400,
    "damas_vitorias_100": 700,
    "damas_derrotar_cacau": 80,
    "damas_derrotar_pita": 140,
    "damas_derrotar_tex": 200,
    "damas_derrotar_magno": 300,
    "damas_derrotar_cacau_com_poder": 30,
    "damas_derrotar_pita_com_poder": 50,
    "damas_derrotar_tex_com_poder": 80,
    "damas_derrotar_magno_com_poder": 120,
    "damas_lenda": 350,
    "damas_lenda_com_poder": 140,
    "damas_segurou_magno": 250,
    "damas_segurou_magno_com_poder": 100,
    "damas_partida_perfeita": 250,
    "damas_primeira_dama": 40,
    "damas_captura_tripla": 120,
    "damas_captura_cinco": 220,
    "desafio_primeiro": 40,
    "desafio_resolvidos_10": 100,
    "desafio_resolvidos_50": 200,
    "desafio_resolvidos_100": 350,
    "desafio_semana_completa": 120,
    "desafio_mes_completo": 400,
}

#: As do Quatro em Linha, que chegam com a 1.4.0. Ficam congeladas também: a
#: partir da publicação, mudar uma é o mesmo problema de cima.
PUBLICADOS_NA_1_4_0: dict[str, int] = {
    "quatro_vitorias_1": 80,
    "quatro_vitorias_10": 200,
    "quatro_vitorias_50": 400,
    "quatro_vitorias_100": 700,
    "quatro_derrotar_cacau": 80,
    "quatro_derrotar_pita": 140,
    "quatro_derrotar_tex": 200,
    "quatro_derrotar_magno": 300,
    "quatro_derrotar_cacau_com_poder": 30,
    "quatro_derrotar_pita_com_poder": 50,
    "quatro_derrotar_tex_com_poder": 80,
    "quatro_derrotar_magno_com_poder": 120,
    "quatro_lenda": 350,
    "quatro_lenda_com_poder": 140,
    "quatro_segurou_magno": 250,
    "quatro_segurou_magno_com_poder": 100,
    "quatro_torre": 40,
    "quatro_diagonal": 40,
    "quatro_relampago": 120,
    "quatro_dupla": 120,
    "quatro_cinco": 220,
    "quatro_folego_longo": 120,
}


def test_o_valor_de_uma_conquista_publicada_nao_muda():
    """Conquista nova entra com valor novo; conquista publicada fica como está."""
    for codigo, bonus in {**PUBLICADOS_ATE_A_1_3_1, **PUBLICADOS_NA_1_4_0}.items():
        assert BONUS_DAS_CONQUISTAS.get(codigo) == bonus, (
            f"{codigo}: o app em campo soma {bonus}, e o servidor creditaria "
            f"{BONUS_DAS_CONQUISTAS.get(codigo)}"
        )


def test_controle_os_congelados_cobrem_a_tabela_de_hoje():
    """CONTROLE: os dois grupos congelados têm 69 + 22 = as 91 da tabela. Se
    uma conquista nova entrar na tabela, este caso lembra de congelá-la quando
    ela for publicada."""
    assert len(PUBLICADOS_ATE_A_1_3_1) == 69
    assert len(PUBLICADOS_NA_1_4_0) == 22
    assert set(PUBLICADOS_ATE_A_1_3_1) | set(PUBLICADOS_NA_1_4_0) == set(
        BONUS_DAS_CONQUISTAS
    )

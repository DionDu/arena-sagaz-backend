"""O MEU DIA - `GET /v1/desafios/{id}/meu-dia` (T085za, `contracts/meu-dia.md`).

O que estes casos protegem:
  · a rota **exige conta** - o dia e pessoal, e o convidado ⛔ tem servidor;
  · a tentativa que **so uma dica criou** ⛔ conta (a partida largada ⛔ entra no
    `1/n`, §8q) - senao o aparelho novo acharia uma tentativa a mais;
  · o "na N-a tentativa" e o `n` que o APLICATIVO mandou (a parcela
    `tentativas`), e ⛔ o `nu_sequencia`, que a linha da dica largada desloca;
  · o retrato vem como veio, e `null` (resolucao anterior a `0027`) passa como
    `null` - a tela cai em "Objetivo cumprido".
"""

from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

import pytest

from api.desafios.meu_dia import (
    SQL_DIA_DO_DESAFIO,
    SQL_RESOLUCAO_DO_DIA,
    SQL_TENTATIVAS_FECHADAS,
    ServicoMeuDia,
)
from api.desafios.modelos_resposta import MeuDia
from api.nucleo.excecoes import ErroNaoEncontrado

EU = "uid-eu"
ID_DESAFIO = uuid4()
ID_DIA = uuid4()

RETRATO = {"medidas": {"caixas_fechadas": 4}, "janela_gasta": 2}


class RepoFalso:
    """Um `RepositorioMeuDia` de mentira - ele anota com quem falou."""

    def __init__(self, *, dia=ID_DIA, tentativas=0, dicas=0, resolucao=None):
        self._dia = dia
        self._tentativas = tentativas
        self._dicas = dicas
        self._resolucao = resolucao
        self.perguntas: list[tuple[str, object]] = []

    async def dia_do_desafio(self, *, id_desafio):
        self.perguntas.append(("dia", id_desafio))
        return self._dia

    async def tentativas_fechadas(self, *, id_desafio_dia, id_usuario):
        self.perguntas.append(("tentativas", (id_desafio_dia, id_usuario)))
        return self._tentativas

    async def dicas(self, *, id_desafio_dia, id_usuario):
        self.perguntas.append(("dicas", (id_desafio_dia, id_usuario)))
        return self._dicas

    async def resolucao(self, *, id_desafio_dia, id_usuario):
        self.perguntas.append(("resolucao", (id_desafio_dia, id_usuario)))
        return self._resolucao


def resolucao(**trocas) -> dict:
    """Uma linha de `SQL_RESOLUCAO_DO_DIA`, como o banco a devolve."""
    base = {
        "nu_xp": 26,
        "nu_tempo_ms": 48210,
        "js_feito": RETRATO,
        "nu_sequencia": 4,
        # ⚠️ `Decimal`: `vr_medida` e `NUMERIC(12,3)`.
        "vr_tentativas": Decimal("3.000"),
    }
    base.update(trocas)
    return base


@pytest.mark.asyncio
async def test_quem_nao_jogou_recebe_o_dia_VAZIO() -> None:
    corpo = await ServicoMeuDia(RepoFalso()).montar(id_desafio=ID_DESAFIO, id_usuario=EU)
    assert corpo == {
        "id_desafio_dia": ID_DIA,
        "tentativas": 0,
        "dicas": 0,
        "resolveu": False,
        "primeira": None,
    }
    # E a forma bate com o contrato.
    MeuDia(**corpo)


@pytest.mark.asyncio
async def test_a_pergunta_e_sobre_QUEM_pergunta() -> None:
    """⛔ O dia de outra pessoa ⛔ vaza: toda consulta leva o `id_usuario`."""
    repo = RepoFalso()
    await ServicoMeuDia(repo).montar(id_desafio=ID_DESAFIO, id_usuario=EU)
    assert {p for p, _ in repo.perguntas} == {"dia", "tentativas", "dicas", "resolucao"}
    for pergunta, argumentos in repo.perguntas:
        if pergunta != "dia":
            assert argumentos == (ID_DIA, EU)


@pytest.mark.asyncio
async def test_quem_resolveu_recebe_o_retrato_e_o_N_QUE_O_APP_MANDOU() -> None:
    """O `nu_sequencia` e 4 (uma dica largada ocupou um numero), e a nota foi
    calculada com 3: a tela diz "na 3a tentativa"."""
    repo = RepoFalso(tentativas=3, dicas=1, resolucao=resolucao())
    corpo = await ServicoMeuDia(repo).montar(id_desafio=ID_DESAFIO, id_usuario=EU)

    assert corpo["resolveu"] is True
    assert corpo["tentativas"] == 3
    assert corpo["dicas"] == 1
    assert corpo["primeira"] == {
        "na_tentativa": 3,
        "pontuacao": 26,
        "tempo_ms": 48210,
        "feito": RETRATO,
    }
    modelo = MeuDia(**corpo)
    assert modelo.primeira is not None
    assert modelo.primeira.feito is not None
    assert modelo.primeira.feito.janela_gasta == 2


@pytest.mark.asyncio
async def test_sem_a_parcela_de_tentativas_vale_a_sequencia() -> None:
    """A reserva: ⛔ deve acontecer, mas um `null` apagaria o "na N-a"."""
    repo = RepoFalso(resolucao=resolucao(vr_tentativas=None))
    corpo = await ServicoMeuDia(repo).montar(id_desafio=ID_DESAFIO, id_usuario=EU)
    assert corpo["primeira"]["na_tentativa"] == 4


@pytest.mark.asyncio
async def test_a_resolucao_anterior_ao_retrato_vem_SEM_feito() -> None:
    repo = RepoFalso(resolucao=resolucao(js_feito=None))
    corpo = await ServicoMeuDia(repo).montar(id_desafio=ID_DESAFIO, id_usuario=EU)
    assert corpo["primeira"]["feito"] is None
    MeuDia(**corpo)


@pytest.mark.asyncio
async def test_o_retrato_em_TEXTO_vira_objeto() -> None:
    repo = RepoFalso(resolucao=resolucao(js_feito='{"medidas": {"caixas_fechadas": 4}, "janela_gasta": 2}'))
    corpo = await ServicoMeuDia(repo).montar(id_desafio=ID_DESAFIO, id_usuario=EU)
    assert corpo["primeira"]["feito"] == RETRATO


@pytest.mark.asyncio
async def test_desafio_nao_publicado_e_404() -> None:
    with pytest.raises(ErroNaoEncontrado):
        await ServicoMeuDia(RepoFalso(dia=None)).montar(
            id_desafio=ID_DESAFIO, id_usuario=EU
        )


def test_a_linha_que_SO_A_DICA_criou_nao_conta() -> None:
    """🔒 As tres marcas juntas: ⛔ resolvida, tempo zero, com dica pendurada.

    ⚠️ Texto do SQL, e ⛔ banco: e o cadeado mais barato contra alguem
    "simplificar" a contagem para `COUNT(*)` - que passaria em todo caso com
    repositorio falso.
    """
    sql = " ".join(SQL_TENTATIVAS_FECHADAS.split())
    assert "NOT t.ic_resolveu" in sql
    assert "t.nu_tempo_ms = 0" in sql
    assert "EXISTS (SELECT 1 FROM desafio_dia.vw005_poder_consumido p" in sql
    assert "AND NOT (" in sql


def test_o_N_sai_da_parcela_de_TENTATIVAS() -> None:
    assert "x.co_tipo_xp = 'tentativas'" in SQL_RESOLUCAO_DO_DIA


@pytest.mark.parametrize(
    "sql", [SQL_DIA_DO_DESAFIO, SQL_TENTATIVAS_FECHADAS, SQL_RESOLUCAO_DO_DIA]
)
def test_a_LEITURA_vai_a_VIEW(sql: str) -> None:
    """🔒 Convencao do projeto desde a `0001`: le-se pela VIEW."""
    alvos = re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+\.[a-z0-9_]+)", sql, re.I)
    assert alvos
    assert not [a for a in alvos if ".tb" in a], alvos


def test_a_rota_EXIGE_CONTA() -> None:
    """⚠️ `usuario_autenticado`, e ⛔ `usuario_opcional`: sem conta ⛔ ha dia no
    servidor, e responder um dia vazio a um convidado diria "voce ⛔ jogou" a
    quem jogou - so ⛔ subiu ainda."""
    from api.desafios.rotas import router
    from api.nucleo.dependencias_conta_nuvem import usuario_autenticado

    rota = next(r for r in router.routes if r.path == "/{id_desafio}/meu-dia")
    dependencias = [d.call for d in rota.dependant.dependencies]
    assert usuario_autenticado in dependencias

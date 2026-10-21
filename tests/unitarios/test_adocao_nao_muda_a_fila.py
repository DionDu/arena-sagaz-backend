"""🔒 O jogo novo só TOMA dias; a fila do Pontinhos e das damas não muda (T120, F-7).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

A T120 mexe em código de PRODUÇÃO: `gerador.escolher_jogo` decide o jogo de
todo dia do Desafio do Dia, e o backend publica a cada push. A promessa da
R-23 (item 4) é que a adoção decide **só os dias do jogo novo**: nos outros, a
resposta é exatamente a de antes, e o rodízio de tipos (`dias // 2`) não muda de
fase. Se mudasse, a variedade de tipos de que o dono reclamou em 10/09/2026
voltaria por outro caminho, e nada daria erro.

Por isso as duas funções de ANTES estão **copiadas aqui**, com a tupla e o
divisor escritos por extenso, e não importadas: um teste que compara o gerador
com ele mesmo passa com qualquer mudança.

O que se trava:

  1. com o jogo novo fora do ar (nenhum aparelho na versão) ou sem adoção
     nenhuma, **365 dias seguidos** dão o mesmo jogo e o mesmo tipo de antes -
     inclusive com vizinhos;
  2. com o jogo novo no ar, todo dia que **não** é dele sai igual ao de antes,
     e o tipo de cada jogo antigo nos dias dele também;
  3. a vizinhança vale para o jogo novo, e um jogo do rodízio não entra pela
     adoção;
  4. a idempotência: a mesma data e a mesma faixa dão o mesmo jogo;
  5. a ligação no job: a amostra é lida UMA vez por execução, vai ao log, e a
     MESMA faixa chega às duas escolhas do jogo (a de `cobrir_um_dia` e a de
     `gerar_candidatos`).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

import pytest

from job import __main__ as principal_mod
from job import gerador as gerador_mod
from job.adocao import NAO_APARECE, Frequencia
from job.editorial import EDITORIAL
from job.gerador import EPOCA_DO_RODIZIO, escolher_jogo, escolher_tipo, tipos_do_jogo
from job.repositorio import SQL_AVISTAMENTOS_DA_ADOCAO, RepositorioDoJob
from job.vizinhanca import preferir
from tests.unitarios.fakes_desafio import FakeSessaoSQL
from tests.unitarios.test_principal_do_job import _rodar, _sessao_feliz

#: O 1º dia do ano de referência: o dia seguinte ao da T120.
INICIO = date(2026, 10, 22)

#: Um ano de dias seguidos.
UM_ANO = [INICIO + timedelta(days=n) for n in range(365)]

#: Os vizinhos que a fila pode ter, para o desvio também ser comparado.
VIZINHOS_POSSIVEIS = [(), ("pontinhos",), ("damas",), ("pontinhos", "damas")]


# ═══════════════════════════════════════════════════════════════════════════
# As funções de ANTES da T120, copiadas (21/10/2026, backend `cea8a5f39`)
# ═══════════════════════════════════════════════════════════════════════════


def _escolher_jogo_de_antes(dt_dia: date, *, evitar: tuple[str, ...] = ()) -> str:
    """`gerador.escolher_jogo` como era: o rodízio dos dois jogos pela data."""
    dias = (dt_dia - date(2026, 1, 1)).days
    return preferir(("pontinhos", "damas"), indice_do_rodizio=dias, evitar=evitar)


def _escolher_tipo_de_antes(co_jogo: str, dt_dia: date) -> str:
    """`gerador.escolher_tipo` como era, sem `tipos_recentes` (que não muda a conta).

    ⚠️ O divisor `2` é o `len(JOGOS_DO_RODIZIO)` de antes, escrito por extenso:
    se alguém pusesse o jogo novo naquela tupla, este caso acusaria.
    """
    disponiveis = tipos_do_jogo(co_jogo)
    dias = (dt_dia - date(2026, 1, 1)).days
    return disponiveis[(dias // 2) % len(disponiveis)]


def test_a_epoca_do_rodizio_e_a_da_copia():
    assert EPOCA_DO_RODIZIO == date(2026, 1, 1)


def test_o_rodizio_ainda_e_dos_dois_jogos():
    """⛔ O jogo novo nunca entra nesta tupla (a fase dos tipos dela depende)."""
    assert gerador_mod.JOGOS_DO_RODIZIO == ("pontinhos", "damas")
    assert "quatro" in gerador_mod.JOGOS_EM_ADOCAO
    assert not set(gerador_mod.JOGOS_EM_ADOCAO) & set(gerador_mod.JOGOS_DO_RODIZIO)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Fora do ar: a fila de um ano é a de antes
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("frequencias", [None, {}, {"quatro": NAO_APARECE}])
@pytest.mark.parametrize("evitar", VIZINHOS_POSSIVEIS)
def test_com_adocao_zero_365_dias_dao_a_mesma_fila(frequencias, evitar):
    for dia in UM_ANO:
        jogo = escolher_jogo(dia, evitar=evitar, frequencias=frequencias)
        assert jogo == _escolher_jogo_de_antes(dia, evitar=evitar), dia
        assert escolher_tipo(jogo, dia) == _escolher_tipo_de_antes(jogo, dia), dia


# ═══════════════════════════════════════════════════════════════════════════
# 2. No ar: o jogo novo toma dias, e só isso
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("n", [6, 4, 3])
@pytest.mark.parametrize("evitar", VIZINHOS_POSSIVEIS)
def test_com_o_jogo_novo_no_ar_o_resto_da_fila_e_o_de_antes(n, evitar):
    frequencias = {"quatro": Frequencia(um_dia_em=n)}
    tomados = 0
    for dia in UM_ANO:
        jogo = escolher_jogo(dia, evitar=evitar, frequencias=frequencias)
        if jogo == "quatro":
            tomados += 1
            continue
        assert jogo == _escolher_jogo_de_antes(dia, evitar=evitar), dia
        # E o tipo do jogo antigo, no dia dele, também é o de antes.
        assert escolher_tipo(jogo, dia) == _escolher_tipo_de_antes(jogo, dia), dia
    # O jogo novo tomou a parte dele do ano (com folga de quatro dias).
    assert abs(tomados - 365 / n) <= 4


def test_o_jogo_novo_toma_dias_dos_dois_jogos_antigos():
    """⚠️ Se tomasse só dos dias pares, o Pontinhos pagaria o jogo novo sozinho."""
    frequencias = {"quatro": Frequencia(um_dia_em=6)}
    perdidos = {"pontinhos": 0, "damas": 0}
    for dia in UM_ANO:
        if escolher_jogo(dia, frequencias=frequencias) == "quatro":
            perdidos[_escolher_jogo_de_antes(dia)] += 1
    assert perdidos["pontinhos"] > 0 and perdidos["damas"] > 0
    assert abs(perdidos["pontinhos"] - perdidos["damas"]) <= 6


# ═══════════════════════════════════════════════════════════════════════════
# 3. Vizinhança e recusa
# ═══════════════════════════════════════════════════════════════════════════


def _um_dia_do_quatro(frequencias: dict[str, Frequencia]) -> date:
    return next(d for d in UM_ANO if escolher_jogo(d, frequencias=frequencias) == "quatro")


def test_o_jogo_novo_desvia_do_vizinho_que_ja_e_dele():
    frequencias = {"quatro": Frequencia(um_dia_em=3)}
    dia = _um_dia_do_quatro(frequencias)
    assert escolher_jogo(dia, evitar=("quatro",), frequencias=frequencias) == (
        _escolher_jogo_de_antes(dia, evitar=("quatro",))
    )


@pytest.mark.parametrize("co_jogo", ["pontinhos", "damas"])
def test_jogo_do_rodizio_nao_entra_pela_adocao(co_jogo):
    with pytest.raises(ValueError):
        escolher_jogo(INICIO, frequencias={co_jogo: Frequencia(um_dia_em=6)})


# ═══════════════════════════════════════════════════════════════════════════
# 4. Idempotência
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("n", [6, 4, 3])
def test_duas_execucoes_no_mesmo_dia_escolhem_o_mesmo_jogo(n):
    for dia in UM_ANO:
        assert escolher_jogo(dia, frequencias={"quatro": Frequencia(um_dia_em=n)}) == (
            escolher_jogo(dia, frequencias={"quatro": Frequencia(um_dia_em=n)})
        )


# ═══════════════════════════════════════════════════════════════════════════
# 5. A ligação no job
# ═══════════════════════════════════════════════════════════════════════════


def test_a_versao_minima_do_quatro_vem_do_editorial():
    assert gerador_mod.versao_minima_do_jogo("quatro") == "1.4.0"
    # E é a menor das publicações no ar do jogo (hoje, todas pedem a 1.4.0).
    versoes = {
        publicacao.co_versao_minima
        for co_tipo in tipos_do_jogo("quatro")
        for publicacao in EDITORIAL[co_tipo]
    }
    assert versoes == {"1.4.0"}


def test_jogo_sem_publicacao_no_ar_nao_tem_versao_minima():
    with pytest.raises(ValueError):
        gerador_mod.versao_minima_do_jogo("velha")


def test_a_amostra_nao_filtra_as_linhas_legadas():
    """⛔ Sem o app 1.3 na amostra, a adoção leria 100% no dia do lançamento."""
    assert "ic_legado" not in SQL_AVISTAMENTOS_DA_ADOCAO
    assert "log.vw004_aparelho_dia" in SQL_AVISTAMENTOS_DA_ADOCAO
    assert "BETWEEN :dt_inicio AND :dt_fim" in SQL_AVISTAMENTOS_DA_ADOCAO


def _linhas_de_aparelho(adotaram: int, total: int) -> list[dict[str, Any]]:
    """`total` aparelhos na amostra, `adotaram` deles na 1.4.0."""
    return [
        {
            "id_aparelho": uuid.UUID(int=i + 1),
            "co_versao_app": "1.4.0+17" if i < adotaram else "1.3.1",
        }
        for i in range(total)
    ]


@pytest.mark.asyncio
async def test_ler_frequencias_le_a_janela_e_escreve_no_log(capsys):
    sessao = FakeSessaoSQL(
        respostas={"log.vw004_aparelho_dia": _linhas_de_aparelho(2, 5)}
    )
    relatorio = principal_mod.Relatorio()

    frequencias = await principal_mod.ler_frequencias(
        RepositorioDoJob(sessao), dt_hoje=date(2026, 10, 21), relatorio=relatorio
    )

    assert frequencias == {"quatro": Frequencia(um_dia_em=4)}
    leituras = [p for sql, p in sessao.executadas if "log.vw004_aparelho_dia" in sql]
    assert leituras == [{"dt_inicio": date(2026, 10, 14), "dt_fim": date(2026, 10, 20)}]
    # O número com o denominador e a consequência na fila.
    assert relatorio.adocao == [
        "quatro (>= 1.4.0): 2 de 5 aparelhos (40.0%) entre 2026-10-14 e "
        "2026-10-20 -> 1 dia em 4"
    ]
    assert "[job] adocao de quatro (>= 1.4.0): 2 de 5" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_amostra_vazia_tira_o_jogo_novo_do_ar():
    relatorio = principal_mod.Relatorio()
    frequencias = await principal_mod.ler_frequencias(
        RepositorioDoJob(FakeSessaoSQL()), dt_hoje=date(2026, 10, 21), relatorio=relatorio
    )
    assert frequencias == {"quatro": NAO_APARECE}
    assert relatorio.adocao[0].endswith("0 de 0 aparelhos (0.0%) entre 2026-10-14 e 2026-10-20 -> não aparece")


@pytest.mark.asyncio
async def test_a_execucao_le_a_adocao_uma_vez_e_entrega_a_mesma_a_todo_dia(monkeypatch):
    sessao = _sessao_feliz()
    sessao.respostas["log.vw004_aparelho_dia"] = _linhas_de_aparelho(4, 5)
    recebidas: list[Any] = []

    async def cobrir_espiao(*_a: Any, **kwargs: Any) -> None:
        recebidas.append(kwargs["frequencias"])
        return None

    monkeypatch.setattr(principal_mod, "cobrir_um_dia", cobrir_espiao)
    relatorio = await _rodar(sessao)

    leituras = [sql for sql, _ in sessao.executadas if "log.vw004_aparelho_dia" in sql]
    assert len(leituras) == 1
    assert len(recebidas) >= 2  # o plano tem vários dias
    esperado = {"quatro": Frequencia(um_dia_em=3, rodizio_pleno=True)}
    assert all(f == esperado for f in recebidas)
    # O MESMO objeto, e não uma releitura por dia.
    assert all(f is recebidas[0] for f in recebidas)
    assert "[job] adocao: quatro (>= 1.4.0): 4 de 5 aparelhos" in relatorio.resumo()


@pytest.mark.asyncio
async def test_cobrir_um_dia_entrega_a_mesma_adocao_as_duas_escolhas(monkeypatch):
    """⛔ Se só um lado recebesse a faixa, o tipo do Quatro iria a uma posição de outro jogo."""
    frequencias = {"quatro": Frequencia(um_dia_em=3)}
    dia = _um_dia_do_quatro(frequencias)
    vistos: list[dict[str, Any]] = []

    def gerar_espiao(dt_dia: date, **kwargs: Any) -> list[Any]:
        vistos.append(kwargs)
        return []  # sem candidato: o dia cai na reprise, que aqui não importa

    sessao = FakeSessaoSQL()
    await principal_mod.cobrir_um_dia(
        sessao,
        RepositorioDoJob(sessao),
        dt_dia=dia,
        relatorio=principal_mod.Relatorio(),
        gerar=gerar_espiao,
        frequencias=frequencias,
    )

    assert len(vistos) == 1
    assert vistos[0]["frequencias"] is frequencias
    # E o jogo escolhido por fora já foi o Quatro: é com ele que o rodízio de
    # tipos é consultado.
    jogos_consultados = [
        p["co_jogo"] for sql, p in sessao.executadas if p and "d.co_jogo = :co_jogo" in sql
    ]
    assert jogos_consultados == ["quatro"]


def test_o_gerador_escolhe_o_jogo_com_a_adocao_que_recebe(monkeypatch):
    """O outro lado: `gerar_candidatos` passa a faixa ao `escolher_jogo` de dentro."""
    frequencias = {"quatro": Frequencia(um_dia_em=3)}
    dia = _um_dia_do_quatro(frequencias)
    escolhidos: list[str] = []

    def receita_espia(co_tipo: str):
        escolhidos.append(co_tipo)
        raise gerador_mod.SemCandidato("parar aqui")

    monkeypatch.setattr(gerador_mod, "receita_de", receita_espia)
    with pytest.raises(gerador_mod.SemCandidato):
        gerador_mod.gerar_candidatos(dia, parametros={}, frequencias=frequencias)
    assert escolhidos == ["quatro_virada"]


def test_dois_jogos_novos_ao_mesmo_tempo_dividem_os_dias():
    """Genérico: um 2º jogo em adoção começa a janela noutro ponto da volta.

    ⚠️ Sem o deslocamento os dois teriam as MESMAS janelas, e o 1º da ordem
    ficaria com todos os dias - o 2º nunca sairia, sem erro nenhum.
    """
    frequencias = {"quatro": Frequencia(um_dia_em=6), "outro": Frequencia(um_dia_em=6)}
    jogos = [escolher_jogo(dia, frequencias=frequencias) for dia in UM_ANO]
    assert abs(jogos.count("quatro") - 365 / 6) <= 4
    assert abs(jogos.count("outro") - 365 / 6) <= 4


def test_a_versao_minima_e_a_menor_por_numero(monkeypatch):
    """`1.9.0` vem antes de `1.10.0` - o texto diria o contrário."""

    class _Publicacao:
        def __init__(self, versao: str) -> None:
            self.co_versao_minima = versao

    monkeypatch.setattr(gerador_mod, "tipos_do_jogo", lambda _j: ["t1", "t2"])
    monkeypatch.setattr(
        gerador_mod.editorial_mod,
        "EDITORIAL",
        {"t1": (_Publicacao("1.10.0"),), "t2": (_Publicacao("1.9.0"), _Publicacao("1.12.0"))},
    )
    assert gerador_mod.versao_minima_do_jogo("qualquer") == "1.9.0"

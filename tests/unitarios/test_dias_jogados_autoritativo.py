"""O servidor passa a devolver `nu_dias_jogados` — o total de dias DIFERENTES
jogados, recalculado do histórico.

Motivo (relato de 12/08/2026): uma usuária com 21 dias de chama nunca recebia a
conquista "10 Dias na Arena". O contador equivalente do app
(`diasJogadosTotal`) vive só no aparelho, dentro de `js_estado_local`, e some
quando o rascunho local é sobrescrito — enquanto a chama, que o servidor
recalcula do log, volta sempre certa. Daí a assimetria.

A correção é dar ao total de dias o mesmo tratamento da chama: derivá-lo do
histórico, para que qualquer aparelho o reconstrua. `recalcular_chama` já tem a
lista de dias distintos em mãos; o total é `len(dias)`, de graça.

Estes testes usam uma sessão FALSA: `recalcular_chama` só precisa que o
`execute` do SELECT devolva as datas e que o `execute` do UPDATE seja aceito.
Assim o comportamento é testado sem Postgres.
"""

from datetime import date
from typing import Any

import pytest

from api.sincronizacao.repositorio import RepositorioSincronizacao


class _ResultadoFalso:
    """Imita o retorno de `sessao.execute` para o SELECT dos dias."""

    def __init__(self, linhas: list[tuple[Any, ...]]) -> None:
        self._linhas = linhas

    def all(self) -> list[tuple[Any, ...]]:
        return self._linhas


class _SessaoFalsa:
    """Sessão mínima: devolve os dias no 1º `execute` (SELECT) e aceita o 2º
    (UPDATE), guardando os parâmetros para inspeção."""

    def __init__(self, dias: list[date]) -> None:
        self._dias = dias
        self.executados: list[dict[str, Any]] = []
        self._primeira_chamada = True

    async def execute(self, _sql: Any, params: dict[str, Any] | None = None):
        if self._primeira_chamada:
            self._primeira_chamada = False
            return _ResultadoFalso([(d,) for d in self._dias])
        # É o UPDATE que persiste sequência e data.
        self.executados.append(params or {})
        return _ResultadoFalso([])


@pytest.mark.asyncio
async def test_sem_partidas_devolve_zero_dias():
    """Quem nunca jogou tem 0 dias — e a linha NÃO é tocada (o UPDATE nem roda),
    para não zerar sequência vinda de merge de convidado ainda não sincronizado."""
    sessao = _SessaoFalsa([])
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    seq, ultimo, total_dias = await repo.recalcular_chama("id-qualquer")

    assert (seq, ultimo, total_dias) == (0, None, 0)
    assert sessao.executados == [], "não pode escrever quando não há histórico"


@pytest.mark.asyncio
async def test_dias_consecutivos_o_total_bate_com_a_chama():
    """Sem buracos, total de dias e chama coincidem — é o caso da usuária do
    relato: 21 dias seguidos, chama 21, e portanto 21 dias jogados."""
    # 23/07 a 12/08 de 2026, sem falhar um dia (o histórico real dela).
    dias = [date(2026, 7, 23)]
    d = date(2026, 7, 23)
    for _ in range(20):
        d = date.fromordinal(d.toordinal() + 1)
        dias.append(d)
    assert len(dias) == 21

    sessao = _SessaoFalsa(dias)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    seq, ultimo, total_dias = await repo.recalcular_chama("id-dela")

    assert total_dias == 21, "21 dias distintos jogados"
    assert seq == 21, "sem buracos, a chama iguala o total"
    assert ultimo == date(2026, 8, 12)
    # E o total de dias, ao contrário de sequência e data, NÃO é persistido.
    assert set(sessao.executados[0]) == {"id", "seq", "dia"}


@pytest.mark.asyncio
async def test_com_buracos_o_total_supera_a_chama():
    """O total conta DEDICAÇÃO (dias diferentes), a chama conta CONSTÂNCIA. Com
    buracos os dois divergem — e é por isso que um não pode ser derivado do
    outro no app."""
    dias = [
        date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3),  # 3 seguidos
        date(2026, 7, 20),                                     # sumiu 16 dias
        date(2026, 7, 21),
    ]
    sessao = _SessaoFalsa(dias)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    seq, ultimo, total_dias = await repo.recalcular_chama("id-qualquer")

    assert total_dias == 5, "cinco dias diferentes jogados"
    assert seq < total_dias, "a chama decaiu no buraco; o total não"
    assert ultimo == date(2026, 7, 21)

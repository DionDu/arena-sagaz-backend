"""T124c (spec 010) - a amostra do `scripts/medir_fases_das_posicoes_quatro.py`.

A tabela desse script decidiu o preparo do *"Vença em N"* e o orçamento de
tentativas do Quatro (histórico do backend, "2026-10-21 (7)"). A parte que pode
errar calada é a AMOSTRA: o LADO de cada posição sai da paridade dos lances
jogados e da cor do Magno naquela partida, e uma inversão trocaria as duas
linhas da tabela sem erro nenhum - o resumo diria "o lado do Tex é o bom".

Estes casos não abrem o motor: a busca já tem o controle dentro do script (um
lance antes do fim, quem venceu vence em 1).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

# `parents[2]` sobe de `tests/unitarios/este_arquivo.py` para a raiz do backend,
# onde mora a pasta `scripts/` (que não é pacote instalado).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from job.posicoes_de_autoplay_quatro import PartidaDeAutoplay  # noqa: E402
from scripts.medir_fases_das_posicoes_quatro import Contagem, amostrar  # noqa: E402


def _partida(lances: str, magno: int, vencedor: int = 1) -> PartidaDeAutoplay:
    """Uma partida de mentira; os lances são texto `s4s5...` cortado de 2 em 2."""
    return PartidaDeAutoplay(
        lances=tuple(lances[i : i + 2] for i in range(0, len(lances), 2)),
        magno=magno,
        vencedor=vencedor,
    )


def _lados(partidas, comprimento: int) -> dict[tuple[str, ...], str]:
    """A amostra inteira (sem corte), como dicionário posição -> lado."""
    return dict(amostrar(tuple(partidas), comprimento, 999, random.Random(0)))


def test_com_lances_PARES_a_vez_e_de_quem_abre() -> None:
    """Com 2 lances jogados a vez é do jogador 1 (`+1`): se o Magno abriu, a
    posição é do lado do Magno; se abriu o Tex, do lado do Tex."""
    magno_abre = _partida("s4s4s3s3", magno=1)
    tex_abre = _partida("s1s1s2s2", magno=-1)
    lados = _lados([magno_abre, tex_abre], 2)
    assert lados[("s4", "s4")] == "magno"
    assert lados[("s1", "s1")] == "tex"


def test_com_lances_IMPARES_a_vez_e_do_outro() -> None:
    """Com 3 lances jogados a vez é do jogador 2 (`-1`): as mesmas partidas do
    caso acima trocam de lado. É o par deste caso com o de cima que pega a
    paridade invertida - um só passaria com a conta errada nos dois sentidos."""
    magno_abre = _partida("s4s4s3s3", magno=1)
    tex_abre = _partida("s1s1s2s2", magno=-1)
    lados = _lados([magno_abre, tex_abre], 3)
    assert lados[("s4", "s4", "s3")] == "tex"
    assert lados[("s1", "s1", "s2")] == "magno"


def test_a_mesma_posicao_em_duas_partidas_conta_UMA_vez() -> None:
    """Aberturas repetidas: o prefixo comum entra uma vez só na amostra."""
    a = _partida("s4s4s3s3", magno=1)
    b = _partida("s4s4s5s5", magno=1)
    amostra = amostrar((a, b), 2, 999, random.Random(0))
    assert [lances for lances, _ in amostra] == [("s4", "s4")]


def test_a_partida_que_ACABA_no_comprimento_nao_entra() -> None:
    """A posição precisa de um lance a jogar: a partida inteira não é posição."""
    curta = _partida("s4s4s3", magno=1)
    assert amostrar((curta,), 3, 999, random.Random(0)) == []
    assert len(amostrar((curta,), 2, 999, random.Random(0))) == 1


def test_a_amostra_respeita_o_TAMANHO_e_a_SEMENTE() -> None:
    """O corte é o pedido, e a mesma semente dá a mesma amostra (a tabela se
    refaz igual)."""
    partidas = tuple(
        _partida(f"s{c1}s{c2}s4s4", magno=1) for c1 in range(1, 8) for c2 in range(1, 8)
    )
    primeira = amostrar(partidas, 2, 5, random.Random(7))
    assert len(primeira) == 5
    assert primeira == amostrar(partidas, 2, 5, random.Random(7))


def test_somar_junta_TODOS_os_campos() -> None:
    """O resumo por lado soma as threads: um campo esquecido zera uma coluna."""
    a = Contagem(total=3, de_cara=1, vence=1, empata=1, perde=0, aberto=0, segure=1)
    a.distancias[9] = 1
    b = Contagem(total=2, de_cara=0, vence=1, empata=0, perde=1, aberto=2, segure=0)
    b.distancias[9] = 1
    b.distancias[11] = 1
    a.somar(b)
    assert (a.total, a.de_cara, a.vence, a.empata, a.perde, a.aberto, a.segure) == (
        5, 1, 2, 1, 1, 2, 1,
    )
    assert a.distancias == {9: 2, 11: 1}

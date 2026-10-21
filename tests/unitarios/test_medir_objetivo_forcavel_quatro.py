"""T124c (spec 010) - as partes do `scripts/medir_objetivo_forcavel_quatro.py`
que podem errar caladas.

A prova forçável tem os casos dela em `test_provas_quatro.py`. Aqui fica o que
é do SCRIPT, e que nenhuma execução denunciaria:

  * **os casos de controle**: se o medidor de produção fosse lido do lado
    errado (as linhas do perdedor, a fita inteira em vez do último lance), o
    controle conferiria posições que não são do tipo - e passaria, ou pararia
    o script, pelo motivo errado;
  * **o grupo `forcavel` da fase 2**: sai do diário da fase 1. Uma posição que
    reprovou entrando no grupo, ou a ordem mudando entre execuções, mudaria a
    amostra sem erro nenhum;
  * **a identidade de cada unidade no diário**: é ela que faz a medição
    retomar. Uma identidade pelo índice no grupo `forcavel` pularia uma posição
    nova achando que já a mediu;
  * **a taxa do resumo**: é sobre TODAS as posições medidas, que é o que o
    gerador sorteia, e não só sobre as que vencem.

Nenhum caso abre o motor.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `parents[2]` sobe de `tests/unitarios/este_arquivo.py` para a raiz do backend,
# onde mora a pasta `scripts/` (que não é pacote instalado).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from job.posicoes_de_autoplay_quatro import PartidaDeAutoplay  # noqa: E402
from motores.quatro.motor_quatro import ler_sequencia  # noqa: E402
from scripts import medir_objetivo_forcavel_quatro as script  # noqa: E402


def _partida(lances: str, vencedor: int) -> PartidaDeAutoplay:
    """Uma partida de mentira, terminada no último lance de [lances]."""
    return PartidaDeAutoplay(lances=ler_sequencia(lances), magno=1, vencedor=vencedor)


# ── Os casos de controle ────────────────────────────────────────────────────

#: As posições montadas à mão do script, terminadas pelo lance que vence.
GOLPE = script.CONTROLE_MANUAL_PASSA["quatro_golpe_duplo"] + "s4"
CINCO = script.CONTROLE_MANUAL_PASSA["quatro_linha_de_cinco"] + "s3"
SO_QUATRO = script.CONTROLE_MANUAL_REPROVA + "s4"


def test_o_controle_separa_o_golpe_duplo_da_linha_de_cinco() -> None:
    casos = script.casos_de_controle(
        [_partida(GOLPE, 1), _partida(CINCO, 1), _partida(SO_QUATRO, 1)]
    )
    # A posição de controle é UM lance antes do fim.
    assert casos["quatro_golpe_duplo"] == [GOLPE[:-2]]
    assert casos["quatro_linha_de_cinco"] == [CINCO[:-2]]


def test_o_controle_ignora_o_empate_e_nao_repete_a_posicao() -> None:
    """Empate não tem jeito de vencer; a mesma posição em duas partidas é UM caso."""
    casos = script.casos_de_controle(
        [_partida(CINCO, 1), _partida(CINCO, 1), _partida(GOLPE, 0)]
    )
    assert casos == {"quatro_golpe_duplo": [], "quatro_linha_de_cinco": [CINCO[:-2]]}


def test_o_controle_para_no_teto_de_casos(monkeypatch) -> None:
    monkeypatch.setattr(script, "CASOS_DE_CONTROLE", 1)
    # Duas posições diferentes com cinco em linha: a 2ª tem um lance a mais do
    # jogador 2 na coluna 7 antes (o desenho na linha 1 é o mesmo).
    outra = "s1s7s2s7s4s6s5s6s7s7s3"
    casos = script.casos_de_controle([_partida(CINCO, 1), _partida(outra, 1)])
    assert len(casos["quatro_linha_de_cinco"]) == 1


# ── O grupo `forcavel` e a identidade no diário ─────────────────────────────


def _fase_1(comprimento: int, lances: str, **por_tipo: bool) -> dict:
    """Uma linha da fase 1, com `passou` por tipo (só os tipos passados)."""
    linha = {"fase": 1, "comprimento": comprimento, "lances": lances, "livre": "vence"}
    for co_tipo, passou in por_tipo.items():
        linha[co_tipo] = {"passou": passou, "lances": 1, "estourou": False, "perguntas": 1}
    return linha


def test_o_grupo_forcavel_so_tem_quem_PASSOU_naquele_tipo_e_em_ordem_estavel() -> None:
    linhas = [
        _fase_1(22, "b", quatro_golpe_duplo=True, quatro_linha_de_cinco=False),
        _fase_1(18, "z", quatro_golpe_duplo=True, quatro_linha_de_cinco=True),
        _fase_1(22, "a", quatro_golpe_duplo=False, quatro_linha_de_cinco=True),
        _fase_1(18, "y"),  # não venceu: as provas nem rodaram
        {"fase": 2, "co_tipo": "quatro_golpe_duplo", "lances": "w"},
    ]
    # Pelo comprimento, depois pelos lances.
    assert script.forcaveis_do_diario(linhas, "quatro_golpe_duplo", 9) == ["z", "b"]
    assert script.forcaveis_do_diario(linhas, "quatro_linha_de_cinco", 9) == ["z", "a"]
    assert script.forcaveis_do_diario(linhas, "quatro_golpe_duplo", 1) == ["z"]


def test_a_identidade_no_forcavel_e_a_POSICAO_e_no_alcance_o_indice() -> None:
    base = {"fase": 2, "co_tipo": "quatro_golpe_duplo", "adversario": "tex"}
    # A mesma posição em outro índice (o diário da fase 1 cresceu): a mesma unidade.
    a = script.chave({**base, "grupo": "forcavel", "indice": 0, "lances": "s4s4"})
    b = script.chave({**base, "grupo": "forcavel", "indice": 3, "lances": "s4s4"})
    c = script.chave({**base, "grupo": "forcavel", "indice": 0, "lances": "s3s3"})
    assert a == b and a != c
    # No `alcance` a posição sai da semente pelo índice: é ele que identifica.
    d = script.chave({**base, "grupo": "alcance", "indice": 0, "lances": None})
    e = script.chave({**base, "grupo": "alcance", "indice": 1, "lances": None})
    assert d != e
    # E o adversário faz parte da unidade.
    assert script.chave({**base, "grupo": "alcance", "indice": 0, "adversario": "pita"}) != d


# ── O resumo da fase 1 ──────────────────────────────────────────────────────


def test_a_taxa_do_resumo_e_sobre_TODAS_as_posicoes_medidas() -> None:
    """Uma passou entre quatro medidas (uma de cara, uma que perde): 25%, e não
    50% (sobre as que vencem) nem 100% (sobre as que passaram por alguma prova)."""
    linhas = [
        _fase_1(20, "a", quatro_golpe_duplo=True, quatro_linha_de_cinco=False),
        _fase_1(20, "b", quatro_golpe_duplo=False, quatro_linha_de_cinco=False),
        {"fase": 1, "comprimento": 20, "lances": "c", "de_cara": True},
        {"fase": 1, "comprimento": 20, "lances": "d", "livre": "perde"},
    ]
    for linha in linhas[:2]:
        linha["quatro_sem_o_meio"] = {"passou": False, "lances": None}
    texto = "\n".join(script._tabela_da_fase_1(linhas))
    assert "[quatro_golpe_duplo] passaram 1 de 4 posições (25.0%)" in texto
    assert "[quatro_linha_de_cinco] passaram 0 de 4 posições (0.0%)" in texto

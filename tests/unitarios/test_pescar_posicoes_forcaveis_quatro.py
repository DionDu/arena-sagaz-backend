"""T124c (spec 010) - as partes do `scripts/pescar_posicoes_forcaveis_quatro.py`
que podem errar caladas.

As provas têm os casos delas em `test_provas_quatro.py` (inclusive a defesa do
jogo, que é a da pescaria). Aqui fica o que é do SCRIPT, e que nenhuma execução
denunciaria:

  * **as posições de cada partida**: uma posição sem lance a jogar, ou uma
    abertura, entraria no banco como se fosse desafio;
  * **a origem de cada posição**: é ela que diz qual confronto rende mais. Ela
    não pode depender da ordem em que os processos terminaram;
  * **a ordem da pescaria**: fixa e embaralhada - é o que faz uma pescaria
    interrompida ser uma amostra do acervo inteiro, e a retomada provar as
    mesmas posições;
  * **o banco**: só as que passaram, por tipo, em ordem estável, e o texto do
    arquivo lendo de volta o mesmo dado.

Nenhum caso abre o motor.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# `parents[2]` sobe de `tests/unitarios/este_arquivo.py` para a raiz do backend,
# onde mora a pasta `scripts/` (que não é pacote instalado).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import pescar_posicoes_forcaveis_quatro as script  # noqa: E402

#: Uma partida de 10 lances (o tabuleiro não importa aqui: só o corte).
DEZ = "s1s2s3s4s5s6s7s1s2s3"


def _partida(confronto: str, indice: int, lances: str) -> dict:
    return {"etapa": "partida", "confronto": confronto, "indice": indice, "lances": lances}


# ── As posições e a origem ──────────────────────────────────────────────────


def test_as_posicoes_passam_da_abertura_e_tem_um_lance_a_jogar() -> None:
    """Com 10 lances e o mínimo de 8: as posições de 8 e 9 lances, e não a de 10
    (a partida acabou nela) nem as de menos de 8 (abertura)."""
    origem = script.posicoes_das_partidas([_partida("magno_tex", 0, DEZ)])
    assert sorted(len(p) // 2 for p in origem) == [8, 9]


def test_a_origem_e_o_PRIMEIRO_confronto_da_lista_e_nao_o_primeiro_que_chegou() -> None:
    """A mesma posição em dois confrontos: a origem é a do confronto que vem
    antes em `CONFRONTOS`, em qualquer ordem de chegada das partidas."""
    tex_tex = _partida("tex_tex", 0, DEZ)
    magno_pita = _partida("magno_pita", 5, DEZ)
    for ordem in ([tex_tex, magno_pita], [magno_pita, tex_tex]):
        assert set(script.posicoes_das_partidas(ordem).values()) == {"magno_pita"}


def test_dentro_do_confronto_vence_o_menor_indice() -> None:
    a = _partida("tex_pita", 7, DEZ)
    b = _partida("tex_pita", 2, DEZ + "s4")
    origem = script.posicoes_das_partidas([a, b])
    # As duas chegam às posições de 8 e 9 lances; a de 10 só a partida `b` tem.
    assert origem[DEZ] == "tex_pita"
    assert len(origem) == 3


# ── A ordem da pescaria ─────────────────────────────────────────────────────


def test_a_ordem_e_FIXA_embaralhada_e_nao_depende_da_entrada() -> None:
    posicoes = [f"s{c}" * n for c in range(1, 8) for n in range(1, 6)]
    uma = script.em_ordem_de_pescaria(posicoes)
    outra = script.em_ordem_de_pescaria(list(reversed(posicoes)))
    assert uma == outra
    assert sorted(uma) == sorted(posicoes)
    # Embaralhada: se saísse em ordem alfabética, uma pescaria interrompida
    # teria provado só as posições de um canto do acervo.
    assert uma != sorted(posicoes)


# ── O banco ─────────────────────────────────────────────────────────────────


def _posicao(lances: str, confronto: str = "tex_tex", **por_tipo) -> dict:
    """Uma linha da etapa B; `por_tipo` dá (passou, lances da pessoa)."""
    linha = {"etapa": "posicao", "lances": lances, "confronto": confronto}
    for co_tipo, (passou, lances_da_pessoa) in por_tipo.items():
        linha[co_tipo] = {
            "passou": passou, "lances": lances_da_pessoa if passou else None,
            "estourou": False, "perguntas": 1, "segundos": 0.1,
        }
    return linha


def _diario() -> list[dict]:
    return [
        _posicao("s7", quatro_golpe_duplo=(True, 6), quatro_linha_de_cinco=(False, 0),
                 quatro_sem_o_meio=(True, 5)),
        _posicao("s2", "magno_pita", quatro_golpe_duplo=(True, 8),
                 quatro_linha_de_cinco=(True, 7), quatro_sem_o_meio=(False, 0)),
        # Fora da faixa: as provas nem rodaram.
        {"etapa": "posicao", "lances": "s1", "confronto": "tex_tex", "fora": "distancia"},
        _partida("tex_tex", 0, DEZ),
    ]


def test_o_banco_tem_so_as_que_PASSARAM_por_tipo_e_em_ordem() -> None:
    dado = script.banco(_diario(), teto=23, perguntas=2000)
    assert dado["tipos"]["quatro_golpe_duplo"] == [
        {"lances": "s2", "lances_da_pessoa": 8, "confronto": "magno_pita"},
        {"lances": "s7", "lances_da_pessoa": 6, "confronto": "tex_tex"},
    ]
    assert [a["lances"] for a in dado["tipos"]["quatro_linha_de_cinco"]] == ["s2"]
    assert [a["lances"] for a in dado["tipos"]["quatro_sem_o_meio"]] == ["s7"]
    # O critério da pescaria vai junto: quem lê sabe contra que defesa se provou.
    assert dado["defesa"] == "jogo" and dado["teto_de_meios_lances"] == 23
    assert dado["parametros"]["quatro_golpe_duplo"] == {"linhas": 2}


def test_o_texto_do_banco_le_de_volta_o_mesmo_dado() -> None:
    dado = script.banco(_diario(), teto=23, perguntas=2000)
    assert json.loads(script.banco_para_json(dado)) == dado
    # E o banco vazio (a 1ª execução interrompida cedo) também é JSON válido.
    vazio = script.banco([], teto=23, perguntas=2000)
    assert json.loads(script.banco_para_json(vazio)) == vazio


def test_a_identidade_no_diario() -> None:
    assert script.chave(_partida("tex_tex", 3, DEZ)) == ("partida", "tex_tex", 3)
    assert script.chave(_posicao("s7")) == ("posicao", "s7")

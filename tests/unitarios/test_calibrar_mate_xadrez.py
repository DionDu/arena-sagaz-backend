"""O script que calibra o acervo de mate do xadrez (21/11/2026).

O que se confere, sem motor nenhum (a `tentar` da regua e trocada por uma de
mentira, que diz "resolveu" conforme uma regra do teste):

  1. a faixa da escada em ACERTOS de 20 (as bordas 0,05, 0,45, 0,75, 0,85
     viram 1, 9, 15, 17, sem o erro de ponto flutuante);
  2. a semente da unidade: fixa, na faixa do job, e diferente por adversario;
  3. o parar cedo: o mascote que sai da faixa encerra a unidade, e os outros nem
     sao medidos; o que fica dentro mede as 20 execucoes;
  4. o resultado gravado: so os problemas na escada, por adversario, com o
     carimbo do motor.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from job import regua as regua_mod

RAIZ = Path(__file__).resolve().parents[2]


def _carregar_script():
    """Carrega `scripts/calibrar_mate_xadrez.py` pelo caminho.

    `scripts/` nao e pacote (nao tem `__init__.py`), entao `import` comum nao o
    acha; `spec_from_file_location` carrega um arquivo solto.
    """
    spec = importlib.util.spec_from_file_location(
        "calibrar_mate_xadrez", RAIZ / "scripts" / "calibrar_mate_xadrez.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["calibrar_mate_xadrez"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


CALIBRAR = _carregar_script()
ESCADA = dict(regua_mod.ESCADA_ALVO)


def test_a_faixa_da_escada_em_acertos_de_20():
    assert CALIBRAR.EXECUCOES == regua_mod.EXECUCOES_PADRAO == 20
    assert CALIBRAR.faixa_de_acertos(ESCADA["cacau"], 20) == (0, 4)
    assert CALIBRAR.faixa_de_acertos(ESCADA["pita"], 20) == (1, 9)
    assert CALIBRAR.faixa_de_acertos(ESCADA["tex"], 20) == (9, 17)
    assert CALIBRAR.faixa_de_acertos(ESCADA["magno"], 20) == (15, 20)


def test_a_semente_e_fixa_na_faixa_do_job_e_muda_com_o_adversario():
    a = CALIBRAR.semente_da_unidade("007mr", "pita")
    assert a == CALIBRAR.semente_da_unidade("007mr", "pita")
    assert 1 <= a <= 2**32 - 1
    assert a != CALIBRAR.semente_da_unidade("007mr", "tex")


def _problema() -> dict:
    """Um problema de mate em 2 do acervo (so o formato importa aqui)."""
    return next(p for p in CALIBRAR.provas_mod.carregar_problemas_de_mate() if p["mate_em"] == 2)


@pytest.fixture
def tentar_de_mentira(monkeypatch):
    """Troca o motor e a `tentar` da regua por uma regra; devolve o registro das chamadas.

    A regra e `{mascote: quantas das primeiras execucoes resolvem}`.
    """
    chamadas: list[tuple[str, int]] = []
    regra: dict[str, int] = {}

    def tentativa_com_motor(**_):
        def tentar(quem, execucao):
            chamadas.append((quem, execucao))
            return execucao <= regra[quem]

        return tentar

    monkeypatch.setattr(CALIBRAR.regua_mod, "tentativa_com_motor", tentativa_com_motor)
    monkeypatch.setattr(CALIBRAR, "_JOGADOR", object())
    return regra, chamadas


def test_a_pita_alta_encerra_a_unidade_cedo_e_os_outros_nem_jogam(tentar_de_mentira):
    regra, chamadas = tentar_de_mentira
    regra.update({"pita": 20, "tex": 12, "cacau": 0})
    linha = CALIBRAR.medir_unidade((_problema(), "magno", 2, 3, ESCADA))
    # Com 10 acertos a Pita ja passou de 9 (0,45 de 20): para na 10a execucao.
    assert linha["acertos"] == {"pita": [10, 10]} and linha["na_escada"] is False
    assert {quem for quem, _ in chamadas} == {"pita"}


def test_a_pita_que_nunca_acerta_vai_ate_o_fim_e_sai_por_baixo(tentar_de_mentira):
    regra, _ = tentar_de_mentira
    regra.update({"pita": 0, "tex": 12, "cacau": 0})
    linha = CALIBRAR.medir_unidade((_problema(), "magno", 2, 3, ESCADA))
    # Com 0 em 20 ela fica abaixo de 1 (0,05): so a 20a execucao decide.
    assert linha["acertos"] == {"pita": [0, 20]} and linha["na_escada"] is False


def test_todos_dentro_da_faixa_medem_as_20_e_caem_na_escada(tentar_de_mentira):
    regra, chamadas = tentar_de_mentira
    regra.update({"pita": 9, "tex": 9, "cacau": 4})
    linha = CALIBRAR.medir_unidade((_problema(), "magno", 2, 3, ESCADA))
    assert linha["acertos"] == {"pita": [9, 20], "tex": [9, 20], "cacau": [4, 20]}
    assert linha["na_escada"] is True
    # O adversario do dia nao e medido, e a ordem e a mais seletiva primeiro.
    assert [quem for quem, _ in chamadas][::20] == ["pita", "tex", "cacau"]


def test_o_adversario_pita_comeca_pelo_tex(tentar_de_mentira):
    regra, _ = tentar_de_mentira
    regra.update({"tex": 15, "cacau": 2, "magno": 20})
    linha = CALIBRAR.medir_unidade((_problema(), "pita", 2, 3, ESCADA))
    assert list(linha["acertos"]) == ["tex", "cacau", "magno"] and linha["na_escada"] is True


def test_o_resultado_grava_so_os_da_escada_por_adversario(monkeypatch, tmp_path):
    destino = tmp_path / "calibracao_do_mate.json"
    monkeypatch.setattr(CALIBRAR.provas_mod, "CALIBRACAO_DO_MATE", destino)
    monkeypatch.setattr(CALIBRAR, "RAIZ", tmp_path)
    linhas = [
        {"id": "b", "adversario": "tex", "acertos": {"pita": [3, 20]}, "na_escada": True},
        {"id": "a", "adversario": "tex", "acertos": {"pita": [3, 20]}, "na_escada": True},
        {"id": "c", "adversario": "tex", "acertos": {"pita": [10, 10]}, "na_escada": False},
        {"id": "a", "adversario": "pita", "acertos": {"tex": [20, 20]}, "na_escada": False},
    ]
    carimbo = {"versao_do_motor": "rust_9.9.9", "lances": 2, "execucoes": 20}
    relatorio = CALIBRAR.escrever_resultado(linhas, carimbo, ESCADA)
    gravada = json.loads(destino.read_text(encoding="utf-8"))
    assert gravada["versao_do_motor"] == "rust_9.9.9" and gravada["lances"] == 2
    # Ordenados (o arquivo vai ao Git), e o adversario sem nenhum nao aparece.
    assert gravada["na_escada_contra"] == {"tex": ["a", "b"]}
    assert gravada["medidos_por_adversario"] == {"pita": 1, "tex": 3}
    assert "contra tex" in relatorio and "pita alto" in relatorio and "tex alto" in relatorio

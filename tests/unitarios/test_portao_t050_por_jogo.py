"""🔒 O portão T050 com `--jogo` (T121 da spec 010, o portão 4a do Quatro, R-24).

O script roda contra o `des` de verdade, e por isso não cabe inteiro num teste.
O que se trava aqui são as peças que decidem O QUE ele confere, cada uma fora da
consulta:

  1. **(a) sem `--jogo` continua cobrando o que cobrava** - Pontinhos e damas,
     nenhum estranho -, e um jogo em adoção publicado deixa de reprová-lo (a
     única mudança, de propósito: o 1º desafio do Quatro no `des` deixaria o
     portão da 009 vermelho para sempre); com `--jogo`, o jogo pedido é exigido;
  2. **(c) confere o dia certo**: o de hoje sem `--jogo` (a mesma consulta de
     antes), o publicado mais próximo do jogo com ele, pela rota certa;
  3. **a partida da escrita**: idêntica à de antes para Pontinhos e damas, e com
     a extensão do Quatro que o contrato fixa;
  4. **as listas escritas à mão** batem com as do job e do app;
  5. **o argumento**: só aceita jogo em adoção, e chega à conferência.
"""

from __future__ import annotations

import inspect
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from job import gerador as gerador_mod  # noqa: E402
from motores.quatro import contrato_quatro  # noqa: E402
from scripts import conferir_portao_t050 as portao  # noqa: E402
from tests.unitarios.fakes_desafio import FakeSessaoSQL  # noqa: E402

HOJE = date(2026, 10, 21)


# ═══════════════════════════════════════════════════════════════════════════
# 1. (a) Os jogos publicados
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("jogos", "jogo", "passou"),
    [
        ({"pontinhos", "damas"}, None, True),  # o portão de antes
        ({"pontinhos"}, None, False),  # falta um do rodízio
        ({"damas"}, None, False),
        ({"pontinhos", "damas", "velha"}, None, False),  # estranho continua reprovando
        ({"pontinhos", "damas", "quatro"}, None, True),  # ⚠️ a única mudança
        ({"pontinhos", "damas"}, "quatro", False),  # pediu o Quatro e ele não está
        ({"pontinhos", "damas", "quatro"}, "quatro", True),
        ({"pontinhos", "quatro"}, "quatro", False),  # o rodízio continua exigido
    ],
)
def test_os_jogos_publicados(jogos, jogo, passou):
    resultado, texto = portao.julgar_jogos_publicados(set(jogos), jogo=jogo)
    assert resultado is passou
    assert texto.startswith("⛔") is (not passou)


def test_o_formato_de_cada_jogo():
    assert portao.FORMATO_POR_JOGO == {
        "pontinhos": "sequencia_lances",
        "damas": "fen",
        "quatro": "sequencia_lances",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. (c) O dia conferido e a rota
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sem_jogo_o_dia_conferido_e_o_de_hoje():
    sessao = FakeSessaoSQL()
    await portao._dia_conferido(sessao, hoje=HOJE, jogo=None)
    ((sql, parametros),) = sessao.executadas
    assert "WHERE d.dt_dia = :hoje" in sql
    assert "co_jogo = :co_jogo" not in sql
    assert parametros == {"hoje": HOJE}


@pytest.mark.asyncio
async def test_com_jogo_e_o_publicado_mais_proximo_daquele_jogo():
    linha = {"dt_dia": date(2026, 10, 28), "id_desafio": "q", "co_jogo": "quatro"}
    sessao = FakeSessaoSQL(respostas={"v.co_jogo = :co_jogo": [linha]})
    achado = await portao._dia_conferido(sessao, hoje=HOJE, jogo="quatro")
    ((sql, parametros),) = sessao.executadas
    assert "d.dt_dia >= :hoje AND v.co_jogo = :co_jogo" in sql
    assert "ORDER BY d.dt_dia" in sql and "LIMIT 1" in sql
    assert parametros == {"hoje": HOJE, "co_jogo": "quatro"}
    assert achado == linha


def test_a_rota_do_dia_de_hoje_e_a_do_dia_futuro():
    assert portao.rota_do_desafio({"dt_dia": HOJE, "id_desafio": "x"}, hoje=HOJE) == (
        "/v1/desafios/hoje"
    )
    assert portao.rota_do_desafio(
        {"dt_dia": date(2026, 10, 28), "id_desafio": "abc"}, hoje=HOJE
    ) == "/v1/desafios/abc"


# ═══════════════════════════════════════════════════════════════════════════
# 3. A partida da escrita
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_jogo", ["pontinhos", "damas"])
def test_a_partida_dos_jogos_de_sempre_e_a_de_antes(co_jogo):
    """Byte a byte o corpo de antes da T121: a variante `pequeno`, sem extensão."""
    assert portao.partida_do_portao({"co_jogo": co_jogo}) == {"co_variante": "pequeno"}


def _dia_do_quatro(lances: list[str], *, como_texto: bool = False) -> dict:
    posicao = {
        "co_formato_posicao": "sequencia_lances",
        "sequencia_lances": lances,
        "co_lances": "".join(lances),
    }
    return {
        "co_jogo": "quatro",
        "co_modalidade": "tradicional",
        "js_posicao_inicial": json.dumps(posicao) if como_texto else posicao,
        "nu_semente": 81234567,
    }


@pytest.mark.parametrize("como_texto", [False, True])
def test_a_partida_do_quatro_leva_a_extensao_do_contrato(como_texto):
    corpo = portao.partida_do_portao(
        _dia_do_quatro(["s3", "s3", "s4", "s4"], como_texto=como_texto)
    )
    assert corpo["co_variante"] == "tradicional"
    extensao = corpo["quatro"]
    # As MESMAS chaves do exemplo do contrato (`extensao-log-quatro.md` §1).
    assert set(extensao) == {
        "co_versao_motor",
        "co_versao_contrato",
        "co_lances_iniciais",
        "nu_jogador_abertura",
        "co_preferencia_abertura",
        "nu_semente_partida",
        "js_extra",
    }
    assert extensao["co_lances_iniciais"] == "s3s3s4s4"  # I-9: a posição publicada
    assert extensao["nu_semente_partida"] == 81234567
    assert extensao["co_versao_contrato"] == contrato_quatro.versao_do_contrato()
    assert extensao["co_versao_motor"] == portao.VERSAO_DO_MOTOR_QUATRO_NO_APP
    # Os dois NOT NULL da `jogo_quatro.tb001_partida`, dentro dos CHECK dela.
    assert extensao["nu_jogador_abertura"] in (1, -1)
    assert extensao["co_preferencia_abertura"] in ("j1", "j2", "alternado")


@pytest.mark.parametrize(
    ("lances", "abertura"),
    [
        ([], 1),  # tabuleiro vazio: a pessoa abre
        (["s3", "s3", "s4", "s4"], 1),  # par: a pessoa (J1) abriu a sequência
        (["s3", "s3", "s4"], -1),  # ímpar: quem abriu foi o personagem
    ],
)
def test_quem_abriu_a_sequencia_inteira(lances, abertura):
    """§3 do contrato: a cor de quem fez o 1º lance, a posição incluída."""
    corpo = portao.partida_do_portao(_dia_do_quatro(lances))
    assert corpo["quatro"]["nu_jogador_abertura"] == abertura


# ═══════════════════════════════════════════════════════════════════════════
# 4. As listas escritas à mão
# ═══════════════════════════════════════════════════════════════════════════


def test_as_listas_do_portao_sao_as_do_job():
    assert portao.JOGOS_EM_ADOCAO == gerador_mod.JOGOS_EM_ADOCAO
    assert portao.JOGOS_DO_RODIZIO == gerador_mod.JOGOS_DO_RODIZIO
    # Todo jogo em adoção tem formato e cadeados.
    for co_jogo in portao.JOGOS_EM_ADOCAO:
        assert co_jogo in portao.FORMATO_POR_JOGO
        assert portao.CADEADOS_POR_JOGO[co_jogo]


def test_os_cadeados_do_quatro_existem():
    for caminho in portao.CADEADOS_POR_JOGO["quatro"]:
        assert (RAIZ / caminho).is_file(), caminho


def test_a_versao_do_motor_e_a_que_o_app_grava():
    arquivo = (
        RAIZ.parent
        / "arena-sagaz-frontend"
        / "lib"
        / "modulos"
        / "jogos"
        / "quatro"
        / "log"
        / "versao_do_motor_quatro.dart"
    )
    casou = re.search(
        r"const String versaoDoMotorQuatro = '([^']+)';", arquivo.read_text(encoding="utf-8")
    )
    assert casou is not None
    assert portao.VERSAO_DO_MOTOR_QUATRO_NO_APP == f"dart_{casou.group(1)}"


# ═══════════════════════════════════════════════════════════════════════════
# 5. O argumento
# ═══════════════════════════════════════════════════════════════════════════


def _rodar_main(monkeypatch, argumentos: list[str]) -> dict:
    """Roda o `main` do portão com a conferência trocada por um espião."""
    recebido: dict = {}

    async def conferir_espiao(**kwargs):
        recebido.update(kwargs)
        return 0

    monkeypatch.setattr(portao, "conferir", conferir_espiao)
    monkeypatch.setattr(sys, "argv", ["conferir_portao_t050.py", *argumentos])
    assert portao.main() == 0
    return recebido


def test_sem_argumento_a_conferencia_e_a_de_antes(monkeypatch):
    assert _rodar_main(monkeypatch, []) == {"com_escrita": True, "jogo": None}


def test_o_jogo_chega_a_conferencia(monkeypatch):
    assert _rodar_main(monkeypatch, ["--jogo", "quatro", "--sem-escrita"]) == {
        "com_escrita": False,
        "jogo": "quatro",
    }


@pytest.mark.parametrize("jogo", ["pontinhos", "velha", "xadrez"])
def test_so_jogo_em_adocao_e_aceito(monkeypatch, jogo):
    with pytest.raises(SystemExit):
        _rodar_main(monkeypatch, ["--jogo", jogo])


def test_o_espiao_e_assincrono_como_a_conferencia():
    """O `main` chama `asyncio.run(conferir(...))`: o espião tem de ser corrotina."""
    assert inspect.iscoroutinefunction(portao.conferir)


def test_os_cadeados_do_quatro_sao_os_cinco():
    """Por extenso: tirar um da lista não pode passar calado."""
    assert portao.CADEADOS_POR_JOGO["quatro"] == [
        "tests/unitarios/test_contrato_quatro.py",
        "tests/unitarios/test_regras_quatro_vetores.py",
        "tests/unitarios/test_feitos_quatro.py",
        "tests/unitarios/test_jogador_dart_quatro.py",
        "tests/unitarios/test_contrato_extensao_quatro.py",
    ]

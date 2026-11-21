"""🔒 A posição publicada do xadrez é conferida antes de virar linha (T082 da spec 012).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O job confere toda posição antes de gravá-la (`job/__main__.py`, a chamada a
`posicao_inicial.conferir`). Até a T082 a posição do xadrez caía na conferência
das DAMAS (o formato dos dois é `fen`) e era recusada pela falta da `versao`: o
job não conseguia publicar um desafio de xadrez, e o motivo só apareceria no
`des`, com a fila vazia.

O que se trava aqui:

  1. a posição que o job sorteia, em cada um dos onze tipos no ar, passa;
  2. cada defeito de uma posição do contrato §1 é recusado, com o motivo;
  3. a posição do xadrez nunca cai na conferência das damas (o `jogo` de
     dentro dela decide, e não o formato).

⛔ Nenhuma regra de xadrez aqui: de quem é a vez e se a partida acabou quem diz
é o executável (`estado`). Sem ele compilado, o arquivo pula com a receita, como
os outros testes do xadrez.
"""

from __future__ import annotations

import random

import pytest

from job import posicao_inicial as posicao_mod
from job import provas_xadrez as pv
from job.editorial import EDITORIAL
from job.posicao_inicial import PosicaoInvalida, conferir
from job.tipos_de_desafio import RECEITAS
from motores.xadrez.jogador_xadrez import JogadorXadrez, MotorDartIndisponivel

#: Os tipos do xadrez NO AR (a troca está fora desde a §8zzzz64).
TIPOS_NO_AR = sorted(t for t, r in RECEITAS.items() if r.co_jogo == "xadrez")

#: Uma abertura comum, com as brancas a jogar: há cavalo, bispo, torre e dama dos
#: dois lados, e nenhuma peça fora do lugar.
FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"

#: A mesma abertura, com a vez das pretas (o lance de antes foi das brancas).
FEN_DAS_PRETAS = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R b KQkq - 3 3"

#: Mate do pastor: as pretas a jogar, e a partida já acabou.
FEN_DE_MATE = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"


@pytest.fixture(scope="module")
def motor():
    """O executável, ou o pulo com a receita."""
    try:
        with JogadorXadrez() as jogador:
            yield jogador
    except MotorDartIndisponivel as erro:
        pytest.skip(f"sem o executavel do xadrez compilado: {erro}")


def _posicao(**troca) -> dict:
    """Uma posição válida do contrato §1 (a espiã no cavalo de f3), com [troca]."""
    posicao = {
        "jogo": "xadrez",
        "modalidade": "tradicional",
        "fen": FEN,
        "cor_da_pessoa": "branca",
        "marcas": {"espia": "f3"},
        "origem": "base_equilibrada",
    }
    posicao.update(troca)
    # `None` numa troca quer dizer "tire a chave".
    return {chave: valor for chave, valor in posicao.items() if valor is not None}


def _conferir(posicao: dict, motor) -> None:
    """`conferir` do job, com o executável do módulo."""
    posicao_mod._conferir_xadrez(posicao, "tradicional", motor=motor)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O que o job sorteia passa
# ═══════════════════════════════════════════════════════════════════════════


def test_os_onze_tipos_no_ar():
    """O número de tipos do xadrez no ar (T078): onze, sem a troca."""
    assert len(TIPOS_NO_AR) == 11
    assert "xadrez_troca" not in TIPOS_NO_AR and "xadrez_duas_espias" in TIPOS_NO_AR


@pytest.mark.parametrize("co_tipo", TIPOS_NO_AR)
@pytest.mark.parametrize("semente", [1, 2, 3])
def test_a_posicao_que_o_job_sorteia_passa_na_conferencia(co_tipo, semente, motor):
    """Pelo mesmo `conferir` que o job chama, com o formato do jogo."""
    # Os números da 1ª publicação do editorial: são eles que o gerador passa.
    parametros = dict(EDITORIAL[co_tipo][0].parametros)
    escolhida = pv.sortear_posicao(
        random.Random(semente), co_tipo=co_tipo, parametros=parametros, co_personagem=None
    )
    posicao = escolhida.js_posicao_inicial
    conferir(posicao_mod.formato_do_jogo("xadrez"), posicao, co_modalidade="tradicional")
    # E quem resolve é o `+1` da fita, sem `vez_de` na posição.
    assert "vez_de" not in posicao and "versao" not in posicao
    assert posicao_mod.vez_de_quem_resolve(posicao) == 1


@pytest.mark.parametrize(
    "posicao",
    [
        _posicao(),
        # A pessoa de pretas.
        _posicao(fen=FEN_DAS_PRETAS, cor_da_pessoa="preta", marcas={"espia": "c6"}),
        # As duas espiãs, de classes diferentes (o cavalo e a torre).
        _posicao(marcas={"espia": "f3", "espia2": "h1"}),
        # O alvo é do adversário.
        _posicao(marcas={"espia": "f3", "alvo": "e5"}),
        # Sem marca nenhuma (o mate, o `nao_perder`, os xeques).
        _posicao(marcas=None, origem="problemas_lichess"),
        _posicao(marcas=None, classes={"come": "cavalo", "comida": "peao"}),
        _posicao(marcas=None, classes={"come": "bispo"}),
        _posicao(marcas=None, troca={"minha": "bispo", "dele": "cavalo"}),
    ],
)
def test_posicoes_validas_passam(posicao, motor):
    _conferir(posicao, motor)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Cada defeito é recusado
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("posicao", "motivo"),
    [
        # A forma.
        (_posicao(versao=1), "chaves fora do contrato"),
        (_posicao(vez_de=1), "chaves fora do contrato"),
        (_posicao(modalidade="chess960"), "modalidade"),
        (_posicao(origem="inventada"), "origem"),
        (_posicao(origem=None), "origem"),
        (_posicao(fen=""), "sem `fen`"),
        (_posicao(cor_da_pessoa="azul"), "cor_da_pessoa"),
        # O motor.
        (_posicao(cor_da_pessoa="preta"), "julgado do lado errado"),
        (_posicao(fen="8/8/8/8/8/8/8/8 w - - 0 1", marcas=None), "o motor recusou"),
        (_posicao(fen="nao e fen", marcas=None), "o motor recusou"),
        (_posicao(fen=FEN_DE_MATE, cor_da_pessoa="preta", marcas=None), "ja acabou"),
        # As marcas.
        (_posicao(marcas={}), "sem marca"),
        (_posicao(marcas={"espia": "e4", "rainha": "d1"}), "marcas desconhecidas"),
        (_posicao(marcas={"alvo": "e5"}), "sem a espia"),
        (_posicao(marcas={"espia": "d4"}), "onde nao ha peca"),
        (_posicao(marcas={"espia": "c6"}), "tinha de ser branca"),
        (_posicao(marcas={"espia": "f3", "alvo": "e4"}), "tinha de ser preta"),
        (_posicao(marcas={"espia": "f3", "espia2": "c6"}), "tinha de ser branca"),
        (_posicao(marcas={"espia": "f3", "espia2": "b1"}), "classes"),
        (_posicao(marcas={"espia": "f3", "espia2": "f3"}), "mesma casa"),
        # As classes e a troca.
        (_posicao(marcas=None, classes={"come": "elefante"}), "nao e peca"),
        (_posicao(marcas=None, classes={"cmoe": "cavalo"}), "as chaves sao"),
        # (com peoes: rei e cavalo contra rei seria material insuficiente, e o
        # motor responderia que a partida ja acabou)
        (_posicao(marcas=None, classes={"come": "cavalo", "comida": "bispo"},
                  fen="4k3/p7/8/8/8/8/P7/1N2K3 w - - 0 1"), "classes.comida"),
        (_posicao(marcas=None, troca={"minha": "bispo"}), "as chaves sao"),
        (_posicao(marcas=None, troca={"minha": "bispo", "dele": "cavalo"},
                  fen="4k3/p7/8/8/8/8/P7/2B1K3 w - - 0 1"), "troca.dele"),
    ],
)
def test_cada_defeito_e_recusado_com_o_motivo(posicao, motivo, motor):
    with pytest.raises(PosicaoInvalida, match=motivo) as erro:
        _conferir(posicao, motor)
    assert "Nao publique" in str(erro.value)


def test_modalidade_do_desafio_diferente_da_posicao_e_recusada(motor):
    with pytest.raises(PosicaoInvalida, match="modalidade"):
        posicao_mod._conferir_xadrez(_posicao(), "brasileira", motor=motor)


# ═══════════════════════════════════════════════════════════════════════════
# 3. O xadrez não cai na conferência das damas
# ═══════════════════════════════════════════════════════════════════════════


def test_o_formato_de_sequencia_e_recusado_para_o_xadrez():
    """O `jogo` de dentro da posição manda; um formato trocado falha alto."""
    with pytest.raises(PosicaoInvalida, match="formato"):
        conferir("sequencia_lances", _posicao(), co_modalidade="tradicional")


def test_a_posicao_do_xadrez_nao_vai_ao_motor_das_damas(monkeypatch, motor):
    """⚠️ Até a T082 ela caía em `_conferir_fen` e morria pela `versao`."""

    def nunca(*_a, **_k):
        raise AssertionError("a posicao do xadrez foi a conferencia das damas")

    # A original guardada ANTES da troca: chamá-la pelo módulo daria na troca.
    original = posicao_mod._conferir_xadrez
    chamadas: list[str] = []

    def conferir_com_o_motor(posicao, co_modalidade):
        chamadas.append(co_modalidade)
        original(posicao, co_modalidade, motor=motor)

    monkeypatch.setattr(posicao_mod, "_conferir_fen", nunca)
    monkeypatch.setattr(posicao_mod, "_conferir_xadrez", conferir_com_o_motor)
    conferir("fen", _posicao(), co_modalidade="tradicional")
    assert chamadas == ["tradicional"]


def test_as_damas_continuam_na_conferencia_delas():
    """O outro sentido: uma posição das damas sem `jogo` segue o caminho de antes."""
    posicao = posicao_mod.das_damas("W:W27:B23,15,4")
    conferir("fen", posicao, co_modalidade="brasileira")

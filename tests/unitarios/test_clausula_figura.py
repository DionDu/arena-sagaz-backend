"""T146 da spec 010 - a clausula `figura` da linha de chegada.

═══════════════════════════════════════════════════════════════════════════
O QUE OS VETORES NAO ALCANCAM
═══════════════════════════════════════════════════════════════════════════

Os vetores `quatro-figura-*` (`contratos/vetores-verificacao-desafio.json`)
provam que o juiz daqui e o do aplicativo julgam a mesma fita igual. Este arquivo
cobre o resto: as RECUSAS do formato (o que nao e uma figura), a busca do
desenho numa grade escrita a mao (sem motor nenhum no caminho), e o jogo que nao
entrega a grade - que e recusa, e nao "nao cumpriu".

A grade dos testes e escrita como texto, de cima para baixo: `1` e o J1, `2` o
J2 e `.` a casa vazia - a mesma leitura do `desenho`, para o olho comparar.
"""

from __future__ import annotations

import pytest

from motores.juiz import julgar_desafio
from motores.nucleo.chegada import (
    ChegadaInvalida,
    Clausula,
    ClausulaDeFigura,
    LinhaDeChegada,
    avaliar,
    chegada_encerra_partida,
    encontrar_figura,
    figura_formada,
    ler_clausula,
)
from motores.quatro import feitos_quatro
from motores.quatro.motor_quatro import MotorQuatro


def _grade(*linhas: str) -> list[list[int]]:
    """Uma grade a partir do desenho: `1` J1, `2` J2, `.` vazia."""
    valor = {"1": 1, "2": -1, ".": 0}
    return [[valor[c] for c in linha] for linha in linhas]


def _figura(desenho: list[str], espelhar: bool = False) -> ClausulaDeFigura:
    return ClausulaDeFigura.de_dado(
        {"tipo": "figura", "desenho": desenho, "espelhar": espelhar}
    )


def _chegada(*clausulas: dict, janela: dict | None = None) -> LinhaDeChegada:
    return LinhaDeChegada.de_dado(
        {
            "versao": 1,
            "janela": janela or {"tipo": "lances_do_jogador", "n": 4},
            "clausulas": list(clausulas),
        }
    )


FIGURA_L = {"tipo": "figura", "desenho": ["X.", "X.", "XX"], "espelhar": False}


# ═══════════════════════════════════════════════════════════════════════════
# 1. O que e uma figura (as recusas do formato)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_figura_bem_formada_e_lida() -> None:
    figura = ler_clausula(FIGURA_L)
    assert isinstance(figura, ClausulaDeFigura)
    assert figura.tipo == "figura"
    assert figura.desenho == ("X.", "X.", "XX")
    assert figura.espelhar is False


@pytest.mark.parametrize(
    "clausula, trecho",
    [
        ({"tipo": "figura", "desenho": ["XA"], "espelhar": False}, "simbolos fora"),
        ({"tipo": "figura", "desenho": ["X.", "X"], "espelhar": False}, "tamanhos diferentes"),
        ({"tipo": "figura", "desenho": ["O_", ".O"], "espelhar": False}, "nenhuma peca da pessoa"),
        ({"tipo": "figura", "desenho": [], "espelhar": False}, "lista de linhas"),
        # Um texto solto seria lido letra a letra, como se cada letra fosse uma
        # linha: "XX" viraria uma coluna de duas pecas.
        ({"tipo": "figura", "desenho": "XX", "espelhar": False}, "lista de linhas"),
        ({"tipo": "figura", "desenho": ["X", ""], "espelhar": False}, "texto nao vazio"),
        ({"tipo": "figura", "desenho": ["X"]}, "espelhar"),
        # `1` nao e `True` aqui: o JSON diria uma coisa e o Dart leria outra.
        ({"tipo": "figura", "desenho": ["X"], "espelhar": 1}, "espelhar"),
        (
            {"tipo": "figura", "desenho": ["X"], "espelhar": False, "comparador": "igual"},
            "nao aceita",
        ),
    ],
)
def test_o_que_nao_e_figura_e_recusado(clausula: dict, trecho: str) -> None:
    """🔒 Cada recusa com o motivo dela - e nunca "tenta assim mesmo"."""
    with pytest.raises(ChegadaInvalida, match=trecho):
        _chegada(clausula)


def test_a_figura_nao_entra_pela_porta_das_outras_clausulas() -> None:
    """`Clausula.de_dado` le medida e predicado; a figura tem forma propria."""
    with pytest.raises(ChegadaInvalida, match="forma propria"):
        Clausula.de_dado(FIGURA_L)


def test_a_figura_nao_aparece_como_medida_nem_predicado() -> None:
    """O medidor e o job leem `chaves_de_medida`; a figura nao pede medida."""
    medida = {
        "tipo": "medida",
        "chave": "lances_do_jogador",
        "comparador": "maior_ou_igual",
        "valor": 1,
    }
    chegada = _chegada(FIGURA_L, medida)
    assert chegada.chaves_de_medida == ("lances_do_jogador",)
    assert chegada.predicados == ()
    assert [f.desenho for f in chegada.figuras] == [("X.", "X.", "XX")]


def test_a_figura_nao_encerra_a_partida() -> None:
    """Formar a figura nao e o fim do jogo: a chegada cai no meio (§8zzzr)."""
    assert not chegada_encerra_partida(_chegada(FIGURA_L, janela={"tipo": "partida"}))


# ═══════════════════════════════════════════════════════════════════════════
# 2. A busca do desenho numa grade
# ═══════════════════════════════════════════════════════════════════════════


def test_o_desenho_vale_em_qualquer_lugar() -> None:
    """A translacao: o L no canto de baixo e da direita."""
    grade = _grade(
        ".....",
        "...1.",
        "...1.",
        "...11",
    )
    assert figura_formada(_figura(["X.", "X.", "XX"]), grade, 1)


def test_o_espelho_so_vale_quando_o_desenho_aceita() -> None:
    """O J e o espelho do L; o "z" espelhado seria um "s"."""
    o_j = _grade(
        ".1",
        ".1",
        "11",
    )
    assert not figura_formada(_figura(["X.", "X.", "XX"]), o_j, 1)
    assert figura_formada(_figura(["X.", "X.", "XX"], espelhar=True), o_j, 1)


def test_x_e_da_pessoa_e_o_e_do_adversario() -> None:
    """A mesma grade, lida do lado de cada um: as cores trocam."""
    losango_do_j1 = _grade(
        ".1.",
        "121",
        ".1.",
    )
    losango = _figura([".X.", "XOX", ".X."])
    assert figura_formada(losango, losango_do_j1, 1)
    # Do lado do J2, as quatro pecas em volta sao do ADVERSARIO.
    assert not figura_formada(losango, losango_do_j1, -1)
    # A cruz da pessoa nao e o losango: o meio tem de ser do adversario.
    assert not figura_formada(losango, _grade(".1.", "111", ".1."), 1)
    # Nem o meio vazio: `O` pede uma PECA do adversario, e nao "nao e minha".
    # No Quatro a gravidade nao deixa esta grade existir, mas o juiz e de todos
    # os jogos (a mutacao `dono != jogador` sobrevivia sem este caso).
    assert not figura_formada(losango, _grade(".1.", "1.1", ".1."), 1)


def test_a_casa_vazia_tem_de_estar_vazia_e_o_ponto_aceita_tudo() -> None:
    """`_` pede a casa vazia; `.` aceita vazia, da pessoa ou do adversario."""
    oco, cheio_do_adversario, cheio_da_pessoa = (
        _grade("1.1", "111"),
        _grade("121", "111"),
        _grade("111", "111"),
    )
    u_qualquer = _figura(["X.X", "XXX"])
    u_oco = _figura(["X_X", "XXX"])
    assert figura_formada(u_qualquer, oco, 1)
    assert figura_formada(u_qualquer, cheio_do_adversario, 1)
    assert figura_formada(u_qualquer, cheio_da_pessoa, 1)
    assert figura_formada(u_oco, oco, 1)
    assert not figura_formada(u_oco, cheio_do_adversario, 1)
    assert not figura_formada(u_oco, cheio_da_pessoa, 1)


def test_ONDE_a_figura_se_formou_sao_as_casas_do_desenho_sem_o_ponto() -> None:
    """T154: o painel contorna as casas que a busca devolve.

    O L no canto de baixo e da direita: o canto do desenho e a linha 1, coluna
    3 (contadas de 0, de cima), e as casas sao as quatro `X`, sem os `.`.
    """
    grade = _grade(
        ".....",
        "...1.",
        "...1.",
        "...11",
    )
    achada = encontrar_figura(_figura(["X.", "X.", "XX"]), grade, 1)
    assert achada is not None
    assert (achada.topo, achada.esquerda) == (1, 3)
    assert achada.casas() == ((1, 3), (2, 3), (3, 3), (3, 4))
    # A casa VAZIA exigida (`_`) e da figura; o `.` nao e.
    vazia = encontrar_figura(_figura(["X_X", "XXX"]), _grade("1.1", "111"), 1)
    assert vazia is not None and (0, 1) in vazia.casas()
    assert len(vazia.casas()) == 6
    # E sem figura, nada: o `None` que o `figura_formada` le como "nao".
    assert encontrar_figura(_figura(["XX"]), _grade("1.", ".1"), 1) is None


def test_ONDE_o_espelho_casou_devolve_o_desenho_ESPELHADO() -> None:
    """O J (espelho do L) devolve o desenho que casou, e nao o original: o
    contorno do painel tem de cair no J, e nao onde o L estaria."""
    o_j = _grade(
        ".1",
        ".1",
        "11",
    )
    achada = encontrar_figura(_figura(["X.", "X.", "XX"], espelhar=True), o_j, 1)
    assert achada is not None
    assert achada.desenho == (".X", ".X", "XX")
    assert achada.casas() == ((0, 1), (1, 1), (2, 0), (2, 1))


def test_dois_lugares_vale_o_PRIMEIRO_da_busca_como_no_app() -> None:
    """De cima para baixo, da esquerda para a direita, e o original antes do
    espelho: a ordem do `encontrarFigura` do app, para o painel contornar o
    mesmo lugar que o telefone."""
    duas = _grade(
        "....",
        "11..",
        "..11",
    )
    achada = encontrar_figura(_figura(["XX"]), duas, 1)
    assert achada is not None and (achada.topo, achada.esquerda) == (1, 0)
    # O original (o L) casa antes do espelho (o J) quando os dois estao la.
    l_e_j = _grade(
        "1..1",
        "1..1",
        "1111",
    )
    achada = encontrar_figura(_figura(["X.", "X.", "XX"], espelhar=True), l_e_j, 1)
    assert achada is not None and achada.desenho == ("X.", "X.", "XX")
    assert (achada.topo, achada.esquerda) == (0, 0)


def test_a_figura_maior_que_o_tabuleiro_nunca_aparece() -> None:
    """Sem erro: caber no tabuleiro e conferido no catalogo da T147."""
    assert not figura_formada(_figura(["X", "X", "X"]), _grade("1", "1"), 1)
    assert not figura_formada(_figura(["XXX"]), _grade("11"), 1)


def test_a_figura_e_as_outras_clausulas_valem_juntas() -> None:
    """A conjuncao continua: figura E medida."""
    medida = {
        "tipo": "medida",
        "chave": "lances_do_jogador",
        "comparador": "menor_ou_igual",
        "valor": 3,
    }
    chegada = _chegada({"tipo": "figura", "desenho": ["XX"], "espelhar": False}, medida)
    grade = _grade("..", "11")
    assert avaliar(chegada, {"lances_do_jogador": 3}, grade=grade, jogador=1)
    assert not avaliar(chegada, {"lances_do_jogador": 4}, grade=grade, jogador=1)
    assert not avaliar(chegada, {"lances_do_jogador": 3}, grade=_grade("..", "1."), jogador=1)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Quem nao entrega a grade nao julga figura
# ═══════════════════════════════════════════════════════════════════════════


def test_avaliar_sem_grade_e_recusa() -> None:
    """⛔ Nunca "nao cumpriu": seria um medidor sem grade parecendo uma pessoa."""
    with pytest.raises(ChegadaInvalida, match="grade"):
        avaliar(_chegada(FIGURA_L), {})


def test_o_pontinhos_nao_julga_figura_nem_com_a_fita_vazia() -> None:
    """🔒 A recusa vem antes da fita.

    Com a fita vazia nenhum lance da pessoa chegaria a ser avaliado, e sem a
    pergunta na entrada do `julgar` o veredito sairia "nao cumpriu", calado.
    """
    with pytest.raises(ChegadaInvalida, match="grade"):
        julgar_desafio(
            co_jogo="pontinhos",
            js_posicao_inicial={"versao": 1, "lances": []},
            js_chegada={
                "versao": 1,
                "janela": {"tipo": "lances_do_jogador", "n": 4},
                "clausulas": [FIGURA_L],
            },
            fita=[],
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. A grade que o Quatro entrega
# ═══════════════════════════════════════════════════════════════════════════


def test_a_grade_do_quatro_tem_o_chao_embaixo() -> None:
    """A 1a peca na coluna 4 aparece na ULTIMA linha da grade, na 4a casa.

    ⚠️ O motor guarda cada coluna de baixo para cima; a figura e escrita de
    cima para baixo. Uma grade de cabeca para baixo faria o "i" (pingo em
    cima) ser julgado como um "!" - e as figuras de pe nunca apareceriam.
    """
    motor = MotorQuatro("tradicional")
    grade = feitos_quatro.grade(motor, [], ["s4", "s4", "s1"])
    assert len(grade) == 6 and all(len(linha) == 7 for linha in grade)
    assert grade[5] == [1, 0, 0, 1, 0, 0, 0]
    assert grade[4] == [0, 0, 0, -1, 0, 0, 0]
    assert all(casa == 0 for linha in grade[:4] for casa in linha)


def test_a_grade_do_quatro_recusa_a_fita_ilegal() -> None:
    """Fita que nao se joga e erro, como nas medidas (vira dado invalido)."""
    with pytest.raises(ValueError):
        feitos_quatro.grade(MotorQuatro("tradicional"), [], ["s9"])

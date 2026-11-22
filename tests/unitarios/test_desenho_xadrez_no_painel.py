"""O XADREZ DESENHADO NO PAINEL DE CURADORIA (22/11/2026, spec 012).

O dono vai testar no aparelho um desafio de cada tipo do xadrez, trazendo um
para hoje de cada vez pelo painel (o ciclo do Quatro, `DECISOES-do-dono.md`
§8zzzv do app). Ate hoje o painel mandava todo formato `fen` para o desenho das
DAMAS, e a FEN do xadrez saia como um tabuleiro de damas sem sentido.

O que estes casos protegem:

  · **o dia do xadrez abre** no painel, com o tabuleiro do xadrez (e nao o das
    damas), a legenda das cores e o nome do jogo;
  · **a FEN e lida como tabela**, e o tabuleiro vira para quem resolve: as
    pecas dela sao AZUIS e ficam EMBAIXO, de brancas ou de pretas;
  · **as comidas e as marcas saem da diferenca entre duas FENs** que o motor
    gravou (en passant, roque e promocao, sem regra de xadrez aqui);
  · **a fita do gabarito** sai quadro a quadro, com o titulo em palavras
    ("dama d3 > h3") e o lado certo ("voce" e o `+1`), a partir da solucao
    REAL do 1o desafio de xadrez do `des` (28/11/2026);
  · **a partida de quem jogou** (o raio-x) tambem;
  · **FEN torta vira aviso desenhado**, nunca um 500;
  · **as damas continuam indo para as damas**.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from api.desafios.painel import desenho, pagina
from tests.unitarios.test_painel_curadoria import POSICAO_DAMAS, _desafio

#: O 1o desafio de xadrez publicado no `des` (28/11/2026, `xadrez_dar_mate`
#: contra o Magno): a posicao, o gabarito e as FENs que o job gravou.
POSICAO_DO_MATE = {
    "fen": "r1b3r1/pp1p1p1k/2n1p1p1/q3b1B1/8/1R1Q4/P1P2PPP/5RK1 w - - 0 1",
    "jogo": "xadrez",
    "origem": "problemas_lichess",
    "modalidade": "tradicional",
    "cor_da_pessoa": "branca",
}
SOLUCAO_DO_MATE = {
    "lances": [
        {"n": 1, "lance": "d3h3", "co_acao": "busca_melhor", "jogador": 1},
        {"n": 2, "lance": "h7g7", "co_acao": "lance_unico", "jogador": -1},
        {"n": 3, "lance": "h3h6", "co_acao": "mate_em_um", "jogador": 1},
    ],
    "versao": 1,
    "posicoes": [
        {"n": 1, "fen": "r1b3r1/pp1p1p1k/2n1p1p1/q3b1B1/8/1R5Q/P1P2PPP/5RK1 b - - 1 1"},
        {"n": 2, "fen": "r1b3r1/pp1p1pk1/2n1p1p1/q3b1B1/8/1R5Q/P1P2PPP/5RK1 w - - 2 2"},
        {"n": 3, "fen": "r1b3r1/pp1p1pk1/2n1p1pQ/q3b1B1/8/1R6/P1P2PPP/5RK1 b - - 3 2"},
    ],
    "lance_chave": 3,
}

#: O 2o (29/11/2026, `xadrez_espia_comer`): a torre de a1 e a espia.
POSICAO_DA_ESPIA = {
    "fen": "r3r1k1/pp1n1ppp/2pb4/3p4/3Pb3/2P1BN2/PP2BPPP/R4RK1 w - - 0 1",
    "jogo": "xadrez",
    "marcas": {"espia": "a1"},
    "origem": "base_equilibrada",
    "modalidade": "tradicional",
    "cor_da_pessoa": "branca",
}


def _desafio_de_xadrez(posicao: dict, **campos):
    """Uma linha da fila com o xadrez, no molde de `_desafio`."""
    return replace(
        _desafio(co_curadoria="aprovado", co_jogo="xadrez", posicao=posicao),
        co_modalidade="tradicional",
        co_variante="tradicional",
        co_tipo_desafio="xadrez_dar_mate",
        no_tipo_desafio="De xeque-mate",
        co_chave_objetivo="desafioObjetivoXadrezDarMate",
        js_objetivo={"lances": 2, "personagem": "magno"},
        co_personagem="magno",
        **campos,
    )


def _pecas_na_cor(svg: str, cor: str) -> int:
    """Quantos simbolos de peca estao pintados com [cor]."""
    return len(re.findall(rf'fill="{cor}" stroke="{desenho.MADEIRA_ESC}" stroke-width="0.6"', svg))


def _x_da_letra(svg: str, letra: str) -> float:
    """O `x` da letra de coluna escrita na madeira, embaixo."""
    achado = re.search(rf'<text x="([0-9.]+)" y="[0-9.]+" text-anchor="middle" '
                       rf'font-size="10" fill="{desenho.CREME}">{letra}</text>', svg)
    assert achado, letra
    return float(achado.group(1))


# ── O dia abre ───────────────────────────────────────────────────────────────


def test_o_dia_do_XADREZ_abre_no_painel_com_o_tabuleiro_do_xadrez() -> None:
    """🔒 O dia do xadrez desenha o xadrez, e nao as damas."""
    item = _desafio_de_xadrez(POSICAO_DO_MATE, js_solucao=SOLUCAO_DO_MATE)
    html = pagina.render_detalhe(
        pagina.DetalheDoDia(dt_dia=date(2026, 11, 28), desafio=item),
        dt_hoje=date(2026, 11, 22),
        dt_sugerida=date(2026, 11, 22),
        dt_fim_janela_baixada=date(2026, 11, 25),
    )
    assert 'aria-label="tabuleiro de xadrez, voce de brancas"' in html
    assert "desafio de damas" not in html
    # O nome do jogo, e nao o codigo cru; e a legenda das cores.
    assert ">Xadrez" in html
    assert "azul = voce (quem resolve, embaixo)" in html
    # A fita do gabarito, com o lance em palavras.
    assert "dama d3 &gt; h3" in html or "dama d3 > h3" in html


def test_as_DAMAS_continuam_indo_para_as_damas() -> None:
    svg = desenho.posicao("fen", POSICAO_DAMAS)
    assert "desafio de damas" in svg
    assert "tabuleiro de xadrez" not in svg


def test_o_rotulo_e_a_sigla_do_xadrez() -> None:
    assert pagina.ROTULO_DO_JOGO["xadrez"] == "Xadrez"
    assert pagina.SIGLA_DO_JOGO["xadrez"]


# ── A FEN como tabela, e o tabuleiro virado para quem resolve ───────────────


def test_a_FEN_e_lida_como_TABELA() -> None:
    tabela = desenho.ler_fen_xadrez("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert len(tabela) == 32
    assert tabela["e1"] == "K" and tabela["e8"] == "k"
    assert tabela["a1"] == "R" and tabela["h8"] == "r"
    assert tabela["d2"] == "P" and "e4" not in tabela


def test_quem_resolve_e_AZUL_de_brancas() -> None:
    svg = desenho.xadrez(POSICAO_DO_MATE)
    tabela = desenho.ler_fen_xadrez(POSICAO_DO_MATE["fen"])
    brancas = sum(1 for p in tabela.values() if p.isupper())
    assert _pecas_na_cor(svg, desenho.AZUL_J1) == brancas
    assert _pecas_na_cor(svg, desenho.VERMELHO_J2) == len(tabela) - brancas
    # De brancas, a coluna a fica a esquerda.
    assert _x_da_letra(svg, "a") < _x_da_letra(svg, "h")


def test_quem_resolve_de_PRETAS_e_azul_e_fica_embaixo() -> None:
    """🔒 De pretas, as pretas sao azuis e o tabuleiro vira (a coluna h a esquerda)."""
    posicao = {**POSICAO_DO_MATE, "cor_da_pessoa": "preta"}
    svg = desenho.xadrez(posicao)
    tabela = desenho.ler_fen_xadrez(posicao["fen"])
    pretas = sum(1 for p in tabela.values() if p.islower())
    assert 'voce de pretas' in svg
    assert _pecas_na_cor(svg, desenho.AZUL_J1) == pretas
    assert _x_da_letra(svg, "h") < _x_da_letra(svg, "a")


def test_a_ESPIA_tem_o_selo_do_olho() -> None:
    svg = desenho.xadrez(POSICAO_DA_ESPIA)
    assert svg.count("<ellipse") == 1
    # Sem marca, sem selo.
    assert desenho.xadrez(POSICAO_DO_MATE).count("<ellipse") == 0


def test_o_ALVO_tem_o_selo_da_estrela() -> None:
    posicao = {**POSICAO_DA_ESPIA, "marcas": {"espia": "a1", "alvo": "d7"}}
    svg = desenho.xadrez(posicao)
    assert svg.count("<ellipse") == 1
    assert svg.count(f'fill="{desenho.OURO}"/>') >= 1  # a estrela


# ── As comidas e as marcas pela diferenca das FENs (sem regra) ──────────────


def test_o_EN_PASSANT_come_o_peao_que_nao_esta_no_destino() -> None:
    """O vetor `xadrez-espia-comida-en-passant`: o peao comido esta em e4, e o
    lance vai para e3."""
    antes = desenho.ler_fen_xadrez("4k3/8/8/8/3pP3/8/8/4K3 b - e3 0 1")
    depois = desenho.ler_fen_xadrez("4k3/8/8/8/8/4p3/8/4K3 w - - 0 2")
    assert desenho.comidas_no_lance_xadrez(antes, depois, "d4e3") == ["e4"]
    marcas = desenho.seguir_marcas_xadrez({"espia": "e4"}, antes, depois, "d4e3")
    assert marcas == {"espia": None}


def test_a_ESPIA_anda_com_a_peca() -> None:
    antes = desenho.ler_fen_xadrez("4k3/8/8/8/3p4/8/4P3/4K3 w - - 0 1")
    depois = desenho.ler_fen_xadrez("4k3/8/8/8/3pP3/8/8/4K3 b - e3 0 1")
    assert desenho.seguir_marcas_xadrez({"espia": "e2"}, antes, depois, "e2e4") == {
        "espia": "e4"
    }
    assert desenho.comidas_no_lance_xadrez(antes, depois, "e2e4") == []


def test_a_TORRE_espia_anda_junto_no_ROQUE() -> None:
    """O roque leva a torre sem ela ser a origem do lance (`e1g1`)."""
    antes = desenho.ler_fen_xadrez("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
    depois = desenho.ler_fen_xadrez("4k3/8/8/8/8/8/8/5RK1 b - - 1 1")
    assert desenho.seguir_marcas_xadrez({"espia": "h1"}, antes, depois, "e1g1") == {
        "espia": "f1"
    }
    # O roque nao come nada (a torre e do proprio lado).
    assert desenho.comidas_no_lance_xadrez(antes, depois, "e1g1") == []


def test_o_PEAO_espiao_promovido_continua_espiao() -> None:
    antes = desenho.ler_fen_xadrez("4k3/1P6/8/8/8/8/8/4K3 w - - 0 1")
    depois = desenho.ler_fen_xadrez("1Q2k3/8/8/8/8/8/8/4K3 b - - 0 1")
    assert desenho.seguir_marcas_xadrez({"espia": "b7"}, antes, depois, "b7b8q") == {
        "espia": "b8"
    }
    assert desenho.descrever_lance_xadrez(antes, "b7b8q", []) == "peao b7 > b8, vira dama"


def test_a_ESPIA_comida_por_captura_comum() -> None:
    antes = desenho.ler_fen_xadrez("4k3/8/8/8/8/2n5/1P6/4K3 b - - 0 1")
    depois = desenho.ler_fen_xadrez("4k3/8/8/8/8/8/1n6/4K3 w - - 0 2")
    assert desenho.comidas_no_lance_xadrez(antes, depois, "c3b2") == ["b2"]
    assert desenho.seguir_marcas_xadrez({"espia": "b2"}, antes, depois, "c3b2") == {
        "espia": None
    }
    assert desenho.descrever_lance_xadrez(antes, "c3b2", ["b2"]) == (
        "cavalo c3 > b2, come o(a) peao"
    )


# ── A fita do gabarito e a da partida ────────────────────────────────────────


def test_a_fita_do_GABARITO_sai_quadro_a_quadro() -> None:
    """🔒 A solucao real do 28/11: tres lances, o 3o e o objetivo, e o final."""
    quadros = desenho.fita_da_solucao("fen", POSICAO_DO_MATE, SOLUCAO_DO_MATE)
    assert [q["tipo"] for q in quadros] == ["lance", "lance", "lance", "final"]
    assert [q["titulo"] for q in quadros[:3]] == [
        "dama d3 > h3",
        "rei h7 > g7",
        "dama h3 > h6",
    ]
    # Quem resolve e o `+1`, mesmo sem `vez_de` na posicao do xadrez.
    assert [q["de_quem"] for q in quadros[:3]] == ["voce", "adversario", "voce"]
    assert [q["chave"] for q in quadros] == [False, False, True, False]
    assert all("tabuleiro de xadrez" in q["svg"] for q in quadros)


def test_a_fita_SEGUE_a_espia_quadro_a_quadro() -> None:
    """A torre espia sai de a1, e o selo vai com ela ate a posicao final."""
    solucao = {
        "lances": [{"n": 1, "lance": "a1c1", "jogador": 1}],
        "posicoes": [
            {"n": 1, "fen": "r3r1k1/pp1n1ppp/2pb4/3p4/3Pb3/2P1BN2/PP2BPPP/2R2RK1 b - - 1 1"}
        ],
        "lance_chave": None,
    }
    quadros = desenho.fita_da_solucao("fen", POSICAO_DA_ESPIA, solucao)
    assert [q["tipo"] for q in quadros] == ["lance", "final"]
    assert all(q["svg"].count("<ellipse") == 1 for q in quadros)


def test_a_fita_da_PARTIDA_de_quem_jogou() -> None:
    """O raio-x: o log guarda a FEN de ANTES de cada lance; o ultimo fica sem
    o de depois, e por isso sem o quadro final."""
    log = [
        {"nu_ordem": 1, "nu_jogador": 1, "co_lance": "d3h3",
         "co_fen_antes": POSICAO_DO_MATE["fen"]},
        {"nu_ordem": 2, "nu_jogador": 2, "co_lance": "h7g7",
         "co_fen_antes": SOLUCAO_DO_MATE["posicoes"][0]["fen"]},
        {"nu_ordem": 3, "nu_jogador": 1, "co_lance": "h3h6",
         "co_fen_antes": SOLUCAO_DO_MATE["posicoes"][1]["fen"]},
    ]
    quadros = desenho.fita_da_partida(
        "fen", POSICAO_DO_MATE, log, nu_lance_cumpre_desafio=3
    )
    assert [q["tipo"] for q in quadros] == ["lance", "lance", "lance"]
    assert [q["de_quem"] for q in quadros] == ["jogador", "CPU", "jogador"]
    assert quadros[2]["chave"] is True


# ── Dado torto nao derruba ───────────────────────────────────────────────────


def test_FEN_torta_vira_aviso_e_nao_500() -> None:
    svg = desenho.posicao("fen", {"jogo": "xadrez", "fen": ""})
    assert "sem FEN" in svg
    # Uma FEN com simbolo desconhecido desenha o que deu para ler.
    svg = desenho.posicao("fen", {"jogo": "xadrez", "fen": "4k3/8/8/8/8/8/8/4K2X w - - 0 1"})
    assert "tabuleiro de xadrez" in svg


def test_lance_TORTO_nao_derruba_a_fita() -> None:
    solucao = {
        "lances": [{"n": 1, "lance": "zz99", "jogador": 1}],
        "posicoes": [{"n": 1, "fen": POSICAO_DO_MATE["fen"]}],
    }
    quadros = desenho.fita_da_solucao("fen", POSICAO_DO_MATE, solucao)
    assert quadros[0]["titulo"] == "zz99"

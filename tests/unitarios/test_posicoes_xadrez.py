"""🔒 As posicoes dos desafios do xadrez e a escolha das pecas (T073 da spec 012).

O que se confere:

  1. a base: as 3 000 posicoes leem como FEN, e a leitura bate com o MOTOR
     (toda casa de onde ele diz haver lance tem uma peca da cor da vez);
  2. as regras de escolha: a espia nunca e o rei e e da pessoa; a que
     atravessa e torre, dama ou cavalo, fora da ultima fileira; o alvo e do
     adversario e nao e o rei; a classe comida tem pecas bastantes, ou fica de
     fora; a peca a proteger existe; o par da troca e permitido e existe;
  3. a posicao recusada (so os reis) nao serve a nenhum tipo que pede peca, e
     o sorteio a pula;
  4. o formato do contrato §1, e as pecas casam com a receita (T072): a frase
     monta, e o juiz le a cor e as marcas;
  5. a idempotencia: o mesmo sorteio da a mesma posicao, e dias diferentes
     variam;
  6. o motor aceita as marcas (uma marca em casa vazia seria `pedido_invalido`)
     e diz que a peca da espia e a classe escolhida.
"""

from __future__ import annotations

import random

import pytest

from job import posicoes_xadrez as px
from job.editorial import EDITORIAL, EDITORIAL_FORA_DO_AR, parametros_para_conferencia
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR

#: O editorial e as receitas do xadrez, no ar (os onze desde a T078) ou fora
#: dele (a troca): a posicao serve aos dois.
EDITORIAL_DO_XADREZ = {**EDITORIAL, **EDITORIAL_FORA_DO_AR}
RECEITAS_DO_XADREZ = {**RECEITAS, **RECEITAS_FORA_DO_AR}
from motores.xadrez import feitos_xadrez
from motores.xadrez.jogador_xadrez import JogadorXadrez, MotorDartIndisponivel

BASE = px.carregar_base()

#: Um FEN so com os reis: nenhuma peca para espiar, comer, proteger ou trocar.
SO_OS_REIS = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

#: Os K do editorial, que o `xadrez_comer_com` le.
PARAMETROS = {t: dict(EDITORIAL_DO_XADREZ[t][0].parametros) for t in px.TIPOS_DA_BASE}

#: Quantos dias (sementes) cada caso parametrizado percorre.
DIAS = range(40)


def _posicao(co_tipo: str, semente: int) -> px.PosicaoDoDesafioXadrez:
    """A posicao do dia [semente] para [co_tipo]."""
    return px.sortear(random.Random(semente), co_tipo=co_tipo, parametros=PARAMETROS[co_tipo])


@pytest.fixture(scope="module")
def motor():
    """O executavel, ou o pulo com a receita."""
    try:
        with JogadorXadrez() as jogador:
            yield jogador
    except MotorDartIndisponivel as erro:
        pytest.skip(f"sem o executavel do xadrez compilado: {erro}")


# ═══════════════════════════════════════════════════════════════════════════
# 1. A base e a leitura do FEN
# ═══════════════════════════════════════════════════════════════════════════


def test_a_base_tem_as_3000_e_todas_leem() -> None:
    assert len(BASE) == 3000
    for fen in BASE:
        pecas = px.pecas_do_fen(fen)
        # R-22: pelo menos 10 pecas alem dos reis, e um rei de cada cor.
        assert len(pecas) >= 12, fen
        assert sorted(p.cor for p in pecas.values() if p.peca == "rei") == ["branca", "preta"]
        assert px.cor_da_vez(fen) in ("branca", "preta")


def test_a_leitura_do_fen_casa_a_casa() -> None:
    pecas = px.pecas_do_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    assert pecas["e1"] == px.PecaNaCasa("e1", "branca", "rei")
    assert pecas["d8"] == px.PecaNaCasa("d8", "preta", "dama")
    assert pecas["e4"] == px.PecaNaCasa("e4", "branca", "peao")
    assert pecas["g8"].peca == "cavalo" and pecas["c1"].peca == "bispo"
    assert "e2" not in pecas
    assert len(pecas) == 32
    assert px.cor_da_vez("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1") == "preta"


@pytest.mark.parametrize(
    "fen",
    [
        "8/8/8/8/8/8/8 w - - 0 1",  # sete fileiras
        "4k3/8/8/8/8/8/8/4K2X w - - 0 1",  # letra desconhecida
        "4k3/8/8/8/8/8/8/4K4 w - - 0 1",  # fileira com nove casas
        "4k3/8/8/8/8/8/8/4K2 w - - 0 1",  # fileira com sete casas
    ],
)
def test_fen_torto_estoura(fen: str) -> None:
    """⚠️ Pular a letra em silencio sumiria com uma peca do tabuleiro."""
    with pytest.raises(ValueError):
        px.pecas_do_fen(fen)


def test_fen_sem_a_vez_estoura() -> None:
    with pytest.raises(ValueError):
        px.cor_da_vez("4k3/8/8/8/8/8/8/4K3 x - - 0 1")


def test_a_leitura_bate_com_o_motor(motor) -> None:
    """🔒 Toda casa de onde o motor diz haver lance tem uma peca da cor da vez
    na leitura daqui. E o que impede uma segunda escrita do FEN de divergir."""
    for fen in BASE[:: len(BASE) // 60]:
        estado = motor.estado(modalidade=px.MODALIDADE, fen_inicial=fen, lances=[])
        assert estado["vez"] == px.cor_da_vez(fen), fen
        pecas = px.pecas_do_fen(fen)
        for origem in estado["lances_legais"]:
            assert pecas[origem].cor == estado["vez"], (fen, origem)


# ═══════════════════════════════════════════════════════════════════════════
# 2. As regras de escolha
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_tipo", px.TIPOS_DA_ESPIA)
def test_a_espia_e_da_pessoa_e_nunca_o_rei(co_tipo: str) -> None:
    for dia in DIAS:
        posicao = _posicao(co_tipo, dia)
        js = posicao.js_posicao_inicial
        peca = px.pecas_do_fen(js["fen"])[js["marcas"]["espia"]]
        assert peca.cor == js["cor_da_pessoa"]
        assert peca.peca != "rei"
        assert posicao.pecas["espia"] == peca.peca


@pytest.mark.parametrize("co_tipo", sorted(px.TIPOS_EM_QUE_A_ESPIA_AGE))
def test_a_espia_que_age_nunca_e_um_peao(co_tipo: str) -> None:
    """Comer, dar xeque e comer o alvo: a espia nunca e um peao (T077)."""
    for dia in DIAS:
        js = _posicao(co_tipo, dia).js_posicao_inicial
        assert px.pecas_do_fen(js["fen"])[js["marcas"]["espia"]].peca != "peao"


def test_a_espia_que_age_nao_e_o_peao_mesmo_quando_ele_e_a_maioria() -> None:
    """⚠️ Escrito a mao: oito peoes e um cavalo. No "coma com a espia" a espia
    e sempre o cavalo; no "proteja a espia" o peao continua podendo ser ela."""
    fen = "4k3/8/8/8/8/8/PPPPPPPP/1N2K3 w - - 0 1"
    sorteadas_proteger = set()
    for semente in range(20):
        comer = px.posicao_do_desafio(
            random.Random(semente), co_tipo="xadrez_espia_comer", fen=fen,
            parametros={"capturas": 2, "lances": 12},
        )
        assert comer.pecas["espia"] == "cavalo"
        proteger = px.posicao_do_desafio(
            random.Random(semente), co_tipo="xadrez_espia_proteger", fen=fen,
            parametros={"lances": 15},
        )
        sorteadas_proteger.add(proteger.pecas["espia"])
    assert "peao" in sorteadas_proteger


def test_as_duas_espias_sao_da_pessoa_de_classes_diferentes_e_nenhuma_e_peao() -> None:
    """21/11/2026 (§8zzzz64): duas pecas da pessoa, em casas diferentes, de
    classes diferentes (a frase nomeia as duas), nunca o rei nem um peao."""
    for dia in DIAS:
        posicao = _posicao("xadrez_duas_espias", dia)
        js = posicao.js_posicao_inicial
        tabela = px.pecas_do_fen(js["fen"])
        primeira = tabela[js["marcas"]["espia"]]
        segunda = tabela[js["marcas"]["espia2"]]
        assert js["marcas"]["espia"] != js["marcas"]["espia2"]
        for peca in (primeira, segunda):
            assert peca.cor == js["cor_da_pessoa"]
            assert peca.peca not in ("rei", "peao")
        assert primeira.peca != segunda.peca
        assert (posicao.pecas["espia"], posicao.pecas["espia2"]) == (primeira.peca, segunda.peca)


def test_so_uma_classe_alem_dos_peoes_nao_serve_as_duas_espias() -> None:
    """⚠️ Escrito a mao: os peoes e dois cavalos. A 1a espia e um cavalo, e a
    2a nao tem classe diferente: a posicao nao serve (o sorteio tenta outra)."""
    fen = "4k3/8/8/8/8/8/PPPPPPPP/1N2K1N1 w - - 0 1"
    with pytest.raises(px.PosicaoNaoServe, match="segunda espia"):
        px.posicao_do_desafio(
            random.Random(3), co_tipo="xadrez_duas_espias", fen=fen,
            parametros={"capturas": 3, "lances": 12},
        )
    # Com um bispo a mais, serve: o cavalo e o bispo, em alguma ordem.
    fen = "4k3/8/8/8/8/8/PPPPPPPP/1N2KB2 w - - 0 1"
    posicao = px.posicao_do_desafio(
        random.Random(3), co_tipo="xadrez_duas_espias", fen=fen,
        parametros={"capturas": 3, "lances": 12},
    )
    assert {posicao.pecas["espia"], posicao.pecas["espia2"]} == {"cavalo", "bispo"}


def test_os_outros_tipos_da_espia_tem_uma_espia_so() -> None:
    """A 2a marca e so do `xadrez_duas_espias`: os outros cinco seguem iguais."""
    for co_tipo in px.TIPOS_DA_ESPIA:
        if co_tipo == "xadrez_duas_espias":
            continue
        for dia in range(10):
            js = _posicao(co_tipo, dia).js_posicao_inicial
            assert "espia2" not in js["marcas"], co_tipo


def test_a_espia_que_atravessa_e_torre_dama_ou_cavalo_e_ainda_nao_chegou() -> None:
    for dia in DIAS:
        js = _posicao("xadrez_espia_atravessar", dia).js_posicao_inicial
        peca = px.pecas_do_fen(js["fen"])[js["marcas"]["espia"]]
        assert peca.peca in ("torre", "dama", "cavalo")
        assert peca.casa[-1] != feitos_xadrez.ULTIMA_FILEIRA[js["cor_da_pessoa"]]


def test_a_peca_que_ja_esta_do_outro_lado_nao_e_espia_que_atravessa() -> None:
    """⚠️ Escrito a mao porque a base quase nunca tem uma peca da pessoa na
    ultima fileira (a mutacao que tirava o filtro passou pelos 40 dias).

    Brancas com a torre em a8 (ja do outro lado), um cavalo em b1 e um bispo em
    c1 (bispo nao atravessa): a unica espia possivel e o cavalo. E com as pretas
    o espelho: a torre em h1 ja chegou."""
    fen = "R3k3/8/8/8/8/8/8/1NB1K3 w - - 0 1"
    for semente in range(10):
        js = px.posicao_do_desafio(
            random.Random(semente), co_tipo="xadrez_espia_atravessar", fen=fen, parametros={}
        ).js_posicao_inicial
        assert js["marcas"]["espia"] == "b1"
    fen_pretas = "1nb1k3/8/8/8/8/8/8/4K2r b - - 0 1"
    for semente in range(10):
        js = px.posicao_do_desafio(
            random.Random(semente), co_tipo="xadrez_espia_atravessar", fen=fen_pretas, parametros={}
        ).js_posicao_inicial
        assert js["marcas"]["espia"] == "b8"


def test_o_alvo_e_do_adversario_e_nunca_o_rei() -> None:
    for dia in DIAS:
        posicao = _posicao("xadrez_espia_alvo", dia)
        js = posicao.js_posicao_inicial
        alvo = px.pecas_do_fen(js["fen"])[js["marcas"]["alvo"]]
        assert alvo.cor != js["cor_da_pessoa"]
        assert alvo.peca != "rei"
        assert posicao.pecas["alvo"] == alvo.peca
        assert js["marcas"]["alvo"] != js["marcas"]["espia"]


def test_o_alvo_fica_ao_alcance_da_espia() -> None:
    """Desde a regua de 9 dias: o alvo nao e torre, fica a ate 4 casas da espia,
    e o bispo espiao so tem alvo na cor das casas dele."""
    for dia in DIAS:
        js = _posicao("xadrez_espia_alvo", dia).js_posicao_inicial
        tabela = px.pecas_do_fen(js["fen"])
        espia, alvo = tabela[js["marcas"]["espia"]], tabela[js["marcas"]["alvo"]]
        assert alvo.peca not in px.PECAS_LONGE_DO_ALCANCE
        assert px.distancia_entre_casas(espia.casa, alvo.casa) <= px.DISTANCIA_MAXIMA_DO_ALVO
        if espia.peca == "bispo":
            assert px.cor_da_casa(espia.casa) == px.cor_da_casa(alvo.casa)


def test_o_bispo_espiao_nao_ganha_alvo_na_outra_cor() -> None:
    """⚠️ Escrito a mao: o bispo de c1 e a unica espia possivel; o cavalo preto
    de d3 esta numa casa da OUTRA cor, e o peao de e3 na mesma. O alvo so pode
    ser o peao (a torre de b2, da mesma cor e perto, tambem nao: torre nao e
    alvo)."""
    fen = "7k/8/8/8/8/3np3/1r6/2B4K w - - 0 1"
    for semente in range(20):
        js = px.posicao_do_desafio(
            random.Random(semente), co_tipo="xadrez_espia_alvo", fen=fen, parametros={"lances": 12}
        ).js_posicao_inicial
        assert js["marcas"] == {"espia": "c1", "alvo": "e3"}


def test_a_classe_comida_nunca_e_torre_nem_dama() -> None:
    """Com duas torres, duas damas e dois peoes do adversario, pedir 2 capturas
    so pode dar o peao como classe comida."""
    fen = "rq2k1qr/pp6/8/8/8/8/8/2B1K3 w - - 0 1"
    for semente in range(20):
        posicao = px.posicao_do_desafio(
            random.Random(semente), co_tipo="xadrez_comer_com", fen=fen, parametros={"capturas": 2}
        )
        assert posicao.js_posicao_inicial["classes"]["comida"] == "peao"


def test_as_classes_do_comer_com() -> None:
    """`come` e da pessoa; `comida` tem pelo menos K pecas do adversario."""
    k = PARAMETROS["xadrez_comer_com"]["capturas"]
    for dia in DIAS:
        posicao = _posicao("xadrez_comer_com", dia)
        js = posicao.js_posicao_inicial
        pecas = px.pecas_do_fen(js["fen"]).values()
        pessoa = js["cor_da_pessoa"]
        classes = js["classes"]
        assert any(p.cor == pessoa and p.peca == classes["come"] for p in pecas)
        assert classes["come"] in feitos_xadrez.TIPOS_COMIVEIS
        if "comida" in classes:
            dele = [p for p in pecas if p.cor != pessoa and p.peca == classes["comida"]]
            assert len(dele) >= k
        assert posicao.pecas == classes


def test_sem_classe_com_K_pecas_a_comida_fica_de_fora() -> None:
    """Com um peao so de cada classe do adversario, pedir 2 capturas deixa a
    `comida` de fora: o desafio vale para qualquer peca comida."""
    fen = "4k3/3p4/8/8/8/8/3N4/4K3 w - - 0 1"
    posicao = px.posicao_do_desafio(
        random.Random(1), co_tipo="xadrez_comer_com", fen=fen, parametros={"capturas": 2}
    )
    assert posicao.js_posicao_inicial["classes"] == {"come": "cavalo"}
    com_um = px.posicao_do_desafio(
        random.Random(1), co_tipo="xadrez_comer_com", fen=fen, parametros={"capturas": 1}
    )
    assert com_um.js_posicao_inicial["classes"] == {"come": "cavalo", "comida": "peao"}


def test_a_peca_a_proteger_e_uma_que_a_pessoa_tem() -> None:
    for dia in DIAS:
        posicao = _posicao("xadrez_nao_perder", dia)
        js = posicao.js_posicao_inicial
        pessoa = js["cor_da_pessoa"]
        assert any(
            p.cor == pessoa and p.peca == posicao.pecas["peca"]
            for p in px.pecas_do_fen(js["fen"]).values()
        )
        # O contrato §1 nao tem campo para ela: so a chegada a usa.
        assert set(js) == {"jogo", "modalidade", "fen", "cor_da_pessoa", "origem"}


def test_o_par_da_troca_e_permitido_e_existe() -> None:
    for dia in DIAS:
        posicao = _posicao("xadrez_troca", dia)
        js = posicao.js_posicao_inicial
        par = (js["troca"]["minha"], js["troca"]["dele"])
        assert par in px.PARES_DA_TROCA
        pecas = px.pecas_do_fen(js["fen"]).values()
        pessoa = js["cor_da_pessoa"]
        assert any(p.cor == pessoa and p.peca == par[0] for p in pecas)
        assert any(p.cor != pessoa and p.peca == par[1] for p in pecas)
        assert posicao.pecas == js["troca"]


def test_os_pares_sao_os_do_RF_XDR_202() -> None:
    """Bispo e cavalo (nas duas direcoes), torre e torre, dama e dama. Escrito
    aqui, e nao lido do modulo: o caso acima confere contra a lista dele."""
    assert set(px.PARES_DA_TROCA) == {
        ("bispo", "cavalo"),
        ("cavalo", "bispo"),
        ("torre", "torre"),
        ("dama", "dama"),
    }


def test_a_troca_so_com_o_par_que_existe() -> None:
    """So torres: o unico par possivel e torre por torre."""
    fen = "r3k3/8/8/8/8/8/8/R3K3 w - - 0 1"
    for semente in range(10):
        posicao = px.posicao_do_desafio(
            random.Random(semente), co_tipo="xadrez_troca", fen=fen, parametros={}
        )
        assert posicao.js_posicao_inicial["troca"] == {"minha": "torre", "dele": "torre"}


def test_bispo_de_um_lado_e_cavalo_do_outro_e_par_numa_direcao_so() -> None:
    """A pessoa com bispo e o adversario com cavalo: so "bispo por cavalo"."""
    fen = "4k3/8/2n5/8/8/2B5/8/4K3 w - - 0 1"
    posicao = px.posicao_do_desafio(
        random.Random(3), co_tipo="xadrez_troca", fen=fen, parametros={}
    )
    assert posicao.js_posicao_inicial["troca"] == {"minha": "bispo", "dele": "cavalo"}


# ═══════════════════════════════════════════════════════════════════════════
# 3. A posicao que nao serve
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "co_tipo",
    [t for t in px.TIPOS_DA_BASE if t not in ("xadrez_xeques_seguidos", "xadrez_sem_levar_xeque")],
)
def test_so_os_reis_nao_serve_a_quem_pede_peca(co_tipo: str) -> None:
    with pytest.raises(px.PosicaoNaoServe):
        px.posicao_do_desafio(
            random.Random(0), co_tipo=co_tipo, fen=SO_OS_REIS, parametros={"capturas": 1}
        )


@pytest.mark.parametrize("co_tipo", ["xadrez_xeques_seguidos", "xadrez_sem_levar_xeque"])
def test_os_tipos_sem_peca_servem_em_qualquer_posicao(co_tipo: str) -> None:
    js = px.posicao_do_desafio(
        random.Random(0), co_tipo=co_tipo, fen=SO_OS_REIS, parametros={}
    ).js_posicao_inicial
    assert set(js) == {"jogo", "modalidade", "fen", "cor_da_pessoa", "origem"}


def test_o_sorteio_pula_a_posicao_que_nao_serve() -> None:
    base = (SO_OS_REIS, "r3k3/8/8/8/8/8/8/R3K3 w - - 0 1")
    for semente in range(10):
        posicao = px.sortear(
            random.Random(semente), co_tipo="xadrez_troca", parametros={}, base=base
        )
        assert posicao.js_posicao_inicial["fen"] == base[1]


def test_sem_nenhuma_que_sirva_falha_alto() -> None:
    with pytest.raises(px.SemPosicaoXadrez):
        px.sortear(
            random.Random(0), co_tipo="xadrez_troca", parametros={}, base=(SO_OS_REIS,), tentativas=5
        )


def test_o_mate_nao_sai_da_base() -> None:
    """O `xadrez_dar_mate` vem do banco de problemas do Lichess (T074)."""
    with pytest.raises(ValueError, match="T074"):
        px.posicao_do_desafio(
            random.Random(0), co_tipo="xadrez_dar_mate", fen=BASE[0], parametros={}
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. O formato, e as pecas casam com a receita
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_tipo", px.TIPOS_DA_BASE)
def test_o_formato_do_contrato_e_a_frase_monta(co_tipo: str) -> None:
    posicao = _posicao(co_tipo, 7)
    js = posicao.js_posicao_inicial
    # A ordem das chaves e a do contrato §1 e dos vetores do juiz.
    chaves = list(js)
    assert chaves[:4] == ["jogo", "modalidade", "fen", "cor_da_pessoa"]
    assert chaves[-1] == "origem" and js["origem"] == "base_equilibrada"
    assert js["jogo"] == "xadrez" and js["modalidade"] == px.MODALIDADE
    # O juiz le a cor e as marcas da posicao publicada.
    assert feitos_xadrez.cor_da_pessoa(js) == px.cor_da_vez(js["fen"])
    assert set(feitos_xadrez.marcas_iniciais(js)) <= {"espia", "espia2", "alvo"}
    # As pecas, somadas aos numeros do editorial, montam a chegada e a frase.
    receita = RECEITAS_DO_XADREZ[co_tipo]
    parametros = {
        **parametros_para_conferencia(EDITORIAL_DO_XADREZ[co_tipo][0].parametros),
        **posicao.pecas,
    }
    receita.montar(parametros)
    valores = receita.valores_da_frase(parametros, "tex")
    for espaco in ("espia", "espia2", "alvo", "come", "comida", "peca", "minha", "dele"):
        if espaco in posicao.pecas:
            assert valores[espaco] == posicao.pecas[espaco]


# ═══════════════════════════════════════════════════════════════════════════
# 5. A idempotencia
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_tipo", px.TIPOS_DA_BASE)
def test_o_mesmo_dia_da_a_mesma_posicao_e_os_dias_variam(co_tipo: str) -> None:
    assert _posicao(co_tipo, 11) == _posicao(co_tipo, 11)
    fens = {_posicao(co_tipo, dia).js_posicao_inicial["fen"] for dia in DIAS}
    assert len(fens) > len(DIAS) // 2


# ═══════════════════════════════════════════════════════════════════════════
# 6. O motor aceita as marcas
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_tipo", px.TIPOS_DA_ESPIA)
def test_o_motor_segue_a_espia_que_escolhemos(co_tipo: str, motor) -> None:
    """🔒 Com as marcas no `aplicar`, o motor aceita (marca em casa vazia seria
    `pedido_invalido`). Quando a espia tem lance, o motor diz que quem andou e
    a classe que este modulo escolheu."""
    for dia in range(10):
        posicao = _posicao(co_tipo, dia)
        js = posicao.js_posicao_inicial
        estado = motor.estado(modalidade=px.MODALIDADE, fen_inicial=js["fen"], lances=[])
        casa = js["marcas"]["espia"]
        destinos = estado["lances_legais"].get(casa)
        if destinos:
            lance = casa + destinos[0]
            if casa in estado["promocoes"]:
                lance += "q"
        else:
            # A espia presa: anda outra peca, e ela tem de continuar marcada.
            origem, destinos = next(iter(estado["lances_legais"].items()))
            lance = origem + destinos[0]
            if origem in estado["promocoes"]:
                lance += "q"
        resposta = motor.aplicar(
            modalidade=px.MODALIDADE,
            fen_inicial=js["fen"],
            lances=[],
            lance=lance,
            marcas=js["marcas"],
        )
        if destinos and lance.startswith(casa):
            assert resposta["fatos"]["peca_movida"] == posicao.pecas["espia"]
        assert resposta["marcas"]["espia"]["casa"] is not None
        # A 2a espia (so nas duas espias) tambem e seguida pelo motor, pelo nome.
        if "espia2" in js["marcas"]:
            assert resposta["marcas"]["espia2"]["casa"] is not None

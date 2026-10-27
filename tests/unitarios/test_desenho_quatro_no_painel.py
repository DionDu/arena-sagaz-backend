"""O QUATRO EM LINHA DESENHADO NO PAINEL (27/10/2026).

Relato do dono: o dia 28/10/2026, o primeiro do Quatro no calendario do `des`,
respondia *Internal Server Error*. O Quatro grava o MESMO formato do Pontinhos
(`sequencia_lances`), e o desenho mandava a posicao para o Pontinhos, que tentou
ler `s4` como traco (`H_0_1`) e estourou.

O que estes casos protegem:

  · **o dia do Quatro abre** (o caso exato do relato);
  · **a posicao e a do arbitro**: cada peca desenhada e a que o `MotorQuatro`
    diz que esta la, nas cores dos jogadores;
  · **a fita do gabarito** sai quadro a quadro, com o aro de ouro no ultimo lance;
  · **uma sequencia torta vira aviso desenhado**, nunca um 500;
  · **o Pontinhos continua indo para o Pontinhos**;
  · **o feito realcado no quadro-chave** (T154): a figura que o juiz achou, em
    salvia, ou a linha vencedora do arbitro, na capsula de ouro - no gabarito e
    na partida de quem jogou, com a chegada vinda do banco.
"""

from __future__ import annotations

from dataclasses import replace

from api.desafios.painel import desenho, pagina
from motores.quatro.motor_quatro import MotorQuatro
from tests.unitarios.test_painel_curadoria import POSICAO_PONTINHOS, _desafio

#: A posicao publicada do desafio de 28/10/2026 no `des` (a do relato).
LANCES_DO_RELATO = "s4 s4 s4 s4 s5 s3 s3 s3 s3 s5 s2 s4 s2 s6 s6".split()

POSICAO_QUATRO = {
    "versao": 1,
    "vez_de": -1,
    "co_jogo": "quatro",
    "co_lances": "".join(LANCES_DO_RELATO),
    "co_modalidade": "tradicional",
    "sequencia_lances": LANCES_DO_RELATO,
    "co_formato_posicao": "sequencia_lances",
}

SOLUCAO_QUATRO = {
    "lances": [
        {"n": 1, "lance": "s4", "jogador": -1},
        {"n": 2, "lance": "s3", "jogador": 1},
        {"n": 3, "lance": "s6", "jogador": -1},
    ],
    "lance_chave": 3,
}


def _tabuleiro(lances: list[str]):
    motor = MotorQuatro("tradicional")
    return motor.tabuleiro(motor.estado_de_sequencia("".join(lances)))


def _pecas(svg: str, cor: str) -> int:
    """Quantos furos estao pintados com [cor]."""
    return svg.count(f'fill="{cor}" stroke="{desenho.BORDA_QUATRO}"')


def test_o_dia_do_QUATRO_abre_no_painel() -> None:
    """🔒 O relato: a pagina do dia com o Quatro respondia 500."""
    item = replace(
        _desafio(co_curadoria="aprovado", co_jogo="quatro", posicao=POSICAO_QUATRO,
                 co_formato="sequencia_lances"),
        js_solucao=SOLUCAO_QUATRO,
        co_modalidade="tradicional",
    )
    from datetime import date

    html = pagina.render_detalhe(
        pagina.DetalheDoDia(dt_dia=date(2026, 10, 28), desafio=item),
        dt_hoje=date(2026, 10, 27),
        dt_sugerida=date(2026, 10, 27),
        dt_fim_janela_baixada=date(2026, 10, 30),
    )
    assert 'aria-label="tabuleiro do Quatro em Linha"' in html


def test_as_pecas_sao_as_do_ARBITRO_e_QUEM_RESOLVE_e_azul() -> None:
    """🔒 Relato do dono (27/10/2026): as cores saiam trocadas.

    No app, quem resolve e sempre o J1 da tela (azul). Aqui a vez e do `-1` do
    motor: as 7 pecas dele sao as de quem resolve, e saem AZUIS; as 8 do `+1`
    (o personagem, que abriu) saem vermelhas.
    """
    svg = desenho.posicao("sequencia_lances", POSICAO_QUATRO, maior=True)
    tabuleiro = _tabuleiro(LANCES_DO_RELATO)
    mais = sum(p == 1 for coluna in tabuleiro.colunas for p in coluna)
    menos = sum(p == -1 for coluna in tabuleiro.colunas for p in coluna)
    assert (mais, menos) == (8, 7)  # 15 lances, o +1 abriu
    assert _pecas(svg, desenho.AZUL_J1) == menos
    assert _pecas(svg, desenho.VERMELHO_J2) == mais
    j1, j2 = mais, menos
    # E o resto dos 42 furos, vazio.
    assert _pecas(svg, desenho.PAPEL) == 42 - j1 - j2


def test_a_peca_cai_no_CHAO_e_nao_no_topo() -> None:
    """Um lance so (`s1`): a peca azul fica na fileira de BAIXO do desenho."""
    svg = desenho.quatro({"co_jogo": "quatro", "co_modalidade": "tradicional",
                          "sequencia_lances": ["s1"]})
    # Na miniatura a casa tem 26 px e a margem 6: o chao (linha 1) tem o
    # centro em y = 6 + 5,5 x 26 = 149.
    assert f'cy="149.0" r="9.9" fill="{desenho.AZUL_J1}"' in svg


def test_a_fita_do_gabarito_sai_QUADRO_A_QUADRO_com_o_aro_no_ultimo_lance() -> None:
    quadros = desenho.fita_da_solucao("sequencia_lances", POSICAO_QUATRO, SOLUCAO_QUATRO)
    assert [q["tipo"] for q in quadros] == ["inicio", "lance", "lance", "lance"]
    # Cada quadro tem uma peca a mais que o anterior.
    totais = [
        _pecas(q["svg"], desenho.AZUL_J1) + _pecas(q["svg"], desenho.VERMELHO_J2)
        for q in quadros
    ]
    assert totais == [15, 16, 17, 18]
    # O aro de ouro so nos quadros de lance, e um por quadro.
    assert [q["svg"].count(f'stroke="{desenho.ARO_QUATRO}"') for q in quadros] == [0, 1, 1, 1]
    # 🔒 E o contorno escuro por baixo: so o ouro sumia na madeira clara.
    assert [
        q["svg"].count(f'stroke="{desenho.CONTORNO_DO_ARO_QUATRO}" stroke-width="6"')
        for q in quadros
    ] == [0, 1, 1, 1]
    # Quem resolve e o `vez_de` (-1): o 1o lance e "voce", e a peca dele e AZUL
    # (o aro de ouro fica em volta dela).
    assert quadros[1]["de_quem"] == "voce"
    novas_azuis = [_pecas(q["svg"], desenho.AZUL_J1) for q in quadros]
    assert novas_azuis == [7, 8, 8, 9]
    assert quadros[3]["chave"]


def test_sequencia_TORTA_vira_aviso_e_nao_500() -> None:
    """Sete pecas numa coluna de seis: o arbitro recusa, e o painel mostra o motivo."""
    torta = {"co_jogo": "quatro", "co_modalidade": "tradicional",
             "sequencia_lances": ["s1"] * 7}
    svg = desenho.posicao("sequencia_lances", torta)
    assert "Quatro:" in svg and "tabuleiro do Quatro" not in svg


def test_modalidade_DESCONHECIDA_vira_aviso_e_nao_500() -> None:
    svg = desenho.posicao(
        "sequencia_lances", {**POSICAO_QUATRO, "co_modalidade": "pop_out_futuro"}
    )
    assert "Quatro:" in svg


def test_sem_a_lista_le_a_sequencia_CONCATENADA() -> None:
    sem_lista = {k: v for k, v in POSICAO_QUATRO.items() if k != "sequencia_lances"}
    assert desenho.posicao("sequencia_lances", sem_lista) == desenho.posicao(
        "sequencia_lances", POSICAO_QUATRO
    )


def test_o_PONTINHOS_continua_indo_para_o_pontinhos() -> None:
    """O controle: sem `co_jogo: quatro`, o mesmo formato e o do Pontinhos."""
    svg = desenho.posicao("sequencia_lances", POSICAO_PONTINHOS)
    assert "tabuleiro do Quatro" not in svg
    assert desenho.posicao("sequencia_lances", POSICAO_PONTINHOS) == desenho.pontinhos(
        POSICAO_PONTINHOS
    )


def test_a_madeira_e_a_CLARA_do_aplicativo() -> None:
    """🔒 Pedido do dono (27/10/2026): o tabuleiro saia muito escuro.

    A placa e a borda sao as do tema claro do app; a madeira escura dos outros
    jogos nao aparece no desenho do Quatro.
    """
    svg = desenho.posicao("sequencia_lances", POSICAO_QUATRO, maior=True)
    assert f'fill="{desenho.PLACA_QUATRO}"' in svg
    assert desenho.MADEIRA not in svg and desenho.MADEIRA_ESC not in svg


def test_a_FIGURA_e_desenhada_com_os_quatro_simbolos() -> None:
    """Pedido do dono: *"Forme a figura. Que figura e esta?"*"""
    svg = desenho.figura_quatro(["XO.", "_XX"])
    assert svg.count(f'fill="{desenho.AZUL_J1}"') == 3  # X: quem resolve
    assert svg.count(f'fill="{desenho.VERMELHO_J2}"') == 1  # O: o adversario
    assert svg.count(f'fill="{desenho.PAPEL}"') == 1  # _: casa vazia
    assert svg.count('stroke-dasharray="2 3"') == 1  # .: qualquer coisa


def test_o_cartao_do_desafio_de_FIGURA_mostra_o_desenho() -> None:
    item = replace(
        _desafio(co_curadoria="aprovado", co_jogo="quatro", posicao=POSICAO_QUATRO,
                 co_formato="sequencia_lances"),
        co_tipo_desafio="quatro_figura",
        co_chave_objetivo="desafioObjetivoQuatroFigura",
        js_objetivo={"figura": ["XX.", ".XX"], "lances": 7, "personagem": "magno"},
        js_solucao=SOLUCAO_QUATRO,
        co_modalidade="tradicional",
    )
    html = pagina._frase_do_desafio(item)
    assert 'aria-label="a figura a formar"' in html
    assert "azul = voce" in html


# ═══════════════════════════════════════════════════════════════════════════
# T154: o feito realcado no quadro do lance que cumpre o objetivo
# ═══════════════════════════════════════════════════════════════════════════
#
# Pedido do dono (27/10/2026): no quadro-chave da fita, contornar a FIGURA
# formada (a busca do juiz) ou a LINHA vencedora (o arbitro do Quatro). O Z e o
# golpe duplo sao desafios reais do `des` (27/10/2026); a imagem conferida com
# o Chrome headless esta descrita no historico do backend.

#: O "Forme um Z" do `des`: a pessoa e o `-1` do motor (`vez_de`), e o Z se
#: forma no 9o lance do gabarito, embaixo e a direita.
POSICAO_DO_Z = {
    "versao": 1,
    "vez_de": -1,
    "co_jogo": "quatro",
    "co_modalidade": "tradicional",
    "sequencia_lances": "s4 s3 s4 s2 s4 s4 s2 s3 s4 s5 s3 s3 s3".split(),
}
SOLUCAO_DO_Z = {
    "lances": [
        # O gabarito comeca pela pessoa (`-1`): os lances impares sao dela.
        {"n": n, "lance": lance, "jogador": -1 if n % 2 else 1}
        for n, lance in enumerate("s5 s5 s2 s2 s6 s2 s7 s4 s6".split(), start=1)
    ],
    "lance_chave": 9,
}
CHEGADA_DO_Z = {
    "versao": 1,
    "janela": {"tipo": "lances_do_jogador", "n": 7},
    "clausulas": [{"tipo": "figura", "desenho": ["XX.", ".XX"], "espelhar": False}],
}
#: As casas do Z no arbitro, `(coluna, linha)` com a linha 1 embaixo: a fileira
#: de cima do desenho (`XX.`) na linha 2, a de baixo (`.XX`) na linha 1.
CASAS_DO_Z = {(5, 2), (6, 2), (6, 1), (7, 1)}

#: Uma vitoria escrita a mao: o J1 tem 1, 2 e 3 no chao, e `s4` fecha a linha.
POSICAO_DA_VITORIA = {
    "versao": 1,
    "vez_de": 1,
    "co_jogo": "quatro",
    "co_modalidade": "tradicional",
    "sequencia_lances": "s1 s1 s2 s2 s3 s3".split(),
}
SOLUCAO_DA_VITORIA = {"lances": [{"n": 1, "lance": "s4", "jogador": 1}], "lance_chave": 1}
CHEGADA_DA_VITORIA = {
    "versao": 1,
    "janela": {"tipo": "partida"},
    "clausulas": [{"tipo": "medida", "chave": "vitoria", "comparador": "igual", "valor": 1}],
}

#: Uma forma do contorno da figura, na salvia (a faixa ou o veu).
SALVIA = f'fill="{desenho.CONTORNO_DA_FIGURA_QUATRO}"'
#: A capsula da linha: o caminho de ouro (o contorno escuro vem por baixo).
CAPSULA = f'fill="none" stroke="{desenho.ARO_QUATRO}" stroke-width="3" stroke-linejoin'


def _feito(
    posicao: dict, lances: list[str], chegada: dict | None, pessoa: int | None = None
) -> desenho.FeitoNoQuatro:
    """O feito do tabuleiro depois de [lances], do lado de [pessoa] (o
    `vez_de` da posicao, se nao vier)."""
    motor = MotorQuatro("tradicional")
    tabuleiro = motor.tabuleiro(
        motor.estado_de_sequencia("".join(posicao["sequencia_lances"] + lances))
    )
    lado = posicao["vez_de"] if pessoa is None else pessoa
    return desenho.feito_no_quatro(motor, tabuleiro, chegada, lado)


def test_o_feito_da_FIGURA_sao_as_casas_que_o_JUIZ_achou() -> None:
    """🔒 As casas contornadas sao as da busca do juiz, no lado de quem resolve."""
    lances = [l["lance"] for l in SOLUCAO_DO_Z["lances"]]
    feito = _feito(POSICAO_DO_Z, lances, CHEGADA_DO_Z)
    assert set(feito.figura) == CASAS_DO_Z
    assert feito.linhas == ()
    # 🔒 O LADO: julgado como o `+1` (o personagem), o Z nao esta la. Quem
    # resolve e o `vez_de`, o mesmo `jogador` com que o job julga.
    assert _feito(POSICAO_DO_Z, lances, CHEGADA_DO_Z, pessoa=1).figura == ()


def test_a_fita_contorna_a_figura_SO_no_quadro_chave() -> None:
    quadros = desenho.fita_da_solucao(
        "sequencia_lances", POSICAO_DO_Z, SOLUCAO_DO_Z, js_chegada=CHEGADA_DO_Z
    )
    assert [q["chave"] for q in quadros].index(True) == 9
    # O Z tem 4 casas e 3 emendas: (5,2)-(6,2) e (6,1)-(7,1) na horizontal, e
    # (6,2)-(6,1) na vertical. Sao 7 formas em cada uma das duas camadas
    # salvia (a faixa e o veu), so no quadro-chave.
    assert [q["svg"].count(SALVIA) for q in quadros] == [0] * 9 + [2 * (4 + 3)]
    # 🔒 O contorno vem ANTES das pecas: e um anel em volta das casas, e as
    # pecas ficam por cima dele (pintado depois, cobriria o Z).
    svg = quadros[9]["svg"]
    assert svg.index(SALVIA) < svg.index("<circle")
    # 🔒 A emenda VERTICAL cai entre (6,2) e (6,1): do centro da de cima
    # (y = 6 + (6 - 2 + 0,5) x 40 = 186) uma casa para BAIXO. Na faixa salvia o
    # quadrado cresce 2 (o "fora") + 2,8 (a grossura): x = 226 - 20 - 4,8.
    assert f'<rect x="201.2" y="186.0" width="49.6" height="40.0" {SALVIA}/>' in svg
    # A figura nao e linha: nenhuma capsula.
    assert all(CAPSULA not in q["svg"] for q in quadros)


def test_o_feito_da_VITORIA_e_a_linha_do_ARBITRO() -> None:
    feito = _feito(POSICAO_DA_VITORIA, ["s4"], CHEGADA_DA_VITORIA)
    assert feito.figura == ()
    assert feito.linhas == (((1, 1), (2, 1), (3, 1), (4, 1)),)
    quadros = desenho.fita_da_solucao(
        "sequencia_lances", POSICAO_DA_VITORIA, SOLUCAO_DA_VITORIA,
        js_chegada=CHEGADA_DA_VITORIA,
    )
    assert [q["svg"].count(CAPSULA) for q in quadros] == [0, 1]
    # 🔒 A capsula passa em volta das pecas do chao: do centro da coluna 1
    # (x = 6 + 0,5 x 40 = 26) ao da 4 (146), na linha 1 (y = 6 + 5,5 x 40 =
    # 226), afastada do eixo pelo raio da peca mais 4 (15,2 + 4 = 19,2).
    assert "M 26.0 245.2 L 146.0 245.2" in quadros[1]["svg"]
    # A capsula vem DEPOIS de todas as pecas: por cima delas e da placa.
    svg = quadros[1]["svg"]
    assert svg.rindex("<circle") < svg.index(CAPSULA)
    # 🔒 Sem a chegada (um desafio que nao a trouxe), a linha continua
    # contornada: a vitoria e do arbitro, e nao depende do objetivo.
    sem_chegada = desenho.fita_da_solucao(
        "sequencia_lances", POSICAO_DA_VITORIA, SOLUCAO_DA_VITORIA
    )
    assert [q["svg"].count(CAPSULA) for q in sem_chegada] == [0, 1]


def test_o_GOLPE_DUPLO_contorna_as_DUAS_linhas() -> None:
    """Um lance que fecha duas linhas: o arbitro entrega as duas, e as duas
    ganham a capsula (o caso real do `des`, `quatro_golpe_duplo`)."""
    posicao = {
        "versao": 1, "vez_de": -1, "co_jogo": "quatro", "co_modalidade": "tradicional",
        "sequencia_lances": (
            "s4 s4 s4 s4 s5 s3 s3 s3 s3 s5 s7 s6 s7 s5 s3 s5 s5 s4 s7 s7 s3 s1 s5 s1 s7"
        ).split(),
    }
    lances = "s4 s1 s1 s2 s1 s6 s1 s6 s6".split()
    chegada = {
        "versao": 1, "janela": {"tipo": "partida"},
        "clausulas": [
            {"tipo": "medida", "chave": "vitoria", "comparador": "igual", "valor": 1},
            {"tipo": "medida", "chave": "linhas_no_lance_final",
             "comparador": "maior_ou_igual", "valor": 2},
        ],
    }
    assert len(_feito(posicao, lances, chegada).linhas) == 2
    solucao = {
        "lances": [{"n": n, "lance": l, "jogador": -1 if n % 2 else 1}
                   for n, l in enumerate(lances, start=1)],
        "lance_chave": 9,
    }
    quadros = desenho.fita_da_solucao("sequencia_lances", posicao, solucao, js_chegada=chegada)
    assert quadros[9]["svg"].count(CAPSULA) == 2


def test_quadro_chave_SEM_figura_e_SEM_linha_nao_realca_nada() -> None:
    """O "Encoste" se cumpre no meio da partida: nao ha o que contornar."""
    assert _feito(POSICAO_DA_VITORIA, ["s5"], CHEGADA_DA_VITORIA) == desenho.FeitoNoQuatro()


def test_figura_que_NAO_esta_no_tabuleiro_nao_contorna_o_vazio() -> None:
    """Um gabarito torto (a figura pedida nao se formou): sem contorno de
    figura, e a linha vencedora, havendo, continua contornada."""
    feito = _feito(POSICAO_DA_VITORIA, ["s4"], CHEGADA_DO_Z)
    assert feito.figura == ()
    assert feito.linhas == (((1, 1), (2, 1), (3, 1), (4, 1)),)


def test_chegada_INVALIDA_nao_derruba_o_painel() -> None:
    """Uma chegada que o juiz recusaria: o quadro sai, sem o realce da figura."""
    torta = {"versao": 99, "janela": {"tipo": "partida"}, "clausulas": []}
    feito = _feito(POSICAO_DO_Z, [l["lance"] for l in SOLUCAO_DO_Z["lances"]], torta)
    assert feito.figura == ()


def test_a_PARTIDA_de_quem_jogou_tambem_realca_o_feito() -> None:
    """O raio-x: o quadro do `nu_lance_cumpre_desafio` leva o contorno, e SO
    ele.

    ⚠️ A pessoa pode seguir jogando depois do objetivo (RF-DES-213): aqui o
    personagem joga `s1` no 10o lance, e o Z continua no tabuleiro. O contorno
    marca o INSTANTE do feito, e nao "onde o Z esta" em todo quadro seguinte.
    """
    lances = [l["lance"] for l in SOLUCAO_DO_Z["lances"]] + ["s1"]
    log = [
        # No log o jogador vem 1/2; o 2 e o `-1`, aqui a pessoa.
        {"nu_ordem": n, "nu_jogador": 2 if n % 2 else 1, "co_lance": lance}
        for n, lance in enumerate(lances, start=1)
    ]
    quadros = desenho.fita_da_partida(
        "sequencia_lances", POSICAO_DO_Z, log,
        nu_lance_cumpre_desafio=9, js_chegada=CHEGADA_DO_Z,
    )
    assert [SALVIA in q["svg"] for q in quadros] == [False] * 9 + [True, False]
    # O Z ainda esta la no 10o quadro: e a escolha, e nao a falta dele.
    assert set(_feito(POSICAO_DO_Z, lances, CHEGADA_DO_Z).figura) == CASAS_DO_Z


def test_a_pagina_passa_a_CHEGADA_do_desafio() -> None:
    """🔒 O cartao do dia le `js_chegada` do desafio."""
    item = replace(
        _desafio(co_curadoria="aprovado", co_jogo="quatro", posicao=POSICAO_DO_Z,
                 co_formato="sequencia_lances"),
        js_solucao=SOLUCAO_DO_Z,
        co_modalidade="tradicional",
        js_chegada=CHEGADA_DO_Z,
    )
    assert SALVIA in pagina._fita_da_solucao(item)
    assert SALVIA not in pagina._fita_da_solucao(replace(item, js_chegada={}))


def test_o_raio_x_da_pagina_passa_a_CHEGADA() -> None:
    """🔒 O raio-x da pagina le `js_chegada` da tentativa."""
    from uuid import uuid4

    from api.desafios.painel.estatisticas import RaioX

    raio = RaioX(
        id_tentativa=uuid4(), id_usuario=uuid4(), co_usuario=None, no_exibicao="Ana",
        nu_sequencia=1, ic_resolveu=True, nu_tempo_ms=1000, dh_inicio=None,
        co_formato_posicao="sequencia_lances", js_posicao_inicial=POSICAO_DO_Z,
        nu_lance_cumpre_desafio=9,
        lances=tuple(
            {"nu_ordem": n, "nu_jogador": 2 if n % 2 else 1, "co_lance": l["lance"]}
            for n, l in enumerate(SOLUCAO_DO_Z["lances"], start=1)
        ),
        js_chegada=CHEGADA_DO_Z,
    )
    assert SALVIA in pagina.render_raio_x(raio)
    assert SALVIA not in pagina.render_raio_x(replace(raio, js_chegada={}))


def test_o_banco_entrega_a_CHEGADA_ao_painel() -> None:
    """🔒 Toda coluna do `DesafioNoPainel` sai da consulta, e o raio-x le a
    chegada. Sem isto o campo novo ficaria no valor padrao (vazio) em
    producao, e so o teste, que monta o objeto a mao, teria o contorno."""
    from dataclasses import fields

    from api.desafios.painel import estatisticas, repositorio

    colunas = repositorio._COLUNAS_DO_DESAFIO
    faltando = [
        f.name for f in fields(repositorio.DesafioNoPainel)
        if f.name != "medicoes" and f".{f.name}" not in colunas
    ]
    assert faltando == []
    assert "d.js_chegada" in estatisticas._SQL_RAIO_X


def test_o_RAIO_X_carrega_a_chegada_da_linha_do_banco() -> None:
    """O `raio_x` passa o `js_chegada` do cabecalho para o `RaioX`."""
    import asyncio
    from uuid import uuid4

    from api.desafios.painel import estatisticas

    class EstatisticasFalsas(estatisticas.EstatisticasDoDia):
        """So o cabecalho do raio-x; as outras consultas voltam vazias."""

        async def _linhas(self, sql, parametros):  # noqa: ANN001
            if sql == estatisticas._SQL_RAIO_X:
                return [{
                    "id_tentativa": uuid4(), "id_usuario": uuid4(), "id_partida": uuid4(),
                    "co_formato_posicao": "sequencia_lances",
                    "js_posicao_inicial": POSICAO_DO_Z, "js_chegada": CHEGADA_DO_Z,
                }]
            return []

    raio = asyncio.run(EstatisticasFalsas(None).raio_x(uuid4()))  # type: ignore[arg-type]
    assert raio is not None and raio.js_chegada == CHEGADA_DO_Z

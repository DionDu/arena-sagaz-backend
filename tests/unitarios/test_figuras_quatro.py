"""T147 da spec 010 - o catalogo de figuras do "Forme a figura" (`job/figuras_quatro.py`).

Quatro partes:

  1. **a tabela da proposta, por extenso**: pecas, apoios, maior linha e
     lugares de cada figura, copiados de `PROPOSTA-revisao-catalogo-quatro.md`
     §2. ⚠️ Os numeros estao escritos aqui, e nao lidos do catalogo: um caso que
     lesse as proprias contas passaria com qualquer figura;
  2. **as recusas**: o catalogo inteiro passa, e as figuras que a proposta tirou
     (a seta, o triangulo com base so da pessoa, o "n" e o "i" com o vao vazio)
     sao recusadas pelo motivo de cada uma;
  3. **a distancia**, em tabuleiros escritos a mao;
  4. **cada figura se forma numa partida de verdade**: o arbitro joga uma fita
     que monta a figura sem ninguem vencer, e o juiz de producao diz "cumpriu"
     com o prazo exato e "nao cumpriu" com um lance a menos. E o que prova que a
     figura existe de pe no 7 x 6, e nao so no papel.
"""

from __future__ import annotations

import pytest

from job import editorial as editorial_mod
from job import figuras_quatro as fq
from job.tipos_de_desafio import RECEITAS_FORA_DO_AR
from motores.juiz import julgar_desafio
from motores.nucleo.medidor_por_fita import CUMPRIU, NAO_CUMPRIU
from motores.quatro import contrato_quatro
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro, TabuleiroQuatro

MODALIDADE = contrato_quatro.modalidades_declaradas()[0]
DIMENSOES = MotorQuatro(MODALIDADE).regras.dimensoes


# ═══════════════════════════════════════════════════════════════════════════
# 1. A tabela da proposta, por extenso
# ═══════════════════════════════════════════════════════════════════════════

#: figura: (X, O, apoios desde o chao, maior linha da pessoa, lugares no 7 x 6).
#: Copiado da tabela "As figuras, uma a uma" da proposta.
TABELA_DA_PROPOSTA = {
    "t": (5, 0, 4, 3, 20),
    "mais": (5, 0, 2, 3, 20),
    "z": (4, 0, 1, 2, 25),
    "igual": (4, 0, 2, 2, 24),
    "losango": (4, 1, 2, 2, 20),
    "c": (5, 1, 0, 3, 24),
    "i": (3, 1, 0, 2, 21),
    "quadrado": (4, 0, 0, 2, 30),
    "l": (4, 0, 0, 3, 24),
    "v_grande": (5, 0, 6, 3, 12),
    "xis": (5, 0, 3, 3, 20),
}


def test_o_catalogo_tem_as_onze_da_proposta_e_as_familias_certas() -> None:
    """O primeiro lote (sete), os dois controles e os dois do teto."""
    assert set(fq.FIGURAS_QUATRO) == set(TABELA_DA_PROPOSTA)
    familias = {nome: f.familia for nome, f in fq.FIGURAS_QUATRO.items()}
    assert {n for n, fam in familias.items() if fam == "lote"} == {
        "t", "mais", "z", "igual", "losango", "c", "i",
    }
    assert {n for n, fam in familias.items() if fam == "controle"} == {"quadrado", "l"}
    assert {n for n, fam in familias.items() if fam == "teto"} == {"v_grande", "xis"}


@pytest.mark.parametrize("nome", sorted(TABELA_DA_PROPOSTA))
def test_as_contas_batem_com_a_tabela_da_proposta(nome: str) -> None:
    x, o, apoios, maior, lugares = TABELA_DA_PROPOSTA[nome]
    desenho = fq.FIGURAS_QUATRO[nome].desenho
    assert fq.pecas(desenho) == (x, o)
    assert fq.apoios_desde_o_chao(desenho) == apoios
    assert fq.maior_linha_da_pessoa(desenho) == maior
    assert fq.lugares(desenho, DIMENSOES) == lugares


# ═══════════════════════════════════════════════════════════════════════════
# 2. As recusas
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("nome", sorted(fq.FIGURAS_QUATRO))
def test_toda_figura_do_catalogo_passa_nas_cinco_recusas(nome: str) -> None:
    assert fq.recusas(fq.FIGURAS_QUATRO[nome], DIMENSOES) == []


@pytest.mark.parametrize(
    "desenho, trecho",
    [
        # As que a proposta tirou, cada uma pelo seu motivo ("As que ficaram de fora").
        ([".X.", "XXX", ".X.", ".X."], "em linha"),           # a seta: a haste e uma linha de 4
        (["..X..", ".XOX.", "XXXXX"], "em linha"),           # o triangulo com base so da pessoa
        (["XXX", "X_X"], "casa vazia embaixo"),              # o "n" com o vao vazio
        (["X", "_", "X", "X"], "casa vazia embaixo"),        # o "i" com o vao vazio
        # E as outras tres.
        (["O", "X"], "ultima peca da coluna"),               # so o adversario poderia fecha-la
        (["X.X.X.X.X"], "nao cabe"),                         # nove de largura
        # A linha de quatro na diagonal que DESCE para a direita: a direcao que
        # nenhuma figura do catalogo separa das outras (o xis e o V grande tem
        # as duas diagonais de tres).
        (["...X", "..X.", ".X..", "X..."], "em linha"),
        (["XA"], "fora do formato"),
    ],
)
def test_o_que_a_proposta_tirou_e_recusado(desenho: list[str], trecho: str) -> None:
    figura = fq.FiguraQuatro("teste", tuple(desenho), False, "lote")
    motivos = fq.recusas(figura, DIMENSOES)
    assert any(trecho in m for m in motivos), motivos


def test_a_clausula_da_figura_e_a_do_juiz() -> None:
    """O desenho viaja inteiro na chegada, e a receita o le do catalogo."""
    parametros = editorial_mod.parametros_efetivos(
        {"figura": "losango", "folga": 2}, encostadas=4, distancia=4
    )
    assert parametros["lances"] == 6
    assert parametros[editorial_mod.DISTANCIA_DA_FIGURA] == 4
    chegada = RECEITAS_FORA_DO_AR["quatro_figura"].montar(parametros)
    assert chegada["janela"] == {"tipo": "lances_do_jogador", "n": 6}
    assert chegada["clausulas"] == [
        {"tipo": "figura", "desenho": [".X.", "XOX", ".X."], "espelhar": False}
    ]


def test_o_prazo_sem_a_distancia_falha_alto() -> None:
    with pytest.raises(TypeError, match="distancia"):
        editorial_mod.parametros_efetivos({"figura": "t", "folga": 1}, encostadas=4)


# ═══════════════════════════════════════════════════════════════════════════
# 3. A distancia
# ═══════════════════════════════════════════════════════════════════════════


def _tabuleiro(colunas: dict[int, str], vez: int = 1) -> TabuleiroQuatro:
    """Um tabuleiro escrito por coluna, de BAIXO para cima: `1` J1, `2` J2.

    ⚠️ Montado direto, sem passar pelo arbitro: a distancia so le as casas e a
    vez, e assim o caso escreve posicoes que nenhuma partida de verdade teria
    (uma linha inteira de uma cor so) quando precisa.
    """
    pilhas = tuple(
        tuple(1 if c == "1" else -1 for c in colunas.get(j, ""))
        for j in range(1, DIMENSOES.largura + 1)
    )
    return TabuleiroQuatro(colunas=pilhas, vez=vez, lances_jogados=sum(map(len, pilhas)))


def _distancia(nome: str, tabuleiro: TabuleiroQuatro) -> int | None:
    return fq.distancia(fq.FIGURAS_QUATRO[nome], tabuleiro, DIMENSOES)


def test_no_tabuleiro_vazio_a_distancia_e_pecas_mais_apoios() -> None:
    """Por extenso: o quadrado 4, o L 4, o T 5 + 4 apoios, o "i" 3 + 1 do adversario."""
    vazio = _tabuleiro({})
    assert _distancia("quadrado", vazio) == 4
    assert _distancia("l", vazio) == 4
    assert _distancia("t", vazio) == 9
    assert _distancia("i", vazio) == 4
    assert _distancia("v_grande", vazio) == 11


def test_a_peca_da_pessoa_encurta_e_a_do_adversario_atrapalha() -> None:
    # O J1 com duas na coluna 1 e uma na 2: falta UMA casa para o quadrado.
    perto = _tabuleiro({1: "11", 2: "1", 7: "22", 6: "2"})
    assert _distancia("quadrado", perto) == 1
    # O mesmo, do lado do J2: as pecas do J1 sao do adversario, e o quadrado
    # dele mais perto e o das colunas 6 e 7 (faltam duas).
    assert _distancia("quadrado", _tabuleiro({1: "11", 2: "1", 7: "22", 6: "2"}, vez=-1)) == 1


def test_o_apoio_que_falta_conta() -> None:
    # Com o J2 embaixo nas colunas 1 a 7, o quadrado do J1 nao cabe na linha 1,
    # e na linha 2 os apoios ja estao la: 4. Sem a linha de baixo, tambem 4 (no
    # chao). Mas com o J2 so nas colunas impares, todo lugar no chao tem um
    # conflito, e o melhor lugar e na linha 2, com UM apoio a pagar.
    cheio_embaixo = _tabuleiro({j: "2" for j in range(1, 8)})
    assert _distancia("quadrado", cheio_embaixo) == 4
    impares = _tabuleiro({1: "2", 3: "2", 5: "2", 7: "2"})
    assert _distancia("quadrado", impares) == 5


def test_a_casa_O_ja_ocupada_pelo_adversario_encurta() -> None:
    # O "i": haste do J1 nas linhas 1 e 2 da coluna 4, a peca do J2 em cima:
    # falta so o pingo.
    assert _distancia("i", _tabuleiro({4: "112"})) == 1
    # Com a peca do J1 onde o desenho pede a do adversario (a linha 3), o lugar
    # no chao nao serve: a haste SOBE para as linhas 2 e 3, e faltam o "O" na
    # 4 e o pingo na 5. Sao 2, e nao 1.
    assert _distancia("i", _tabuleiro({4: "111"})) == 2


def test_sem_lugar_livre_de_conflito_a_distancia_e_None() -> None:
    """A linha de baixo toda do adversario: a figura que pede `X` no chao em toda
    coluna, de altura 6, nao cabe em lugar nenhum."""
    alta = fq.FiguraQuatro("alta", ("X", "O", "X", "O", "X", "O"), False, "lote")
    pecas_do_j1_embaixo = _tabuleiro({j: "1" for j in range(1, 8)})
    assert fq.distancia(alta, pecas_do_j1_embaixo, DIMENSOES) is None


def test_a_casa_vazia_do_desenho_ocupada_e_conflito() -> None:
    """O U so oco (`X_X` / `XXX`): no canto, o miolo tem a peca do J2, e esse
    lugar nao serve. O melhor e nas colunas 3 a 5 (faltam tres casas), e nao
    zero - quem ignorasse o `_` daria a figura por formada."""
    u_oco = fq.FiguraQuatro("u_oco", ("X_X", "XXX"), False, "lote")
    quase = _tabuleiro({1: "11", 2: "12", 3: "11"})
    assert fq.distancia(u_oco, quase, DIMENSOES) == 3


def test_o_espelho_so_conta_quando_a_figura_aceita() -> None:
    # O J (espelho do L) quase pronto: coluna 5 com tres do J1 e falta a 4.
    j_quase = _tabuleiro({5: "111", 7: "222"})
    sem_espelho = fq.FiguraQuatro("l", ("X.", "X.", "XX"), False, "controle")
    com_espelho = fq.FiguraQuatro("l", ("X.", "X.", "XX"), True, "controle")
    # Sem espelho, o L mais perto e a coluna 5 com a 6 do lado: falta 1 tambem.
    assert fq.distancia(sem_espelho, j_quase, DIMENSOES) == 1
    # A diferenca aparece quando o lado direito esta tomado.
    j_so_pela_esquerda = _tabuleiro({5: "111", 6: "2", 7: "222"})
    assert fq.distancia(com_espelho, j_so_pela_esquerda, DIMENSOES) == 1
    assert fq.distancia(sem_espelho, j_so_pela_esquerda, DIMENSOES) > 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. Cada figura se forma numa partida de verdade
# ═══════════════════════════════════════════════════════════════════════════


def _casas_da_figura(desenho: tuple[str, ...]) -> list[tuple[int, int, int]]:
    """As casas a ocupar para a figura existir no canto de baixo e da esquerda.

    Cada uma como `(linha, coluna, dono)`, com `+1` a pessoa e `-1` o
    adversario; os APOIOS ficam com o adversario. Em ordem de linha (de baixo
    para cima): assim cada casa ja tem as de baixo ocupadas quando chega a vez.
    """
    altura = len(desenho)
    casas = []
    for j, coluna in enumerate(fq.colunas(desenho), start=1):
        topo = min((i for i in (coluna.find("X"), coluna.find("O")) if i >= 0), default=None)
        if topo is None:
            continue
        for i in range(topo, altura):
            linha = altura - i
            simbolo = coluna[i]
            casas.append((linha, j, 1 if simbolo == "X" else -1))
    return sorted(casas)


def _fita_que_forma(desenho: tuple[str, ...]) -> list[str]:
    """Uma partida, a partir do tabuleiro vazio, que monta a figura.

    O J1 e a pessoa. Em cada vez, quem joga poe a proxima casa DELE se ela ja
    tem apoio; senao gasta o lance numa coluna fora da figura - a primeira que
    nao encerre a partida. ⚠️ Se nenhuma servir, o caso falha: a figura nao se
    monta sem alguem vencer, e isso e um defeito do catalogo.
    """
    motor = MotorQuatro(MODALIDADE)
    estado = EstadoQuatro(MODALIDADE, ())
    pendentes = {1: [], -1: []}
    for linha, coluna, dono in _casas_da_figura(desenho):
        pendentes[dono].append((linha, coluna))
    largura = len(desenho[0])
    fora = list(range(DIMENSOES.largura, largura, -1))
    fita: list[str] = []
    while pendentes[1] or pendentes[-1]:
        tabuleiro = motor.tabuleiro(estado)
        quem = tabuleiro.vez
        candidatos = []
        if pendentes[quem]:
            linha, coluna = pendentes[quem][0]
            if len(tabuleiro.colunas[coluna - 1]) == linha - 1:
                candidatos.append(f"s{coluna}")
        candidatos += [f"s{c}" for c in fora if len(tabuleiro.colunas[c - 1]) < DIMENSOES.altura]
        for lance in candidatos:
            depois = motor.aplicar(estado, lance)
            if motor.veredito(depois).acabou:
                continue
            if pendentes[quem] and lance == f"s{pendentes[quem][0][1]}" and lance == candidatos[0]:
                pendentes[quem].pop(0)
            estado = depois
            fita.append(lance)
            break
        else:
            pytest.fail(f"a figura {desenho} nao se monta sem a partida acabar")
    return fita


@pytest.mark.parametrize("nome", sorted(fq.FIGURAS_QUATRO))
def test_cada_figura_se_forma_numa_partida_e_o_prazo_conta(nome: str) -> None:
    figura = fq.FIGURAS_QUATRO[nome]
    fita = _fita_que_forma(figura.desenho)
    lances_da_pessoa = (len(fita) + 1) // 2
    posicao = MotorQuatro(MODALIDADE).para_dado(EstadoQuatro(MODALIDADE, ()))

    def julgar(prazo: int):
        return julgar_desafio(
            co_jogo="quatro",
            js_posicao_inicial=posicao,
            js_chegada=RECEITAS_FORA_DO_AR["quatro_figura"].montar(
                {"figura": nome, "lances": prazo}
            ),
            fita=[
                {"n": n, "jogador": 1 if n % 2 else -1, "lance": lance}
                for n, lance in enumerate(fita, start=1)
            ],
            jogador=1,
            co_modalidade=MODALIDADE,
        )

    no_prazo = julgar(lances_da_pessoa)
    assert no_prazo.veredito == CUMPRIU, (nome, fita)
    # Fecha no ultimo lance da fita: a ultima casa de toda coluna e da pessoa
    # (a recusa 5), e ela e quem poe a ultima.
    assert no_prazo.nu_lance_cumpre_desafio == len(fita), (nome, fita)
    assert julgar(lances_da_pessoa - 1).veredito == NAO_CUMPRIU, (nome, fita)


def test_o_quem_explicito_vence_a_vez_do_tabuleiro() -> None:
    """⚠️ O perseguidor (T148) mede o tabuleiro DEPOIS do lance da pessoa, quando
    a vez ja e do adversario: sem o `quem`, mediria a figura do lado errado.

    O J1 com tres pecas do quadrado e a vez do J2: para o J1 falta 1 casa; para
    o J2 (a vez), o quadrado mais perto e o das colunas 6 e 7, a 2."""
    tabuleiro = _tabuleiro({1: "11", 2: "1", 7: "2", 6: "2"}, vez=-1)
    quadrado = fq.FIGURAS_QUATRO["quadrado"]
    assert fq.distancia(quadrado, tabuleiro, DIMENSOES, quem=1) == 1
    assert fq.distancia(quadrado, tabuleiro, DIMENSOES) == 2
    assert fq.distancia(quadrado, tabuleiro, DIMENSOES, quem=-1) == 2


def test_os_custos_sao_um_por_lugar_e_a_distancia_e_o_menor() -> None:
    """`custos` (a soma do perseguidor) e `distancia` (o prazo) leem a mesma conta."""
    from motores.quatro import distancia_da_figura_quatro as dq

    tabuleiro = _tabuleiro({1: "11", 2: "1", 7: "22", 6: "2"})
    quadrado = fq.FIGURAS_QUATRO["quadrado"]
    custos = dq.custos(quadrado.desenho, False, tabuleiro, DIMENSOES, 1)
    # No 7 x 6 o quadrado tem 6 x 5 = 30 cantos; os que esbarram nas pecas do J2
    # (colunas 6 e 7, linhas 1 e 2) sao conflito e ficam fora.
    assert 0 < len(custos) < 30
    assert min(custos) == fq.distancia(quadrado, tabuleiro, DIMENSOES) == 1
    # Sem lugar livre: lista vazia, e a distancia `None`.
    alta = fq.FiguraQuatro("alta", ("X", "O", "X", "O", "X", "O"), False, "lote")
    cheio = _tabuleiro({j: "1" for j in range(1, 8)})
    assert dq.custos(alta.desenho, False, cheio, DIMENSOES, 1) == []

"""T028/T029/T030 - o julgamento do desafio, medido contra os VETORES.

═══════════════════════════════════════════════════════════════════════════
O TESTE QUE IMPORTA E O PRIMEIRO
═══════════════════════════════════════════════════════════════════════════

`test_o_juiz_concorda_com_cada_vetor` roda os doze vetores de
`contratos/vetores-verificacao-desafio.json` pelo juiz de verdade e exige que o
veredito **e as medidas** batam.

⚠️ **E o mesmo arquivo que o lado Dart vai rodar** (T053). E isso que torna a
regra "a mesma" nos dois lados: nao ha uma implementação só — ha um **teste** só,
sobre os mesmos dados.

Os demais casos deste arquivo cobrem o que os vetores nao alcançam: as recusas de
formato (chegada malformada e desafio que nao deveria ter sido publicado), a
aritmética das janelas e a derivação de `ic_chegada_encerra_partida`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from motores.juiz import JogoDesconhecido, julgar_desafio
from motores.nucleo.chegada import (
    ChegadaInvalida,
    LinhaDeChegada,
    avaliar,
    chegada_encerra_partida,
    comparar,
)
from motores.nucleo.medidor_por_fita import prefixo_da_janela, turnos_da_fita
from motores.pontinhos.feitos_pontinhos import CAIXAS_DO_TABULEIRO_PEQUENO

RAIZ = Path(__file__).resolve().parents[2]
VETORES = RAIZ / "contratos" / "vetores-verificacao-desafio.json"


def _vetores() -> list[dict]:
    """Os vetores do disco. ⛔ Ausência e falha, nao motivo para pular."""
    assert VETORES.is_file(), (
        f"os vetores nao estao em {VETORES}. Sem eles este arquivo nao prova "
        "nada — e por isso ele falha em vez de pular."
    )
    return json.loads(VETORES.read_text(encoding="utf-8"))["vetores"]


TODOS = _vetores()
IDS = [v["id"] for v in TODOS]


# ═══════════════════════════════════════════════════════════════════════════
# 1. O cadeado principal
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("vetor", TODOS, ids=IDS)
def test_o_juiz_concorda_com_cada_vetor(vetor: dict) -> None:
    """🔒 Veredito e medidas, vetor a vetor.

    ⚠️ **As medidas contam tanto quanto o veredito.** Dois lados podem concordar
    que a pessoa cumpriu e discordar de quantas caixas ela fechou — e e a medida
    que vira `Q`, que vira a ordem do quadro do dia.
    """
    julgamento = julgar_desafio(
        co_jogo=vetor["co_jogo"],
        js_posicao_inicial=vetor["js_posicao_inicial"],
        js_chegada=vetor["js_chegada"],
        fita=vetor["lances"],
        co_modalidade=vetor.get("co_modalidade", "brasileira"),
    )

    assert julgamento.veredito == vetor["esperado"]["veredito"], (
        f"{vetor['id']}: o juiz disse {julgamento.veredito!r}, o vetor diz "
        f"{vetor['esperado']['veredito']!r}. Motivo: {julgamento.de_motivo}"
    )

    esperados = vetor["esperado"]["feitos"]
    if not esperados:
        # Fita recusada nao produz medida.
        assert julgamento.feitos == {}
        return

    divergentes = {
        chave: (valor, julgamento.feitos.get(chave))
        for chave, valor in esperados.items()
        if julgamento.feitos.get(chave) != valor
    }
    assert not divergentes, (
        f"{vetor['id']}: medidas divergentes (esperado x medido): {divergentes}"
    )


@pytest.mark.parametrize(
    "vetor", [v for v in TODOS if v["esperado"]["veredito"] == "cumpriu"],
    ids=[v["id"] for v in TODOS if v["esperado"]["veredito"] == "cumpriu"],
)
def test_quem_cumpriu_diz_EM_QUE_LANCE(vetor: dict) -> None:
    """`nu_lance_cumpre_desafio` e o ponteiro do replay do Raio-X.

    Ele abre **em torno** desse lance: alguns antes para dar contexto, alguns
    depois para mostrar o efeito. Sem o número, o replay começaria do zero e a
    pessoa teria de procurar sozinha o instante em que venceu.
    """
    julgamento = julgar_desafio(
        co_jogo=vetor["co_jogo"],
        js_posicao_inicial=vetor["js_posicao_inicial"],
        js_chegada=vetor["js_chegada"],
        fita=vetor["lances"],
        co_modalidade=vetor.get("co_modalidade", "brasileira"),
    )
    assert julgamento.nu_lance_cumpre_desafio is not None
    assert 1 <= julgamento.nu_lance_cumpre_desafio <= len(vetor["lances"])


def test_quem_nao_cumpriu_TAMBEM_tem_feitos() -> None:
    """⚠️ Tentar e ser medido: o XP de consolo e o Raio-X vivem disso.

    Um julgamento que devolvesse feitos vazios para quem nao cumpriu deixaria a
    tela de resultado sem nada a mostrar justamente para quem mais precisa de um
    motivo para voltar amanhã.
    """
    vetor = next(v for v in TODOS if v["esperado"]["veredito"] == "nao_cumpriu")
    julgamento = julgar_desafio(
        co_jogo=vetor["co_jogo"],
        js_posicao_inicial=vetor["js_posicao_inicial"],
        js_chegada=vetor["js_chegada"],
        fita=vetor["lances"],
        co_modalidade=vetor.get("co_modalidade", "brasileira"),
    )
    assert julgamento.feitos, "quem nao cumpriu ficou sem medida nenhuma"
    assert julgamento.nu_lance_cumpre_desafio is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. A fronteira do formato — T028
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "dado, porque",
    [
        ({"janela": {"tipo": "partida"}, "clausulas": []}, "sem versao"),
        (
            {"versao": 2, "janela": {"tipo": "partida"}, "clausulas": []},
            "versao futura",
        ),
        (
            {"versao": 1, "janela": {"tipo": "partida"}, "clausulas": []},
            "sem clausula nenhuma",
        ),
        (
            {"versao": 1, "janela": {"tipo": "ate_o_fim"}, "clausulas": [{}]},
            "janela inventada",
        ),
        (
            {
                "versao": 1,
                "janela": {"tipo": "turnos_do_jogador"},
                "clausulas": [{}],
            },
            "janela de turnos sem n",
        ),
        (
            {
                "versao": 1,
                "janela": {"tipo": "partida", "n": 3},
                "clausulas": [{}],
            },
            "janela `partida` com n",
        ),
    ],
)
def test_chegada_malformada_e_RECUSADA(dado: dict, porque: str) -> None:
    """⛔ Formato desconhecido e recusa, nunca "tenta assim mesmo".

    ⚠️ Um desafio escrito num formato futuro, julgado por um avaliador antigo,
    daria um veredito que ninguém consegue explicar depois — e o veredito decide
    XP de gente real.
    """
    with pytest.raises(ChegadaInvalida):
        LinhaDeChegada.de_dado(dado)


@pytest.mark.parametrize(
    "clausula, porque",
    [
        (
            {"tipo": "expressao", "chave": "x", "comparador": "igual", "valor": 1},
            "tipo de clausula inventado",
        ),
        (
            {"tipo": "medida", "chave": "x", "comparador": "maior", "valor": 1},
            "comparador que nao existe",
        ),
        ({"tipo": "medida", "chave": "", "comparador": "igual", "valor": 1}, "sem chave"),
        ({"tipo": "medida", "chave": "x", "comparador": "igual"}, "sem valor"),
        (
            {"tipo": "medida", "chave": "x", "comparador": "em", "valor": 3},
            "`em` sem lista",
        ),
        (
            {"tipo": "medida", "chave": "x", "comparador": "igual", "valor": [1, 2]},
            "`igual` com lista",
        ),
    ],
)
def test_clausula_fora_do_vocabulario_e_RECUSADA(clausula: dict, porque: str) -> None:
    """🔒 A fronteira entre publicar DADO e publicar CODIGO (RF-DES-192).

    ⛔ Ficam de fora, de propósito: `OU`/`NAO` aninhados, aritmética entre chaves,
    chave livre e expressão avaliada em runtime. Um desafio viaja para milhões de
    aparelhos sem passar por revisão de loja.
    """
    with pytest.raises(ChegadaInvalida):
        LinhaDeChegada.de_dado(
            {"versao": 1, "janela": {"tipo": "partida"}, "clausulas": [clausula]}
        )


def test_medida_que_a_clausula_pede_e_nao_foi_medida_e_ERRO() -> None:
    """⚠️ Chave ausente e erro, nunca `False`.

    Tratar "nao medi" como "nao cumpriu" faria um medidor com defeito parecer uma
    pessoa que nao conseguiu — e o defeito ficaria escondido atrás de milhares de
    tentativas fracassadas.
    """
    chegada = LinhaDeChegada.de_dado(
        {
            "versao": 1,
            "janela": {"tipo": "partida"},
            "clausulas": [
                {
                    "tipo": "medida",
                    "chave": "caixas_fechadas",
                    "comparador": "maior_ou_igual",
                    "valor": 1,
                }
            ],
        }
    )
    with pytest.raises(ChegadaInvalida):
        avaliar(chegada, {"outra_coisa": 9})


def test_todas_as_clausulas_precisam_valer() -> None:
    """E sempre um "E", nunca um "ou" — e a conjunção e a forma inteira."""
    chegada = LinhaDeChegada.de_dado(
        {
            "versao": 1,
            "janela": {"tipo": "partida"},
            "clausulas": [
                {
                    "tipo": "medida",
                    "chave": "caixas_fechadas",
                    "comparador": "maior_ou_igual",
                    "valor": 4,
                },
                {
                    "tipo": "medida",
                    "chave": "caixas_do_adversario",
                    "comparador": "igual",
                    "valor": 0,
                },
            ],
        }
    )
    assert avaliar(chegada, {"caixas_fechadas": 4, "caixas_do_adversario": 0})
    assert not avaliar(chegada, {"caixas_fechadas": 4, "caixas_do_adversario": 1})
    assert not avaliar(chegada, {"caixas_fechadas": 3, "caixas_do_adversario": 0})


@pytest.mark.parametrize(
    "medido, comparador, alvo, esperado",
    [
        (4, "maior_ou_igual", 4, True),
        (3, "maior_ou_igual", 4, False),
        (3, "menor_ou_igual", 4, True),
        (4, "igual", 4, True),
        (4, "diferente", 4, False),
        (2, "em", [1, 2, 3], True),
        (9, "em", [1, 2, 3], False),
        (9, "fora_de", [1, 2, 3], True),
        # ⚠️ `True == 1` em Python, e isso e útil: um predicado casa com
        # `valor: true` e também com `valor: 1`.
        (True, "igual", 1, True),
    ],
)
def test_os_seis_comparadores(medido, comparador, alvo, esperado) -> None:
    """Um caso por comparador — a folha da conjunção.

    ⚠️ Negar na folha (`diferente`, `fora_de`) **nao e** aninhar um `NAO`: cada
    uma tem um número fixo de casos, e cada caso esta aqui. Um `NAO` sobre uma
    subárvore seria um interpretador.
    """
    assert comparar(medido, comparador, alvo) is esperado


# ═══════════════════════════════════════════════════════════════════════════
# 3. As janelas — T029
# ═══════════════════════════════════════════════════════════════════════════


def test_turno_e_corrida_de_lances_do_MESMO_jogador() -> None:
    """⚠️ E a diferença que o Pontinhos cria: quem fecha caixa joga de novo.

    Quatro caixas fechadas em quatro lances seguidos sao **um** turno. Medir
    turno como lance faria "em 2 turnos" virar "em 2 lances" — um desafio de
    dificuldade completamente diferente, sem que ninguém tivesse mexido nele.
    """
    fita = [
        {"n": 1, "jogador": 1, "lance": "a"},
        {"n": 2, "jogador": 1, "lance": "b"},
        {"n": 3, "jogador": 1, "lance": "c"},
        {"n": 4, "jogador": -1, "lance": "d"},
        {"n": 5, "jogador": 1, "lance": "e"},
    ]
    assert turnos_da_fita(fita) == [1, 1, 1, 2, 3]


def test_a_janela_partida_abrange_a_fita_inteira() -> None:
    chegada = LinhaDeChegada.de_dado(
        {
            "versao": 1,
            "janela": {"tipo": "partida"},
            "clausulas": [
                {"tipo": "medida", "chave": "x", "comparador": "igual", "valor": 1}
            ],
        }
    )
    fita = [{"n": i, "jogador": 1, "lance": "x"} for i in range(1, 6)]
    assert prefixo_da_janela(fita, chegada, jogador=1) == 5


def test_a_janela_de_turnos_para_no_turno_seguinte() -> None:
    """Dois turnos do jogador: a janela fecha quando o TERCEIRO começa.

    ⚠️ E o caso de fronteira que o vetor "nao cumpre por pouco" existe para pegar.
    Um `>=` no lugar de `>` aqui daria um turno a mais a todo mundo.
    """
    chegada = LinhaDeChegada.de_dado(
        {
            "versao": 1,
            "janela": {"tipo": "turnos_do_jogador", "n": 2},
            "clausulas": [
                {"tipo": "medida", "chave": "x", "comparador": "igual", "valor": 1}
            ],
        }
    )
    fita = [
        {"n": 1, "jogador": 1, "lance": "a"},   # turno 1
        {"n": 2, "jogador": -1, "lance": "b"},  # turno 2 (do adversário)
        {"n": 3, "jogador": 1, "lance": "c"},   # turno 3 — 2o turno DELE
        {"n": 4, "jogador": -1, "lance": "d"},  # turno 4
        {"n": 5, "jogador": 1, "lance": "e"},   # turno 5 — 3o turno dele: FORA
    ]
    assert prefixo_da_janela(fita, chegada, jogador=1) == 4


def test_a_janela_de_lances_conta_so_os_do_jogador() -> None:
    """Os lances do adversário nao contam para o limite — mas ficam na fita.

    Eles mudam a posição, e ignorá-los faria a medida sair de um tabuleiro que
    nunca existiu.
    """
    chegada = LinhaDeChegada.de_dado(
        {
            "versao": 1,
            "janela": {"tipo": "lances_do_jogador", "n": 1},
            "clausulas": [
                {"tipo": "medida", "chave": "x", "comparador": "igual", "valor": 1}
            ],
        }
    )
    fita = [
        {"n": 1, "jogador": 1, "lance": "a"},
        {"n": 2, "jogador": -1, "lance": "b"},
        {"n": 3, "jogador": 1, "lance": "c"},
    ]
    assert prefixo_da_janela(fita, chegada, jogador=1) == 2


def test_jogo_sem_medidor_falha_ALTO() -> None:
    """⚠️ Um jogo novo sem medidor devolveria "nao cumpriu" para todo mundo.

    Seria um desafio impossível, sem erro nenhum no log — a espécie de defeito
    que este projeto vem catalogando.
    """
    with pytest.raises(JogoDesconhecido):
        julgar_desafio(
            co_jogo="velha",
            js_posicao_inicial={"versao": 1, "lances": []},
            js_chegada={
                "versao": 1,
                "janela": {"tipo": "partida"},
                "clausulas": [
                    {
                        "tipo": "medida",
                        "chave": "lances_otimos",
                        "comparador": "maior_ou_igual",
                        "valor": 1,
                    }
                ],
            },
            fita=[],
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. `ic_chegada_encerra_partida` e DERIVADO — T030
# ═══════════════════════════════════════════════════════════════════════════


def _chegada(janela: dict, clausulas: list[dict]) -> LinhaDeChegada:
    return LinhaDeChegada.de_dado(
        {"versao": 1, "janela": janela, "clausulas": clausulas}
    )


def test_fechar_4_caixas_de_12_NAO_encerra_a_partida() -> None:
    """🔒 O caso de prova de RF-DES-194, e o que o dono pediu por escrito.

    *"Chegue a 7x3"* num tabuleiro de 12 caixas nao encerra a partida: 7 + 3 = 10,
    e sobram duas. Digitado a mão, esse `TRUE` erraria calado no dia em que o
    tabuleiro mudasse de tamanho — e a tela pararia a partida de quem quisesse
    continuar (RF-DES-213).
    """
    chegada = _chegada(
        {"tipo": "partida"},
        [
            {
                "tipo": "medida",
                "chave": "caixas_fechadas",
                "comparador": "maior_ou_igual",
                "valor": 4,
            }
        ],
    )
    assert (
        chegada_encerra_partida(
            chegada, total_de_unidades=CAIXAS_DO_TABULEIRO_PEQUENO
        )
        is False
    )


def test_vencer_a_partir_daqui_ENCERRA() -> None:
    """`vitoria` e um marco que só existe com a partida terminada."""
    chegada = _chegada(
        {"tipo": "partida"},
        [{"tipo": "medida", "chave": "vitoria", "comparador": "igual", "valor": 1}],
    )
    assert chegada_encerra_partida(chegada) is True


def test_fechar_TODAS_as_caixas_encerra() -> None:
    """Exigir 12 de 12 nao deixa lance por jogar."""
    chegada = _chegada(
        {"tipo": "partida"},
        [
            {
                "tipo": "medida",
                "chave": "caixas_fechadas",
                "comparador": "maior_ou_igual",
                "valor": CAIXAS_DO_TABULEIRO_PEQUENO,
            }
        ],
    )
    assert (
        chegada_encerra_partida(
            chegada, total_de_unidades=CAIXAS_DO_TABULEIRO_PEQUENO
        )
        is True
    )


def test_janela_limitada_NUNCA_encerra() -> None:
    """Uma janela de N turnos fecha antes do fim do jogo, por construção.

    Mesmo *"vença em 2 turnos"*: a janela acaba no 2o turno, e o jogo segue para
    quem quiser continuar.
    """
    chegada = _chegada(
        {"tipo": "turnos_do_jogador", "n": 2},
        [{"tipo": "medida", "chave": "vitoria", "comparador": "igual", "valor": 1}],
    )
    assert chegada_encerra_partida(chegada) is False

"""O MOSTRADOR DA SAFRA: com que numeros cada tipo vai ao ar (T049c).

═══════════════════════════════════════════════════════════════════════════
⚠️ RECEITA E EDITORIAL SAO COISAS DIFERENTES, E O CORTE E ESTE
═══════════════════════════════════════════════════════════════════════════

    `tipos_de_desafio.py`  → a RECEITA: como um tipo vira linha de chegada
                             ("fechar caixas" e uma clausula de medida sobre a
                             chave `caixas_fechadas`, numa janela de turnos)

    este arquivo           → o EDITORIAL: com QUE NUMEROS ele vai ao ar hoje
                             (quatro caixas em dois turnos), o que ele MEDE, que
                             versao de aplicativo EXIGE e qual e o teto do log

⚠️ **Trocar 4 por 6 e mudanca de DADO** (SC-027): nao toca `.arb`, nao toca
codigo do aplicativo e nao muda `co_versao_minima`. E por isso que os numeros
moram separados da receita — se estivessem dentro dela, mexer na dificuldade de
um desafio pareceria mexer na regra que o julga.

⛔ **E nao cabia em `gravacao.py`**, que e sobre a fila: quantos dias cobrir e
quando parar de gerar nao tem relacao com quantas caixas o desafio pede.

═══════════════════════════════════════════════════════════════════════════
⚠️ OS PESOS SAO `Decimal` E SOMAM 1,000 — E ISSO E CONFERIDO ANTES DE GRAVAR
═══════════════════════════════════════════════════════════════════════════

`medidas_de_saida.conferir()` recusa um conjunto que nao feche. ⚠️ E os pesos
sao `Decimal` porque `0.6 + 0.4` em ponto flutuante **nao da** `1.0` — um
conjunto correto seria reprovado pela aritmetica, e alguem "consertaria" o teste
afrouxando a comparacao, que e como uma regra vira decoracao.

═══════════════════════════════════════════════════════════════════════════
⚠️ TODO TIPO TEM UMA MEDIDA DE PESO ZERO, E ELA NAO E DESPERDICIO
═══════════════════════════════════════════════════════════════════════════

*"Quantas caixas voce deixou o adversario fechar"* interessa em **qualquer**
desafio de Pontinhos, e aparece no Raio-X; mas so e **merito** num desafio cujo
objetivo seja nao entrega-las. Peso zero e exatamente isso: medido e exibido,
nao pontuado. O `ck003_faixa` da migracao amarra os dois.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .medidas_de_saida import linha_de_faixa, linha_de_fracao, linha_so_medida

#: A versao do aplicativo que estreia o Desafio do Dia.
#:
#: ⚠️ **Ela e o numero que `contracts/desafio-publicado.md` documenta**, e nao um
#: palpite: o aplicativo compara `versao_minima_app` com a sua e cai na tela de
#: atualizar quando nao alcanca (RF-DES-020 a 029).
#:
#: ⚠️ **Tipo novo sobe este numero**, e e assim que o ciclo fecha sem release
#: para *parametro* e com release para *texto*: a chave `.arb` do enunciado de um
#: tipo novo so existe a partir da versao que a trouxe, e um aplicativo mais
#: antigo precisa cair na tela de atualizar em vez de mostrar a chave crua.
VERSAO_MINIMA_DOS_TIPOS_FUNDADORES = "1.3.0"

#: Quantos meios-lances o log de uma partida de desafio pode ter.
#:
#: ⚠️ **Acima do teto e DADO INVALIDO, e nao "log grande"** (T057): o replay nao
#: se monta, e ⚠️ **o veredito que a pessoa viu permanece** — truncar o log nao
#: desfaz a resolucao nem o XP.
#:
#: 120 e o numero do `data-model.md`. Ele e folgado para os dois jogos de hoje —
#: o Pontinhos pequeno tem 31 tracos ao todo, e uma partida de damas de desafio
#: comeca de um molde, ja perto do fim.
TETO_DE_LOG_PADRAO = 120

# ── Os dois botoes da GERACAO, e por que eles sao por tipo ───────────────────
#
# ⚠️ **Medido em 10/09/2026, depois de a primeira execucao real nao gerar NENHUM
# desafio de Pontinhos em quatro dias.** Os dois tipos falhavam, e por motivos
# opostos:
#
#     pontinhos_fechar_caixas    → 0 candidatos com preparo 8; **1 com preparo 14**
#     pontinhos_chegar_ao_placar → 0 candidatos com teto 12;   **1 com teto 34**
#
# ⛔ Um numero global nao serve para os dois. *"Feche 4 caixas em 2 turnos"* falha
# porque um tabuleiro com so 8 tracos **nao tem cadeia de 4 caixas para fechar** —
# nao adianta procurar por mais tempo, a posicao nao existe. Ja *"chegue a 7 de
# 12 caixas"* tem a janela da **partida inteira**, e 12 lances nao chegam la de
# jeito nenhum: a solucao medida usa 22.
#
# ⚠️ E o mesmo `nu_maximo_de_lances` vale para a REGUA. Medir com um teto maior
# que o da geracao faria os mascotes resolverem desafios que o gerador nao
# conseguiu montar, e a taxa descreveria uma tarefa diferente da publicada.
MAXIMO_DE_LANCES_PADRAO = 12
LANCES_DE_PREPARO_PADRAO = 8


@dataclass(frozen=True, slots=True)
class Publicacao:
    """Como um tipo vai ao ar nesta safra.

    Atributos:
        parametros: os numeros que a receita consome (`{"caixas": 4}`).
        ic_chegada_encerra_partida: cumprir o objetivo **acaba o jogo**?
        co_versao_minima: a versao de aplicativo que sabe desenhar este tipo.
        nu_teto_log: o teto de meios-lances do log.
        medidas: `(parametros) -> linhas de tb003_feito_desafio`.
    """

    parametros: Mapping[str, Any]
    ic_chegada_encerra_partida: bool
    medidas: Callable[[Mapping[str, Any]], list[dict[str, Any]]]
    co_versao_minima: str = VERSAO_MINIMA_DOS_TIPOS_FUNDADORES
    nu_teto_log: int = TETO_DE_LOG_PADRAO
    nu_maximo_de_lances: int = MAXIMO_DE_LANCES_PADRAO
    nu_lances_de_preparo: int = LANCES_DE_PREPARO_PADRAO


class TipoSemEditorial(ValueError):
    """O tipo tem receita e vetor, mas ninguem disse com que numeros publica-lo.

    ⚠️ **Falha alto de proposito.** Um padrao aqui — *"se nao souber, use 3"* —
    poria no ar um desafio cuja dificuldade ninguem escolheu, e ele pareceria
    igual aos outros na tela.
    """


# ═══════════════════════════════════════════════════════════════════════════
# As quatro linhas da safra de hoje
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Sao quatro porque sao quatro os tipos publicaveis** (receita E vetor). Os
# onze propostos em T049 entram aqui quando tiverem linha na dimensao, chave de
# i18n e vetor — e ha cadeado que falha se alguem os importar antes.


def _medidas_do_pontinhos_fechar_caixas(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """As tres linhas do exemplo do `data-model.md`, com o alvo por parametro.

    ⚠️ **`vr_max` e o proprio alvo do desafio**, e nao o total do tabuleiro:
    fechar quatro caixas quando o pedido eram quatro e nota cheia. Normalizar
    sobre as doze caixas do tabuleiro pagaria um terco a quem cumpriu o objetivo
    inteiro.
    """
    return [
        linha_de_faixa(
            "caixas_fechadas",
            nu_ordem=1,
            vr_peso="0.600",
            vr_min=0,
            vr_max=p["caixas"],
        ),
        linha_de_fracao(
            "lances_do_jogador",
            nu_ordem=2,
            vr_peso="0.400",
            co_sobre="lances_da_solucao",
        ),
        linha_so_medida("caixas_do_adversario", nu_ordem=3),
    ]


def _medidas_do_pontinhos_placar(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Chegar ao placar: o merito e o placar, e a economia de lances pesa menos."""
    return [
        linha_de_faixa(
            "caixas_fechadas",
            nu_ordem=1,
            vr_peso="0.700",
            vr_min=0,
            vr_max=p["caixas"],
        ),
        linha_de_fracao(
            "lances_do_jogador",
            nu_ordem=2,
            vr_peso="0.300",
            co_sobre="lances_da_solucao",
        ),
        linha_so_medida("caixas_do_adversario", nu_ordem=3),
    ]


def _medidas_do_damas_coroar(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Coroar: o merito e a dama, e o material que sobrou aparece sem pontuar."""
    return [
        linha_de_faixa(
            "damas_coroadas",
            nu_ordem=1,
            vr_peso="0.600",
            vr_min=0,
            vr_max=p["damas"],
        ),
        linha_de_fracao(
            "lances_do_jogador",
            nu_ordem=2,
            vr_peso="0.400",
            co_sobre="lances_da_solucao",
        ),
        linha_so_medida("material_do_adversario", nu_ordem=3),
    ]


def _medidas_do_damas_captura(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Captura multipla: o merito e o tamanho da maior captura.

    ⚠️ `capturas_extras` entra com peso zero e nao por acaso: ela e a medida
    **irma**, e mostra-la ao lado explica a nota — *"voce fez uma de tres e mais
    duas simples"* — sem que a nota dependa dela.
    """
    return [
        linha_de_faixa(
            "maior_captura",
            nu_ordem=1,
            vr_peso="0.700",
            vr_min=0,
            vr_max=p["pecas"],
        ),
        linha_de_fracao(
            "lances_do_jogador",
            nu_ordem=2,
            vr_peso="0.300",
            co_sobre="lances_da_solucao",
        ),
        linha_so_medida("capturas_extras", nu_ordem=3),
    ]


EDITORIAL: dict[str, Publicacao] = {
    "pontinhos_fechar_caixas": Publicacao(
        # Os numeros do exemplo do `data-model.md`: quatro caixas em dois turnos,
        # num tabuleiro de doze. ⚠️ Dois turnos e apertado de proposito — quem
        # fecha caixa joga de novo, entao quatro caixas cabem num turno so quando
        # a cadeia esta armada.
        parametros={"caixas": 4, "turnos": 2},
        # Quatro de doze deixam o jogo em aberto.
        ic_chegada_encerra_partida=False,
        # ⚠️ **Preparo 14, e nao 8** — medido: com 8 tracos o tabuleiro nao tem
        # cadeia de 4 caixas, e procurar por mais tempo nao inventa uma.
        nu_lances_de_preparo=14,
        medidas=_medidas_do_pontinhos_fechar_caixas,
    ),
    "pontinhos_chegar_ao_placar": Publicacao(
        # Sete de doze e a maioria: quem chega la **ja venceu**.
        parametros={"caixas": 7},
        # ⚠️ E ainda assim `False`: a partida esta DECIDIDA, e nao terminada —
        # sobram tracos no tabuleiro, e ⛔ o aplicativo nao interrompe quem quiser
        # continuar (RF-DES-213/214).
        ic_chegada_encerra_partida=False,
        # ⚠️ **A janela e a PARTIDA INTEIRA**, e por isso o teto e outro: a
        # solucao medida usa 22 lances, e com 12 nunca se chega a sete caixas.
        nu_maximo_de_lances=34,
        medidas=_medidas_do_pontinhos_placar,
    ),
    "damas_coroar": Publicacao(
        # Uma dama em seis lances — o mesmo alvo com que os moldes foram escritos
        # e com que a T034 foi medida.
        parametros={"damas": 1, "lances": 6},
        ic_chegada_encerra_partida=False,
        medidas=_medidas_do_damas_coroar,
    ),
    "damas_capturar_multipla": Publicacao(
        # Uma captura de duas pecas em quatro lances.
        parametros={"pecas": 2, "lances": 4},
        ic_chegada_encerra_partida=False,
        medidas=_medidas_do_damas_captura,
    ),
}


def publicacao_de(co_tipo_desafio: str) -> Publicacao:
    """Como aquele tipo vai ao ar. Falha alto se ninguem escolheu os numeros.

    Raises:
        TipoSemEditorial: sempre que o tipo nao estiver em [EDITORIAL].
    """
    if co_tipo_desafio not in EDITORIAL:
        raise TipoSemEditorial(
            f"o tipo {co_tipo_desafio!r} nao tem editorial. ⛔ Ele tem receita "
            "(sabe-se COMO julga-lo), mas ninguem disse com QUE NUMEROS publica-lo "
            "— e um padrao aqui poria no ar um desafio cuja dificuldade ninguem "
            f"escolheu. Os que tem editorial hoje: {sorted(EDITORIAL)}"
        )
    return EDITORIAL[co_tipo_desafio]


def parametros_de(co_tipo_desafio: str) -> dict[str, Any]:
    """Os numeros daquele tipo, como dicionario novo.

    ⚠️ **Copia, e nao a referencia**: o gerador recebe isto e nao deveria poder
    alterar a safra de quem vier depois na mesma execucao.
    """
    return dict(publicacao_de(co_tipo_desafio).parametros)


__all__ = [
    "EDITORIAL",
    "LANCES_DE_PREPARO_PADRAO",
    "MAXIMO_DE_LANCES_PADRAO",
    "TETO_DE_LOG_PADRAO",
    "VERSAO_MINIMA_DOS_TIPOS_FUNDADORES",
    "Publicacao",
    "TipoSemEditorial",
    "parametros_de",
    "publicacao_de",
]

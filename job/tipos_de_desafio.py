"""AS RECEITAS DE CADA TIPO DE DESAFIO (T034).

═══════════════════════════════════════════════════════════════════════════
TIPO x FORMA DE CHEGADA — E ISSO CONFUNDIU A SPEC POR SEMANAS
═══════════════════════════════════════════════════════════════════════════

**O tipo e a IDENTIDADE** do desafio: e ele que da a frase, o rodizio (para nao
cair o mesmo tipo dois dias seguidos) e o agrupamento na curadoria.

**A forma de chegada e COMO SE JULGA**, e ela e **uma so** — a conjuncao de
clausulas. Dez tipos diferentes usam hoje a mesma forma.

⚠️ Foi por confundir os dois que *"o lance unico"* e *"final da base"* pareceram,
por um tempo, nao ter forma propria: eles sao **tipos**, e a linha de chegada
deles e a comum.

Uma **receita** e o que liga um ao outro: dado o tipo e os parametros do dia, ela
monta o `js_chegada`, a chave de i18n do enunciado e os valores que entram na
frase.

═══════════════════════════════════════════════════════════════════════════
⛔ TIPO SEM RECEITA NAO E PUBLICAVEL — E E ASSIM QUE TEM DE SER
═══════════════════════════════════════════════════════════════════════════

E a regra 2 do contrato dos vetores, vista deste lado. Um tipo publicado sem
receita produziria um desafio cuja linha de chegada ninguem escreveu — e o
julgamento devolveria "nao cumpriu" para todo mundo, **sem erro nenhum**.

⚠️ E a receita nao basta sozinha: o gerador tambem exige **vetor de verificacao**
para o tipo (RF-DES-198). Duas portas, e as duas fecham a mesma falha silenciosa
por caminhos diferentes — a receita garante que existe regra, o vetor garante que
os dois lados a leem igual.

═══════════════════════════════════════════════════════════════════════════
⚠️ PARAMETRO NOVO E `INSERT`, NUNCA CODIGO (SC-027)
═══════════════════════════════════════════════════════════════════════════

Trocar `4` por `6` caixas no mesmo tipo **nao toca `.arb`, nao toca codigo e nao
muda `co_versao_minima`**. E por isso que os numeros sao argumento da receita, e
nao literais espalhados por ela.

O que **ainda exige versao nova do aplicativo** e a chave `.arb` do enunciado: uma
chave desconhecida cai na tela de atualizar. Por isso a chave e parte da receita —
acrescentar um tipo e, por definicao, acrescentar texto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

#: A versao do formato de `js_chegada` que as receitas emitem.
VERSAO_CHEGADA = 1


class TipoSemReceita(ValueError):
    """O tipo nao tem receita — e por isso nao e publicavel.

    ⚠️ Falha alto de proposito. A alternativa (devolver uma chegada vazia) daria
    um desafio que ninguem consegue cumprir, e o log ficaria limpo.
    """


@dataclass(frozen=True, slots=True)
class Receita:
    """Como um tipo vira desafio.

    Atributos:
        nu_tipo_desafio: o numero da dimensao `tb901_tipo_desafio`.
        co_tipo_desafio: o codigo, para leitura humana e para os vetores.
        co_jogo: de que jogo este tipo e.
        co_chave_objetivo: a chave de i18n do enunciado. ⛔ **Nunca a frase**: ela
            viajaria num idioma so.
        montar: `(parametros) -> js_chegada`.
        valores_da_frase: `(parametros, personagem) -> js_objetivo`, os valores
            que entram nos espacos da frase.
        moldes: posicoes de partida de onde este tipo costuma sair. Vazio quer
            dizer "gere a partir do inicio do jogo".

    ⚠️ **Por que MOLDES existem, e a medida que os justifica.** O gerador ingenuo
    parte do tabuleiro vazio (ou da posicao inicial) e joga lances aleatorios ate
    chegar a algo interessante. Isso funciona no Pontinhos, e ⛔ **nao funciona
    nas damas**: medido em 09/09/2026, tres tentativas de gerar *"coroe uma dama
    em 6 lances"* a partir de 40 lances aleatorios deram **zero** candidatos em
    35 segundos — coroar exige atravessar o tabuleiro, e uma abertura aleatoria
    quase nunca deixa uma peca perto da oitava fileira com caminho livre.

    Um molde e uma posicao **de onde o objetivo e alcancavel**, escrita a mao e
    validada pelo motor. O gerador sorteia um molde e o **varia** com poucos
    lances legais antes de procurar a solucao — e e a variacao que impede a fila
    de repetir a mesma posicao todo dia.

    ⚠️ Molde **nao e** o desafio pronto: se a variacao destruir o objetivo, o
    gerador simplesmente nao acha solucao e tenta outra. O molde e ponto de
    partida, nunca garantia.
    """

    nu_tipo_desafio: int
    co_tipo_desafio: str
    co_jogo: str
    co_chave_objetivo: str
    montar: Callable[[Mapping[str, Any]], dict[str, Any]]
    valores_da_frase: Callable[[Mapping[str, Any], str], dict[str, Any]]
    moldes: tuple[str, ...] = ()


def _medida(chave: str, comparador: str, valor: Any) -> dict[str, Any]:
    """Uma clausula de medida, no formato que o avaliador le."""
    return {
        "tipo": "medida",
        "chave": chave,
        "comparador": comparador,
        "valor": valor,
    }


# ═══════════════════════════════════════════════════════════════════════════
# As receitas
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Sao quatro, e nao dez, e isso esta declarado.** As outras seis entram
# quando tiverem receita E vetor — nesta ordem, e nunca uma sem a outra.

RECEITAS: dict[str, Receita] = {
    "pontinhos_fechar_caixas": Receita(
        nu_tipo_desafio=1,
        co_tipo_desafio="pontinhos_fechar_caixas",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoFecharCaixasEmTurnos",
        # "Feche N caixas em T turnos": a janela e de TURNOS, e nao de lances,
        # porque quem fecha caixa joga de novo — quatro caixas em quatro lances
        # seguidos sao um turno so.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "turnos_do_jogador", "n": p["turnos"]},
            "clausulas": [_medida("caixas_fechadas", "maior_ou_igual", p["caixas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "turnos": p["turnos"],
            "personagem": personagem,
        },
    ),
    "pontinhos_chegar_ao_placar": Receita(
        nu_tipo_desafio=4,
        co_tipo_desafio="pontinhos_chegar_ao_placar",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoChegarAoPlacar",
        # Sem limite de turnos: o que importa e o placar no fim.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [_medida("caixas_fechadas", "maior_ou_igual", p["caixas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "personagem": personagem,
        },
    ),
    "damas_coroar": Receita(
        nu_tipo_desafio=6,
        co_tipo_desafio="damas_coroar",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoCoroarEmLances",
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [_medida("damas_coroadas", "maior_ou_igual", p["damas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "damas": p["damas"],
            "lances": p["lances"],
            "personagem": personagem,
        },
        # Finais em que uma branca esta a poucos passos da oitava fileira, com
        # pretas suficientes para a partida nao acabar antes.
        moldes=(
            "W:W9,23,27:B5,12,20",
            "W:W10,24,28:B6,14,21",
            "W:W13,25,30:B8,17,22",
            "W:W14,26,31:B7,18,24",
        ),
    ),
    "damas_capturar_multipla": Receita(
        nu_tipo_desafio=8,
        co_tipo_desafio="damas_capturar_multipla",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoCapturaMultipla",
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [_medida("maior_captura", "maior_ou_igual", p["pecas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "pecas": p["pecas"],
            "lances": p["lances"],
            "personagem": personagem,
        },
        # Posicoes com material suficiente para uma captura encadeada aparecer
        # depois de um ou dois lances.
        moldes=(
            "W:W27,28,31:B15,19,23,4",
            "W:W26,30,32:B14,18,22,3",
            "W:W25,29,31:B13,17,21,2",
            "W:W28,30,32:B16,20,24,1",
        ),
    ),
}


def receita_de(co_tipo_desafio: str) -> Receita:
    """A receita de um tipo. Falha alto se ele nao tiver uma.

    Raises:
        TipoSemReceita: sempre que o tipo nao estiver em [RECEITAS].
    """
    if co_tipo_desafio not in RECEITAS:
        raise TipoSemReceita(
            f"o tipo {co_tipo_desafio!r} nao tem receita. ⛔ Tipo sem receita nao "
            "e publicavel: o desafio sairia com uma linha de chegada que ninguem "
            "escreveu, e o julgamento devolveria 'nao cumpriu' para todo mundo. "
            f"Os que tem receita hoje: {sorted(RECEITAS)}"
        )
    return RECEITAS[co_tipo_desafio]


def tipos_do_jogo(co_jogo: str) -> list[str]:
    """Os tipos publicaveis daquele jogo, em ordem estavel.

    ⚠️ Ordem estavel importa: e ela que faz o rodizio ser reproduzivel, e um
    rodizio que muda de ordem a cada execucao publicaria o mesmo tipo dois dias
    seguidos de vez em quando.
    """
    return sorted(
        codigo for codigo, receita in RECEITAS.items() if receita.co_jogo == co_jogo
    )

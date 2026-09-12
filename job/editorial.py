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
# ⚠️ E o mesmo `nu_maximo_de_meios_lances` vale para a REGUA. Medir com um teto maior
# que o da geracao faria os mascotes resolverem desafios que o gerador nao
# conseguiu montar, e a taxa descreveria uma tarefa diferente da publicada.
#
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ A PALAVRA "LANCE" VALE DUAS COISAS AQUI, E O NOME DIZ QUAL
# ═══════════════════════════════════════════════════════════════════════════
#
# **Meio-lance** e uma entrada da fita: o laco de `_resolver` anda uma volta por
# lance, seja de quem for. **Lance do jogador** e so a vez de quem resolve.
#
#     nu_maximo_de_meios_lances  → MEIOS-lances (os dois lados)  ← este
#     nu_meios_lances_solucao    → MEIOS-lances (o tamanho do gabarito)
#     js_chegada["lances"]       → lances DO JOGADOR (o que a pessoa le)
#
# ⛔ **Nas damas a alternancia e estrita, entao 12 meios-lances sao ~6 lances de
# quem joga.** No Pontinhos nem isso: quem fecha caixa joga de novo, e 12
# meios-lances podem ser 9 de um lado e 3 do outro.
#
# ⚠️ **O nome era `nu_maximo_de_lances` ate 12/09/2026**, e a confusao era real:
# o dono leu "teto de 12" como "doze lances do usuario" — o dobro do que e —, e
# eu ja tinha caido na mesma armadilha em 11/09 lendo a solucao media. Renomear
# custou um `sed`; a ambiguidade ja custou duas leituras erradas.
MAXIMO_DE_MEIOS_LANCES_PADRAO = 12
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
        co_personagens: a que adversarios o tipo se restringe.
    """

    parametros: Mapping[str, Any]
    ic_chegada_encerra_partida: bool
    medidas: Callable[[Mapping[str, Any]], list[dict[str, Any]]]
    co_versao_minima: str = VERSAO_MINIMA_DOS_TIPOS_FUNDADORES
    nu_teto_log: int = TETO_DE_LOG_PADRAO
    nu_maximo_de_meios_lances: int = MAXIMO_DE_MEIOS_LANCES_PADRAO
    nu_lances_de_preparo: int = LANCES_DE_PREPARO_PADRAO

    #: A que adversarios este tipo se restringe. `None` = o rodizio dos quatro.
    #:
    #: ⛔ **Existe porque nem todo desafio cabe contra todo mundo**, e isso so
    #: apareceu com a cadeia longa (12/09/2026): contra o Magno ela e
    #: **impossivel** — medido, 0 de 30 posicoes —, porque vencer no Pontinhos e
    #: partir o tabuleiro em cadeias curtas, o oposto do que o desafio pede.
    #:
    #: ⚠️ **Restringir nao e enfraquecer o adversario**: o personagem publicado
    #: continua jogando no nivel dele, com a semente publicada. O que muda e de
    #: qual lista o rodizio do dia sorteia.
    co_personagens: tuple[str, ...] | None = None


# ═══════════════════════════════════════════════════════════════════════════
# O alvo que NAO vem daqui: `acima_do_guloso`
# ═══════════════════════════════════════════════════════════════════════════

#: A chave cujo numero e **relativo a posicao**, e nao absoluto.
#:
#: ⚠️ **Vocabulario interno.** O que vai na frase e sempre o numero absoluto
#: (*"capture 7 ou mais"*); quem joga nunca ve a palavra "guloso", que seria
#: ininteligivel — ele nao sabe o que um jogador guloso faria naquela posicao.
CHAVE_RELATIVA_AO_GULOSO = "acima_do_guloso"

#: Um `G` plausivel, para as conferencias que rodam SEM uma posicao.
#:
#: ⚠️ **Nao e um padrao de producao.** Ele existe so para que um teste consiga
#: perguntar *"as medidas desta variante fecham em 1000?"* sem ter de gerar um
#: candidato de verdade. ⛔ O valor publicado nunca passa por aqui: ele sai do
#: guloso medido na propria posicao.
GULOSO_DE_EXEMPLO = 5


def alvo_sai_da_posicao(parametros: Mapping[str, Any]) -> bool:
    """Esta variante calcula o alvo a partir da posicao?"""
    return CHAVE_RELATIVA_AO_GULOSO in parametros


def parametros_efetivos(
    parametros: Mapping[str, Any], *, guloso: int
) -> dict[str, Any]:
    """Os numeros que a **receita** consome, com o alvo ja resolvido.

    Args:
        parametros: os do editorial.
        guloso: quantas caixas um jogador que nunca recusa uma caixa faz nesta
            posicao (`G`). Ignorado nas variantes de alvo fixo.

    ⛔ **A traducao mora aqui, e num lugar so.** Ela era uma linha solta no laco
    do gerador; quando as medidas de saida passaram a precisar do mesmo numero,
    havia duas contas para manter iguais — e uma discordancia entre elas
    publicaria uma frase pedindo 7 com a nota calibrada para outro alvo, sem erro
    nenhum.
    """
    if not alvo_sai_da_posicao(parametros):
        return dict(parametros)
    return {"caixas": guloso + parametros[CHAVE_RELATIVA_AO_GULOSO]}


def parametros_para_conferencia(parametros: Mapping[str, Any]) -> dict[str, Any]:
    """Os parametros de uma variante quando nao ha posicao — so para conferir."""
    return parametros_efetivos(parametros, guloso=GULOSO_DE_EXEMPLO)


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


def _medidas_da_cadeia_longa(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Cadeia longa: o merito e a MAIOR cadeia, e o placar aparece sem pontuar.

    ⚠️ **`vr_max` e o proprio alvo**, como nos outros tipos: capturar seis quando
    se pediam seis e nota cheia. ⛔ Normalizar sobre as doze caixas do tabuleiro
    pagaria metade a quem cumpriu o objetivo inteiro.

    ⚠️ **`caixas_fechadas` entra sem peso**, de proposito. Ela e o placar da
    partida, e este desafio **nao e sobre o placar** — quem faz nove caixas em
    cadeias de duas nao cumpriu nada. Ela fica no extrato porque o Raio-X a
    mostra, e porque e ela que explica a diferenca entre as duas coisas.
    """
    return [
        linha_de_faixa(
            "maior_cadeia_capturada",
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
        linha_so_medida("caixas_fechadas", nu_ordem=3),
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


#: ⚠️ **CADA TIPO TEM UMA LISTA DE VARIANTES, e nao um dicionario so** (T049f).
#:
#: > *"E muito importante que estes parametros variem, senao os desafios viram
#: > pura repeticao."* — o dono, 10/09/2026
#:
#: Ate 11/09/2026 havia **uma** publicacao por tipo: todo `chegar_ao_placar` era
#: "7 caixas", todo `coroar` era "1 dama em 6 lances". A **posicao** variava; a
#: **tarefa**, nao.
#:
#: ⚠️ **A escolha e do odometro, e nao sorteada** — `gerador.escolher_variante()`.
#: Sortear faria a idempotencia de T038 depender de sorte: duas execucoes do job
#: para o mesmo dia gerariam desafios diferentes.
#:
#: ⛔ **NENHUMA VARIANTE ENTRA SEM SER MEDIDA**, e o numero anotado ao lado de
#: cada uma e o **pior dia** de oito medidos por
#: `scripts/medir_variantes_do_editorial.py` — quantos candidatos sairam no dia
#: em que sairam menos. ⚠️ **A media esconderia o que importa:** uma variante com
#: 3 candidatos num dia e 0 no outro publica **dia descoberto** a cada duas
#: aparicoes, e a media de 1,5 pareceria saudavel.
#:
#: ⚠️ E o erro nao aparece cedo: uma variante ruim vira dia descoberto **duas
#: semanas depois** de entrar, e o log diz so *"sem candidato"* — sintoma, e nao
#: causa. Foi assim que a primeira execucao real passou quatro dias sem gerar
#: Pontinhos nenhum.
EDITORIAL: dict[str, tuple[Publicacao, ...]] = {
    "pontinhos_fechar_caixas": (
        # ⛔ **`{caixas: 4, turnos: 2}` SAIU em 12/09/2026, e a licao e sobre
        # REMEDIR.** Ela entrou em 11/09 com pior dia **2**, medido antes de a
        # regra de recusa por erro do adversario existir. Remedida com a regra
        # ligada: **0** (2, 0, 0) — dia descoberto na fila a cada aparicao.
        #
        # ⚠️ **Medicao nao e selo vitalicio.** O numero descreve a variante *com
        # o gerador daquele dia*; mudou o gerador, o numero venceu. Quem nao
        # remede publica um ⛔ achando que publica um ✅, e o log so dira "sem
        # candidato" duas semanas depois.
        Publicacao(
            # A mais facil da familia: tres caixas na janela apertada de dois
            # turnos. ⚠️ Dois turnos e apertado de proposito — quem fecha caixa
            # joga de novo, entao as caixas so cabem num turno so quando a cadeia
            # esta armada.
            #
            # Medido 12/09/2026, **com a regra de recusa**: pior dia **1** ·
            # solucao 6,0 lances. (Era 3 antes da regra.)
            parametros={"caixas": 3, "turnos": 2},
            # Tres de doze deixam o jogo em aberto.
            ic_chegada_encerra_partida=False,
            # ⚠️ **Preparo 14, e nao 8** — medido: com 8 tracos o tabuleiro nao
            # tem cadeia formada, e procurar por mais tempo nao inventa uma.
            nu_lances_de_preparo=14,
            medidas=_medidas_do_pontinhos_fechar_caixas,
        ),
        Publicacao(
            # ⚠️ **O mesmo alvo, com um turno a mais** — e a variante que muda a
            # *forma* da tarefa sem mudar o numero: da para chegar la sem a
            # cadeia armada, montando-a.
            # Medido 12/09/2026, com a regra de recusa: pior dia **3** ·
            # solucao 9,9 lances. ⚠️ **A unica da familia que a regra nao derruba**
            # — o turno a mais da folga para o gabarito contornar um lance recusado.
            parametros={"caixas": 4, "turnos": 3},
            ic_chegada_encerra_partida=False,
            nu_lances_de_preparo=14,
            medidas=_medidas_do_pontinhos_fechar_caixas,
        ),
        Publicacao(
            # A mais dura que gera com folga.
            # ⛔ Medidas e **recusadas**: `{"caixas": 5, "turnos": 2}` deu pior dia
            # **0** (2, 0, 2) e `{"caixas": 6, "turnos": 3}` deu pior dia **1**
            # em oito — nenhuma das duas entra.
            # Medido 12/09/2026, com a regra de recusa: pior dia **1** ·
            # solucao 10,3 lances. (Era 3 antes da regra.)
            parametros={"caixas": 5, "turnos": 3},
            ic_chegada_encerra_partida=False,
            nu_lances_de_preparo=14,
            medidas=_medidas_do_pontinhos_fechar_caixas,
        ),
    ),
    "pontinhos_cadeia_longa": (
        Publicacao(
            # ── ⚠️ A IDEIA E DO DONO, 12/09/2026 ─────────────────────────────
            #
            # > *"Deixa o usuario conectar tracos de tal forma que consiga montar
            # > uma cadeia extremamente longa, e depois captura-la, ao inves do
            # > adversario."*
            #
            # A frase: *"Capture 6 ou mais caixas em sequencia"*.
            #
            # ⛔ **SEIS, e nao quatro nem cinco.** Medido em 30 posicoes, as
            # mesmas para os dois lados: quem joga para **vencer** (a CNN no
            # nivel Magno) chega a seis caixas seguidas em **7%** delas; quem
            # joga para a **cadeia**, em 43%. Com quatro, o desafio sairia
            # cumprido por acidente por quem nao fez nada de diferente.
            #
            # Medido 12/09/2026: pior dia **3** · solucao 20,6 lances (~10 lances
            # do jogador). ⚠️ E a tarefa mais longa do Pontinhos hoje.
            parametros={"caixas": 6},
            # ⚠️ Seis de doze nao encerra a partida — sobram caixas.
            ic_chegada_encerra_partida=False,
            # ⛔ **O TABULEIRO COMECA QUASE VAZIO**, e isto e o contrario dos
            # outros tipos de Pontinhos (que usam 14). Cadeia longa se
            # **constroi**: com o tabuleiro ja cheio nao ha o que moldar, e o
            # desafio viraria "capture o que ja esta la".
            nu_lances_de_preparo=4,
            # A janela e a partida inteira, e construir leva tempo.
            nu_maximo_de_meios_lances=34,
            # ⛔ **NUNCA contra o Magno**: medido, 0 de 30 posicoes. Ele parte o
            # tabuleiro em cadeias curtas e controla a paridade — vencer, no
            # Pontinhos, e o oposto do que este desafio pede. Contra o Tex ja cai
            # para 20%; a Cacau (57%) e a Pita (67%) sao onde o tipo vive.
            co_personagens=("cacau", "pita"),
            medidas=_medidas_da_cadeia_longa,
        ),
        Publicacao(
            # A versao dura: sete caixas numa corrida so.
            # Medido 12/09/2026: pior dia **3** · solucao 21,4 lances.
            #
            # ⛔ **E `{caixas: 5}` ficou de FORA, apesar de tambem medir pior 3.**
            # O criterio nao e gerar, e **separar**: quem joga para vencer chega a
            # cinco caixas seguidas em 33% das posicoes, contra 7% em seis. Com
            # cinco, um terco dos dias seria cumprido por quem nao fez nada de
            # diferente — e o desafio deixaria de ensinar o que existe para
            # ensinar.
            parametros={"caixas": 7},
            ic_chegada_encerra_partida=False,
            nu_lances_de_preparo=4,
            nu_maximo_de_meios_lances=34,
            co_personagens=("cacau", "pita"),
            medidas=_medidas_da_cadeia_longa,
        ),
    ),
    "pontinhos_chegar_ao_placar": (
        Publicacao(
            # Sete de doze e a maioria: quem chega la **ja venceu**.
            # Medido 12/09/2026, com a regra de recusa: pior dia **1** ·
            # solucao 22,0 lances. (Era 3 antes da regra.)
            parametros={"caixas": 7},
            # ⚠️ E ainda assim `False`: a partida esta DECIDIDA, e nao terminada
            # — sobram tracos no tabuleiro, e ⛔ o aplicativo nao interrompe quem
            # quiser continuar (RF-DES-213/214).
            ic_chegada_encerra_partida=False,
            # ⚠️ **A janela e a PARTIDA INTEIRA**, e por isso o teto e outro: a
            # solucao medida usa 22 lances, e com 12 nunca se chega a sete caixas.
            nu_maximo_de_meios_lances=34,
            medidas=_medidas_do_pontinhos_placar,
        ),
        Publicacao(
            # Seis de doze e o empate: quem chega la **nao perdeu**.
            # Medido 12/09/2026, com a regra de recusa: pior dia **1** ·
            # solucao 21,3 lances. (Era 3 antes da regra.)
            parametros={"caixas": 6},
            ic_chegada_encerra_partida=False,
            nu_maximo_de_meios_lances=34,
            medidas=_medidas_do_pontinhos_placar,
        ),
        Publicacao(
            # ⚠️ **Cinco nao e maioria**, e a frase nao promete que seja: o
            # objetivo e um placar, e nao a vitoria. A `vr_max` das medidas sai
            # do proprio parametro, entao a nota continua cheia em cinco de cinco.
            # ⛔ Medidas e **recusadas**: `{"caixas": 8}` deu pior dia **0** (0, 0,
            # 1) e `{"caixas": 9}` nao gerou **nada** em tres dias.
            # Medido 12/09/2026, com a regra de recusa: pior dia **1** ·
            # solucao 19,8 lances. (Era 3 antes da regra.)
            parametros={"caixas": 5},
            ic_chegada_encerra_partida=False,
            nu_maximo_de_meios_lances=34,
            medidas=_medidas_do_pontinhos_placar,
        ),
        Publicacao(
            # ── O ALVO SAI DA POSICAO, E NAO DAQUI (desenho do dono, 11/09) ──
            #
            # > *"Se ele capturar de forma gulosa ele fecha o jogo com 5 caixas.
            # > Se capturar usando double dealing ele fecha o jogo com 7. Neste
            # > exemplo o desafio seria: capture 7 ou mais caixas."*
            #
            # ⚠️ **`acima_do_guloso` e vocabulario INTERNO.** O gerador mede
            # quantas caixas um jogador que nunca recusa uma caixa faria naquela
            # posicao (`G`), soma este `1`, e e o numero **absoluto** que vai na
            # frase — quem joga nunca ve a palavra "guloso".
            #
            # ⛔ **Quem so captura nao resolve**, e essa e a diferenca de fundo
            # para as tres publicacoes acima: a solucao ingenua fica excluida
            # **por construcao**, e nao porque alguem julgou que era facil demais.
            # A habilidade cobrada e o *double dealing* — recusar as duas ultimas
            # caixas da cadeia para manter a vez.
            #
            # ⛔ **Preparo 14, e nao o 8 padrao**: com 8 tracos o tabuleiro e
            # comeco de jogo, sem cadeia formada, e sem cadeia nao ha o que
            # recusar. Medido em 60 posicoes reais do `prd` com 14 tracos: 27%
            # rendem um alvo acima do guloso, com diferencas de +1 a +5.
            #
            # ⚠️ **E aqui a regra de recusa por erro do adversario NAO se
            # aplica** (decisao do dono, 12/09/2026): `G` e medido na mesma
            # posicao e contra o mesmo personagem, entao um erro dele levanta os
            # dois lados da conta e se cancela. Com a regra ligada esta variante
            # dava pior dia **0**; sem ela, **3**.
            #
            # Medido 12/09/2026: pior dia **3** · solucao 15,6 lances.
            parametros={"acima_do_guloso": 1},
            # ⚠️ O alvo e um placar, e nao o fim do jogo — como nas irmas.
            ic_chegada_encerra_partida=False,
            nu_maximo_de_meios_lances=34,
            nu_lances_de_preparo=14,
            # ⚠️ As medidas leem `caixas`, e recebem os parametros do
            # **candidato** (`G + 1`), nao os daqui — ver `job/__main__.py`.
            medidas=_medidas_do_pontinhos_placar,
        ),
    ),
    # ⚠️ **AS DAMAS AINDA TEM UMA VARIANTE SO, e isso e pendencia declarada.**
    # Uma geracao de damas custa ~26 s (medido em 11/09/2026), entao medir as
    # candidatas e trabalho de outra janela — o comando esta no cabecalho de
    # `scripts/medir_variantes_do_editorial.py`, e as candidatas ja estao
    # escritas la, em `A_MEDIR`.
    #
    # ⛔ **Ate o numero chegar, elas nao entram.** Uma variante de damas nao
    # medida e pior que nenhuma: os moldes foram escritos e validados contra
    # *"coroar em 6 lances"*, e uma janela mais curta pode nao ser alcancavel a
    # partir de nenhum deles — o que viraria dia descoberto, e nao erro.
    # ⚠️ **MEDIDO em 11/09/2026**, depois da limpeza dos moldes triviais
    # (`scripts/medir_variantes_do_editorial.py damas`, tres dias por candidata):
    #
    #     {damas:1, lances: 4}   pior 3   solucao media 4.3 meios-lances   210s
    #     {damas:1, lances: 6}   pior 3   solucao media 6.8 meios-lances   117s
    #     {damas:1, lances: 8}   pior 3   solucao media 6.8 meios-lances   117s
    #     {damas:1, lances:10}   pior 3   solucao media 6.8 meios-lances   117s
    #
    # ⛔ **So as duas primeiras entraram, e o motivo esta nos numeros iguais.**
    # `lances` e a janela em **lances do jogador**; `nu_lances_solucao` conta
    # **meios-lances** (a fita do gabarito inclui o adversario). Entao 6,8
    # meios-lances sao ~3,4 lances do jogador — e a janela de 6 ja nao aperta
    # nada. As linhas de 6, 8 e 10 saem identicas **inclusive no tempo de
    # geracao** porque o gerador nao descarta candidato nenhum por causa delas:
    # sao a mesma tarefa com um numero maior escrito na frase.
    #
    # ⚠️ **A de 4 aperta de verdade**, e a prova e o custo: 210s contra 117s, com
    # a solucao caindo para 4,3 — o gerador teve de recusar candidatos e procurar
    # mais. E ela que torna a fila variada em DIFICULDADE, e nao so no texto.
    #
    # ⏳ **A variacao que falta medir e a do OUTRO parametro** (`damas: 2`), que
    # muda a tarefa em vez da folga — esta escrita em `A_MEDIR` do script.
    #
    # ═══════════════════════════════════════════════════════════════════════
    # ✅ REMEDIDO EM 12/09/2026, DEPOIS DE O ACERVO IR DE 330 PARA 515 MOLDES
    # ═══════════════════════════════════════════════════════════════════════
    #
    #     {damas:1, lances: 6}   pior 3   solucao media 6.8 meios-lances   103s
    #     {damas:1, lances: 4}   pior 3   solucao media 6.1 meios-lances   176s
    #     {damas:2, lances: 8}   pior 1   solucao media 9.6 meios-lances   525s
    #     {damas:2, lances:10}   pior 1   solucao media 9.6 meios-lances   532s
    #
    # ✅ **A variante de controle nao se moveu** — pior 3, 6,8, e ate um pouco
    # mais rapida. O acervo cresceu 56% e a tarefa que esta no ar continua do
    # mesmo tamanho: era exatamente o que se queria da SOMA (185 moldes reais
    # entraram sem deslocar os 330 que ja funcionavam).
    #
    # ✅ **`lances:10` continua sendo `lances:8` com outro numero na frase** —
    # 9,6 contra 9,6, `[1,3,3]` contra `[1,3,3]`. A decisao de 11/09 se confirma
    # no acervo novo, e nao por inercia.
    #
    # ⚠️ **Mas a de 4 deixou de apertar tanto, e isso enfraquece a justificativa
    # dela.** Ela entrou porque apertava: a solucao caia de 6,8 para 4,3. Hoje
    # cai para **6,1** — sete decimos de meio-lance. O custo ainda sinaliza
    # aperto (176 s contra 103 s: o gerador segue recusando candidato), mas o que
    # a pessoa **joga** quase nao difere. ⏳ Nao e motivo para tira-la agora; e
    # motivo para olha-la de novo na proxima mudanca de acervo.
    "damas_coroar": (
        Publicacao(
            # Uma dama em seis lances — o alvo com que os moldes foram escritos.
            parametros={"damas": 1, "lances": 6},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_coroar,
        ),
        Publicacao(
            # A mesma dama com a janela apertada: a unica medida que muda o que o
            # gerador aceita.
            parametros={"damas": 1, "lances": 4},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_coroar,
        ),
        # ── ⚠️ DUAS DAMAS: a variante que o dono pediu, e a mais longa ────────
        #
        # ⚠️ **Pedido dele, olhando a curadoria** (11/09/2026): *"esta solucao me
        # parece extremamente banal. Ate um macaco treinado conseguiria resolver.
        # **Se fosse ao menos coroar 2 damas**, talvez fizesse sentido"*.
        #
        # ✅ **MEDIDO no mesmo dia**, e o resultado da razao a ele:
        #
        #     {damas:1, lances: 6}   pior 3   solucao media 7.4 meios-lances    88s
        #     {damas:1, lances: 4}   pior 3   solucao media 5.2 meios-lances   132s
        #     {damas:2, lances: 8}   pior 3   solucao media 9.7 meios-lances   314s
        #     {damas:2, lances:10}   pior 3   solucao media 9.4 meios-lances   265s
        #
        # ⚠️ **9,7 meios-lances sao ~5 lances do jogador**, contra ~3,7 da melhor
        # variante de uma dama so. E a tarefa mais longa que as damas tem hoje.
        #
        # ⛔ **So a de 8 entrou, e o motivo e o de sempre:** 9,7 e 9,4 sao o mesmo
        # numero, entao `lances: 10` e a mesma tarefa com uma folga maior escrita
        # na frase. Publicar as duas seria a repeticao que a variacao existe para
        # acabar.
        #
        # ⚠️ **O preco e tempo de geracao**: ~105 s por dia contra ~29 s da
        # variante de uma dama. O job acorda uma vez por dia, entao cabe — mas e
        # o numero a olhar se a execucao no Railway comecar a se arrastar.
        #
        # ⚠️ **Ressalva honesta sobre a medida:** as duas linhas de `damas: 2`
        # foram medidas com a maquina dividida com a cacada de moldes, e o teto
        # de tempo do gerador (2 s por lance) pode ter mordido. ⛔ Isso torna o
        # **veredito** conservador (passou apesar da disputa, entao passa sozinho)
        # mas deixa a media de lances com incerteza para cima.
        #
        # ⚠️ **12/09/2026: a ressalva acima virou pendencia de verdade.** Na
        # remedicao com o acervo de 515 moldes, esta variante caiu de `pior 3`
        # para **`pior 1`** (9,6 meios-lances, 525 s) — e a rodada de novo
        # dividiu a maquina, agora com a suite do aplicativo. ⛔ `pior 1` ainda
        # publica, mas e folga ZERO: o proximo degrau e o dia descoberto.
        # ⏳ Remedir com a maquina livre antes de mexer em qualquer botao daqui.
        Publicacao(
            parametros={"damas": 2, "lances": 8},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_coroar,
        ),
    ),
    # ⚠️ **MEDIDO no mesmo dia, e o resultado foi UMA variante so:**
    #
    #     {pecas:2, lances:4}   pior 3   solucao media 2.8 meios-lances   116s
    #     {pecas:2, lances:6}   pior 3   solucao media 2.8 meios-lances   116s
    #     {pecas:2, lances:8}   pior 3   solucao media 2.8 meios-lances   116s
    #
    # ⛔ **Os tres numeros sao o mesmo numero.** A captura encadeada cai em ~1,4
    # lances do jogador; qualquer janela de 4 para cima e folga pura, e as tres
    # linhas descrevem a mesma geracao. Publicar as tres seria a "pura repeticao"
    # que esta tarefa existe para acabar, com tres rotulos diferentes.
    #
    # ⚠️ **E a medicao ANTERIOR deste tipo estava contaminada**: ela deu `[3,2,1]`
    # com solucao media 2,0 porque rodou sobre 5 moldes, **tres deles entregando
    # o objetivo no primeiro lance** (T049g). Com os 9 moldes limpos, os mesmos
    # parametros dao `[3,3,3]` — a fragilidade era dos moldes, nao do tipo.
    #
    # ✅ **A janela APERTADA foi medida em 11/09/2026, e nao muda nada:**
    #
    #     {pecas:2, lances:4}   pior 3   solucao media 3.0 meios-lances   69s
    #     {pecas:2, lances:3}   pior 3   solucao media 3.0 meios-lances   70s
    #     {pecas:2, lances:2}   pior 3   solucao media 3.0 meios-lances   70s
    #
    # ⛔ **Tres numeros iguais, e desta vez ate o tempo e igual.** A captura
    # encadeada cai **sempre** em 3 meios-lances — dois lances do jogador —, e
    # nenhuma janela de 2 para cima chega perto disso. O tipo e estruturalmente
    # curto, e ⛔ **isso nao se conserta com parametro**: e o que a posicao pede.
    #
    # ⚠️ **O dono reclamou exatamente disto** (*"o usuario entra pra resolver um
    # desafio e nao joga praticamente nada"*), e a resposta honesta e que a saida
    # esta nos **moldes**, nao aqui: os de hoje foram cacados com o alvo *"o
    # objetivo cai no lance 3"*, que e o piso do script (`LANCE_MINIMO = 3`).
    # Moldes mais distantes do alvo dariam capturas que exigem preparo — e e a
    # cacada de 1.000 candidatas que pode revela-los, escolhendo pelo topo da
    # ordenacao (ela ja ordena pelo objetivo que demora mais a cair).
    #
    # ═══════════════════════════════════════════════════════════════════════
    # ✅ REMEDIDO EM 12/09/2026, COM O ACERVO REAL — E O PARAGRAFO ACIMA CAIU
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⚠️ Tudo o que esta escrito acima descreve os **9 moldes sinteticos**. Eles
    # sairam: o acervo foi TROCADO por 295 moldes pescados de partidas humanas
    # do `prd` (material 17,3 contra ~7). Os mesmos parametros, acervo novo:
    #
    #     {pecas:2, lances:4}   pior 1   solucao media  3.7 meios-lances   603s
    #     {pecas:2, lances:3}   pior 1   solucao media  3.7 meios-lances   602s
    #     {pecas:2, lances:2}   pior 1   solucao media  3.0 meios-lances   671s
    #     {pecas:3, lances:4}   pior 0   ⛔ NAO ENTRA                      696s
    #     {pecas:3, lances:6}   pior 1   solucao media 10.3 meios-lances   691s
    #
    # ⚠️ **A janela de 2 virou variante de verdade.** Em 11/09 as tres davam o
    # mesmo numero **e o mesmo tempo** — assinatura de janela que nao descarta
    # nada. Hoje `lances:2` se separa (3,0 contra 3,7, com 70 s a mais): ela
    # passou a recusar candidato, que e o unico criterio para merecer linha
    # propria aqui.
    #
    # ⚠️ **E o "2 pecas" pode virar 3 — mas so com janela 6.** Era pergunta do
    # dono (*"este 2 e fixo ou varia?"*). Com `lances:4` da **zero nos tres
    # dias**; com `lances:6` da pior 1, e a solucao sobe para 10,3 meios-lances
    # (~5,2 lances do jogador) — a tarefa **mais longa** que as damas tem, mais
    # longa ate que o coroar de duas damas. ⛔ **O aperto tem nome:** 10,3 contra
    # um teto de geracao de **12**, margem de menos de dois meios-lances.
    #
    # ⏳ **Nenhuma das duas entrou ainda** — a decisao e de quem le o numero, e o
    # `pior 1` pede uma remedicao com a maquina livre (esta rodada dividiu o
    # computador com a suite do aplicativo, e o gerador tem teto de 2 s por
    # lance). Detalhe em `docs/historico_decisoes.md`, 12/09/2026.
    "damas_capturar_multipla": (
        Publicacao(
            # Uma captura de duas pecas em quatro lances.
            parametros={"pecas": 2, "lances": 4},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_captura,
        ),
    ),
}


def variantes_de(co_tipo_desafio: str) -> tuple[Publicacao, ...]:
    """Todas as variantes daquele tipo, na ordem do odometro.

    Raises:
        TipoSemEditorial: sempre que o tipo nao estiver em [EDITORIAL].

    ⚠️ **Nunca devolve tupla vazia**: um tipo sem nenhuma variante seria um tipo
    sem numeros, e e exatamente o que `TipoSemEditorial` existe para recusar.
    """
    if co_tipo_desafio not in EDITORIAL:
        raise TipoSemEditorial(
            f"o tipo {co_tipo_desafio!r} nao tem editorial. ⛔ Ele tem receita "
            "(sabe-se COMO julga-lo), mas ninguem disse com QUE NUMEROS publica-lo "
            "— e um padrao aqui poria no ar um desafio cuja dificuldade ninguem "
            f"escolheu. Os que tem editorial hoje: {sorted(EDITORIAL)}"
        )

    variantes = EDITORIAL[co_tipo_desafio]
    if not variantes:
        raise TipoSemEditorial(
            f"o tipo {co_tipo_desafio!r} esta no editorial com **zero** variantes. "
            "⛔ Isso e o mesmo que nao ter editorial, so que mais dificil de ver: "
            "a lista existe, e esta vazia."
        )
    return variantes


def publicacao_de(co_tipo_desafio: str, nu_variante: int) -> Publicacao:
    """A variante `nu_variante` daquele tipo.

    Args:
        co_tipo_desafio: o tipo.
        nu_variante: o indice que `gerador.escolher_variante()` devolveu.
            ⛔ **Obrigatorio, e sem valor padrao.** Um padrao `0` faria uma
            chamada esquecida publicar a **primeira** variante para sempre — a
            fila voltaria a repetir a mesma tarefa todo dia, e ⚠️ **nada
            denunciaria**: o desafio sairia bem formado, so que sempre igual. E o
            mesmo motivo pelo qual `RegrasXp.calcularGanho` exige o perfil do jogo
            sem padrao.

    Raises:
        TipoSemEditorial: se o tipo nao tiver editorial.
        IndexError: se o indice nao existir. ⚠️ Falhar alto e melhor que dar a
            volta com `% len(...)` aqui: o resto so esconderia um odometro
            calculado com o numero errado de variantes.
    """
    return variantes_de(co_tipo_desafio)[nu_variante]


__all__ = [
    "EDITORIAL",
    "LANCES_DE_PREPARO_PADRAO",
    "MAXIMO_DE_MEIOS_LANCES_PADRAO",
    "TETO_DE_LOG_PADRAO",
    "VERSAO_MINIMA_DOS_TIPOS_FUNDADORES",
    "Publicacao",
    "TipoSemEditorial",
    "publicacao_de",
    "variantes_de",
]

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
        Publicacao(
            # Os numeros do exemplo do `data-model.md`: quatro caixas em dois
            # turnos, num tabuleiro de doze. ⚠️ Dois turnos e apertado de
            # proposito — quem fecha caixa joga de novo, entao quatro caixas
            # cabem num turno so quando a cadeia esta armada.
            #
            # Medido 11/09/2026: pior dia **2** candidatos · solucao 6,6 lances.
            parametros={"caixas": 4, "turnos": 2},
            # Quatro de doze deixam o jogo em aberto.
            ic_chegada_encerra_partida=False,
            # ⚠️ **Preparo 14, e nao 8** — medido: com 8 tracos o tabuleiro nao
            # tem cadeia de 4 caixas, e procurar por mais tempo nao inventa uma.
            nu_lances_de_preparo=14,
            medidas=_medidas_do_pontinhos_fechar_caixas,
        ),
        Publicacao(
            # A mais facil da familia: tres caixas na mesma janela apertada.
            # Medido: pior dia **3** · solucao 5,7 lances.
            parametros={"caixas": 3, "turnos": 2},
            ic_chegada_encerra_partida=False,
            nu_lances_de_preparo=14,
            medidas=_medidas_do_pontinhos_fechar_caixas,
        ),
        Publicacao(
            # ⚠️ **O mesmo alvo, com um turno a mais** — e a variante que muda a
            # *forma* da tarefa sem mudar o numero: da para chegar la sem a
            # cadeia armada, montando-a.
            # Medido: pior dia **3** · solucao 8,6 lances.
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
            # Medido: pior dia **3** · solucao 9,8 lances.
            parametros={"caixas": 5, "turnos": 3},
            ic_chegada_encerra_partida=False,
            nu_lances_de_preparo=14,
            medidas=_medidas_do_pontinhos_fechar_caixas,
        ),
    ),
    "pontinhos_chegar_ao_placar": (
        Publicacao(
            # Sete de doze e a maioria: quem chega la **ja venceu**.
            # Medido: pior dia **2** · solucao 21,5 lances.
            parametros={"caixas": 7},
            # ⚠️ E ainda assim `False`: a partida esta DECIDIDA, e nao terminada
            # — sobram tracos no tabuleiro, e ⛔ o aplicativo nao interrompe quem
            # quiser continuar (RF-DES-213/214).
            ic_chegada_encerra_partida=False,
            # ⚠️ **A janela e a PARTIDA INTEIRA**, e por isso o teto e outro: a
            # solucao medida usa 22 lances, e com 12 nunca se chega a sete caixas.
            nu_maximo_de_lances=34,
            medidas=_medidas_do_pontinhos_placar,
        ),
        Publicacao(
            # Seis de doze e o empate: quem chega la **nao perdeu**.
            # Medido: pior dia **3** · solucao 20,2 lances.
            parametros={"caixas": 6},
            ic_chegada_encerra_partida=False,
            nu_maximo_de_lances=34,
            medidas=_medidas_do_pontinhos_placar,
        ),
        Publicacao(
            # ⚠️ **Cinco nao e maioria**, e a frase nao promete que seja: o
            # objetivo e um placar, e nao a vitoria. A `vr_max` das medidas sai
            # do proprio parametro, entao a nota continua cheia em cinco de cinco.
            # ⛔ Medidas e **recusadas**: `{"caixas": 8}` deu pior dia **0** (0, 0,
            # 1) e `{"caixas": 9}` nao gerou **nada** em tres dias.
            # Medido: pior dia **3** · solucao 18,9 lances.
            parametros={"caixas": 5},
            ic_chegada_encerra_partida=False,
            nu_maximo_de_lances=34,
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
    "MAXIMO_DE_LANCES_PADRAO",
    "TETO_DE_LOG_PADRAO",
    "VERSAO_MINIMA_DOS_TIPOS_FUNDADORES",
    "Publicacao",
    "TipoSemEditorial",
    "publicacao_de",
    "variantes_de",
]

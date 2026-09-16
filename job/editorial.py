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

#: O PISO do gabarito, em meios-lances. ⛔ **Zero quer dizer "sem piso"**, que e
#: o comportamento de sempre.
#:
#: ⛔ **Ele existe porque o teto sozinho nunca alongou desafio nenhum**, e essa
#: licao custou tres tentativas. O dono relatou em 11/09/2026:
#:
#: > *"Todos sao resolviveis em 3 lances no total. O usuario entra pra resolver
#: > um desafio e nao joga praticamente nada. Consegue resolve-los em uns 10
#: > segundos e sai do App?"*
#:
#: ⚠️ **As duas primeiras correcoes mexeram no ACERVO** — cortaram os moldes
#: curtos da lista — e as duas reincidiram. O motivo e aritmetico: o gerador pede
#: 3 candidatos e fica com o primeiro que cabe na janela, e **o mais curto cabe
#: sempre**. Cortar a lista so muda qual e o mais curto que sobrou. Em 16/09/2026
#: o acervo do `damas_coroar` foi trocado inteiro e **42% dele ainda resolvia em
#: 2 lances do jogador**.
#:
#: ⚠️ **E aumentar `js_chegada["lances"]` tambem nao alonga** — medido em 11/09:
#: as linhas de 6, 8 e 10 lances sairam identicas **inclusive no tempo de
#: geracao**, porque o gerador nao descarta candidato nenhum por causa delas. Sao
#: a mesma tarefa com um numero maior escrito na frase.
#:
#: ⛔ **O padrao e ZERO de proposito.** Ligar o piso em todos os tipos de uma vez
#: mudaria sete variantes ja publicadas sem que nenhuma fosse medida — e variante
#: nao medida e a regra que este editorial inteiro existe para nao quebrar. Cada
#: tipo liga o seu quando a medicao disser em que numero ele para de gerar.
MINIMO_DE_MEIOS_LANCES_PADRAO = 0

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

    #: O piso do gabarito, em MEIOS-lances. Zero = sem piso.
    #:
    #: ⚠️ **E o irmao do teto, e os dois se leem na mesma unidade:** `9` aqui sao
    #: ~5 lances de quem resolve, porque nas damas a alternancia e estrita.
    #: ⛔ Um piso ACIMA do teto nunca gera — ha cadeado para isso.
    nu_minimo_de_meios_lances: int = MINIMO_DE_MEIOS_LANCES_PADRAO

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
# OS ALVOS QUE NAO VEM DAQUI: `acima_do_guloso` e o material das damas
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Sao dois mecanismos com a mesma forma, e um deles e novo (14/09/2026).**
# O editorial publica uma variante escrita em vocabulario **relativo**, e quem a
# traduz para numero absoluto e quem tem a posicao na mao — o gerador.
#
#     acima_do_guloso: 2   →   caixas: G + 2          (mede-se o guloso)
#     capturar: 3          →   resta_ao_adversario: A - 3   (contam-se as pecas)
#     entregar: 1          →   resta_a_voce:        M - 1   (idem)
#
# ⛔ **Por que o segundo precisou existir.** O `damas_sacrificio` pede *"troque
# uma peca por tres"*, e isso e uma afirmacao sobre **quanto sobrou dos dois
# lados**. Escrever `material_restante <= 4` a mao no editorial valeria para um
# molde e mentiria em todos os outros: os moldes pescados de partidas reais tem
# material de 5 a 12 pecas por lado, entao um teto fixo publicaria ora um desafio
# impossivel, ora um que ja nasce cumprido. ⚠️ **E nenhum dos dois daria erro** —
# o impossivel vira dia descoberto semanas depois, e o cumprido vira desafio de
# um toque.

#: A chave cujo numero e **relativo a posicao**, e nao absoluto.
#:
#: ⚠️ **Vocabulario interno.** O que vai na frase e sempre o numero absoluto
#: (*"capture 7 ou mais"*); quem joga nunca ve a palavra "guloso", que seria
#: ininteligivel — ele nao sabe o que um jogador guloso faria naquela posicao.
CHAVE_RELATIVA_AO_GULOSO = "acima_do_guloso"

#: Quantas pecas do adversario o desafio pede que se tire do tabuleiro.
#:
#: ⚠️ **Tambem e vocabulario interno**, e pela mesma razao: a frase diz *"capture
#: 3 de Pita"*, e a clausula diz `material_do_adversario <= A - 3`. Quem joga ve
#: o que fez; o juiz conta o que sobrou.
CHAVE_CAPTURAR = "capturar"

#: Quantas pecas **proprias** o desafio admite perder — e, no sacrificio, EXIGE.
#:
#: ⛔ **E ela que faz o sacrificio ser sacrificio.** Sem esta clausula o tipo e
#: `damas_capturar_multipla` com outro nome: capturar tres sem dar nada e o
#: desafio que ja esta no ar desde 12/09/2026.
CHAVE_ENTREGAR = "entregar"

#: Um `G` plausivel, para as conferencias que rodam SEM uma posicao.
#:
#: ⚠️ **Nao e um padrao de producao.** Ele existe so para que um teste consiga
#: perguntar *"as medidas desta variante fecham em 1000?"* sem ter de gerar um
#: candidato de verdade. ⛔ O valor publicado nunca passa por aqui: ele sai do
#: guloso medido na propria posicao.
GULOSO_DE_EXEMPLO = 5

#: Um material plausivel, pelo mesmo motivo e com a mesma ressalva.
#:
#: ⚠️ **E o tabuleiro CHEIO (12 x 12), de proposito**, e nao a media dos moldes.
#: O cadeado que mais depende deste numero e o de *"ninguem cumpre sem jogar"*
#: (`test_tipos_propostos.py`), e ele avalia a chegada contra as medidas de quem
#: ainda nao fez um lance — onde o material tambem esta cheio. ⛔ Com dois numeros
#: diferentes o teste continuaria verde, mas por comparar duas posicoes que nao
#: existem juntas: passaria a provar menos do que o nome dele promete.
MATERIAL_DE_EXEMPLO = (12, 12)


def alvo_sai_da_posicao(parametros: Mapping[str, Any]) -> bool:
    """Esta variante calcula o alvo a partir da posicao?"""
    return CHAVE_RELATIVA_AO_GULOSO in parametros


def alvo_sai_do_material(parametros: Mapping[str, Any]) -> bool:
    """Esta variante calcula o alvo contando as pecas do tabuleiro?"""
    return CHAVE_CAPTURAR in parametros or CHAVE_ENTREGAR in parametros


class MaterialInsuficiente(ValueError):
    """A posicao nao tem pecas suficientes para o que a variante pede.

    ⚠️ **Nao e defeito: e uma posicao que nao serve.** Pedir *"capture 3"* num
    molde onde o adversario tem duas pecas produziria a clausula
    `material_do_adversario <= -1`, que nenhuma partida cumpre — e o sintoma
    chegaria como **dia descoberto**, semanas depois, sem uma linha de log
    apontando para a causa.

    ⛔ Por isso ela sobe, e quem chama decide: o gerador **descarta a tentativa**
    e tenta outro molde (ha centenas), e o script de pescaria conta o descarte
    como motivo, em vez de o confundir com *"o Sagaz nao resolveu"*.
    """


def parametros_efetivos(
    parametros: Mapping[str, Any],
    *,
    guloso: int | None = None,
    material: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Os numeros que a **receita** consome, com o alvo ja resolvido.

    Args:
        parametros: os do editorial.
        guloso: quantas caixas um jogador que nunca recusa uma caixa faz nesta
            posicao (`G`). So e lido nas variantes de `acima_do_guloso`.
        material: `(minhas_pecas, pecas_do_adversario)` na posicao publicada. So
            e lido nas variantes de `capturar`/`entregar`.

    Returns:
        Um dicionario com os numeros **absolutos** que `Receita.montar` espera.

    Raises:
        MaterialInsuficiente: a posicao nao comporta o que a variante pede.
        TypeError: a variante e relativa e o valor de referencia nao veio.

    ⛔ **A traducao mora aqui, e num lugar so.** Ela era uma linha solta no laco
    do gerador; quando as medidas de saida passaram a precisar do mesmo numero,
    havia duas contas para manter iguais — e uma discordancia entre elas
    publicaria uma frase pedindo 7 com a nota calibrada para outro alvo, sem erro
    nenhum.
    """
    if alvo_sai_da_posicao(parametros):
        if guloso is None:
            raise TypeError(
                "esta variante e relativa ao guloso e nenhum `guloso=` foi dado"
            )
        return {"caixas": guloso + parametros[CHAVE_RELATIVA_AO_GULOSO]}

    if alvo_sai_do_material(parametros):
        if material is None:
            raise TypeError(
                "esta variante e relativa ao material e nenhum `material=` foi dado"
            )
        meu, do_adversario = material
        # ⚠️ Os relativos ficam no dicionario **junto** com os absolutos: e deles
        # que a frase se serve (*"troque 1 por 3"*), enquanto a clausula consome
        # os absolutos. Apagar os relativos aqui deixaria o enunciado sem numero.
        saida = dict(parametros)
        if CHAVE_CAPTURAR in parametros:
            quantas = parametros[CHAVE_CAPTURAR]
            if do_adversario < quantas:
                raise MaterialInsuficiente(
                    f"a variante pede capturar {quantas}, e o adversario tem "
                    f"{do_adversario} peca(s)"
                )
            saida["resta_ao_adversario"] = do_adversario - quantas
        if CHAVE_ENTREGAR in parametros:
            quantas = parametros[CHAVE_ENTREGAR]
            # ⛔ **O piso e 1, e nao 0.** Com `resta_a_voce: 0` a clausula seria
            # cumprida por quem ficou sem pecas — ou seja, por quem **perdeu a
            # partida**. Um desafio nao se cumpre perdendo.
            if meu - quantas < 1:
                raise MaterialInsuficiente(
                    f"a variante pede entregar {quantas}, e voce tem {meu} peca(s): "
                    "sobraria menos de uma"
                )
            saida["resta_a_voce"] = meu - quantas
        return saida

    return dict(parametros)


def parametros_para_conferencia(parametros: Mapping[str, Any]) -> dict[str, Any]:
    """Os parametros de uma variante quando nao ha posicao — so para conferir."""
    return parametros_efetivos(
        parametros, guloso=GULOSO_DE_EXEMPLO, material=MATERIAL_DE_EXEMPLO
    )


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


# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ OS QUATRO TIPOS DE PONTINHOS DE 14/09, E A ARMADILHA DA DIRECAO
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **A direcao de cada feito e GLOBAL, e vem do catalogo** — `lances_do_jogador`
# e `menor_melhor` para o app inteiro, porque em quase todo desafio economizar
# lance e merito.
#
# ⚠️ **Nos dois tipos de "aguente" isso se INVERTE**, e a inversao nao tem como
# ser escrita: em `nao_entregar` e `paciencia`, quem resiste **mais** lances joga
# **melhor**. Pontuar `lances_do_jogador` ali pagaria mais a quem aguentou menos.
#
# ✅ **A saida e nao pontua-la nesses dois** (`linha_so_medida`, peso zero): ela
# continua no extrato e no Raio-X, que e onde ela explica o que aconteceu, e o
# peso inteiro vai para a medida que **e** o objetivo.
#
# ⛔ **A alternativa — mudar `co_direcao` no catalogo — esta descartada**, e o
# motivo e que ela quebraria os cinco tipos em que economizar lance e merito de
# verdade. A direcao e do FEITO, nao do desafio.


def _medidas_do_pontinhos_nao_entregar(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Nao entregar: o merito e o zero do adversario, e so ele pontua.

    ⚠️ **A faixa vai de 0 ate o numero de lances pedidos**, e nao ate as doze
    caixas do tabuleiro: em `lances` lances o adversario nao teria como fechar
    doze, e normalizar por um maximo inalcancavel faria quase todo mundo tirar
    nota quase cheia — inclusive quem entregou tudo o que dava.
    """
    return [
        linha_de_faixa(
            "caixas_do_adversario",
            nu_ordem=1,
            vr_peso="1.000",
            vr_min=0,
            vr_max=p["lances"],
        ),
        # ⛔ Peso zero, e nao esquecimento — ver o bloco acima sobre a direcao.
        linha_so_medida("lances_do_jogador", nu_ordem=2),
        linha_so_medida("caixas_fechadas", nu_ordem=3),
    ]


def _medidas_do_pontinhos_economia(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Economia de lances: aqui `lances_do_jogador` pontua, e pesado.

    ⚠️ **E o unico tipo em que a economia E o objetivo**, entao ela leva mais
    peso que nos outros (0,500 contra os 0,300/0,400 habituais). ⛔ O alvo de
    caixas continua pontuando: sem ele, quem nao fechasse nada tiraria nota
    cheia por ter gasto zero lance.
    """
    return [
        linha_de_faixa(
            "caixas_fechadas",
            nu_ordem=1,
            vr_peso="0.500",
            vr_min=0,
            vr_max=p["caixas"],
        ),
        linha_de_fracao(
            "lances_do_jogador",
            nu_ordem=2,
            vr_peso="0.500",
            co_sobre="lances_da_solucao",
        ),
        linha_so_medida("caixas_do_adversario", nu_ordem=3),
    ]


def _medidas_do_pontinhos_troca(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Troca favoravel: as DUAS metades do objetivo pontuam, e em partes iguais.

    ⚠️ **E o unico tipo em que `caixas_do_adversario` tem peso ao lado de outra
    medida**, e e isso que descreve a tarefa: fechar muito cedendo pouco. ⛔ Dar
    o peso so ao que se fecha faria o tipo virar `chegar_ao_placar`.

    ⚠️ **O teto da faixa do que se cede e `ceder + 1`**, e nao `ceder`: com o
    teto no proprio alvo, quem cedesse exatamente o permitido tiraria **zero**
    naquela parcela, e ele **cumpriu** o desafio. O `+1` poe o zero da nota uma
    caixa depois do limite, que e onde o desafio de fato falha.
    """
    return [
        linha_de_faixa(
            "caixas_fechadas",
            nu_ordem=1,
            vr_peso="0.500",
            vr_min=0,
            vr_max=p["ganhar"],
        ),
        linha_de_faixa(
            "caixas_do_adversario",
            nu_ordem=2,
            vr_peso="0.500",
            vr_min=0,
            vr_max=p["ceder"] + 1,
        ),
        linha_so_medida("lances_do_jogador", nu_ordem=3),
    ]


def _medidas_do_pontinhos_paciencia(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Paciencia: as duas medidas do objetivo tem direcao INVERTIDA aqui.

    ⛔ **Nenhuma das duas pode pontuar, e por motivos opostos:**

      · `caixas_fechadas` e `maior_melhor` no catalogo, e aqui fechar caixa
        **quebra** o desafio — pontua-la pagaria exatamente o erro;
      · `lances_do_jogador` e `menor_melhor`, e aqui aguentar mais e melhor.

    ✅ Sobra `caixas_do_adversario`, que e a unica cuja direcao do catalogo
    coincide com a do desafio: nao ceder e melhor, aqui e em toda parte.

    ⚠️ **Peso 1,000 numa medida so nao e preguica**: este desafio e binario por
    natureza — ou voce atravessou os lances sem mexer no placar, ou nao. A
    gradacao que existe e *quanto* se cedeu ao falhar, e e ela que a faixa mede.
    """
    return [
        linha_de_faixa(
            "caixas_do_adversario",
            nu_ordem=1,
            vr_peso="1.000",
            vr_min=0,
            vr_max=p["lances"],
        ),
        linha_so_medida("caixas_fechadas", nu_ordem=2),
        linha_so_medida("lances_do_jogador", nu_ordem=3),
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


def _medidas_do_damas_sacrificio(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Sacrificio: o merito e o que sumiu do adversario.

    ⛔ **`material_restante` NAO PODE PONTUAR AQUI, e a razao e a mesma da
    `pontinhos_paciencia`: a direcao do catalogo esta VIRADA em relacao a do
    desafio.** No catalogo ela e `maior_melhor` — em quase todo desafio de damas
    conservar peca e bom. ⚠️ **Neste tipo perder peca e EXIGIDO**: e ela que faz o
    sacrificio ser sacrificio, e pontua-la pagaria exatamente a quem nao
    sacrificou nada.

    ⚠️ **A faixa vai do estado de PARTIDA ao ALVO, e nao de zero ao alvo.** As
    outras faixas do editorial comecam em zero porque medem coisa que so cresce
    (caixas fechadas, damas coroadas); esta mede o que **sobrou** do adversario,
    que comeca cheio e diminui:

        vr_min = resta_ao_adversario   →  cumpriu o pedido       nota 1,0
        vr_max = resta + capturar = A  →  nao comeu nada         nota 0,0

    ⚠️ `menor_melhor` inverte a conta em `extrato_xp`, e comer **mais** do que o
    pedido cai fora da faixa pelo lado bom — o `_clamp` segura em 1,0.

    ⛔ **E `A` sai dos parametros, nunca de um numero escrito aqui:** quem publica
    e o gerador, com `resta_ao_adversario` ja calculado na posicao do dia.
    """
    return [
        linha_de_faixa(
            "material_do_adversario",
            nu_ordem=1,
            vr_peso="0.700",
            vr_min=p["resta_ao_adversario"],
            vr_max=p["resta_ao_adversario"] + p["capturar"],
        ),
        linha_de_fracao(
            "lances_do_jogador",
            nu_ordem=2,
            vr_peso="0.300",
            co_sobre="lances_da_solucao",
        ),
        linha_so_medida("material_restante", nu_ordem=3),
    ]


def _medidas_do_damas_sobreviver(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Sobreviver: o merito e o material que ficou de pe.

    ⛔ **AS OUTRAS DUAS MEDIDAS FICAM COM PESO ZERO, e cada uma por um motivo
    diferente — nenhum deles e falta de ideia:**

      · `lances_do_jogador` e `menor_melhor` no catalogo, e aqui **aguentar mais
        e melhor**. E a direcao virada da `pontinhos_paciencia`, no outro jogo;

      · `material_do_adversario` e `menor_melhor`, e a direcao ate **coincide** —
        comer peca nao quebra este desafio. ⛔ **Mas pontua-la pagaria pelo
        comportamento que faz falhar.** Foi o que a regua mostrou em 15/09/2026:
        quem joga para vencer troca pecas, e trocar pecas estando atras e como se
        perde. ⚠️ *"Resistir nao e vencer"* — e o XP nao pode dizer o contrario
        do enunciado.

    ✅ Sobra `material_restante`, que e `maior_melhor` no catalogo e aqui tambem.
    Peso 1,000 numa medida so nao e preguica: como a paciencia, este desafio e
    **binario por natureza** — ou voce aguentou os lances dentro do teto de
    perdas, ou nao. A gradacao que existe e *quanto* material sobrou.

    ⚠️ **E o topo da faixa e o PISO do desafio** (`resta_a_voce = M - entregar`),
    como o alvo e o topo em `damas_coroar`: quem cumpre leva a parcela cheia, e
    quem fica abaixo gradua entre 0 e 1. ⛔ Nao adianta pedir mais que o piso —
    o `_clamp` segura em 1,0, e o desafio ja estaria cumprido de qualquer jeito.
    """
    return [
        linha_de_faixa(
            "material_restante",
            nu_ordem=1,
            vr_peso="1.000",
            vr_min=0,
            vr_max=p["resta_a_voce"],
        ),
        linha_so_medida("lances_do_jogador", nu_ordem=2),
        linha_so_medida("material_do_adversario", nu_ordem=3),
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
#: ⛔ **NENHUMA VARIANTE ENTRA SEM SER MEDIDA**, e o rotulo anotado ao lado de
#: cada uma diz como ela se saiu no **dia mais fraco** da amostra, medido por
#: `scripts/medir_variantes_do_editorial.py` — quantos candidatos sairam no dia
#: em que sairam menos. ⚠️ **A media esconderia o que importa:** uma variante com
#: 3 candidatos num dia e 0 no outro publica **dia descoberto** a cada duas
#: aparicoes, e a media de 1,5 pareceria saudavel.
#:
#: ⚠️ **Os rotulos, e o que cada um quer dizer na fila** (o job pede 3 candidatos
#: por dia e publica UM: o primeiro que cai na banda de dificuldade):
#:
#:     FOLGA        3 de 3  sobra candidato; o job escolhe o mais bem calibrado
#:     APERTADO     2 de 3  ja publica, com menos escolha
#:     NO LIMITE    1 de 3  publica o unico que houver, calibrado ou nao
#:     SEM DESAFIO  0 de 3  a fila fica com um dia vazio, e a pessoa ve na tela
#:
#: ⚠️ **A palavra era `pior N` ate 12/09/2026**, e saiu a pedido do dono: *"tem
#: hora que eu acho que entendi, mas depois de um tempo nao lembro mais o que
#: isso significa"*. ⛔ E o incomodo era justo — `pior 3` era **bom** e `pior 1`
#: era **ruim**, o contrario do que a palavra sugere a quem le de passagem.
#:
#: ⛔ **E NENHUM rotulo e garantia.** A amostra e de 3 dias; o ano tem 365. Em
#: 2026-09-18 a `{caixas: 5}` do `chegar_ao_placar`, medida **NO LIMITE**, deu
#: **zero** na execucao real: 18 posicoes tentadas, 18 recusadas por erro do
#: adversario, e a fila ficou com um dia descoberto. E o que `TENTATIVAS_POR_JOGO`
#: (em `job/gerador.py`) passou a atacar.
#:
#: ⚠️ E o erro nao aparece cedo: uma variante ruim vira dia descoberto **duas
#: semanas depois** de entrar, e o log diz so *"sem candidato"* — sintoma, e nao
#: causa. Foi assim que a primeira execucao real passou quatro dias sem gerar
#: Pontinhos nenhum.
EDITORIAL: dict[str, tuple[Publicacao, ...]] = {
    "pontinhos_fechar_caixas": (
        # ⛔ **`{caixas: 4, turnos: 2}` SAIU em 12/09/2026, e a licao e sobre
        # REMEDIR.** Ela entrou em 11/09 com **APERTADO** (2 de 3), medido antes de a
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
            # Medido 12/09/2026, **com a regra de recusa**: **NO LIMITE** (1 de 3) ·
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
            # Medido 12/09/2026, com a regra de recusa: **FOLGA** (3 de 3) ·
            # solucao 9,9 lances. ⚠️ **A unica da familia que a regra nao derruba**
            # — o turno a mais da folga para o gabarito contornar um lance recusado.
            parametros={"caixas": 4, "turnos": 3},
            ic_chegada_encerra_partida=False,
            nu_lances_de_preparo=14,
            medidas=_medidas_do_pontinhos_fechar_caixas,
        ),
        Publicacao(
            # A mais dura que gera com folga.
            # ⛔ Medidas e **recusadas**: `{"caixas": 5, "turnos": 2}` deu
            # **SEM DESAFIO** (0 de 3, nos dias 2/0/2) e `{"caixas": 6, "turnos": 3}`
            # deu **NO LIMITE** (1 de 3) — nenhuma das duas entra.
            # Medido 12/09/2026, com a regra de recusa: **NO LIMITE** (1 de 3) ·
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
            # Medido 12/09/2026: **FOLGA** (3 de 3) · solucao 20,6 lances (~10 lances
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
            # Medido 12/09/2026: **FOLGA** (3 de 3) · solucao 21,4 lances.
            #
            # ⛔ **E `{caixas: 5}` ficou de FORA, apesar de tambem medir FOLGA.**
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
            # Medido 12/09/2026, com a regra de recusa: **NO LIMITE** (1 de 3) ·
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
            # Medido 12/09/2026, com a regra de recusa: **NO LIMITE** (1 de 3) ·
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
            # ⛔ Medidas e **recusadas**: `{"caixas": 8}` deu **SEM DESAFIO**
            # (0 de 3, nos dias 0/0/1) e `{"caixas": 9}` nao gerou **nada**.
            # Medido 12/09/2026, com a regra de recusa: **NO LIMITE** (1 de 3) ·
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
            # dava **SEM DESAFIO** (0 de 3); sem ela, **FOLGA** (3 de 3).
            #
            # Medido 12/09/2026: **FOLGA** (3 de 3) · solucao 15,6 lances.
            parametros={"acima_do_guloso": 1},
            # ⚠️ O alvo e um placar, e nao o fim do jogo — como nas irmas.
            ic_chegada_encerra_partida=False,
            nu_maximo_de_meios_lances=34,
            nu_lances_de_preparo=14,
            # ⚠️ As medidas leem `caixas`, e recebem os parametros do
            # **candidato** (`G + 1`), nao os daqui — ver `job/__main__.py`.
            medidas=_medidas_do_pontinhos_placar,
        ),
        Publicacao(
            # ── ✅ MEDIDA COM AS 20 TENTATIVAS, EM 14/09/2026 ────────────────
            #
            #     {acima_do_guloso: 1}   FOLGA (3 de 3)   15,6 meios-lances   12s
            #     {acima_do_guloso: 2}   FOLGA (3 de 3)   16,1 meios-lances   16s
            #
            # ⚠️ **As duas dao folga cheia, e a de 2 e mais longa.** Ela entra
            # porque o tipo precisava de uma segunda variante de alvo variavel:
            # as quatro de caixas fixas ficaram todas em **NO LIMITE** na mesma
            # rodada (`[3,1,3]`), e um tipo cujo odometro so passa por variantes
            # apertadas publica dia descoberto mais cedo ou mais tarde.
            #
            # ⛔ **E `acima_do_guloso: 3` NAO foi medida**, entao nao entra. O
            # salto de 1 para 2 custou 0,5 meio-lance; supor que o de 2 para 3
            # custe o mesmo e a extrapolacao que este editorial existe para
            # impedir.
            parametros={"acima_do_guloso": 2},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_pontinhos_placar,
            nu_maximo_de_meios_lances=34,
            nu_lances_de_preparo=14,
        ),
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # ⛔ TUDO O QUE ESTA MEDIDO ABAIXO DESCREVE UM ACERVO QUE JA SAIU (16/09)
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⛔ **Nenhum numero deste bloco vale para o `damas_coroar` de hoje**, e sao
    # DOIS motivos independentes, cada um bastando sozinho:
    #
    # 1. **O acervo foi trocado**, nao somado: os 515 moldes que produziram estas
    #    linhas sairam inteiros e entraram 133 outros, com material medio 16,1
    #    contra 7,3 e a pedra a 3+ fileiras da coroacao (§8k-13). ⚠️ A tarefa
    #    mudou de tamanho — e era esse o objetivo do dono, nao um efeito colateral.
    # 2. **A regua deixou de ser a MEDIA e passou a ser a ESCADA** (§8k-15): o
    #    criterio de aceite agora e *quase nenhum para a Cacau, poucos para a
    #    Pita, mais da metade para o Tex, quase sempre o Magno*. ⛔ Uma taxa
    #    uniforme NUNCA passa numa escada, entao "FOLGA (3 de 3)" aqui nao diz
    #    mais se a variante entra.
    #
    # ⚠️ **O historico fica, e fica de proposito.** Ele e a unica forma de ver que
    # a variante de 4 lances vinha perdendo aperto a cada acervo (4,3 → 6,1) e que
    # a de duas damas media escassez enquanto todo mundo lia dificuldade. ⛔ O que
    # nao se pode e **usa-lo como se fosse a medida de agora**.
    #
    # ⏳ **O que destrava:** a remedicao com a escada, que e comando do dono —
    # `scripts/medir_variantes_do_editorial.py no-ar-damas --com-regua` (~2h20).
    # Ate ela chegar, as variantes abaixo continuam publicando, porque tira-las
    # deixaria dia descoberto; o que muda e que **nenhuma decisao nova se apoia
    # nestes numeros**.
    #
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
    #     {damas:1, lances: 4}   FOLGA       (3 de 3)     solucao media 4.3 meios-lances   210s
    #     {damas:1, lances: 6}   FOLGA       (3 de 3)     solucao media 6.8 meios-lances   117s
    #     {damas:1, lances: 8}   FOLGA       (3 de 3)     solucao media 6.8 meios-lances   117s
    #     {damas:1, lances:10}   FOLGA       (3 de 3)     solucao media 6.8 meios-lances   117s
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
    #     {damas:1, lances: 6}   FOLGA       (3 de 3)     solucao media 6.8 meios-lances   103s
    #     {damas:1, lances: 4}   FOLGA       (3 de 3)     solucao media 6.1 meios-lances   176s
    #     {damas:2, lances: 8}   NO LIMITE   (1 de 3)     solucao media 9.6 meios-lances   525s
    #     {damas:2, lances:10}   NO LIMITE   (1 de 3)     solucao media 9.6 meios-lances   532s
    #
    # ✅ **A variante de controle nao se moveu** — FOLGA, solucao 6,8, e ate um pouco
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
    # ═══════════════════════════════════════════════════════════════════════
    # ⛔ 16/09/2026 — O PISO ENTRA, E O TETO SOBE DE 12 PARA 20
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⛔ **O dono cobrou isto por semanas, e as duas "correcoes" anteriores nao
    # atacaram a causa.** As duas cortaram moldes curtos do acervo; nenhuma
    # impediu o gerador de escolher o mais curto que sobrou.
    #
    # > *"3 meios lances e muito ruim. O usuario entra no App e em 10 segundos
    # > conclui o desafio. Se colocar um teto de 20 meio-lances e um piso de 9
    # > meio-lances, por exemplo, nao resolveria?"*
    #
    # ✅ **Resolve, e os dois numeros sao dele.** O teto de 12 vinha do padrao, e
    # o `damas_coroar` era o ULTIMO tipo ainda nele: o Pontinhos usa 34, o
    # `capturar_multipla` 16 e 20, o `sobreviver` 18.
    #
    # ⛔ **O teto de 12 nao "limitava a dificuldade": ele produzia o acervo
    # banal.** A peneira da pescaria usa o mesmo numero, entao toda posicao que
    # demorasse mais de 6 lances do jogador para coroar era descartada com
    # `nao_cumpriu_no_teto` — **3.674 das 4.096** na pescaria de 16/09. ⚠️ E o
    # proprio `cacar_moldes_damas.py` avisa que esse motivo e *"indistinguivel de
    # 'o jogo nao permite'"*. Sobravam so as posicoes com a pedra quase coroando,
    # que sao exatamente as que o dono reprovou em 17/09.
    #
    # ⚠️ **9 meios-lances sao ~5 lances de quem resolve** (nas damas a
    # alternancia e estrita). Contra os ~3,5 de hoje.
    #
    # ⏳ **O acervo ainda nao acompanha, e isso e declarado:** com piso 9, apenas
    # **20 dos 133 moldes** de hoje qualificam — eles foram pescados com o teto
    # de 12 e estao truncados nele. A repescagem com `--teto 20` e o que enche o
    # acervo; ate la a variante gera pouco, e a medicao dira quanto.
    "damas_coroar": (
        Publicacao(
            # Uma dama em seis lances — o alvo com que os moldes foram escritos.
            parametros={"damas": 1, "lances": 6},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_coroar,
            nu_maximo_de_meios_lances=20,
            nu_minimo_de_meios_lances=9,
        ),
        Publicacao(
            # A mesma dama com a janela apertada: a unica medida que muda o que o
            # gerador aceita.
            #
            # ⚠️ **Com o piso de 9 esta variante ficou quase impossivel, e por
            # aritmetica:** a janela de 4 lances do jogador sao 8 meios-lances no
            # melhor caso, e o piso pede 9. ⛔ Ela so fecha quando o adversario
            # gasta meios-lances sem que o jogador precise de mais que 4 — o que
            # existe, mas e raro. ⏳ A medicao dira se sobra candidato; se nao
            # sobrar, a decisao e trocar a janela, e nao baixar o piso.
            parametros={"damas": 1, "lances": 4},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_coroar,
            nu_maximo_de_meios_lances=20,
            nu_minimo_de_meios_lances=9,
        ),
        # ── ⚠️ DUAS DAMAS: a variante que o dono pediu, e a mais longa ────────
        #
        # ⚠️ **Pedido dele, olhando a curadoria** (11/09/2026): *"esta solucao me
        # parece extremamente banal. Ate um macaco treinado conseguiria resolver.
        # **Se fosse ao menos coroar 2 damas**, talvez fizesse sentido"*.
        #
        # ✅ **MEDIDO no mesmo dia**, e o resultado da razao a ele:
        #
        #     {damas:1, lances: 6}   FOLGA       (3 de 3)     solucao media 7.4 meios-lances    88s
        #     {damas:1, lances: 4}   FOLGA       (3 de 3)     solucao media 5.2 meios-lances   132s
        #     {damas:2, lances: 8}   FOLGA       (3 de 3)     solucao media 9.7 meios-lances   314s
        #     {damas:2, lances:10}   FOLGA       (3 de 3)     solucao media 9.4 meios-lances   265s
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
        # ⚠️ **12/09/2026: esta variante caiu de FOLGA para NO LIMITE.** Na
        # remedicao com o acervo de 515 moldes ela deu **1 candidato dos 3
        # pedidos** (9,6 meios-lances, 525 s), e a suspeita na hora foi a maquina
        # dividida com a suite do aplicativo.
        #
        # ✅ **MEDIDA DE NOVO no mesmo dia, ~2 h depois, e a suspeita caiu:**
        # `[1, 3, 3]` virou `[1, 2, 3]`, **sem trocar de rotulo**, e a rodada
        # "livre" foi ate mais LENTA (636 s contra 525 s). As duas linhas de uma
        # dama sairam identicas ao digito nas duas rodadas.
        #
        # ⛔ **Entao e o acervo, e nao o relogio.** NO LIMITE ainda publica, mas e
        # folga ZERO: o proximo degrau e o dia descoberto.
        #
        # ⏳ **E a alavanca provavel e o TETO, nao a janela.** A solucao media
        # (9,3) esta colada nos 12 meios-lances, e as janelas de 8 e de 10 medem
        # identico justamente porque nenhuma das duas chega a ser exercida — o
        # gerador para antes. Ha candidata escrita em
        # `scripts/medir_variantes_do_editorial.py` para medir isso com teto 16.
        # ── ⛔ APOSENTADA EM 16/09/2026, POR DECISAO DO DONO ─────────────────
        #
        # > *"Entao vamos abandonar por hora o coroar 2 damas."*
        #
        # ⚠️ **E ele chegou nisso pelo caminho contrario do que este comentario
        # registrava.** Tudo acima diz que a variante era DURA (NO LIMITE nas tres
        # medicoes, folga zero de candidato). ⛔ Olhando o desafio publicado em
        # 17/09 no painel, o dono viu que ela e **FACIL**:
        #
        # > *"Ele e extremamente facil. Ele e simplesmente empurrar as 2 pecas
        # > azuis para frente. Nao ha desafio algum nisso. Nao ha barreiras de
        # > pecas."*
        #
        # ⚠️ **As duas coisas eram verdade ao mesmo tempo**, e e isso que torna o
        # caso instrutivo: era dificil de GERAR (poucos moldes comportam duas
        # coroacoes na janela) e trivial de RESOLVER (os moldes que comportam sao
        # justamente os de tabuleiro vazio). ⛔ O rotulo NO LIMITE media a
        # escassez, e ninguem leu que escassez e facilidade eram a mesma coisa.
        #
        # ⚠️ **E a regua nao podia avisar:** ela deu 0,05 nos tres mascotes, e a
        # causa nao era dificuldade — os mascotes coroam a primeira dama e depois
        # jogam com ELA, porque usar a dama e o melhor lance *da partida*. Medido
        # em 20 execucoes por mascote: `coroou 0 damas` deu **zero** nos tres.
        #
        # ⛔ **O codigo dela nao se perde** — esta neste historico e no Git. O que
        # falta para ela voltar e um acervo de tabuleiro cheio, e ai a pergunta
        # muda: atravessar o tabuleiro DUAS vezes com oposicao provavelmente nao
        # cabe em 8 lances. ⚠️ A variante vive de uma faixa estreita que talvez
        # nao exista, e e por isso que a volta dela depende de medicao, e nao de
        # vontade.
    ),
    # ⚠️ **MEDIDO no mesmo dia, e o resultado foi UMA variante so:**
    #
    #     {pecas:2, lances:4}   FOLGA       (3 de 3)     solucao media 2.8 meios-lances   116s
    #     {pecas:2, lances:6}   FOLGA       (3 de 3)     solucao media 2.8 meios-lances   116s
    #     {pecas:2, lances:8}   FOLGA       (3 de 3)     solucao media 2.8 meios-lances   116s
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
    #     {pecas:2, lances:4}   FOLGA       (3 de 3)     solucao media 3.0 meios-lances   69s
    #     {pecas:2, lances:3}   FOLGA       (3 de 3)     solucao media 3.0 meios-lances   70s
    #     {pecas:2, lances:2}   FOLGA       (3 de 3)     solucao media 3.0 meios-lances   70s
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
    #     {pecas:2, lances:4}   NO LIMITE   (1 de 3)     solucao media  3.7 meios-lances   603s
    #     {pecas:2, lances:3}   NO LIMITE   (1 de 3)     solucao media  3.7 meios-lances   602s
    #     {pecas:2, lances:2}   NO LIMITE   (1 de 3)     solucao media  3.0 meios-lances   671s
    #     {pecas:3, lances:4}   SEM DESAFIO (0 de 3)     ⛔ NAO ENTRA                      696s
    #     {pecas:3, lances:6}   NO LIMITE   (1 de 3)     solucao media 10.3 meios-lances   691s
    #
    # ⚠️ **A janela de 2 virou variante de verdade.** Em 11/09 as tres davam o
    # mesmo numero **e o mesmo tempo** — assinatura de janela que nao descarta
    # nada. Hoje `lances:2` se separa (3,0 contra 3,7, com 70 s a mais): ela
    # passou a recusar candidato, que e o unico criterio para merecer linha
    # propria aqui.
    #
    # ⚠️ **E o "2 pecas" pode virar 3 — mas so com janela 6.** Era pergunta do
    # dono (*"este 2 e fixo ou varia?"*). Com `lances:4` da **zero nos tres
    # dias**; com `lances:6` da **NO LIMITE**, e a solucao sobe para 10,3 meios-lances
    # (~5,2 lances do jogador) — a tarefa **mais longa** que as damas tem, mais
    # longa ate que o coroar de duas damas. ⛔ **O aperto tem nome:** 10,3 contra
    # um teto de geracao de **12**, margem de menos de dois meios-lances.
    #
    # ═══════════════════════════════════════════════════════════════════════
    # ✅ MEDIDO DE NOVO NO MESMO DIA — AS CINCO LINHAS SAIRAM IGUAIS
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⚠️ A rodada acima dividiu o computador com a suite do aplicativo, e isso
    # punha em duvida o **10,3** e o **0 de 3**. A segunda rodada, ~2 h depois,
    # devolveu as cinco linhas **identicas digito a digito** — inclusive os
    # tempos, dentro de 3 s. ⛔ A leitura e do acervo, e nao do relogio.
    #
    # ⚠️ **E o log diz ONDE esta o aperto.** Das 18 posicoes tentadas por dia, so
    # **tres** aparecem descartadas por *"o objetivo cai no lance 1"*. As outras
    # ~14 morrem em `_resolver`: e o Sagaz **nao achando a captura de tres dentro
    # dos 12 meios-lances de teto**. As que passam vem com solucao 10,3, colada
    # nele.
    #
    # ⛔ **Para `{pecas: 3, lances: 6}` a janela e o teto sao o MESMO limite** —
    # 6 lances do jogador sao 12 meios-lances, exatamente o teto —, entao subir
    # so um nao traz candidato nenhum de volta. A janela de 4 prova a direcao
    # contraria: mesmo acervo, mesma posicao, **0 de 3**.
    #
    # ⏳ **Nenhuma das duas entrou ainda, e a proxima medicao e a que decide.**
    # O dono autorizou subir o teto por qualidade (12/09/2026,
    # `DECISOES-do-dono.md` §8k-5); ha candidatas escritas em
    # `scripts/medir_variantes_do_editorial.py` com teto 16 e 20, mais o controle
    # de duas pecas no mesmo teto. ⚠️ **Se `{pecas: 3}` subir para FOLGA, ela e a
    # melhor variante que as damas tem**: a mais longa de todas (10,3 contra 3,0
    # a 9,6) e a unica que ampliaria este tipo, que hoje tem uma variante so.
    # Detalhe em `docs/historico_decisoes.md`, 12/09/2026.
    # ═══════════════════════════════════════════════════════════════════════
    # ✅ 14/09/2026: O TETO ERA O QUE APERTAVA, E O CONTROLE PROVOU
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⚠️ **A medicao com teto maior foi desenhada para responder sobre TRES
    # pecas, e quem deu a melhor resposta foi o CONTROLE de duas:**
    #
    #     {pecas:2, lances:4}  teto 12   NO LIMITE (1 de 3)   [3,1,2]   3,7 meios-lances
    #     {pecas:2, lances:8}  teto 16   ✅ FOLGA  (3 de 3)   [3,3,3]   9,0 meios-lances
    #     {pecas:3, lances:8}  teto 16   NO LIMITE (1 de 3)   [1,1,1]  10,3 meios-lances
    #     {pecas:3, lances:10} teto 20   NO LIMITE (1 de 3)   [3,1,1]  13,8 meios-lances
    #
    # ⛔ **A variante que estava no ar era a mais curta do catalogo por causa do
    # TETO, e nao do tipo.** Com 12 meios-lances o gerador so achava as capturas
    # que caem em 3,7; com 16 ele acha as de 9,0 — a **mesma tarefa**, duas
    # vezes e meia mais longa, e com folga de candidato em vez de nenhuma.
    #
    # ⚠️ **Isso e o criterio 6 do dono em cheio** (§8k-0: *"de preferencia muitos
    # lances ate chegar a conclusao do desafio"*), e ele custou zero: nao ha tipo
    # novo, nem migracao, nem chave de i18n. So dois numeros.
    "damas_capturar_multipla": (
        Publicacao(
            # ⛔ **APOSENTOU a `{pecas: 2, lances: 4}`**, que estava aqui desde a
            # primeira safra e media 3,7 meios-lances em NO LIMITE. A decisao de
            # aposentar esta na §8k-7 (*"quando a de 3 pecas entrar"*); o que
            # mudou e que quem a substitui e a **mesma tarefa com teto maior**, e
            # nao a de tres pecas.
            parametros={"pecas": 2, "lances": 8},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_captura,
            nu_maximo_de_meios_lances=16,
        ),
        Publicacao(
            # ⚠️ **TRES pecas, a tarefa mais longa de todo o catalogo** — 13,8
            # meios-lances, contra os 6,0 a 22,0 do Pontinhos e os 3,0 a 11,3 das
            # outras variantes de damas.
            #
            # ⛔ **Entra em NO LIMITE, e isso e decisao consciente.** O dia mais
            # fraco da 1 de 3, mas os dias sao `[3, 1, 1]` — melhores que os
            # `[1, 1, 1]` da versao de teto 16. ⚠️ **NO LIMITE publica**; o risco
            # e o dia descoberto, e o contrapeso e que este tipo agora tem DUAS
            # variantes, entao o odometro nao depende so dela.
            #
            # ⚠️ **E o preco esta medido:** 923 s para 3 dias, ou ~5 min por dia
            # de damas — contra o teto de ~27 min/dia da §8k-8.
            parametros={"pecas": 3, "lances": 10},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_captura,
            nu_maximo_de_meios_lances=20,
        ),
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # OS DOIS TIPOS NOVOS DE DAMAS — MEDIDOS COM REGUA EM 16/09/2026
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⚠️ **ESTA FOI A PRIMEIRA MEDICAO QUE OLHOU A REGUA, E ELA RESPONDE OUTRA
    # PERGUNTA.** Ate 15/09/2026 o script dizia *"a variante gera?"* — quantos
    # candidatos saem no dia mais fraco. ⛔ **O job nao publica qualquer
    # candidato:** ele percorre os tres e publica o **primeiro que cai na banda**
    # de dificuldade `[0,70; 0,80]`. Sao perguntas diferentes, e as seis variantes
    # abaixo deram `✅ FOLGA 3 de 3` na primeira **e** tiveram dia fora da banda
    # na segunda.
    #
    # ⚠️ **Entao cada linha daqui leva DOIS numeros**, e o segundo e novo:
    #
    #     FOLGA 3 de 3          → sempre houve candidato (a pergunta antiga)
    #     banda 2 de 3 dias     → em 2 dos 3 dias algum deles estava calibrado
    #
    # ⛔ **Um dia fora da banda NAO deixa a fila vazia** — o job publica o
    # candidato mais proximo, e o relatorio diz por quanto ele erra. Dia
    # descoberto continua sendo `0 de 3` na primeira pergunta, e nenhuma destas
    # seis chegou perto disso.
    #
    # ⚠️ **A rodada inteira custou 5.005 segundos**, e e o preco de medir os dois
    # eixos: por variante, 3 dias x 3 candidatos x 3 mascotes x 10 execucoes.
    "damas_sacrificio": (
        Publicacao(
            # ✅ FOLGA (3 de 3) · banda em 2 de 3 dias · solucao 6,1 meios-lances · 498s
            #     01/10 ✅ candidato 2 → 0,77   ·   03/10 ✅ candidato 3 → 0,73
            #     05/10 ⛔ nenhum dos 3 (0,83 · 1,00 · 0,57) — erra por **0,03**
            #
            # ⚠️ **E a mais bem calibrada das tres, e por isso abre a lista:** o
            # unico dia em que ela escapa da banda escapa por 0,03 — menos que um
            # passo da grade de 10 execucoes, que e 0,10.
            parametros={"capturar": 2, "entregar": 1},
            # ⚠️ Sobram pecas dos dois lados: a partida continua depois da troca.
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_sacrificio,
        ),
        Publicacao(
            # ✅ FOLGA (3 de 3) · banda em 2 de 3 dias · solucao 6,3 meios-lances · 602s
            #     01/10 ✅ candidato 2 → 0,77   ·   05/10 ✅ candidato 1 → 0,73
            #     03/10 ⛔ nenhum dos 3 (1,00 · 0,90 · 0,97) — erra por 0,10
            #
            # ⚠️ **E a frase que da nome ao tipo** — *"troque 1 peca por 3"* —, e o
            # dia em que ela escapa escapa **para o lado facil**: os tres
            # candidatos daquele dia eram banais. ⛔ Banal e pior para o produto do
            # que duro, e e o que esta linha registra para quem remedir.
            parametros={"capturar": 3, "entregar": 1},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_sacrificio,
        ),
        Publicacao(
            # ✅ FOLGA (3 de 3) · banda em 2 de 3 dias · solucao 7,7 meios-lances · 805s
            #     01/10 ✅ candidato 2 → 0,77   ·   05/10 ✅ candidato 1 → 0,73
            #     03/10 ⛔ nenhum dos 3 (1,00 · 0,87 · 0,13) — erra por 0,07
            #
            # ⚠️ **A mais longa das tres** (7,7 contra 6,1), e o criterio 6 do dono
            # — *"de preferencia muitos lances"* — e o que a mantem aqui apesar de
            # ela ser tambem a mais cara de gerar.
            parametros={"capturar": 3, "entregar": 2},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_sacrificio,
        ),
    ),
    "damas_sobreviver": (
        Publicacao(
            # ✅ FOLGA (3 de 3) · **banda nos 3 de 3 dias** · solucao 15,0 · 557s
            #     01/10 ✅ candidato 1 → 0,80   ·   03/10 ✅ candidato 1 → 0,73
            #     05/10 ✅ candidato 2 → 0,70
            #
            # ✅ **A UNICA VARIANTE DO CATALOGO QUE ACERTOU A BANDA NOS TRES DIAS**,
            # e ela chegou aqui por correcao: a primeira versao pedia
            # `material_restante >= 1` — *"voce ainda esta de pe"* —, e a Cacau
            # resolvia **30 de 30**, com a escada do produto invertida. ⚠️ O piso
            # relativo (`M - 2`) e o que cobra habilidade.
            parametros={"lances": 8, "entregar": 2},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_sobreviver,
            # ⛔ **O TETO E O BOTAO DESTE TIPO, e nao o enunciado.** `lances: 8`
            # sao 16 meios-lances no minimo aritmetico (os dois lados alternam), e
            # o teto padrao e **12** — publicar com ele devolveria zero candidato
            # por aritmetica, sem erro nenhum no log.
            nu_maximo_de_meios_lances=18,
        ),
        Publicacao(
            # ✅ FOLGA (3 de 3) · banda em 2 de 3 dias · solucao 15,0 · 1.136s
            #     01/10 ✅ candidato 3 → 0,70   ·   05/10 ✅ candidato 1 → 0,77
            #     03/10 ⛔ nenhum dos 3 (0,57 · 0,37 · 0,40) — erra por 0,13
            #
            # ⚠️ **Aperta o MATERIAL sem mexer no tempo**, e o dia que ela perde
            # perde para o lado **duro** — o oposto do dia ruim do sacrificio.
            # ✅ E e a rede da de cima: com duas variantes, um dia fraco de uma nao
            # deixa o tipo sem candidato.
            parametros={"lances": 8, "entregar": 1},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_damas_sobreviver,
            nu_maximo_de_meios_lances=18,
        ),
        # ⛔ **`{lances: 10, entregar: 2}` NAO ENTRA, e foi a REGUA que a barrou.**
        #
        # ✅ FOLGA (3 de 3) na pergunta antiga — ela gera candidato todo dia —, e
        # ⛔ **banda em 1 de 3 dias**: 01/10 (0,37 · 0,47 · 0,23, erro 0,23) e
        # 03/10 (0,63 · 0,47 · 0,17, erro 0,07) sairiam **duros**, e cinco dos seis
        # candidatos desses dois dias ficaram abaixo da banda.
        #
        # ⚠️ **Dois lances a mais de resistencia mudam o degrau, e nao so o
        # numero**: 19,0 meios-lances contra 15,0, com teto 22 e 1.407s de geracao
        # — a mais cara de todas as variantes do catalogo.
        #
        # ⛔ **Ela e o unico ⛔ desta rodada, e e o que prova que a regua serve
        # para alguma coisa:** pela pergunta antiga as seis eram iguais.
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # OS QUATRO TIPOS NOVOS DE PONTINHOS — MEDIDOS EM 14/09/2026
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⚠️ **A rodada inteira custou 254 segundos** (`em-avaliacao`, 3 dias, 20
    # tentativas por candidato). Os numeros de cada variante estao na linha dela.
    #
    # ⛔ **O que NAO entrou, e por que:**
    #
    #   · `{turnos: 6}` e `{turnos: 8}` do `nao_entregar` — **SEM DESAFIO nos
    #     tres dias**. ⚠️ A sondagem de UM dia tinha apontado o 6 (11 meios-lances
    #     numa amostra), e a rodada de tres dias desmentiu. Mesma licao do dia
    #     2026-09-18, e o motivo de a medicao ter tres dias.
    #   · `{turnos: 6}` do `paciencia` — idem, zero nos tres.
    #   · `{ganhar: 5, ceder: 1}` do `troca_favoravel` — NO LIMITE, e ha duas
    #     variantes melhores do mesmo tipo.
    "pontinhos_nao_entregar": (
        Publicacao(
            # ✅ FOLGA (3 de 3) · dias [3,3,3] · 6,6 meios-lances · 7s
            #
            # ⚠️ **Uma variante so, e e o que a medicao permite.** Este tipo vive
            # numa faixa estreita: 4 da folga cheia, 6 e 8 dao zero. ⛔ Nao ha
            # segunda variante para publicar, e inventar uma sem medida e o que
            # este editorial existe para impedir.
            parametros={"lances": 4},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_pontinhos_nao_entregar,
        ),
    ),
    "pontinhos_economia_de_lances": (
        # ⚠️ **O tipo mais generoso do catalogo**: FOLGA (3 de 3) nas TRES
        # variantes medidas, com solucoes de 9,0 a 10,1 meios-lances. Nao houve
        # variante ruim para descartar.
        Publicacao(
            # ✅ FOLGA (3 de 3) · dias [3,3,3] · 10,1 meios-lances · 20s
            parametros={"caixas": 5, "lances": 8},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_pontinhos_economia,
            nu_lances_de_preparo=14,
        ),
        Publicacao(
            # ✅ FOLGA (3 de 3) · dias [3,3,3] · 10,1 meios-lances · 20s
            #
            # ⚠️ **Mesma solucao media da de cima, e mesmo assim ela entra:** o
            # que muda e a promessa na tela — sete lances contra oito para as
            # mesmas cinco caixas —, e e a promessa que a pessoa le. ⛔ Os dois
            # numeros iguais aqui querem dizer *"o gerador acha as mesmas
            # solucoes"*, e nao *"a tarefa e a mesma"*.
            parametros={"caixas": 5, "lances": 7},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_pontinhos_economia,
            nu_lances_de_preparo=14,
        ),
        Publicacao(
            # ✅ FOLGA (3 de 3) · dias [3,3,3] · 9,0 meios-lances · 12s
            # A mais facil das tres, e a que abre o tipo para quem nunca o viu.
            parametros={"caixas": 4, "lances": 6},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_pontinhos_economia,
            nu_lances_de_preparo=14,
        ),
    ),
    "pontinhos_troca_favoravel": (
        Publicacao(
            # ⚠️ APERTADO (2 de 3) · dias [3,3,2] · 10,0 meios-lances · 20s
            #
            # ⛔ **Entra APERTADO de proposito, e a conta e explicita:** 10,0
            # meios-lances contra os 7,6 da variante folgada. ⚠️ APERTADO ainda
            # publica com escolha (dois candidatos no pior dia), e o criterio 6
            # do dono (*"de preferencia muitos lances"*) decide o empate.
            parametros={"ganhar": 5, "ceder": 2},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_pontinhos_troca,
            nu_lances_de_preparo=14,
        ),
        Publicacao(
            # ✅ FOLGA (3 de 3) · dias [3,3,3] · 7,6 meios-lances · 18s
            # ⚠️ **E a rede da de cima:** com duas variantes, um dia fraco da
            # apertada nao deixa o tipo sem candidato.
            parametros={"ganhar": 4, "ceder": 2},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_pontinhos_troca,
            nu_lances_de_preparo=14,
        ),
    ),
    "pontinhos_paciencia": (
        Publicacao(
            # ✅ FOLGA (3 de 3) · dias [3,3,3] · 5,0 meios-lances · 6s
            #
            # ⚠️ **E o mais curto dos quatro** (5,0 contra 10,1), e isso e
            # sabido. ⛔ Ele entra assim mesmo porque a tarefa dele **nao existe
            # em nenhum outro tipo**: e o unico em que o acerto e nao jogar o
            # lance obvio, e variedade de TAREFA e o criterio 1 do dono.
            #
            # ⏳ `{lances: 4}` mediu NO LIMITE (1 de 3, 7,0 meios-lances) e ficou
            # de fora: um tipo de variante unica nao sobrevive a um dia fraco.
            parametros={"lances": 3},
            ic_chegada_encerra_partida=False,
            medidas=_medidas_do_pontinhos_paciencia,
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
    "MINIMO_DE_MEIOS_LANCES_PADRAO",
    "TETO_DE_LOG_PADRAO",
    "VERSAO_MINIMA_DOS_TIPOS_FUNDADORES",
    "Publicacao",
    "TipoSemEditorial",
    "publicacao_de",
    "variantes_de",
]

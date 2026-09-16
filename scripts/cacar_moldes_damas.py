"""Caca MOLDES novos para os tipos de damas — e so propoe o que foi MEDIDO (T049g).

═══════════════════════════════════════════════════════════════════════════
PARA QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Um **molde** e a posicao de partida de onde um tipo de desafio costuma sair
(`job/tipos_de_desafio.py`, campo `moldes`). Hoje sao **quatro por tipo**, com no
maximo dois lances de variacao em cima — e a fila do `des` ja repetiu a mesma FEN
duas vezes em sete dias. Mais moldes e a unica saida: eles sao o que separa um
desafio novo de um desafio parecido.

⛔ **Mas molde nao se inventa: molde se mede.** Uma FEN escrita a mao que pareca
promissora e, na pratica, nao tenha solucao **nao da erro nenhum** — o gerador
simplesmente nao acha candidato, tenta outro molde, e o sintoma so aparece como
"dia descoberto" semanas depois. E por isso que este script existe: ele pergunta
ao Sagaz, e so imprime o que ele resolveu de verdade.

⚠️ **E mede contra as QUATRO modalidades.** Os quatro regulamentos rodam nos
mesmos moldes (todos sao damas de 32 casas), mas nao com o mesmo resultado: dos 8
moldes de hoje, a brasileira resolveu 4, a anglo 5, a portuguesa 7 e a casa 4. Um
molde que so serve a brasileira vale menos, porque some do rodizio em tres dias
de cada quatro — o criterio de entrada e **servir a pelo menos tres**.

═══════════════════════════════════════════════════════════════════════════
⚠️ OS DOIS DEFEITOS DA PRIMEIRA VERSAO, QUE ESTA CORRIGE
═══════════════════════════════════════════════════════════════════════════

A primeira caçada (10/09/2026) fotografou 229 posicoes e aprovou **zero**. O zero
nao era do jogo, era da ferramenta:

1. ⛔ **O teto de lances ficava ABAIXO da janela do tipo.** A janela de
   `damas_coroar` e `lances_do_jogador: 6`, e a busca rodava com teto de **8
   lances totais** — como os dois lados alternam, isso da ~4 lances do jogador. A
   janela nunca podia fechar, e todo molde reprovava por aritmetica. Aqui o teto
   vem de `editorial.MAXIMO_DE_MEIOS_LANCES_PADRAO`, que e o que o gerador usa de
   verdade.

2. ⛔ **As posicoes nao tinham a FORMA do objetivo.** Ela sorteava posicoes de
   meio de partida, metade delas com a vez das pretas, nenhuma com peca perto da
   coroacao. Os quatro moldes de hoje foram desenhados: vez das brancas, uma
   branca a dois passos da oitava fileira, e pretas suficientes para a partida
   nao acabar antes. Aqui as candidatas nascem com essa forma.

⚠️ **E nada e engolido em silencio.** A versao antiga tinha dois
`except Exception: return False`, e um erro de montagem ficava indistinguivel de
"o Sagaz nao resolveu". Aqui cada motivo de descarte e contado e impresso.

═══════════════════════════════════════════════════════════════════════════
GEOMETRIA DO TABULEIRO (para quem for ler os numeros)
═══════════════════════════════════════════════════════════════════════════

As 32 casas escuras sao numeradas de 1 a 32, quatro por fileira. As brancas
comecam em 21..32 e **andam para numeros menores**, coroando em 1..4; as pretas
comecam em 1..12 e coroam em 29..32. E por isso que uma branca em 5..8 esta a um
passo da coroacao, e uma em 9..12 esta a dois.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\cacar_moldes_damas.py

⚠️ **Use o `-u`.** Sem ele o Python bufferiza a saida redirecionada e o
acompanhamento so aparece no fim — foi o que aconteceu na primeira caçada.
"""

from __future__ import annotations

import multiprocessing
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

# O script mora em `scripts/`, e importa `job/` e `motores/`, que sao irmaos dele.
# `parents[1]` sobe de `scripts/` para a raiz do backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job import editorial as editorial_mod  # noqa: E402
from job.moldes_de_damas import (  # noqa: E402
    MODALIDADES,
    material_de_quem_joga,
    objetivo_no_primeiro_lance,
)
from job import posicao_inicial as pos  # noqa: E402
from job import semente as sem  # noqa: E402
from job.tipos_de_desafio import RECEITAS, Receita, receita_de  # noqa: E402
from job.tipos_propostos import PROPOSTAS  # noqa: E402
from motores.damas.motor_damas import EstadoDamas, MotorDamas  # noqa: E402
from motores.juiz import julgar_desafio  # noqa: E402
from motores.nucleo.orcamento import Orcamento  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402

#: ⚠️ `MODALIDADES` vem de `job/moldes_de_damas.py`, e nao e redeclarada aqui: o
#: verificador de trivialidade usa a mesma lista, e duas copias divergiriam no dia
#: em que a italiana entrasse — o script cacaria em quatro e o cadeado guardaria
#: cinco, ou o contrario. Um molde precisa servir a **tres** delas.

#: Quantas das quatro um molde precisa atender para ser proposto.
MINIMO_DE_MODALIDADES = 3

#: Antes deste lance o objetivo e trivial: a peca anda ate a coroacao ou o salto
#: encadeado ja esta armado, e as pretas nao tem o que fazer. ⚠️ O criterio nao e
#: uma opiniao sobre o que e dificil — e o reconhecimento de que um molde que cai
#: no primeiro lance publica o mesmo desafio todo dia, porque nem os dois lances
#: de variacao do gerador conseguem muda-lo.
LANCE_MINIMO = 3

#: O teto de lances da busca. ⚠️ Vem do editorial de proposito: e o mesmo numero
#: que o gerador usa em producao. Um teto diferente aqui aprovaria molde que la
#: nao gera — foi exatamente o defeito da primeira versao.
TETO_DE_LANCES = editorial_mod.MAXIMO_DE_MEIOS_LANCES_PADRAO

#: Os tipos cuja janela NAO cabe no teto padrao, e o teto que eles exigem.
#:
#: ⛔ **E o defeito nº 1 desta ferramenta, de volta num tipo novo.** A primeira
#: cacada (10/09/2026) aprovou zero moldes porque o teto de 12 meios-lances
#: ficava **abaixo** da janela do tipo: os dois lados alternam, entao 12
#: meios-lances sao ~6 lances do jogador, e a janela nunca podia fechar.
#:
#: ⚠️ `damas_sobreviver` pede `lances_do_jogador >= 8`, que sao **16
#: meios-lances** no melhor dos casos. Com o teto padrao ele reprovaria por
#: aritmetica — ⛔ e o log diria *"nao cumpriu no teto"*, que e indistinguivel
#: de *"o jogo nao permite"*.
#:
#: ⛔ **ESTA TABELA E SO O SOCORRO DE QUEM NAO TEM EDITORIAL** desde 16/09/2026 —
#: tipos em avaliacao, que ainda nao publicam. Quem publica e lido do editorial
#: por `teto_do_tipo`, e a razao e um defeito que esta lista causou: ela era uma
#: **copia escrita a mao** do numero que o gerador usa, e o proprio comentario
#: dizia *"o numero tem de bater com o do editorial"*. ⚠️ Em 16/09 o
#: `damas_coroar` subiu para teto 20 no editorial e a pescaria continuaria
#: peneirando com 12 — aprovando moldes truncados **em silencio**, que e como a
#: pescaria daquele dia produziu um acervo com 42% de desafios de 2 lances.
TETO_POR_TIPO: Mapping[str, int] = {
    "damas_sobreviver": 18,
}


def teto_do_tipo(co_tipo: str) -> int:
    """Quantos meios-lances a busca pode gastar neste tipo.

    ⛔ **Pergunta ao EDITORIAL, e nao a uma lista** — pelo mesmo motivo que o
    painel pergunta ao banco quais schemas existem: uma lista escrita a mao fica
    verde e cega no dia em que o outro lado muda.

    ⚠️ **Entre variantes do mesmo tipo, vale a MAIOR.** A peneira decide o que
    entra no acervo, e o acervo e um so para todas as variantes: peneirar pelo
    teto da mais apertada esconderia, da variante folgada, justamente os moldes
    longos que ela poderia usar.
    """
    try:
        tetos = [
            publicacao.nu_maximo_de_meios_lances
            for publicacao in editorial_mod.variantes_de(co_tipo)
        ]
    except editorial_mod.TipoSemEditorial:
        # ⚠️ **Tipo em avaliacao nao tem editorial, e nao poderia ter:** o
        # editorial diz com que numeros o tipo VAI AO AR, e ele ainda nao vai.
        # ⛔ Deixar a excecao subir aqui derrubaria a cacada de um tipo novo — que
        # e justamente quando a ferramenta mais serve.
        tetos = []
    if tetos:
        return max(tetos)
    return TETO_POR_TIPO.get(co_tipo, TETO_DE_LANCES)

#: Orcamento da PENEIRA (fase 1): barato, so para separar o que merece a medicao
#: cara. Um falso negativo aqui custa um molde perdido; um falso positivo custa
#: dois segundos. A assimetria e de proposito.
NOS_DA_PENEIRA = 20_000

#: ⛔ **O teto de TEMPO e alto de proposito, e isso mudou em 11/09/2026.**
#:
#: O orcamento do motor para no que vier primeiro — nos **ou** segundos. Com 0,5 s
#: aqui e 2,0 s na medicao, o teto de tempo nunca mordia numa maquina ociosa
#: (medido: ~0,66 s por lance, contra 2,0 de teto).
#:
#: ⚠️ **Mas esta cacada passou a rodar em paralelo**, e ai a conta muda: catorze
#: processos disputando oito nucleos fisicos deixam cada busca mais lenta em
#: tempo de **parede**, sem mudar o numero de nos. Com o teto antigo, a busca
#: pararia mais cedo — e ⛔ **o resultado da cacada passaria a depender do quanto
#: a maquina estava ocupada**, o que e o oposto de uma medicao.
#:
#: Com o teto alto, quem manda e sempre o numero de nos, que e identico em
#: qualquer maquina e com qualquer carga. ⚠️ O tempo continua la como **rede de
#: seguranca**: uma posicao patologica nao trava o processo para sempre.
SEGUNDOS_DA_PENEIRA = 30.0

#: Orcamento da MEDICAO (fase 2): identico ao do gerador
#: (`job/gerador.py`, `NOS_POR_LANCE_NA_GERACAO`). E o que torna o resultado
#: transferivel — o molde aprovado aqui gera la.
NOS_DA_MEDICAO = 60_000

#: Ver `SEGUNDOS_DA_PENEIRA`: rede de seguranca, e nao criterio.
SEGUNDOS_DA_MEDICAO = 60.0

#: A semente da busca. Fixa: a medicao precisa ser reproduzivel, senao um molde
#: "aprovado" hoje pode reprovar amanha e ninguem sabera por que.
SEMENTE_DA_BUSCA = 777

#: Os tipos cacados, com os parametros com que o editorial os publica hoje.
#:
#: ⚠️ **Os dois ultimos ainda NAO estao no ar** (14/09/2026): sao propostas em
#: `job/tipos_propostos.py`, e e justamente por isso que aparecem aqui — sem
#: acervo nao ha o que medir, e sem medicao eles nao sobem. ⛔ A ordem e sempre
#: essa: **moldes, depois medicao de variantes, depois promocao**.
TIPOS: dict[str, Mapping[str, Any]] = {
    "damas_coroar": {"damas": 1, "lances": 6},
    "damas_capturar_multipla": {"pecas": 2, "lances": 4},
    "damas_sacrificio": {"capturar": 3, "entregar": 1},
    "damas_sobreviver": {"lances": 8},
}


def parametros_do_tipo(co_tipo: str) -> Mapping[str, Any]:
    """Com que numeros a peneira julga este tipo — **a variante mais FOLGADA**.

    ⛔ **A janela da peneira e uma segunda parede, irma do teto**, e ela produziu
    o mesmo estrago em 16/09/2026. `TIPOS` dizia `{"damas": 1, "lances": 6}` para
    o `damas_coroar`: toda posicao que precisasse de mais de **6 lances do
    jogador** era reprovada na peneira, mesmo com o teto folgado. O acervo nascia
    curto duas vezes.

    ⚠️ **Por que a mais folgada, e nao a que esta no ar:** o acervo e **um so**
    para todas as variantes do tipo. Peneirar pela janela mais apertada esconderia
    da variante folgada justamente os moldes longos que ela poderia usar — e a
    apertada continua podendo recusa-los na geracao, que e o lugar certo.

    ⚠️ **E "mais folgada" e por JANELA, nao por alvo.** `{damas: 2}` e uma tarefa
    diferente, e nao uma folga: ela pede **duas** coroacoes, entao peneirar com
    ela reprovaria as posicoes que so comportam uma. Quem quiser o acervo de duas
    damas pesca com `--parametros`, num diario proprio.
    """
    try:
        variantes = editorial_mod.variantes_de(co_tipo)
    except editorial_mod.TipoSemEditorial:
        # ⚠️ Tipo em avaliacao ainda nao publica; o padrao da tabela e o que ha.
        return TIPOS[co_tipo]

    padrao = TIPOS[co_tipo]
    if "lances" not in padrao:
        return padrao
    # ⛔ So a JANELA sobe. Os outros numeros ficam como a tabela os declara, para
    # nao trocar de tarefa sem ninguem pedir.
    maior = max(
        (
            publicacao.parametros["lances"]
            for publicacao in variantes
            if "lances" in publicacao.parametros
        ),
        default=padrao["lances"],
    )
    return {**padrao, "lances": max(maior, padrao["lances"])}


def receita_do_tipo(co_tipo: str) -> Receita:
    """A receita do tipo, esteja ela **no ar** ou ainda **em proposta**.

    ⚠️ **A cacada precisa dos dois mundos, e isso e proprio dela.** O gerador so
    conhece `RECEITAS`, e isso e um cadeado (`test_gerador_de_candidatos.py`
    prova que o job nunca pede uma receita em avaliacao). Aqui e o contrario: um
    tipo so chega a `RECEITAS` **depois** de ter moldes, e moldes so existem
    depois desta cacada. ⛔ Exigir a promocao antes da medicao seria exigir que o
    tipo subisse sem prova — a regra que este projeto mais protege.
    """
    if co_tipo in RECEITAS:
        return receita_de(co_tipo)
    return PROPOSTAS[co_tipo]


def chegada_da_posicao(
    co_tipo: str, parametros: Mapping[str, Any], fen: str
) -> dict[str, Any]:
    """A `js_chegada` desta posicao, com os parametros relativos ja resolvidos.

    Args:
        co_tipo: o tipo cacado.
        parametros: os do editorial — podem ser relativos (`capturar`/`entregar`).
        fen: a posicao, de onde sai o material dos dois lados.

    Raises:
        editorial.MaterialInsuficiente: a posicao nao comporta o pedido.

    ⛔ **A chegada e por POSICAO, e nao por tipo**, desde que `damas_sacrificio`
    entrou. Montar uma vez so, fora do laco, publicaria o mesmo teto de material
    em moldes de 5 e de 12 pecas — ⚠️ e o de 12 sairia trivial enquanto o de 5
    sairia impossivel, os dois sem erro nenhum.
    """
    if editorial_mod.alvo_sai_do_material(parametros):
        efetivos = editorial_mod.parametros_efetivos(
            parametros, material=material_de_quem_joga(fen)
        )
    else:
        efetivos = dict(parametros)
    return receita_do_tipo(co_tipo).montar(efetivos)


# ═══════════════════════════════════════════════════════════════════════════
# As candidatas — posicoes com a FORMA do objetivo, nao posicoes quaisquer
# ═══════════════════════════════════════════════════════════════════════════


def _fen(brancas: Sequence[int], pretas: Sequence[int]) -> str:
    """Monta a FEN no formato do motor: `W:W<casas>:B<casas>`.

    O `W:` inicial e de quem e a vez. Todos os moldes partem com as brancas,
    porque o desafio e de quem esta jogando e o gerador le `vez_de` da propria
    FEN.
    """
    return f"W:W{','.join(str(c) for c in sorted(brancas))}:B{','.join(str(c) for c in sorted(pretas))}"


def candidatas_para_coroar(sorteio: random.Random, quantas: int) -> Iterator[str]:
    """Posicoes com uma branca a um ou dois passos da oitava fileira.

    A forma copia a dos quatro moldes de hoje, e nao por imitacao: uma branca
    longe da coroacao precisaria de mais lances do que a janela permite, e a
    posicao reprovaria por distancia, nao por dificuldade — gastando dois
    segundos de Sagaz para descobrir o obvio.

    ⚠️ **As pretas existem para a partida nao acabar antes.** Sem elas o motor
    devolve "a partida ja acabou" no primeiro lance, que foi como onze das 229
    posicoes da primeira caçada morreram.
    """
    for _ in range(quantas):
        # A ponta de lanca: uma branca em 5..12 (uma ou duas fileiras da coroacao).
        lanca = sorteio.randint(5, 12)
        # Duas de retaguarda, longe o bastante para nao trombarem com a lanca.
        retaguarda = sorteio.sample([c for c in range(17, 33)], 2)
        # Tres pretas no miolo, que e onde elas atrapalham sem fechar o caminho.
        pretas = sorteio.sample([c for c in range(13, 25) if c not in retaguarda], 3)
        brancas = [lanca, *retaguarda]
        if set(brancas) & set(pretas):
            continue  # duas pecas na mesma casa: FEN impossivel, descarta
        yield _fen(brancas, pretas)


def candidatas_para_capturar(sorteio: random.Random, quantas: int) -> Iterator[str]:
    """Posicoes com pretas AGRUPADAS, que e o que uma captura encadeada exige.

    Capturar duas em sequencia so acontece quando duas pretas estao em casas que
    um mesmo salto alcanca. Sortear pretas espalhadas pelo tabuleiro produz
    posicoes onde o objetivo e impossivel — e o Sagaz leva os doze lances inteiros
    para provar isso.
    """
    for _ in range(quantas):
        # O nucleo do agrupamento, e duas vizinhas de fileira dele.
        nucleo = sorteio.randint(13, 23)
        pretas = {nucleo}
        for salto in sorteio.sample([-5, -4, -3, 3, 4, 5], 3):
            alvo = nucleo + salto
            if 1 <= alvo <= 32:
                pretas.add(alvo)
        if len(pretas) < 3:
            continue  # agrupamento ralo demais para uma cadeia
        # Brancas atras do grupo, de onde o salto parte.
        brancas = sorteio.sample([c for c in range(25, 33) if c not in pretas], 3)
        if set(brancas) & set(pretas):
            continue
        yield _fen(brancas, sorted(pretas))


def candidatas_para_sacrificio(sorteio: random.Random, quantas: int) -> Iterator[str]:
    """Posicoes com pretas agrupadas E uma branca exposta — a isca.

    ⚠️ **Um sacrificio precisa das DUAS metades no tabuleiro**, e e isso que
    separa esta forma da do `capturar_multipla`:

      1. **o grupo de pretas**, sem o qual nao ha o que capturar em cadeia;
      2. **uma branca adiantada e sozinha**, que a preta e obrigada a comer — e
         ao comer ela se muda para a casa que fecha a cadeia.

    ⛔ **E o material dos dois lados precisa ser FOLGADO**, o que nao vale para
    os outros tipos: a chegada pede `capturar: 3` e `entregar: 1`, entao um molde
    com tres pretas publicaria *"capture 3"* com o tabuleiro inteiro do
    adversario em jogo — e `editorial.MaterialInsuficiente` recusaria qualquer
    coisa abaixo disso. Aqui nascem cinco de cada lado.

    ⚠️ **A sintese vale POUCO aqui, e isso esta medido em outro tipo.** Em
    11/09/2026 o `capturar_multipla` sintetico deu 29 moldes, todos de 3 lances;
    as posicoes reais do `prd` deram 184, com 87 de 4 lances ou mais — a diferenca
    era a **fonte**, e nao o jogo. ⛔ Esta funcao existe para a cacada nao ficar
    sem candidata nenhuma; o acervo do sacrificio sai da pescaria.
    """
    for _ in range(quantas):
        # O nucleo do agrupamento das pretas, e duas vizinhas de salto.
        nucleo = sorteio.randint(13, 22)
        pretas = {nucleo}
        for salto in sorteio.sample([-5, -4, -3, 3, 4, 5], 3):
            alvo = nucleo + salto
            if 1 <= alvo <= 32:
                pretas.add(alvo)
        # Duas pretas de retaguarda, para o adversario ter as 3 que o desafio
        # manda capturar e ainda sobrar tabuleiro.
        for casa in sorteio.sample(range(1, 10), 2):
            pretas.add(casa)
        if len(pretas) < 5:
            continue  # agrupamento ralo: a cadeia nao se forma

        # ⚠️ **A isca vai a FRENTE do grupo**, e nao atras: uma branca em 9..12
        # esta ao alcance de uma preta do miolo, que e obrigada a captura-la.
        iscas = [c for c in range(9, 13) if c not in pretas]
        if not iscas:
            continue
        isca = sorteio.choice(iscas)
        # E a retaguarda branca, de onde o contra-ataque parte depois da isca.
        livres = [c for c in range(21, 33) if c not in pretas and c != isca]
        if len(livres) < 4:
            continue
        brancas = [isca, *sorteio.sample(livres, 4)]
        if set(brancas) & set(pretas):
            continue
        yield _fen(brancas, sorted(pretas))


def candidatas_para_sobreviver(sorteio: random.Random, quantas: int) -> Iterator[str]:
    """Posicoes em DESVANTAGEM — as unicas da cacada que procuram o contrario.

    ⛔ **Todas as pescarias ate hoje procuraram vantagem**, e esta e a primeira
    que procura estar pior: o tipo pede *"resista 8 lances sem perder"*, e resistir
    de uma posicao confortavel nao e resistir — e esperar.

    ⚠️ **A desvantagem e de MATERIAL, e nao de posicao**, porque e a unica que se
    escreve sem opinar. Julgar "posicao ruim" exigiria um avaliador, e ai a cacada
    estaria medindo o gosto de quem a escreveu.

    ⛔ **E A DESVANTAGEM NAO PODE SER GRANDE — isto foi medido, e a primeira
    forma estava errada** (14/09/2026). Duas ou tres brancas contra cinco ou seis
    pretas nao produzem resistencia: produzem **derrota antes do oitavo lance**,
    e a cacada anota `partida_acabou`, que e o motivo certo pela razao errada.
    Com o Sagaz jogando os dois lados e 8 lances de janela:

        2-3 minhas x +2/+3     1 de 3 sobreviveu
        4 x 6                  5 de 6
        5 x 7                  6 de 6
        6 x 8                  5 de 6
        5 x 6                  5 de 6

    ⚠️ **E "sobreviveu" AQUI nao quer dizer "e um bom desafio".** Este tipo cai
    sempre no lance 8 — e o minimo aritmetico da janela —, entao ⛔ **o criterio
    de trivialidade dos outros tipos (`LANCE_MINIMO`) nao diz nada sobre ele**.
    O que separa o dificil do banal e **quantos mascotes conseguem**, e isso quem
    mede e a regua, em `scripts/medir_variantes_do_editorial.py`. A cacada aqui
    responde a uma pergunta so, e mais modesta: *"desta posicao, da para
    resistir?"* — porque um molde de onde **nao** da produz desafio impossivel.
    """
    for _ in range(quantas):
        quantas_minhas = sorteio.randint(4, 6)
        quantas_dele = quantas_minhas + sorteio.randint(2, 3)
        # As brancas ficam atras, encolhidas: e de la que se resiste.
        brancas = sorteio.sample(range(21, 33), quantas_minhas)
        # As pretas vem a frente, ja adiantadas — perto de coroar, que e o que
        # torna a resistencia urgente.
        pretas = sorteio.sample(
            [c for c in range(5, 25) if c not in brancas], quantas_dele
        )
        if set(brancas) & set(pretas):
            continue
        yield _fen(brancas, sorted(pretas))


CANDIDATAS = {
    "damas_coroar": candidatas_para_coroar,
    "damas_capturar_multipla": candidatas_para_capturar,
    "damas_sacrificio": candidatas_para_sacrificio,
    "damas_sobreviver": candidatas_para_sobreviver,
}


# ═══════════════════════════════════════════════════════════════════════════
# A medicao
# ═══════════════════════════════════════════════════════════════════════════


class MotivoDeDescarte(Counter):
    """Conta por que cada candidata caiu.

    ⚠️ Existe porque a versao antiga engolia tudo num `except Exception`. Saber
    que 400 candidatas reprovaram nao ajuda; saber que 380 delas nem chegaram a
    ter um lance legal ajuda, e aponta o defeito para o gerador de candidatas, e
    nao para o jogo.
    """


def resolve(
    fen: str,
    co_tipo: str,
    parametros: Mapping[str, Any],
    modalidade: str,
    *,
    nos: int,
    segundos: float,
    motivos: MotivoDeDescarte,
) -> int | None:
    """Em que lance o Sagaz cumpre o objetivo a partir desta FEN? `None` se nao cumpre.

    Joga os **dois** lados com o Sagaz, que e o que o gerador faz
    (`job/gerador.py`, `_resolver`): o adversario tambem joga bem, e um objetivo
    que so cai contra um adversario ruim nao e um desafio, e uma armadilha.

    Args:
        fen: a posicao candidata.
        co_tipo: o tipo de desafio (`damas_coroar`, ...).
        parametros: os numeros do tipo, como o editorial os publica.
        modalidade: qual dos quatro regulamentos.
        nos: teto de nos por lance.
        segundos: teto de tempo por lance.
        motivos: onde registrar a causa do descarte.

    Returns:
        O numero do lance em que o objetivo caiu, ou `None` se ele nao caiu
        dentro da janela do tipo.

    ⚠️ **Devolve o LANCE, e nao um sim/nao, porque "resolveu" nao basta.** Um
    molde cujo objetivo cai no primeiro ou segundo lance e trivial: a branca anda
    ate a coroacao sem que as pretas tenham o que fazer. Ele passaria no criterio
    das quatro modalidades e produziria um desafio sem graca — e um molde facil
    demais estraga a fila tanto quanto um impossivel, so que sem deixar rastro no
    log.
    """
    motor = MotorDamas(modalidade)
    try:
        estado = EstadoDamas(co_modalidade=modalidade, fen_inicial=fen)
        js_posicao = pos.das_damas(estado.fen, co_modalidade=modalidade)
    except Exception as erro:  # noqa: BLE001 — o tipo do erro vira o motivo
        motivos[f"montagem:{type(erro).__name__}"] += 1
        return None

    # ⚠️ Depois da montagem da posicao, e nao antes: a chegada dos tipos de
    # material depende das pecas que estao no tabuleiro.
    try:
        js_chegada = chegada_da_posicao(co_tipo, parametros, fen)
    except editorial_mod.MaterialInsuficiente:
        # ⛔ Motivo proprio, e nao "nao cumpriu": a posicao nunca teve chance, e
        # confundir as duas coisas faria a distribuicao final mentir sobre o jogo.
        motivos["material_insuficiente"] += 1
        return None

    fita: list[dict[str, Any]] = []
    atual = estado

    # ⚠️ O teto e POR TIPO: `damas_sobreviver` nao cabe nos 12 do padrao.
    for numero in range(1, teto_do_tipo(co_tipo) + 1):
        try:
            lance = motor.escolher_lance(
                atual,
                NivelDeMotor.SAGAZ,
                # ⚠️ Orcamento NOVO a cada lance, como no gerador: reaproveitar o
                # mesmo objeto transformaria um teto de lance num teto de partida.
                limite=Orcamento(nos_maximos=nos, segundos_maximos=segundos).iniciar(),
                semente=sem.semente_do_lance(SEMENTE_DA_BUSCA, numero),
            )
        except ValueError:
            # A partida acabou antes de o objetivo cair.
            motivos["partida_acabou" if numero > 1 else "sem_lance_no_1o"] += 1
            return None

        fita.append({"n": numero, "jogador": atual.vez_de, "lance": lance})
        atual = motor.aplicar(atual, lance)

        julgamento = julgar_desafio(
            co_jogo="damas",
            js_posicao_inicial=js_posicao,
            js_chegada=js_chegada,
            fita=fita,
            jogador=js_posicao["vez_de"],
            co_modalidade=modalidade,
        )
        if julgamento.cumpriu:
            return julgamento.nu_lance_cumpre_desafio or numero

    motivos["nao_cumpriu_no_teto"] += 1
    return None


def resolve_varios_alvos(
    fen: str,
    co_tipo: str,
    alvos: Mapping[str, Mapping[str, Any]],
    modalidade: str,
    *,
    nos: int,
    segundos: float,
    motivos: MotivoDeDescarte,
) -> dict[str, int | None]:
    """Como `resolve`, mas julga VARIOS objetivos na MESMA fita.

    ⛔ **Uma busca responde por todos, e isso nao e otimizacao esperta: e uma
    consequencia direta de o Sagaz jogar a PARTIDA, e nao o DESAFIO.** O lance
    sai de `motor.escolher_lance(estado, SAGAZ, limite, semente)` — o objetivo
    **nao entra na escolha**. Entao, para a mesma FEN e a mesma modalidade, a
    fita de lances e identica quer se procure uma coroacao ou duas; o que muda e
    so o `julgar_desafio` a cada meio-lance, que e barato perto da busca.

    ⚠️ **A economia e quase a pescaria inteira, e nao metade** (pergunta do dono,
    16/09/2026). Procurar `{damas: 1}` **para** quando a primeira coroa;
    `{damas: 2}` continua. Uma busca unica que vai ate o alvo mais exigente ja
    contem a resposta do menos exigente — o custo do combinado e o custo do mais
    caro sozinho, e os outros saem de graca.

    Args:
        fen: a posicao candidata.
        co_tipo: o tipo de desafio.
        alvos: `{nome: parametros}`. O nome e o que vai para o diario.
        modalidade: qual dos quatro regulamentos.
        nos: teto de nos por lance.
        segundos: teto de tempo por lance.
        motivos: onde registrar a causa do descarte.

    Returns:
        `{nome: lance_em_que_caiu_ou_None}`, com uma entrada por alvo.

    ⚠️ **O laco so para quando TODOS caem** — parar no primeiro devolveria `None`
    para os demais sem que eles tivessem sido testados ate o teto, que e o defeito
    que esta funcao existe para nao ter.
    """
    motor = MotorDamas(modalidade)
    try:
        estado = EstadoDamas(co_modalidade=modalidade, fen_inicial=fen)
        js_posicao = pos.das_damas(estado.fen, co_modalidade=modalidade)
    except Exception as erro:  # noqa: BLE001 — o tipo do erro vira o motivo
        motivos[f"montagem:{type(erro).__name__}"] += 1
        return {nome: None for nome in alvos}

    # ⚠️ Cada alvo tem a sua chegada, e um pode ser inviavel sem que os outros
    # sejam: `{damas: 2}` pede duas pedras, `{damas: 1}` se contenta com uma.
    chegadas: dict[str, Any] = {}
    for nome, parametros in alvos.items():
        try:
            chegadas[nome] = chegada_da_posicao(co_tipo, parametros, fen)
        except editorial_mod.MaterialInsuficiente:
            motivos[f"material_insuficiente:{nome}"] += 1

    achados: dict[str, int | None] = {nome: None for nome in alvos}
    if not chegadas:
        return achados

    fita: list[dict[str, Any]] = []
    atual = estado

    for numero in range(1, teto_do_tipo(co_tipo) + 1):
        try:
            lance = motor.escolher_lance(
                atual,
                NivelDeMotor.SAGAZ,
                # ⚠️ Orcamento NOVO a cada lance, como no gerador — e a MESMA
                # semente de `resolve`, para as duas funcoes darem a mesma fita.
                limite=Orcamento(nos_maximos=nos, segundos_maximos=segundos).iniciar(),
                semente=sem.semente_do_lance(SEMENTE_DA_BUSCA, numero),
            )
        except ValueError:
            # ⚠️ A partida acabou. Quem ja caiu fica; quem nao caiu fica `None`.
            motivos["partida_acabou" if numero > 1 else "sem_lance_no_1o"] += 1
            return achados

        fita.append({"n": numero, "jogador": atual.vez_de, "lance": lance})
        atual = motor.aplicar(atual, lance)

        for nome, js_chegada in chegadas.items():
            if achados[nome] is not None:
                continue
            julgamento = julgar_desafio(
                co_jogo="damas",
                js_posicao_inicial=js_posicao,
                js_chegada=js_chegada,
                fita=fita,
                jogador=js_posicao["vez_de"],
                co_modalidade=modalidade,
            )
            if julgamento.cumpriu:
                achados[nome] = julgamento.nu_lance_cumpre_desafio or numero

        if all(valor is not None for valor in achados.values()):
            return achados

    for nome, valor in achados.items():
        if valor is None:
            motivos[f"nao_cumpriu_no_teto:{nome}"] += 1
    return achados


# ═══════════════════════════════════════════════════════════════════════════
# O TRABALHO EM PARALELO
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Cada candidata e independente de todas as outras**, e e isso que torna
# esta cacada um caso de livro para `multiprocessing`: nao ha estado
# compartilhado, nao ha ordem a respeitar, e o trabalho e 100% CPU.
#
# ⛔ **Nao serve `threading`.** O motor e Python puro, e o GIL faria catorze
# threads se revezarem num nucleo so — o programa ficaria **mais lento** que a
# versao sequencial, por causa do custo de trocar de contexto.
#
# ⚠️ **As funcoes abaixo precisam ser de MODULO** (e nao locais nem `lambda`):
# no Windows o `multiprocessing` usa `spawn`, que **re-importa** este arquivo em
# cada processo novo e localiza a funcao pelo nome. Uma closure nao sobrevive a
# isso, e o erro (`PicklingError`) chega so quando o Pool ja abriu.
#
# ⚠️ **Por isso o `if __name__ == "__main__"` no fim nao e enfeite:** sem ele,
# cada processo filho re-executaria a cacada inteira ao importar o modulo.


def _mapear(funcao, tarefas: list, processos: int):
    """Roda `funcao` sobre `tarefas` — em paralelo quando vale a pena.

    Args:
        funcao: um dos trabalhadores de modulo deste arquivo.
        tarefas: a lista de entradas.
        processos: quantos processos usar. `1` roda em sequencia, **no proprio
            processo**.

    Yields:
        Os resultados, ⚠️ **fora de ordem** quando em paralelo.

    ⚠️ **A ordem nao importa aqui, e e bom deixar isso explicito:** a peneira so
    junta as aprovadas num conjunto, e a medicao ordena tudo no fim. Depender da
    ordem seria depender do escalonador do sistema operacional.

    ⚠️ **`processos=1` nao abre Pool nenhum**, e nao e so economia: com um
    processo so, o rastro de uma excecao aparece inteiro e no lugar certo, o que
    torna este o modo de depurar quando algo der errado.

    ⚠️ **`chunksize` pequeno de proposito.** Cada tarefa custa segundos; lotes
    grandes fariam um processo terminar cedo e ficar parado enquanto outro ainda
    tem dez candidatas na fila — e o ganho do paralelismo iria embora no fim da
    execucao, que e justamente quando se esta esperando.
    """
    if processos <= 1:
        for tarefa in tarefas:
            yield funcao(tarefa)
        return

    with multiprocessing.Pool(processes=processos) as pool:
        yield from pool.imap_unordered(funcao, tarefas, chunksize=2)


def _peneirar_uma(tarefa: tuple[str, str, dict]) -> tuple[str, object, dict]:
    """Fase 1 para UMA candidata. Devolve `(fen, lance_ou_None, motivos)`.

    ⚠️ **Os motivos voltam no retorno, e nao num contador compartilhado.** Cada
    processo tem a sua memoria; um `Counter` global seria incrementado em catorze
    copias e nenhuma delas chegaria ao pai.
    """
    fen, co_tipo, parametros = tarefa
    motivos = MotivoDeDescarte()

    de_cara = next(
        (
            f"{modalidade}:{lance}"
            for modalidade in MODALIDADES
            if (lance := objetivo_no_primeiro_lance(fen, co_tipo, modalidade))
        ),
        None,
    )
    if de_cara is not None:
        motivos[f"objetivo_no_lance_1_em_{de_cara.split(':')[0]}"] += 1
        return fen, None, dict(motivos)

    lance = resolve(
        fen,
        co_tipo,
        parametros,
        "brasileira",
        nos=NOS_DA_PENEIRA,
        segundos=SEGUNDOS_DA_PENEIRA,
        motivos=motivos,
    )
    return fen, lance, dict(motivos)


def _medir_uma(tarefa: tuple[str, str, dict]) -> tuple[str, list, dict]:
    """Fase 2 para UMA candidata: as quatro modalidades, orcamento do gerador."""
    fen, co_tipo, parametros = tarefa
    motivos = MotivoDeDescarte()
    lances = [
        resolve(
            fen,
            co_tipo,
            parametros,
            modalidade,
            nos=NOS_DA_MEDICAO,
            segundos=SEGUNDOS_DA_MEDICAO,
            motivos=motivos,
        )
        for modalidade in MODALIDADES
    ]
    return fen, lances, dict(motivos)


def processos_padrao() -> int:
    """Quantos processos usar quando ninguem disser.

    ⚠️ **Deixa dois de fora.** O dono roda isto na maquina que ele usa; tomar
    todos os nucleos faz o resto do sistema engasgar, e uma cacada que trava o
    computador e uma cacada que ninguem deixa terminar.
    """
    return max(1, (os.cpu_count() or 4) - 2)


def cacar(
    co_tipo: str, quantas_candidatas: int, *, processos: int = 1
) -> list[tuple[int, float, str]]:
    """Gera, peneira e mede as candidatas de um tipo.

    A busca roda em duas fases porque a medicao honesta e cara: com o orcamento
    do gerador (60 mil nos, 2 s por lance) e doze lances, uma unica candidata em
    quatro modalidades pode levar quase dois minutos. A peneira derruba a maioria
    a um vigesimo do custo.

    Returns:
        Triplas `(quantas_modalidades, lance_medio, fen)`, da melhor para a pior.
    """
    parametros = TIPOS[co_tipo]
    sorteio = random.Random(20260911)
    motivos = MotivoDeDescarte()

    candidatas = list(CANDIDATAS[co_tipo](sorteio, quantas_candidatas))
    # ⚠️ Duplicata e desperdicio puro: a mesma FEN medida duas vezes gasta o dobro
    # e responde a mesma coisa.
    candidatas = sorted(set(candidatas))
    print(f"[{co_tipo}] candidatas geradas: {len(candidatas)}")
    print(
        f"[{co_tipo}] processos: {processos} "
        f"(a maquina tem {os.cpu_count()} nucleos logicos)",
        flush=True,
    )

    # ── Fase 1: a peneira, so na brasileira ──────────────────────────────────
    #
    # ⛔ **A pergunta "o objetivo cai no lance 1?" vem antes de tudo, e nao custa
    # um no de busca** (acrescentada em 11/09/2026, depois que o cadeado
    # `test_moldes_de_damas.py` reprovou 13 moldes ja aprovados por este script).
    # O Sagaz joga a **partida**, e nao o **desafio**: coroar de cara costuma ser
    # mau lance, entao ele escolhia outra coisa e a medicao anotava "objetivo no
    # lance 3" em posicoes que qualquer pessoa resolve no primeiro toque.
    #
    # ⚠️ **Nas QUATRO modalidades**, porque a peneira com Sagaz roda so na
    # brasileira — e foi assim que dois moldes entraram com a portuguesa
    # cumprindo no lance 1.
    inicio = time.monotonic()
    peneiradas = []
    tarefas = [(fen, co_tipo, parametros) for fen in candidatas]
    for indice, (fen, lance, motivos_da_vez) in enumerate(
        _mapear(_peneirar_uma, tarefas, processos), start=1
    ):
        motivos.update(motivos_da_vez)
        if lance is not None:
            peneiradas.append(fen)
        if indice % 25 == 0 or indice == len(tarefas):
            gasto = time.monotonic() - inicio
            print(
                f"[{co_tipo}] peneira {indice}/{len(candidatas)} "
                f"— {len(peneiradas)} passaram — {gasto:.0f}s",
                flush=True,
            )
    print(
        f"[{co_tipo}] peneira concluida: {len(peneiradas)} de {len(candidatas)} "
        f"em {time.monotonic() - inicio:.0f}s"
    )
    print(f"[{co_tipo}] motivos de descarte na peneira: {dict(motivos)}")

    # ── Fase 2: a medicao nas quatro, com o orcamento do gerador ─────────────
    motivos_da_medicao = MotivoDeDescarte()
    inicio = time.monotonic()
    resultados: list[tuple[int, float, str]] = []
    tarefas = [(fen, co_tipo, parametros) for fen in peneiradas]
    for indice, (fen, lances, motivos_da_vez) in enumerate(
        _mapear(_medir_uma, tarefas, processos), start=1
    ):
        motivos_da_medicao.update(motivos_da_vez)
        cumpridos = [lance for lance in lances if lance is not None]
        # ⛔ **A trivialidade se confere nas QUATRO, e nao so na brasileira.** A
        # peneira roda num regulamento so, e na medicao de 11/09 dois moldes
        # passaram por ela com a portuguesa cumprindo no lance 1 — publicariam um
        # desafio de um lance em um dia de cada quatro. Basta uma modalidade
        # trivial para o molde nao servir.
        if cumpridos and min(cumpridos) < LANCE_MINIMO:
            motivos_da_medicao[f"trivial_em_alguma_modalidade_no_lance_{min(cumpridos)}"] += 1
            cumpridos = []
        quantas = len(cumpridos)
        # O lance medio so tem sentido entre as modalidades que cumpriram; sem
        # nenhuma, guarda-se zero para a ordenacao nao estourar.
        lance_medio = sum(cumpridos) / len(cumpridos) if cumpridos else 0.0
        resultados.append((quantas, lance_medio, fen))
        detalhe = ", ".join(
            f"{modalidade[:4]}={lance or '-'}"
            for modalidade, lance in zip(MODALIDADES, lances)
        )
        print(
            f"[{co_tipo}] medicao {indice}/{len(peneiradas)}: "
            f"{quantas}/4 modalidades, lance medio {lance_medio:.1f} "
            f"({detalhe}) — {fen}",
            flush=True,
        )
    print(f"[{co_tipo}] medicao concluida em {time.monotonic() - inicio:.0f}s")

    # ⚠️ A distribuicao sai SEMPRE, mesmo quando nada e aprovado. Foi a falta
    # dela que fez a primeira caçada terminar com uma linha so de saida e nenhuma
    # pista do motivo.
    print(f"[{co_tipo}] motivos de descarte na medicao: {dict(motivos_da_medicao)}")
    distribuicao = Counter(quantas for quantas, _, _ in resultados)
    print(f"[{co_tipo}] distribuicao (modalidades atendidas -> quantos moldes):")
    for quantas in range(5):
        print(f"    {quantas}/4 : {distribuicao.get(quantas, 0)}")

    # Ordena por modalidades atendidas e, dentro do empate, pelo objetivo que
    # demora mais a cair — entre dois moldes que servem as quatro, o que exige
    # mais lances rende o desafio mais interessante.
    resultados.sort(reverse=True)
    return [linha for linha in resultados if linha[0] >= MINIMO_DE_MODALIDADES]


def main() -> int:
    """Caca moldes e imprime o que passou, pronto para colar.

    Uso:

        python scripts/cacar_moldes_damas.py [quantas] [--processos N] [--tipo T]

    ⚠️ **Sem `--processos`, usa todos os nucleos menos dois** — ver
    `processos_padrao()`. `--processos 1` roda em sequencia, que e o modo de
    depurar: o rastro de uma excecao aparece inteiro.

    ⚠️ **`--tipo` passou a existir em 14/09/2026**, quando a cacada deixou de
    ter dois tipos e passou a ter quatro. ⛔ Sem ele, pedir moldes do sacrificio
    obrigaria a recacar os dois tipos que ja tem acervo — quase uma hora de CPU
    para reconfirmar o que ja esta em `tipos_de_desafio.py`.
    """
    argumentos = sys.argv[1:]
    processos = processos_padrao()
    if "--processos" in argumentos:
        onde = argumentos.index("--processos")
        processos = max(1, int(argumentos[onde + 1]))
        del argumentos[onde : onde + 2]

    escolhidos = list(TIPOS)
    if "--tipo" in argumentos:
        onde = argumentos.index("--tipo")
        pedido = argumentos[onde + 1]
        # ⛔ Falha alto, e com a lista: um nome errado silenciosamente ignorado
        # faria a cacada terminar em zero segundos parecendo que nada serve.
        if pedido not in TIPOS:
            print(f"⛔ tipo desconhecido: {pedido!r}. Ha: {', '.join(TIPOS)}")
            return 2
        escolhidos = [pedido]
        del argumentos[onde : onde + 2]

    quantas = int(argumentos[0]) if argumentos else 150

    aprovados: dict[str, list[tuple[int, float, str]]] = {}
    for co_tipo in escolhidos:
        print(f"\n{'=' * 70}\n{co_tipo}\n{'=' * 70}")
        aprovados[co_tipo] = cacar(co_tipo, quantas, processos=processos)

    print(f"\n{'=' * 70}\nMOLDES APROVADOS — prontos para `job/tipos_de_desafio.py`\n{'=' * 70}")
    for co_tipo, lista in aprovados.items():
        print(f"\n# {co_tipo}: {len(lista)} molde(s) servindo a {MINIMO_DE_MODALIDADES}+ modalidades")
        for quantas_modalidades, lance_medio, fen in lista:
            print(
                f'    "{fen}",   # {quantas_modalidades}/4 modalidades, '
                f"objetivo no lance {lance_medio:.1f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

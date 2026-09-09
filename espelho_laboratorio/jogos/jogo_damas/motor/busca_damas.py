"""Busca alfa-beta: o motor escolhendo o lance.

O que esta peça faz, em uma frase: imagina lances e respostas, desiste cedo dos
ramos que comprovadamente não mudariam a decisão, e devolve o melhor lance que
encontrou no tempo que teve.

A garantia que torna tudo isso confiável
----------------------------------------
**Alfa-beta devolve exatamente a mesma resposta que o minimax completo.** Não é
aproximação nem atalho arriscado: ela só deixa de calcular o que
comprovadamente não mudaria a escolha. Essa igualdade é testável, e é testada —
`../testes/test_busca_damas.py` roda as duas em dezenas de posições e exige que
o valor bata. É o que permite confiar na poda para sustentar um nível "quase
perfeito".

Negamax
-------
Em vez de escrever "na minha vez maximize, na dele minimize", escreve-se um só
caso: **o valor de uma posição para mim é o melhor entre `-valor(posição depois
do lance)` para ele**. Como a avaliação já devolve a nota do ponto de vista de
quem tem a vez (ver `avaliacao_damas.avaliar`), o sinal se resolve sozinho. É
metade do código e um terço dos bugs.

O que esta versão ainda NÃO faz
-------------------------------
- **Não tem livro de aberturas** — etapa 8.
- **Não é o motor rápido.** Este é o de referência, em Python. O port em Dart
  vem depois, e é ele que roda no aparelho.

O que ela passou a fazer em 2026-07-28
--------------------------------------
**Conhece os empates por regra.** Os arts. 97b (20 lances só de damas) e 98
(posição repetida três vezes) entraram na busca, vindos de
`empates_por_historico_damas`. Antes disso eles só existiam na arena, como num
árbitro — e o motor, que não os conhecia, avaliava como vantagem um final que o
regulamento já ia encerrar empatado. Os arts. 99 e 100 entram por outro caminho:
já estão gravados dentro da **base de finais**.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from jogos.jogo_damas.motor.avaliacao_damas import (
    PESOS_PADRAO,
    VITORIA,
    PesosAvaliacao,
    avaliar,
)

# ⚠️ **Alias obrigatório.** Os dois módulos de avaliação exportam uma função
# chamada `avaliar`, e a de cima já está importada. Sem o `as`, a segunda venceria
# em silêncio e o motor passaria a avaliar com a treinada mesmo sem ninguém pedir
# — o pior tipo de defeito, porque nada quebra: o motor só joga diferente. Não é
# hipótese: em 2026-07-30 um `VERSAO` importado sem alias fez o contrato publicar
# a versão errada, e só um teste pegou.
from jogos.jogo_damas.motor.avaliacao_treinada_damas import (
    PesosDosPadroes,
    avaliar as avaliar_treinado,
)
from jogos.jogo_damas.motor.empates_por_historico_damas import (
    HistoricoDaPartida,
    limite_de_equilibrio_parado,
    muda_o_equilibrio,
    tres_damas_contra_uma,
    zera_o_contador,
)
from jogos.jogo_damas.motor.regras_damas import (
    BRASILEIRAS,
    Lance,
    Regulamento,
    aplicar_lance,
    gerar_lances,
)
from jogos.jogo_damas.motor.tabuleiro_damas import Tabuleiro

# A busca consulta a base de finais quando ela é fornecida (*probing*). O import
# é de mão única — `tablebase/` não conhece a busca —, então não há ciclo. Os
# dois `VITORIA` diferentes são renomeados aqui de propósito: um é nota de
# avaliação (1.000.000), o outro é o código de resultado guardado na base (2).
# Deixá-los com o mesmo nome no mesmo arquivo seria implorar por um bug de sinal.
from jogos.jogo_damas.tablebase.indice_damas import (  # noqa: E402
    EMPATE as EMPATE_NA_BASE,
)
from jogos.jogo_damas.tablebase.indice_damas import (  # noqa: E402
    VITORIA as VITORIA_NA_BASE,
)
from jogos.jogo_damas.tablebase.retrograda_damas import BaseDeFinais  # noqa: E402


def contar_pecas(tabuleiro: Tabuleiro) -> int:
    """Quantas peças há no tabuleiro, de qualquer cor ou tipo.

    `Peca.VAZIA` vale 0 e as demais valem 1 a 4, então "casa ocupada" é
    simplesmente "valor verdadeiro" — o mesmo truque que a numeração da base
    usa. Existe aqui, e não em `Tabuleiro`, porque quem precisa dela é a
    consulta à base: é o filtro barato que evita perguntar por uma posição de
    meio-jogo que a base nunca teria.
    """
    return sum(1 for conteudo in tabuleiro.casas if conteudo)

# Limite de extensões de captura, para a quiescência não descer para sempre numa
# posição de trocas encadeadas. 12 é folgado: sequências forçadas mais longas que
# isso praticamente não existem em damas 8x8.
MAX_EXTENSAO = 12

MARGEM_DO_ERRO = 200
"""Quão pior o segundo melhor lance pode ser e ainda assim ser jogado, em
centésimos de pedra — ver `Nivel.chance_de_errar`.

200 = duas pedras. O número é o freio de sanidade que separa "erro humano" de
"lance absurdo": dar **uma** pedra é o engano clássico de quem está aprendendo e
deixa o jogador com uma vantagem que ele entende como ter conquistado; entregar
uma dama de graça, ou entrar numa perda forçada (nota da ordem de ±1.000.000),
não parece um adversário fraco — parece um adversário quebrado.

Sem este freio, `chance_de_errar` reintroduziria exatamente o defeito que a
decisão original de 2026-07-24 evitava ao manter o ruído longe da escolha do
lance."""

# Marcadores do que um registro da tabela de transposição significa.
EXATO = 0
"""O valor guardado é a nota verdadeira daquela posição."""
LIMITE_INFERIOR = 1
"""A nota verdadeira é **pelo menos** isto (houve corte beta)."""
LIMITE_SUPERIOR = 2
"""A nota verdadeira é **no máximo** isto (nenhum lance superou alfa)."""

BITS_DA_TABELA = 20
"""A tabela de transposição tem ``2 ** BITS_DA_TABELA`` casas — **fixo**.

1.048.576 casas é folgado para o maior orçamento de nós em uso (o Sagaz visita
até 288 mil posições) e ainda cabe num aparelho modesto.

**É fixo de propósito** (decisão de 2026-07-28, etapa 8). O caminho natural seria
dimensionar a tabela pela RAM disponível — e isso reintroduziria pela porta dos
fundos exatamente o problema que o orçamento de nós resolveu: com tabela maior a
busca reaproveita mais, poda mais e chega mais fundo no mesmo número de nós. O
aparelho voltaria a mandar no nível.

⚠️ **Este número é o mesmo do motor em Dart (`bitsDaTabela: 20`) e do Rust, e
tem de continuar sendo.** Ele não muda quais lances são legais — muda quantos nós
a busca gasta para varrer a mesma árvore. Dois motores com tabelas de tamanhos
diferentes param em pontos diferentes quando o orçamento acaba, e orçamento é
exatamente como os quatro níveis do app são definidos."""

ENTRADAS_NA_TABELA = 1 << BITS_DA_TABELA
"""Quantas casas a tabela tem, já calculado. Ver `BITS_DA_TABELA`."""


@dataclass
class Estatisticas:
    """O que aconteceu durante uma busca. Serve para medir e para depurar."""

    nos: int = 0
    """Posições visitadas. É o número que a etapa 3 mede em nós por segundo."""

    cortes: int = 0
    """Quantas vezes a poda descartou o resto de um ramo."""

    acertos_na_tabela: int = 0
    """Quantas vezes a posição já estava calculada na tabela de transposição."""

    consultas_a_base: int = 0
    """Quantas vezes a base de finais respondeu **no meio da busca**.

    Este número mede o que a medição de fases da partida não conseguia ver: a
    base começa a influenciar o jogo muitos meios-lances antes de o tabuleiro
    chegar a 4 ou 5 peças, porque a busca **enxerga** o final antes de a partida
    chegar lá. É um dos dois números que decidem a etapa 6e (quanto da base
    viaja dentro do app).
    """

    empates_por_historico: int = 0
    """Quantas vezes a busca declarou empate pelos arts. 97b ou 98.

    Zero numa abertura é o esperado — as duas regras só disparam em final
    embaralhado. Número alto num final de damas contra damas é o **sinal de que
    o recurso está funcionando**: cada um desses é um ramo em que o motor antes
    enxergava vantagem e agora enxerga o empate que o árbitro daria.
    """

    profundidade_atingida: int = 0
    tempo_segundos: float = 0.0

    motivo_da_parada: str = "profundidade"
    """Por que o aprofundamento iterativo parou: ``"profundidade"`` (chegou ao
    teto pedido), ``"nos"``, ``"tempo"`` ou ``"decidido"`` (achou vitória ou
    derrota forçada, e aprofundar não muda mais nada).

    Numa partida do Sagaz isto tem de dizer ``"nos"`` quase sempre. Se disser
    ``"tempo"``, o aparelho é lento demais para o orçamento configurado e **o
    nível deixou de ser o mesmo nível** — é o sintoma que o §7.1 de
    `docs/como_funciona_a_ia_de_damas.md` descreve.
    """


@dataclass
class Resultado:
    """O que a busca devolve."""

    lance: Lance | None
    nota: int
    variante_principal: tuple[Lance, ...]
    """A sequência que o motor acha que vai acontecer. Ler isto é o jeito mais
    rápido de descobrir que a avaliação está torta: se a linha principal for
    absurda, o problema não é a busca."""
    estatisticas: Estatisticas


# --- o orçamento dos níveis, e de onde saem estes números ------------------
#
# Aparelho de referência: Galaxy A35 5G, **160.593 nós/s** medidos com o motor em
# Dart (etapa 3c). Os tetos abaixo são "quanto o A35 pensaria naquele tempo" —
# e é esse número, e não o tempo, que vai para dentro do app.
#
# ⚠️ **Os tetos deixaram de ser derivados desta taxa em 2026-09-03.** O valor de
# produção agora é literal, igual ao do motor Dart e ao do contrato — ver o
# comentário logo acima de CACAU. Esta constante e `_teto_para` continuam aqui
# porque a **conta** segue útil para propor um teto para um aparelho novo; ela só
# não decide mais o número que vai ao jogador.
_NOS_POR_SEGUNDO_NO_APARELHO_DE_REFERENCIA = 160_593

# A taxa que vale para o **ritmo da tela**: o motor nativo (Rust) no aparelho de
# ENTRADA, e não o Dart no aparelho de referência.
#
# Sai da medição de 26/08/2026 no Galaxy A04, o mais fraco da bancada: os 288.000
# nós do Sagaz custam **0,74 s** ali, ou seja ~389.000 nós/s. É esta a taxa certa
# para a conta da espera-alvo porque, onde o motor nativo **não** carrega, o
# Sagaz simplesmente não é ofertado (T199) — logo não existe caso em que o Magno
# roda a 160.593 nós/s no aparelho de alguém.
_NOS_POR_SEGUNDO_COM_MOTOR_NATIVO = 389_000

# A **rede de segurança**: o tempo máximo de uma busca, em segundos.
#
# É um número só para os quatro níveis e **não** é parâmetro de dificuldade —
# espelha `redeDeSeguranca` do motor Dart. Toda vez que a rede morde, a promessa
# do teto de nós se quebra (o nível deixa de ser o mesmo nível naquele aparelho,
# e o log grava `motivo_parada=tempo`), então quanto mais alta ela é, mais fiel o
# nível. Subiu de 2-3 s para 10 s em 26/08/2026 e cabe folgada no menor relógio
# da tela, que é o de 20 s do Magno.
REDE_DE_SEGURANCA = 10.0


def _teto_para(segundos: float) -> int:
    """Quantos nós o aparelho de referência visitaria em `segundos`.

    Arredondado para o milhar mais próximo — precisão maior seria falsa, já que
    a taxa medida varia com a posição.
    """
    bruto = _NOS_POR_SEGUNDO_NO_APARELHO_DE_REFERENCIA * segundos
    return int(round(bruto / 1000.0)) * 1000


@dataclass(frozen=True)
class Nivel:
    """Um nível de dificuldade, definido por **orçamento de busca**.

    Os quatro níveis do app não são quatro motores: são o mesmo motor com mais ou
    menos permissão para pensar. É mais simples e mais honesto que treinar
    modelos separados.

    Attributes:
        ruido: quanto de barulho aleatório entra na **avaliação** (em centésimos
            de pedra).

            ⚠️ **Ele vale muito menos do que o número sugere**, e isso foi
            medido de olho em 2026-08-14, quando o dono relatou que nem a Cacau
            era vencível. O ruído é sorteado **em cada folha**, e o minimax é um
            filtro de ruído: máximos e mínimos sobre muitas folhas independentes
            fazem o sorteio se cancelar na média. Pior, ele não desfaz o que
            decide a partida — um lance que ganha uma pedra vale +100, e inverter
            isso exigiria +90 no ramo ruim *e* −90 no bom ao mesmo tempo.

            Continua aqui porque não faz mal e ajuda na margem. Quem afrouxa o
            motor de verdade são os dois campos abaixo.
        extensao_de_captura: a quiescência, **por nível** desde 2026-08-14.

            É o botão mais forte da lista, e ficou anos ligado para todo mundo.
            Com ela, mesmo uma busca de profundidade 2 enxerga toda sequência de
            trocas até o fim e **nunca** deixa uma peça pendurada — que é
            exatamente o que decide partida contra quem está aprendendo. A
            profundidade nominal quase não importa perto disso.

            Desligá-la produz o erro mais humano que existe em damas: parar de
            contar no meio da troca, achar que ganhou uma peça e perceber tarde
            demais que ela é retomada.
        chance_de_errar: probabilidade (0 a 1) de jogar o **segundo** melhor
            lance em vez do primeiro.

            A distinção que a versão anterior deste texto não fazia: sortear
            entre **todos** os lances produz erros absurdos, que irritam; sortear
            entre os **dois melhores**, e só quando estão perto em nota
            (`MARGEM_DO_ERRO`), produz o erro de quem escolheu a segunda melhor
            ideia — que é o que um humano faz.

            E há uma razão estrutural para o erro morar aqui e não na folha:
            **ruído na folha o minimax filtra; erro na raiz não é filtrado por
            nada.** É o único dos dois cuja força cai de forma previsível, e
            portanto o único que se calibra.
        margem_do_erro: quão pior, em centésimos de pedra, pode ser o lance
            sorteado quando o erro acontece. Ver `MARGEM_DO_ERRO`.

            É este campo, e não `chance_de_errar`, que decide **o tamanho** do
            erro — o outro decide só a frequência. Mexer na frequência com a
            margem apertada não move a força quase nada, o que foi medido em
            2026-08-14: 35% e 60% de chance deram o mesmo 0,0% de derrota.
        teto_de_nos: o orçamento **de verdade**, decidido em 2026-07-28. Contar
            posições visitadas, e não segundos, é o que faz o nível ser o mesmo
            nível em qualquer aparelho — ver o §7.1 de
            `docs/como_funciona_a_ia_de_damas.md`.
        tempo_maximo: **rede de segurança**, não critério. Existe para o aparelho
            muito lento não travar a interface; quando ele dispara, o jogador
            recebeu um adversário mais fraco do que o nível promete, e a
            estatística `motivo_da_parada` registra isso.
    """

    identificador: str
    nome: str
    profundidade: int
    ruido: int = 0
    teto_de_nos: int | None = None
    tempo_maximo: float | None = None
    extensao_de_captura: bool = True
    chance_de_errar: float = 0.0
    margem_do_erro: int = MARGEM_DO_ERRO


# A escada desceu um degrau em 2026-08-14, e o número que mandou nisso está em
# `scripts/medir_escada_de_niveis_damas.py`.
#
# O QUE A MEDIÇÃO MOSTROU, e que nenhuma intuição anterior tinha acertado:
#
#   configuração da Cacau            derrota contra o iniciante de referência
#   ------------------------------   ----------------------------------------
#   profundidade 2, sem quiescência                    0,0%   (30 partidas)
#   profundidade 2, sem quiescência, errando 60%       0,0%
#   profundidade 1, COM quiescência                    0,0%
#   profundidade 1, sem quiescência                   36,7%   ✅
#
# A leitura: **o que decide é enxergar ou não a resposta do adversário**, e a
# quiescência é um substituto dela. Em damas a captura é obrigatória, então o
# ramo de captura é quase forçado — estender por ele até o fim equivale a ver a
# resposta, mesmo com profundidade nominal 1. É por isso que as três primeiras
# linhas empatam em zero: nas três o motor enxerga a réplica, por um caminho ou
# por outro.
#
# Daí os dois freios terem de andar JUNTOS na Cacau. Separados, nenhum dos dois
# faz diferença nenhuma — que foi exatamente o resultado de aplicá-los sozinhos.
#
# ⚠️ Os quatro tetos abaixo são **literais e espelham o motor Dart**
# (`../motor_dart/lib/busca_damas.dart`), que é quem roda no aparelho. Não
# voltar a derivá-los de `_teto_para(...)`: a conta antiga devolve 96.000 para o
# Sagaz, e o valor publicado é 288.000.
CACAU = Nivel("cacau", "Cacau", profundidade=1, ruido=90,
              teto_de_nos=24_000, tempo_maximo=REDE_DE_SEGURANCA,
              extensao_de_captura=False, chance_de_errar=0.35,
              margem_do_erro=200)
"""Validada **jogando**, em 2026-08-14: o dono ganhou 3 de 4 partidas na bancada
com exatamente esta configuração. É o único nível cujo número veio de partida
contra gente, e por isso é o que não se mexe sem novo teste jogado."""

PITA = Nivel("pita", "Pita", profundidade=2, ruido=40,
             teto_de_nos=24_000, tempo_maximo=REDE_DE_SEGURANCA,
             extensao_de_captura=False, chance_de_errar=0.25,
             margem_do_erro=150)
"""Um degrau só acima da Cacau — e é o degrau mais brusco da escala: a Pita
**enxerga a resposta** do adversário (profundidade 2), mas continua sem seguir
as trocas até o fim."""

TEX = Nivel("tex", "Tex", profundidade=3, ruido=0,
            teto_de_nos=48_000, tempo_maximo=REDE_DE_SEGURANCA,
            chance_de_errar=0.08, margem_do_erro=80)
"""Aqui entra a **quiescência**, o freio mais forte de todos: o Tex deixa de cair
em troca simples.

⚠️ A profundidade é 3, e não 4 como na primeira proposta, por observação do
dono: *"fico com receio de a distância da Pita para o Tex ser muito grande"*.
Ele estava certo — a proposta original pulava dois degraus da escada medida de
uma vez só. Encurtar aqui sai barato porque sobra espaço até o Magno, que roda
em profundidade ~10."""

SAGAZ = Nivel("sagaz", "Sagaz", profundidade=64, ruido=0,
              teto_de_nos=288_000, tempo_maximo=REDE_DE_SEGURANCA)
"""⚠️ **288.000 nós desde 2026-08-26, e o número saiu de ARM real** — decisão do
dono, espelhada aqui do motor Dart em 2026-09-03.

A conta é a espera-alvo do Magno (0,80 s) vezes o que o aparelho de entrada faz
por segundo **com o motor nativo em Rust**: no Galaxy A04 os 288.000 custam
0,74 s, e cabem nos 800 ms. Onde o motor nativo não carrega, o Sagaz não é
ofertado.

<details><summary>O que valia antes — para o histórico</summary>

Entre 14/08 e 26/08 o teto foi de **96.000** nós, derivado de 0,6 s do aparelho
de referência com o motor **Dart**. O corte de 321 mil para 96 mil fora medido:
em 10 posições ele mudava o lance em 2 casos, com perda de 0,05 pedra em média e
0,10 no pior caso — ruído, não força. O que subiu o teto de volta não foi uma
reavaliação dessa medida, e sim o motor nativo, ~10x mais rápido no mesmo ARM.

A rede de segurança acompanhou o caminho inverso: 8 s → 3 s em 14/08, e de volta
a **10 s** em 26/08, quando ficou claro que rede alta significa nível mais fiel
(ver `REDE_DE_SEGURANCA`).

</details>

✅ **O Magno está confirmado** — decisão do dono em 2026-08-14, depois de jogar
contra o motor: *"já estou convencido de que o motor joga muito bem contra um
humano"*.

Isso **não** atropela a regra do nível Sagaz. A regra exige quase perfeição
medida; o alvo declarado aqui é **menos de 1% de derrota contra um adulto**, e
não contra jogo perfeito. A evidência prática existe: a Cacau, antes de ser
freada, era descrita como quase impossível de vencer — e ela é o nível mais
fraco, com profundidade 2. Este roda em profundidade ~10.

A etapa 9 continua valendo, mas mudou de papel: já não decide *se* há um quarto
nível, e sim **quanto ele vale contra o oráculo** — informação de qualidade, e
insumo para saber se a base de finais compensa o tamanho no APK.

Note que os três primeiros níveis também têm teto de profundidade: neles quem
manda quase sempre é a profundidade, e o teto de nós é o que impede uma posição
com muitas capturas encadeadas de custar dez vezes o normal."""

NIVEIS: dict[str, Nivel] = {n.identificador: n for n in (CACAU, PITA, TEX, SAGAZ)}


class _OrcamentoEsgotado(Exception):
    """Levantada no meio da recursão quando o orçamento da busca acaba.

    Usar exceção — e não um `if` propagado por todo retorno — mantém o negamax
    legível. O resultado da profundidade interrompida é **descartado**: só vale
    a última profundidade que terminou inteira, senão o motor jogaria a partir
    de uma varredura pela metade, que é pior que a anterior completa.
    """


class _TempoEsgotado(_OrcamentoEsgotado):
    """O relógio estourou. Rede de segurança — ver `Nivel.tempo_maximo`."""


class _NosEsgotados(_OrcamentoEsgotado):
    """O teto de posições visitadas estourou. É o critério normal de parada."""


@dataclass
class Buscador:
    """Guarda o que sobrevive entre chamadas: tabela de transposição e histórico.

    É classe e não função solta porque a tabela de transposição é o que faz o
    aprofundamento iterativo valer a pena: a profundidade 5 reaproveita quase
    tudo que a 4 descobriu.
    """

    regulamento: Regulamento = BRASILEIRAS
    pesos: PesosAvaliacao = PESOS_PADRAO

    pesos_treinados: PesosDosPadroes | None = None
    """As tabelas de padrões treinadas. Quando presentes, **substituem** a
    avaliação escrita à mão — `pesos` passa a ser ignorado.

    Por que é um campo e não uma função injetada
    --------------------------------------------
    Passar `avaliar` como parâmetro seria mais flexível e custaria caro no lugar
    errado: a avaliação é a folha da árvore, chamada centenas de milhares de vezes
    por lance, e uma chamada indireta ali não some no ruído. Um `if` num campo,
    sim — o preditor de desvio acerta sempre, porque a resposta é a mesma durante
    a partida inteira.

    Por que o padrão é `None`
    -------------------------
    Os pesos moram em `modelos/`, que está **fora do Git**. O motor de referência
    tem de funcionar num clone limpo, e ele funciona: sem pesos treinados, joga
    com a avaliação manual, que é a que sempre jogou.

    ⚠️ **A escolha ainda não está feita.** Quem decide se a treinada substitui a
    manual em produção é a arena da etapa 9 — se ela não ganhar 100 Elo, este
    campo continua existindo e continua desligado por padrão.
    """

    semente: int | None = None
    """Semente do ruído dos níveis fracos. Fixe-a para partida reproduzível."""

    usar_tabela: bool = True
    """Ligar/desligar a tabela de transposição.

    Existe desligável por causa do teste de equivalência com o minimax. A tabela
    faz uma posição alcançada por dois caminhos diferentes devolver o valor
    calculado na busca **mais funda** das duas — o que é melhor para jogar, e
    diferente do minimax de profundidade fixa. Sem esta chave, o teste que prova
    que a poda não mente compararia coisas diferentes e falharia por um motivo
    que não é o que ele investiga.
    """

    extensao_de_captura: bool = True
    """Ligar/desligar a quiescência, pelo mesmo motivo da chave acima.

    ⚠️ Desde 2026-08-14 este campo é apenas o **padrão**: `buscar()` aceita o seu
    próprio, e `Nivel.extensao_de_captura` o usa para afrouxar os níveis fracos.
    Quem manda durante a busca é `_extensao_ativa`, nunca este atributo — mexer
    aqui achando que se está mexendo no nível é o erro fácil deste trecho.
    """

    usar_empates_por_historico: bool = True
    """Ligar/desligar os arts. 97b e 98 **dentro** da busca.

    Mesma motivação das duas chaves acima: o `minimax_sem_poda` não conhece
    histórico nenhum, então o teste de equivalência precisa comparar contra uma
    busca que também não conheça. Com ela ligada os dois podem divergir
    legitimamente — em posição de damas embaralhando, a alfa-beta enxerga o
    empate por repetição e o minimax não —, e o teste falharia acusando a poda de
    mentir quando a poda está certa.

    Fora do teste, **deixe ligada**. Desligá-la devolve o motor de antes de
    2026-07-28, que achava que estava ganhando finais empatados.
    """

    base: BaseDeFinais | None = None
    """A base de finais, para consulta **dentro** da busca (*probing*).

    Com ela, o motor deixa de estimar o final: quando um ramo da busca chega a
    uma posição que a base cobre, a resposta que volta é a **exata** — vitória,
    derrota ou empate com jogo perfeito —, e não a nota da avaliação.

    O efeito é maior do que "jogar bem os últimos lances": a resposta exata sobe
    pela árvore. Se o motor enxerga 13 meios-lances à frente, ele passa a jogar
    com informação perfeita a partir de ~13 meios-lances **antes** de a partida
    chegar ao número de peças da base.

    `None` desliga a consulta, e é o padrão — o motor de referência precisa
    funcionar sem `dados/`, que está fora do Git.
    """

    bits_da_tabela: int = BITS_DA_TABELA
    """A tabela tem ``2 ** bits_da_tabela`` casas. Ver `BITS_DA_TABELA`.

    Só se mexe nisto em teste, para forçar colisão numa tabela minúscula. Em uso
    normal ele fica no valor do app — mudá-lo faz este motor podar diferente do
    que roda no aparelho.
    """

    # ── A tabela de transposição, em cinco colunas ───────────────────────────
    #
    # A casa `i` de cada lista descreve o mesmo registro. É a mesma forma do
    # motor em Dart, e ela não é escolha de estilo: **a tabela é indexada por
    # `hash & máscara`**, o que faz duas posições diferentes disputarem a mesma
    # casa. Quem chega por último fica com ela.
    #
    # ⚠️ **Antes de 03/09/2026 aqui havia um `dict` com a posição inteira como
    # chave** — sem colisão nenhuma, e por isso "obviamente correto" para um
    # motor de referência. Estava errado do jeito que importa: sem colisão, este
    # motor reaproveitava registros que o app perde, podava mais e visitava
    # menos nós. Medido: 98.583 nós aqui contra 98.938 no Dart, na mesma busca de
    # profundidade 10. Com teto de nós — que é como os níveis são definidos —
    # dois motores que podam diferente param em lugares diferentes e escolhem
    # lances diferentes. Um motor de referência que não reproduz o motor em campo
    # não é referência de nada.

    _tt_chave: list = field(default_factory=list, init=False, repr=False)
    """O hash de Zobrist da posição guardada nesta casa."""

    _tt_profundidade: list = field(default_factory=list, init=False, repr=False)
    """A que profundidade a nota foi calculada. **`-1` significa casa vazia** —
    `0` aqui quer dizer "avaliada na folha", que é coisa bem diferente."""

    _tt_nota: list = field(default_factory=list, init=False, repr=False)
    """A avaliação guardada, em centésimos de pedra."""

    _tt_marcador: list = field(default_factory=list, init=False, repr=False)
    """Se a nota é `EXATO`, `LIMITE_INFERIOR` ou `LIMITE_SUPERIOR`."""

    _tt_lance: list = field(default_factory=list, init=False, repr=False)
    """O melhor lance encontrado naquela posição — o que faz a ordenação começar
    pelo candidato certo."""

    _mascara: int = field(default=0, init=False, repr=False)
    """`2 ** bits_da_tabela - 1`. O `and` com ela transforma o hash de 64 bits no
    número da casa, que é o mesmo que o resto da divisão por uma potência de 2 —
    e muito mais barato."""

    _historico: dict = field(default_factory=dict, init=False, repr=False)
    _aleatorio: random.Random = field(init=False, repr=False)
    _estatisticas: Estatisticas = field(default_factory=Estatisticas, init=False, repr=False)
    _prazo: float | None = field(default=None, init=False, repr=False)
    _teto_de_nos: int | None = field(default=None, init=False, repr=False)
    _ruido: int = field(default=0, init=False, repr=False)
    _pecas_na_base: int = field(default=0, init=False, repr=False)

    _extensao_ativa: bool = field(default=True, init=False, repr=False)
    """A quiescência **desta busca** — ver `extensao_de_captura` e `buscar()`."""

    _chance_de_errar: float = field(default=0.0, init=False, repr=False)
    """A chance de erro **desta busca** — ver `Nivel.chance_de_errar`."""

    _margem_do_erro: int = field(default=MARGEM_DO_ERRO, init=False, repr=False)
    """Quão pior pode ser o lance sorteado — ver `Nivel.margem_do_erro`."""

    _meios_lances_para_empate: int = field(default=0, init=False, repr=False)
    """O limite do art. 97b (ou WCDF 1.27.2) em meios-lances, lido do regulamento
    uma vez só. É consultado a cada nó — resolver a propriedade um milhão de
    vezes por busca custaria sem comprar nada."""

    _meios_lances_da_correlacao: int | None = field(default=None, init=False, repr=False)
    """O limite da FMJD 8.3 em meios-lances, ou `None` se o regulamento não a
    tem. Serve de **porteiro**: só quando o contador o alcança é que vale a pena
    contar as peças para saber se a correlação de forças vale."""

    _menor_limite_de_equilibrio: int | None = field(default=None, init=False, repr=False)
    """O **menor** dos limites da FMJD 8.5, em meios-lances (30 lances = 60, nos
    finais de 4–5 peças). Mesmo papel de porteiro: abaixo dele nenhuma faixa
    pode ter disparado, então nem se conta as peças."""

    _repeticoes_na_partida: dict = field(default_factory=dict, init=False, repr=False)
    """As posições que já ocorreram na partida de verdade, com a contagem de cada
    uma. Vem de fora, pelo `historico` de `buscar`; vazio quando ninguém passa."""

    _no_caminho: dict = field(default_factory=dict, init=False, repr=False)
    """As posições do caminho da raiz até o nó atual, com quantas vezes cada uma
    aparece **neste ramo**.

    É o que permite ver a repetição que ainda não aconteceu: se a partida já
    passou uma vez por P e a busca encontra um ramo que volta a P duas vezes, são
    três — e o art. 98 fecha o jogo ali dentro da imaginação do motor."""

    def __post_init__(self) -> None:
        self._aleatorio = random.Random(self.semente)

        # A tabela nasce inteira, do tamanho definitivo — como no motor em Dart,
        # que aloca cinco vetores de tipo fixo no construtor. Aqui são listas
        # comuns, mas o tamanho e a política de substituição são os mesmos, que é
        # o que decide quantos nós a busca custa.
        casas = 1 << self.bits_da_tabela
        self._mascara = casas - 1
        self._tt_chave = [0] * casas
        # `-1` = casa vazia. Sem esta linha, o zero natural faria toda casa nunca
        # escrita parecer "nota de folha guardada", e a busca leria lixo como nota.
        self._tt_profundidade = [-1] * casas
        self._tt_nota = [0] * casas
        self._tt_marcador = [EXATO] * casas
        self._tt_lance = [None] * casas

        # A quiescência da busca começa igual à do construtor. Quem chama
        # `buscar()` (ou `jogar()`, pelo nível) pode sobrescrevê-la por busca.
        self._extensao_ativa = self.extensao_de_captura

        # ⚠️ Pesos de uma modalidade não valem em outra, e o erro é MUDO.
        #
        # Cada modalidade tem seu auto-jogo e seu treino: o modelo das brasileiras
        # aprendeu num jogo em que a dama voa e a pedra captura para trás. Usá-lo
        # nas anglo-americanas produz notas plausíveis e erradas — a busca roda,
        # a partida termina, o placar sai, e o número não vale nada.
        #
        # Descoberto em 2026-08-12 rodando de propósito uma arena `--regulamento
        # portuguesa` com o `.bin` das brasileiras: saíram placar, PDN e replay,
        # sem um aviso. O nome da modalidade sempre esteve no cabeçalho do
        # arquivo; faltava alguém compará-lo.
        if (
            self.pesos_treinados is not None
            and self.pesos_treinados.regulamento != self.regulamento.identificador
        ):
            raise ValueError(
                "os pesos treinados são da modalidade "
                f"'{self.pesos_treinados.regulamento}', mas o buscador joga "
                f"'{self.regulamento.identificador}'. Cada modalidade precisa do "
                "seu próprio treino — ver a etapa 7 do plano."
            )
        self._meios_lances_para_empate = (
            self.regulamento.meios_lances_sem_progresso_para_empate
        )
        if self.regulamento.lances_tres_damas_contra_uma is not None:
            self._meios_lances_da_correlacao = (
                2 * self.regulamento.lances_tres_damas_contra_uma
            )
        if self.regulamento.lances_equilibrio_parado:
            self._menor_limite_de_equilibrio = 2 * min(
                lances for _, _, lances in self.regulamento.lances_equilibrio_parado
            )
        # Quantas peças a base carregada cobre. Guardar isto evita a consulta
        # mais cara que existe: perguntar à base por uma posição de meio-jogo,
        # que ela nunca teria. Contar peças é barato; montar a fatia e indexar,
        # não. Uma base parcial (só algumas fatias) responde `None` para as que
        # faltam, e a busca segue normalmente ali.
        if self.base is not None and self.base.fatias:
            self._pecas_na_base = max(
                fatia.total_de_pecas for fatia in self.base.fatias.values()
            )

    # -- identidade da posição ----------------------------------------------
    #
    # É o hash de Zobrist, `Tabuleiro.hash` — o mesmo número que o motor do
    # aparelho calcula, com a mesma tabela de números aleatórios (ver
    # `zobrist_damas.py`). Ele serve para três coisas neste arquivo: indexar a
    # tabela de transposição, contar repetições da partida e contar repetições
    # dentro do ramo em exame.
    #
    # ⚠️ Zobrist **tem colisão** — duas posições diferentes podem dar o mesmo
    # número, com chance de uma em 2⁶⁴. Era esse o argumento para este motor usar
    # a posição inteira como chave até 02/09/2026, e ele estava certo em tese e
    # errado na prática: o app convive com a colisão, e um motor de referência
    # que não convive com ela responde por um aparelho que não existe.
    #
    # É a mesma identidade que o art. 98 usa para dizer "mesma posição"
    # (`empates_por_historico_damas.chave_da_posicao`, que agora devolve o mesmo
    # hash). Duas definições de identidade no mesmo motor divergiriam com o
    # tempo, e o sintoma seria empate declarado onde não há.

    # -- avaliação com ruído -------------------------------------------------

    def _avaliar(self, tabuleiro: Tabuleiro) -> int:
        """A nota da folha, do ponto de vista de quem tem a vez.

        **É o único lugar do motor que escolhe entre as duas avaliações.** Ter um
        só ponto de escolha é o que permite trocá-las na arena sem que nada mais
        na busca precise saber qual está valendo.

        As duas devolvem centésimos de pedra do ponto de vista de quem joga, e a
        ordem dos argumentos é **diferente** entre elas (`(tabuleiro, pesos)` na
        manual, `(pesos, tabuleiro)` na treinada) — herança de terem nascido em
        momentos diferentes. Trocar a ordem agora quebraria os 18 arquivos que já
        chamam uma ou outra, e não compraria nada.
        """
        if self.pesos_treinados is not None:
            nota = avaliar_treinado(self.pesos_treinados, tabuleiro)
        else:
            nota = avaliar(tabuleiro, self.pesos)
        if self._ruido:
            nota += self._aleatorio.randint(-self._ruido, self._ruido)
        return nota

    # -- ordenação de lances -------------------------------------------------

    def _ordenar(self, lances: list[Lance], lance_da_tabela: Lance | None) -> list[Lance]:
        """Põe na frente os lances com mais chance de causar corte.

        Ordenação **não muda a resposta** — muda quanto trabalho custa chegar
        nela. Com a ordem certa, a poda corta cedo e o número de posições
        visitadas cai para perto da raiz quadrada; com a ordem errada, o motor
        busca a mesma coisa e demora dezenas de vezes mais.

        Duas fontes, nesta ordem:

        1. **o lance que a tabela guardou** para esta posição — foi o melhor numa
           busca anterior, então é o palpite mais forte que existe;
        2. o **histórico**: lances que causaram corte em outras posições. Barato
           e surpreendentemente eficaz.
        """
        def prioridade(lance: Lance) -> tuple:
            return (
                0 if lance == lance_da_tabela else 1,
                -self._historico.get((lance.origem, lance.destino), 0),
            )

        return sorted(lances, key=prioridade)

    # -- o coração -----------------------------------------------------------

    def _negamax(
        self,
        tabuleiro: Tabuleiro,
        profundidade: int,
        alfa: int,
        beta: int,
        ply: int,
        extensoes: int,
        sem_progresso: int,
        sem_mudar_equilibrio: int,
    ) -> int:
        """A nota da posição, do ponto de vista de quem tem a vez.

        `alfa` é o melhor que quem joga já garantiu; `beta`, o melhor que o
        adversário já garantiu. Quando um lance devolve valor ≥ beta, o
        adversário nunca deixaria chegar aqui — e o resto do ramo é abandonado
        sem ser lido. Isso é o corte.

        Args:
            sem_progresso: há quantos meios-lances só se movem damas, contando
                desde a partida de verdade e continuando pelo caminho imaginado.
                É o contador do art. 97b, e ele **desce** pela recursão em vez de
                morar no `Buscador` porque cada ramo tem o seu: um ramo que
                captura zera, o ramo vizinho que não captura continua contando.
            sem_mudar_equilibrio: o segundo relógio, o da FMJD 8.5. Zera com
                captura ou promoção, e **não** com movimento de pedra — por isso
                não dá para derivá-lo do anterior.
        """
        self._estatisticas.nos += 1

        # O teto de nós é conferido a CADA nó, e não de 2048 em 2048 como o
        # relógio. A diferença não é capricho: se o corte caísse num múltiplo de
        # 2048, o ponto exato de parada dependeria de quantos nós a extensão de
        # captura gastou antes — e o resultado deixaria de ser reproduzível entre
        # aparelhos, que é a única razão de o teto existir.
        if self._teto_de_nos is not None and self._estatisticas.nos > self._teto_de_nos:
            raise _NosEsgotados

        # Conferir o relógio a cada nó custaria caro; a cada 2048 basta, e o erro
        # de estouro fica em milissegundos. Aqui a imprecisão é aceitável porque
        # o relógio é rede de segurança, não critério.
        if self._prazo is not None and self._estatisticas.nos % 2048 == 0:
            if time.monotonic() > self._prazo:
                raise _TempoEsgotado

        alfa_original = alfa
        chave = tabuleiro.hash
        # A casa desta posição na tabela. Calculada uma vez e reusada na escrita
        # lá embaixo — o hash não muda ao longo do nó.
        casa = chave & self._mascara

        # --- os empates que o regulamento declara (arts. 97b e 98) ----------
        #
        # Vêm ANTES da tabela e antes da base, e a ordem importa: as duas
        # respondem pela posição, e estas duas regras não dependem só da posição.
        # Um valor guardado na tabela por um caminho sem repetição diria
        # "vantagem" numa posição que, por ESTE caminho, é empate.
        #
        # Nunca na raiz (`ply == 0`): se a partida de verdade já bateu numa
        # dessas regras, quem encerra é o árbitro, não o jogador — e a raiz tem
        # de devolver um lance, não uma sentença.
        if ply > 0 and self.usar_empates_por_historico:
            # `+ 1` porque a ocorrência atual ainda não foi contada em lugar
            # nenhum: `_no_caminho` só recebe a posição adiante, quando a
            # recursão vai de fato descer por ela.
            ja_vistas = (
                self._repeticoes_na_partida.get(chave, 0)
                + self._no_caminho.get(chave, 0)
                + 1
            )
            if (ja_vistas >= self.regulamento.repeticoes_para_empate
                    or sem_progresso >= self._meios_lances_para_empate):
                self._estatisticas.empates_por_historico += 1
                # Empate vale 0 — literalmente. E este nó **não** vai para a
                # tabela de transposição: o valor é do caminho, não da posição,
                # e guardá-lo envenenaria toda busca futura que passasse aqui
                # por outro caminho.
                return 0

            # As duas regras da FMJD (8.3 e 8.5) precisam olhar a COMPOSIÇÃO do
            # tabuleiro, e contar peças custa 32 comparações. O truque que torna
            # isso de graça: só olhar quando o relógio correspondente já passou
            # do limite. Numa abertura nenhum dos dois chega perto, e o custo por
            # nó fica em duas comparações de inteiro.
            if (self._meios_lances_da_correlacao is not None
                    and sem_progresso >= self._meios_lances_da_correlacao
                    and tres_damas_contra_uma(tabuleiro)):
                self._estatisticas.empates_por_historico += 1
                return 0

            if (self._menor_limite_de_equilibrio is not None
                    and sem_mudar_equilibrio >= self._menor_limite_de_equilibrio):
                limite = limite_de_equilibrio_parado(tabuleiro, self.regulamento)
                if limite is not None and sem_mudar_equilibrio >= limite:
                    self._estatisticas.empates_por_historico += 1
                    return 0

        # `_tt_chave[casa] == chave` é o que separa "esta posição está guardada"
        # de "outra posição ocupou esta casa"; `_tt_profundidade >= 0` separa
        # ambas de "casa nunca escrita".
        lance_da_tabela = None
        if (self.usar_tabela
                and self._tt_chave[casa] == chave
                and self._tt_profundidade[casa] >= 0):
            lance_da_tabela = self._tt_lance[casa]
            if self._tt_profundidade[casa] >= profundidade:
                self._estatisticas.acertos_na_tabela += 1
                nota = self._tt_nota[casa]
                marcador = self._tt_marcador[casa]
                if marcador == EXATO:
                    return nota
                if marcador == LIMITE_INFERIOR:
                    alfa = max(alfa, nota)
                elif marcador == LIMITE_SUPERIOR:
                    beta = min(beta, nota)
                if alfa >= beta:
                    return nota

        # --- consulta à base de finais (probing) ---------------------------
        #
        # ⚠️ Nunca na raiz (`ply == 0`). A raiz precisa **escolher um lance**, e
        # devolver a nota exata daqui faria a busca voltar sem nenhum lance
        # examinado — o motor saberia que ganhou e não saberia como. Nos filhos,
        # a resposta exata sobe pela árvore e a raiz escolhe com ela.
        if ply > 0 and self._pecas_na_base:
            exata = self._consultar_a_base(tabuleiro, ply)
            if exata is not None:
                return exata

        lances = gerar_lances(tabuleiro, self.regulamento)

        # Sem lance legal = derrota de quem tem a vez ("imobilizar ou capturar
        # todas as peças do adversário"). O `+ ply` faz o motor preferir a
        # derrota mais LONGA e a vitória mais CURTA — sem isso ele acha que dar
        # mate em 1 e em 9 é a mesma coisa, e nunca conclui nada.
        if not lances:
            return -VITORIA + ply

        # Extensão de captura (quiescência). Parar a busca com capturas na mesa
        # é o erro clássico: o motor "vê" que ganhou uma peça e não vê que ela é
        # retomada no lance seguinte. Em damas isso é barato, porque a captura é
        # obrigatória — o ramo estendido tem pouquíssimos lances.
        em_captura = lances[0].e_captura
        if profundidade <= 0:
            # `_extensao_ativa`, e não `extensao_de_captura`: o nível pode
            # desligar a quiescência só para esta busca — é o que faz a Cacau
            # parar de contar no meio da troca, como um iniciante.
            if (not self._extensao_ativa
                    or not em_captura
                    or extensoes >= MAX_EXTENSAO):
                return self._avaliar(tabuleiro)
            profundidade = 1
            extensoes += 1

        melhor = -VITORIA * 2
        melhor_lance = None

        # A posição entra no caminho só agora, quando a recursão vai de fato
        # descer por ela. A raiz fica de fora porque ela já está contada no
        # histórico da partida — contá-la duas vezes faria o art. 98 disparar com
        # uma repetição a menos.
        conta_no_caminho = ply > 0 and self.usar_empates_por_historico
        if conta_no_caminho:
            self._no_caminho[chave] = self._no_caminho.get(chave, 0) + 1

        for lance in self._ordenar(lances, lance_da_tabela):
            nota = -self._negamax(
                aplicar_lance(tabuleiro, lance),
                profundidade - 1, -beta, -alfa, ply + 1, extensoes,
                # O contador do art. 97b zera na captura e no movimento de pedra
                # — e é consultado no tabuleiro de ANTES, onde a peça ainda está
                # na origem.
                0 if zera_o_contador(tabuleiro, lance) else sem_progresso + 1,
                # O da FMJD 8.5 zera na captura e na promoção. O lance já sabe se
                # promoveu, então este não precisa consultar tabuleiro nenhum.
                0 if muda_o_equilibrio(lance) else sem_mudar_equilibrio + 1,
            )
            if nota > melhor:
                melhor, melhor_lance = nota, lance
            alfa = max(alfa, nota)
            if alfa >= beta:
                self._estatisticas.cortes += 1
                # Este lance causou um corte: vale a pena tentá-lo cedo da
                # próxima vez. O peso por profundidade² faz corte fundo valer
                # mais que corte raso, que é o que a experiência recomenda.
                chave_historico = (lance.origem, lance.destino)
                self._historico[chave_historico] = (
                    self._historico.get(chave_historico, 0) + profundidade * profundidade
                )
                break

        # Saindo deste ramo, a posição deixa de estar no caminho. Sem este
        # decremento o contador só cresceria, e a busca declararia empate por
        # repetição em ramos que nunca repetiram nada — o motor jogaria para o
        # empate a partida inteira.
        if conta_no_caminho:
            self._no_caminho[chave] -= 1

        if melhor <= alfa_original:
            marcador = LIMITE_SUPERIOR
        elif melhor >= beta:
            marcador = LIMITE_INFERIOR
        else:
            marcador = EXATO
        # **Substituição sempre**: o registro novo sobrescreve o que estava na
        # casa, seja de outra posição ou de uma busca mais funda desta mesma.
        # É a política do motor em Dart, e ela precisa ser a mesma dos dois lados
        # — trocá-la de um lado só muda quantos nós a busca gasta.
        #
        # A escrita acontece mesmo com a tabela desligada, e isso é de propósito:
        # a raiz e a variante principal são lidas daqui depois da busca. O que
        # `usar_tabela=False` desliga é a **leitura** durante a recursão, que é o
        # que alteraria o valor em relação ao minimax de profundidade fixa.
        self._tt_chave[casa] = chave
        self._tt_profundidade[casa] = profundidade
        self._tt_nota[casa] = melhor
        self._tt_marcador[casa] = marcador
        self._tt_lance[casa] = melhor_lance

        return melhor

    def _consultar_a_base(self, tabuleiro: Tabuleiro, ply: int) -> int | None:
        """A nota **exata** desta posição, se a base a cobrir. `None` se não.

        A tradução de resultado para nota tem de manter a convenção do negamax
        (nota do ponto de vista de quem tem a vez) e a preferência por vitória
        curta:

        - **vitória** → `VITORIA − ply − distância`. Quanto mais longo o caminho
          até o fim, menor a nota: entre ganhar em 4 e ganhar em 40, o motor
          escolhe ganhar em 4. Sem isso ele empurra a vitória com a barriga e
          esbarra na regra dos 20 lances (art. 97).
        - **derrota** → o simétrico, e aí a preferência se inverte sozinha:
          perder em 40 vale mais que perder em 4, que é o que faz o motor
          resistir em vez de desistir.
        - **empate** → 0, que é literalmente o que empate vale.

        ⚠️ A distância pode vir como `SEM_DISTANCIA` (−1) — em base carregada
        sem o vetor de distâncias, ou em posição de empate. Tratada como 0: a
        nota continua certa em sinal, só perde o desempate por rapidez.
        """
        if contar_pecas(tabuleiro) > self._pecas_na_base:
            return None

        resultado = self.base.consultar(tabuleiro)
        if resultado is None:
            return None                 # fatia não carregada: busque normalmente

        self._estatisticas.consultas_a_base += 1

        if resultado == EMPATE_NA_BASE:
            return 0

        distancia = self.base.distancia_de(tabuleiro)
        if distancia < 0:
            distancia = 0

        if resultado == VITORIA_NA_BASE:
            return VITORIA - ply - distancia
        return -VITORIA + ply + distancia

    def _guardar_na_raiz(
        self, tabuleiro: Tabuleiro, profundidade: int, nota: int, lance: Lance | None
    ) -> None:
        """Grava a raiz na tabela com o lance **escolhido**, não com o melhor.

        Só o caminho dos níveis fracos usa isto (`chance_de_errar > 0`): lá o
        motor escolhe de propósito o segundo melhor lance, e sem esta gravação a
        variante principal começaria por um lance que ele não vai jogar — o
        relatório da partida mentiria sobre o que o motor estava pensando.

        Não existe `_guardar` genérico: a escrita do negamax é feita direto nas
        cinco colunas, no fim do nó, porque lá a casa já foi calculada na entrada.
        """
        casa = tabuleiro.hash & self._mascara
        self._tt_chave[casa] = tabuleiro.hash
        self._tt_profundidade[casa] = profundidade
        self._tt_nota[casa] = nota
        self._tt_marcador[casa] = EXATO
        self._tt_lance[casa] = lance

    # -- interface pública ---------------------------------------------------

    def _variante_principal(self, tabuleiro: Tabuleiro, limite: int = 12) -> tuple[Lance, ...]:
        """Reconstrói, pela tabela, a linha que o motor espera que aconteça."""
        linha: list[Lance] = []
        atual = tabuleiro
        vistas: set[int] = set()
        for _ in range(limite):
            chave = atual.hash
            if chave in vistas:
                break            # a linha entrou em ciclo; parar de reconstruir
            vistas.add(chave)
            casa = chave & self._mascara
            lance = self._tt_lance[casa]
            # `_tt_chave[casa] != chave` quer dizer que outra posição ocupou esta
            # casa depois — a linha acaba aqui, e não segue por um lance alheio.
            if self._tt_chave[casa] != chave or lance is None:
                break
            linha.append(lance)
            atual = aplicar_lance(atual, lance)
        return tuple(linha)

    def _raiz_com_notas(
        self,
        tabuleiro: Tabuleiro,
        profundidade: int,
        sem_progresso: int,
        sem_equilibrio: int,
    ) -> list[tuple[int, Lance]]:
        """Todos os lances da raiz com a nota de cada um, do melhor para o pior.

        Por que isto existe, se o negamax já devolve o melhor lance
        -----------------------------------------------------------
        Porque ele devolve **só** o melhor. A alfa-beta corta assim que sabe que
        um lance não vence o campeão atual, e o que sobra dos outros é um limite
        superior, não uma nota comparável. Para escolher o *segundo* melhor é
        preciso saber quem ele é — e isso exige buscar cada lance da raiz com
        **janela cheia**, sem deixar um irmão podar o outro.

        Isso custa mais nós que a busca normal. É custo aceitável porque este
        caminho só roda quando `chance_de_errar > 0`, ou seja, nos níveis fracos,
        onde gastar orçamento e chegar menos fundo é o objetivo e não o efeito
        colateral. Tex e Sagaz continuam pelo caminho de sempre, nó por nó
        idênticos ao de antes de 2026-08-14 — o que preserva a impressão digital
        que a bancada compara entre aparelhos.
        """
        avaliados: list[tuple[int, Lance]] = []
        for lance in gerar_lances(tabuleiro, self.regulamento):
            nota = -self._negamax(
                aplicar_lance(tabuleiro, lance),
                profundidade - 1, -VITORIA * 2, VITORIA * 2, 1, 0,
                # Os dois contadores seguem a mesma regra do laço do negamax: o
                # do art. 97b é consultado no tabuleiro de ANTES (a peça ainda
                # está na origem); o da FMJD 8.5 basta perguntar ao lance.
                0 if zera_o_contador(tabuleiro, lance) else sem_progresso + 1,
                0 if muda_o_equilibrio(lance) else sem_equilibrio + 1,
            )
            avaliados.append((nota, lance))

        # `sort` é estável em Python, então lances de nota igual mantêm a ordem
        # do gerador. Isso importa: é o que faz a partida com semente fixa se
        # repetir lance a lance, e sem isso não haveria como testar nada disto.
        avaliados.sort(key=lambda par: -par[0])
        return avaliados

    def _escolher_errando(
        self, avaliados: list[tuple[int, Lance]]
    ) -> tuple[int, Lance]:
        """O lance que o nível fraco vai jogar: o melhor, ou um dos aceitáveis.

        O erro é **sorteado entre os lances que estão dentro da margem**, e não
        entre todos. É essa restrição que separa "adversário fraco" de
        "adversário quebrado": um lance que entrega uma dama, ou que entra numa
        perda forçada (nota da ordem de ±1.000.000), nunca entra no sorteio, por
        mais alta que seja a chance de errar.

        Por que sortear entre vários e não só o segundo
        -----------------------------------------------
        A primeira versão disto, de mais cedo em 2026-08-14, trocava o melhor
        lance pelo **segundo** e só. Medido, isso mudou exatamente nada: 0% de
        derrota antes, 0% depois. O motivo é que o segundo melhor de uma busca
        que enxerga a resposta do adversário costuma ser quase tão bom quanto o
        primeiro — trocar um pelo outro não produz erro nenhum que decida
        partida.

        Alcançar "perder 4 de 5 partidas para um adulto casual" (o alvo de
        produto da Cacau) exige o motor **dando peça**, e para isso o sorteio
        precisa alcançar lances de verdade piores. Quem controla quanto pior é
        `margem`, por nível.
        """
        melhor = avaliados[0]
        if len(avaliados) == 1:
            return melhor
        if self._aleatorio.random() >= self._chance_de_errar:
            return melhor

        # Os candidatos: todos os que perdem no máximo `margem` para o melhor.
        # `avaliados` já vem ordenado, então basta cortar no primeiro que não
        # cabe — e o índice 0 sempre cabe, o que garante lista não vazia.
        limite = melhor[0] - self._margem_do_erro
        aceitaveis = [par for par in avaliados if par[0] >= limite]
        if len(aceitaveis) == 1:
            return melhor
        # O melhor sai do sorteio: mantê-lo dentro faria a chance efetiva de
        # errar ser menor que a pedida, e de um jeito que varia com quantos
        # lances a posição tem — ou seja, incalibrável.
        return self._aleatorio.choice(aceitaveis[1:])

    def buscar(
        self,
        tabuleiro: Tabuleiro,
        profundidade: int = 8,
        teto_de_nos: int | None = None,
        tempo_maximo: float | None = None,
        ruido: int = 0,
        historico: HistoricoDaPartida | None = None,
        extensao_de_captura: bool | None = None,
        chance_de_errar: float = 0.0,
        margem_do_erro: int = MARGEM_DO_ERRO,
    ) -> Resultado:
        """Procura o melhor lance, aprofundando um nível de cada vez.

        **Aprofundamento iterativo:** busca à profundidade 1, depois 2, depois 3…
        Parece desperdício refazer tudo, e não é, por dois motivos: a árvore
        cresce tão rápido que o último nível domina o custo, e cada rodada deixa
        na tabela a ordenação que faz a rodada seguinte podar muito melhor. De
        quebra, é o que permite ter uma resposta pronta a qualquer instante — que
        é o que torna qualquer orçamento interrompível possível.

        Args:
            profundidade: teto de profundidade.
            teto_de_nos: orçamento em **posições visitadas** — o critério que faz
                o mesmo nível jogar igual em qualquer aparelho. Ao estourar,
                devolve-se o resultado da **última profundidade que terminou
                inteira**: uma varredura pela metade é pior que a anterior
                completa.
            tempo_maximo: orçamento em segundos. Desde 2026-07-28 é **rede de
                segurança**, não critério — ver `Nivel.tempo_maximo`.
            ruido: barulho na avaliação, para os níveis fracos.
            historico: o que a partida já acumulou — posições repetidas e o
                contador do art. 97b. Sem ele o motor busca como se a posição
                tivesse acabado de surgir do nada, e **não enxerga** que mais
                uma volta no mesmo ciclo encerra o jogo empatado. Quem joga
                partida de verdade (arena, app) deve sempre passá-lo; quem
                analisa uma posição solta pode omitir.
            extensao_de_captura: a quiescência **desta busca**. `None` (o padrão)
                usa a do construtor; `False` afrouxa o motor de verdade — ver
                `Nivel.extensao_de_captura`.
            chance_de_errar: probabilidade de jogar o segundo melhor lance. Zero
                (o padrão) mantém a busca nó por nó idêntica à de sempre; acima
                de zero liga o caminho de raiz com janela cheia, que custa mais
                nós — ver `_raiz_com_notas`.
        """
        self._estatisticas = Estatisticas()
        self._ruido = ruido
        self._extensao_ativa = (
            self.extensao_de_captura
            if extensao_de_captura is None
            else extensao_de_captura
        )
        self._chance_de_errar = chance_de_errar
        self._margem_do_erro = margem_do_erro
        self._teto_de_nos = None
        self._prazo = None if tempo_maximo is None else time.monotonic() + tempo_maximo
        comeco = time.monotonic()

        # O histórico é lido, nunca alterado — a busca imagina lances, não os
        # joga. `{}` quando ninguém passa nada: aí só as repetições que
        # acontecem dentro da própria árvore contam.
        self._repeticoes_na_partida = historico.repeticoes if historico else {}
        sem_progresso_inicial = (
            historico.meios_lances_sem_progresso if historico else 0
        )
        sem_equilibrio_inicial = (
            historico.meios_lances_sem_mudar_o_equilibrio if historico else 0
        )

        melhor = Resultado(None, 0, (), self._estatisticas)

        for nivel_de_profundidade in range(1, profundidade + 1):
            # Zerado a cada profundidade porque uma varredura interrompida pelo
            # orçamento sobe por exceção, sem passar pelos decrementos do laço —
            # e deixaria posições marcadas como "no caminho" para sempre.
            self._no_caminho = {}

            # A profundidade 1 nunca é interrompida: é ela que garante que existe
            # ALGUM lance para devolver. Um teto minúsculo faz o motor jogar mal,
            # o que é esperado; fazê-lo devolver `None` seria travar o app.
            self._teto_de_nos = None if nivel_de_profundidade == 1 else teto_de_nos

            try:
                if chance_de_errar > 0:
                    # Caminho dos níveis fracos: avalia cada lance da raiz com
                    # janela cheia para poder escolher o segundo melhor.
                    avaliados = self._raiz_com_notas(
                        tabuleiro, nivel_de_profundidade,
                        sem_progresso_inicial, sem_equilibrio_inicial,
                    )
                    nota, lance = self._escolher_errando(avaliados)
                    # A raiz é gravada na tabela com o lance ESCOLHIDO — não com
                    # o melhor. Sem isto a variante principal começaria por um
                    # lance que o motor não vai jogar, e o relatório da partida
                    # mentiria sobre o que ele estava pensando.
                    self._guardar_na_raiz(
                        tabuleiro, nivel_de_profundidade, nota, lance
                    )
                else:
                    nota = self._negamax(
                        tabuleiro, nivel_de_profundidade, -VITORIA * 2, VITORIA * 2,
                        0, 0, sem_progresso_inicial, sem_equilibrio_inicial,
                    )
                    # Sem conferir a chave da casa, como o motor em Dart: a raiz
                    # é a **última** posição gravada por esta varredura (o nó do
                    # topo grava ao voltar), então a casa é dela.
                    lance = self._tt_lance[tabuleiro.hash & self._mascara]
            except _NosEsgotados:
                self._estatisticas.motivo_da_parada = "nos"
                break
            except _TempoEsgotado:
                self._estatisticas.motivo_da_parada = "tempo"
                break

            melhor = Resultado(
                lance, nota, self._variante_principal(tabuleiro), self._estatisticas
            )
            self._estatisticas.profundidade_atingida = nivel_de_profundidade

            # Achou vitória ou derrota forçada: aprofundar não muda mais nada.
            if abs(nota) > VITORIA - 1000:
                self._estatisticas.motivo_da_parada = "decidido"
                break

        self._estatisticas.tempo_segundos = time.monotonic() - comeco
        return melhor

    def jogar(
        self,
        tabuleiro: Tabuleiro,
        nivel: Nivel,
        historico: HistoricoDaPartida | None = None,
    ) -> Resultado:
        """Escolhe o lance com o orçamento de um nível de dificuldade.

        ⚠️ **O nível manda em tudo o que ele define.** Um `Buscador` construído
        com `extensao_de_captura=False` volta a tê-la ligada aqui se o nível a
        pede — porque "jogar como a Pita" tem de significar a mesma coisa em
        qualquer buscador, senão o nível deixa de ser comparável entre arena,
        laboratório e app. Quem quer as chaves do construtor valendo chama
        `buscar()` diretamente.
        """
        return self.buscar(
            tabuleiro,
            profundidade=nivel.profundidade,
            teto_de_nos=nivel.teto_de_nos,
            tempo_maximo=nivel.tempo_maximo,
            ruido=nivel.ruido,
            historico=historico,
            extensao_de_captura=nivel.extensao_de_captura,
            chance_de_errar=nivel.chance_de_errar,
            margem_do_erro=nivel.margem_do_erro,
        )


# ---------------------------------------------------------------------------
# Minimax puro — existe só para provar que a poda não mente
# ---------------------------------------------------------------------------


def minimax_sem_poda(
    tabuleiro: Tabuleiro,
    profundidade: int,
    regulamento: Regulamento = BRASILEIRAS,
    pesos: PesosAvaliacao = PESOS_PADRAO,
    ply: int = 0,
) -> int:
    """A mesma nota que a alfa-beta calcula, **sem nenhuma poda**.

    Lento e inútil para jogar — e é exatamente esse o ponto. Ele é a testemunha
    independente: a alfa-beta promete devolver o mesmo valor visitando muito
    menos, e essa promessa é o que sustenta confiar na poda para um nível "quase
    perfeito". Aqui a promessa vira teste.

    Note que ele **não** faz extensão de captura, e por isso o teste compara
    contra uma busca também sem extensão. Comparar coisas diferentes e ver que
    diferem não prova nada.

    ⚠️ **Ele avalia sempre pela avaliação manual**, e não aceita tabelas
    treinadas. Não é limitação a corrigir: a testemunha precisa ser a mais simples
    possível. Quem comparar contra um `Buscador` com `pesos_treinados` vai ver
    divergência — e a divergência estará no teste, não na poda.
    """
    lances = gerar_lances(tabuleiro, regulamento)
    if not lances:
        return -VITORIA + ply
    if profundidade <= 0:
        return avaliar(tabuleiro, pesos)

    return max(
        -minimax_sem_poda(
            aplicar_lance(tabuleiro, lance), profundidade - 1, regulamento, pesos, ply + 1
        )
        for lance in lances
    )

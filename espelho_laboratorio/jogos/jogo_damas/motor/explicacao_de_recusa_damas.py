"""Por que **este** lance não é permitido — a resposta que o app mostra ao jogador.

O problema que este módulo resolve
----------------------------------
O app já sabe recusar um lance ilegal: basta perguntar ao motor a lista de lances
legais e ver se o tentado está nela. O que ele **não** sabe é *por quê* — e em
damas o porquê é quase sempre uma regra de **obrigatoriedade**, justamente a
categoria que o jogador casual não conhece.

Sem isto, o app teria duas saídas ruins:

1. dizer só *"movimento inválido"*, que não ensina nada e parece bug;
2. **reimplementar as regras em Dart** para deduzir o motivo — e duas
   implementações da mesma regra divergem. É a lição que este projeto já pagou
   duas vezes (a base de finais em 26/07, o limite de empate anglo em 28/07).

Aqui a dedução é feita **com o próprio gerador**, comparando as listas que ele
produz. Nenhuma regra é reescrita: o que se faz é observar *qual filtro* comeu o
lance tentado.

Como a dedução funciona
-----------------------
O gerador produz duas listas, e a diferença entre elas conta a história:

- `_gerar_capturas` — **todas** as sequências de captura completas, sem filtro;
- `gerar_lances` — o que sobra depois da Lei da Maioria e da Lei da Qualidade.

Daí saem os casos:

| onde o lance tentado está | o que aconteceu |
|---|---|
| em `gerar_lances` | é legal — nada a explicar |
| não é captura, mas há capturas | captura é obrigatória |
| em `_gerar_capturas`, com menos peças que o máximo | Lei da Maioria |
| em `_gerar_capturas`, no máximo, mas com menos damas | Lei da Qualidade |
| é **prefixo** de uma sequência completa | parou no meio da captura |
| só existe se a peça comida sair na hora | o art. 15 fechou o caminho |
| em lugar nenhum | o lance não existe (geometria, peça própria, recuo…) |

O penúltimo caso merece uma palavra, porque é o único que não sai de comparar
duas listas *filtradas*: ele compara o gerador **consigo mesmo**, uma vez com o
art. 15 ligado e outra com ele desligado (`condenadas_bloqueiam=False`, em
`regras_damas`). O lance que só aparece na segunda geração é, por construção, um
lance que a peça já comida barrou — e é isso que se diz ao jogador.

O `identificador` é o que o app usa
-----------------------------------
A `mensagem` sai daqui em português e serve de **referência**, não de string de
produção: o app tem três idiomas e a tradução é dele. O que o app deve consumir é
o `identificador` — estável, em `snake_case` — e as casas a destacar.
"""
from __future__ import annotations

from dataclasses import dataclass

from jogos.jogo_damas.motor.regras_damas import (
    BRASILEIRAS,
    Lance,
    Regulamento,
    _damas_capturadas,
    _gerar_capturas,
    gerar_lances,
)
from jogos.jogo_damas.motor.tabuleiro_damas import Direcao, Tabuleiro, raio


@dataclass(frozen=True)
class RecusaDeLance:
    """Por que o lance foi recusado, e o que o app deve mostrar.

    Attributes:
        identificador: a regra que recusou, em `snake_case`. **É isto que o app
            consome** — a chave para escolher a mensagem no idioma do jogador.
        mensagem: o texto em português, já com os números concretos. Serve de
            referência para a tradução e para depurar; não é string de produção.
        casas_a_destacar: as casas que o tabuleiro deve acender. O que elas
            significam muda com a regra — nas capturas obrigatórias são as peças
            que **podem** comer; na Lei da Maioria, o caminho da sequência que
            ele deveria ter jogado.
        lances_obrigatorios: os lances que o jogador deveria ter escolhido.
            Vazio quando a recusa não aponta para uma alternativa específica (um
            lance geometricamente impossível, por exemplo).
    """

    identificador: str
    mensagem: str
    casas_a_destacar: tuple[int, ...] = ()
    lances_obrigatorios: tuple[Lance, ...] = ()


def _e_prefixo(tentado: Lance, completo: Lance) -> bool:
    """`tentado` é o começo de `completo`, parado no meio do caminho?

    Compara caminho **e** capturadas: uma captura múltipla é identificada pelas
    duas coisas, e conferir só o caminho aceitaria uma sequência que passa pelas
    mesmas casas tomando peças diferentes.
    """
    if len(tentado.caminho) >= len(completo.caminho):
        return False
    n = len(tentado.caminho)
    return (
        tentado.caminho == completo.caminho[:n]
        and tentado.capturadas == completo.capturadas[:n - 1]
    )


def _casas_dos_lances(lances) -> tuple[int, ...]:
    """Todas as casas envolvidas nestes lances — caminho e peças tomadas.

    Sem repetição e em ordem crescente, para o destaque do app ser estável: uma
    lista que muda de ordem a cada chamada faria a animação piscar.
    """
    casas: set[int] = set()
    for lance in lances:
        casas.update(lance.caminho)
        casas.update(lance.capturadas)
    return tuple(sorted(casas))


def _casas_entre(origem: int, destino: int) -> tuple[int, ...]:
    """As casas que ficam **entre** duas casas da mesma diagonal, sem elas.

    Geometria pura, não regra: é a mesma pergunta que a dama faz ao deslizar.
    Devolve tupla vazia quando as duas casas não estão na mesma diagonal — não é
    erro, é a resposta certa para um par que não se enxerga.
    """
    for direcao in Direcao:
        diagonal = raio(origem, direcao)
        if destino in diagonal:
            return tuple(diagonal[: diagonal.index(destino)])
    return ()


def _condenadas_que_fecham(lance: Lance) -> tuple[int, ...]:
    """As peças já comidas que **este** lance atravessa ou pisa depois de comê-las.

    É o que o art. 15 barra: a peça capturada fica no tabuleiro até o lance
    terminar, então uma casa por onde ela está é casa fechada. Percorre-se o
    lance perna a perna; em cada uma, olha-se se alguma peça comida **antes**
    daquela perna cai no trecho percorrido (ou na casa de pouso).

    ``capturadas[:i]`` é o que já saiu de circulação quando a perna `i` começa —
    a vítima da própria perna é `capturadas[i]`, e essa, claro, não conta.
    """
    culpadas: set[int] = set()
    for i in range(len(lance.caminho) - 1):
        anteriores = set(lance.capturadas[:i])
        if not anteriores:
            continue
        de, para = lance.caminho[i], lance.caminho[i + 1]
        culpadas.update(anteriores.intersection(_casas_entre(de, para) + (para,)))
    return tuple(sorted(culpadas))


def _bloqueio_por_condenada(
    tabuleiro: Tabuleiro,
    regulamento: Regulamento,
    tentados: tuple[Lance, ...],
) -> RecusaDeLance | None:
    """A recusa do **art. 15**, se for o caso — ou `None`.

    Gera as capturas duas vezes: a normal (com o Tema Turco, que é a regra) e
    uma **fantasma**, em que as peças já tomadas contam como casa vazia. Um lance
    que existe só na segunda foi barrado pela peça condenada, e por nada mais —
    a diferença entre as duas gerações é exatamente esta.

    Args:
        tentados: os lances candidatos. É tupla porque `explicar_gesto` chega
            aqui com vários (um gesto de duas casas pode corresponder a mais de
            uma sequência), e `explicar_recusa`, com um só.

    As casas a destacar são as condenadas que **de fato** fecham o caminho — ver
    `_condenadas_que_fecham`. Acender a peça culpada é o que ensina: ela está
    ali, na tela, com a marca de condenada, e é a resposta visual à pergunta
    "por que não dá para passar?". Se por algum caminho nenhuma for identificada,
    acendem-se todas as comidas pelo lance fantasma: menos preciso, mas ainda
    verdadeiro — todas elas estão no tabuleiro naquele instante.
    """
    fantasmas = _gerar_capturas(tabuleiro, regulamento, False)
    if not fantasmas:
        return None

    reais = _gerar_capturas(tabuleiro, regulamento)
    candidatos = tuple(
        lance for lance in fantasmas
        if lance not in reais and any(
            tentado == lance or _e_prefixo(tentado, lance)
            for tentado in tentados
        )
    )
    if not candidatos:
        return None

    condenadas = tuple(sorted({
        casa for lance in candidatos for casa in _condenadas_que_fecham(lance)
    }))
    if not condenadas:
        condenadas = tuple(sorted({
            casa for lance in candidatos for casa in lance.capturadas
        }))
    return RecusaDeLance(
        identificador="bloqueado_por_condenada",
        mensagem=(
            "A peça que você já comeu continua no tabuleiro até o lance "
            "terminar, e ela fecha esse caminho (art. 15)."
        ),
        casas_a_destacar=condenadas,
        lances_obrigatorios=(),
    )


def explicar_recusa(
    tabuleiro: Tabuleiro,
    tentado: Lance,
    regulamento: Regulamento = BRASILEIRAS,
) -> RecusaDeLance | None:
    """Por que este lance não é permitido. `None` quando ele **é** legal.

    Devolver `None` para lance legal é de propósito: o app chama esta função só
    depois de o lance falhar na lista, e um `None` inesperado aqui é sinal de que
    as duas verificações discordaram — vale tratar como defeito, não ignorar.

    Args:
        tabuleiro: a posição **antes** do lance.
        tentado: o que o jogador tentou fazer.
        regulamento: qual modalidade está em jogo. As respostas mudam com ela —
            a Lei da Maioria não existe nas inglesas, e a da Qualidade só existe
            nas portuguesas.
    """
    legais = gerar_lances(tabuleiro, regulamento)
    if tentado in legais:
        return None

    todas_as_capturas = _gerar_capturas(tabuleiro, regulamento)

    # --- 1. captura obrigatória ---------------------------------------------
    #
    # Vem primeiro porque é a regra que o jogador mais esbarra, e a única em que
    # a peça obrigada pode estar do outro lado do tabuleiro — longe de onde ele
    # estava olhando.
    if not tentado.e_captura and todas_as_capturas:
        origens = tuple(sorted({lance.origem for lance in todas_as_capturas}))
        quantas = len(origens)
        return RecusaDeLance(
            identificador="captura_obrigatoria",
            mensagem=(
                "Você é obrigado a comer. "
                + ("Esta peça pode comer:" if quantas == 1
                   else f"Estas {quantas} peças podem comer:")
            ),
            casas_a_destacar=origens,
            lances_obrigatorios=tuple(legais),
        )

    # --- 2. a captura existe, mas foi filtrada ------------------------------
    if tentado in todas_as_capturas:
        maximo = max(lance.quantas_capturas for lance in todas_as_capturas)

        if tentado.quantas_capturas < maximo:
            maiores = tuple(
                lance for lance in todas_as_capturas
                if lance.quantas_capturas == maximo
            )
            return RecusaDeLance(
                identificador="lei_da_maioria",
                mensagem=(
                    f"Essa captura come {tentado.quantas_capturas} "
                    f"peça{'s' if tentado.quantas_capturas != 1 else ''}, e há "
                    f"uma que come {maximo}. Você é obrigado a comer o maior "
                    f"número."
                ),
                casas_a_destacar=_casas_dos_lances(maiores),
                lances_obrigatorios=maiores,
            )

        # Mesmo número de peças e ainda assim recusado: só a Lei da Qualidade
        # explica, e ela só existe nas portuguesas/espanholas.
        melhor_qualidade = max(
            _damas_capturadas(tabuleiro, lance) for lance in legais
        )
        return RecusaDeLance(
            identificador="lei_da_qualidade",
            mensagem=(
                f"As duas capturas comem {maximo} "
                f"peça{'s' if maximo != 1 else ''}, mas uma delas come a dama. "
                f"Você é obrigado a comer a peça mais valiosa."
            ),
            casas_a_destacar=_casas_dos_lances(legais),
            lances_obrigatorios=tuple(legais),
        )

    # --- 3. parou no meio de uma captura múltipla ---------------------------
    continuacoes = tuple(
        lance for lance in todas_as_capturas if _e_prefixo(tentado, lance)
    )
    if continuacoes:
        return RecusaDeLance(
            identificador="sequencia_incompleta",
            mensagem="A captura ainda não terminou — dá para comer mais.",
            casas_a_destacar=_casas_dos_lances(continuacoes),
            lances_obrigatorios=continuacoes,
        )

    # --- 3b. o art. 15 fechou o caminho -------------------------------------
    #
    # A peça capturada **não sai do tabuleiro no momento do salto**: ela fica
    # onde está, condenada, e continua bloqueando a passagem até o lance inteiro
    # terminar. Quem está aprendendo conta as peças que já comeu como se elas
    # tivessem sumido, e então tenta um caminho que passa por cima de uma delas.
    #
    # A pergunta que se faz aqui é exatamente essa: *este lance existiria se a
    # peça comida saísse na hora?* Quem responde é o próprio gerador, com o
    # art. 15 desligado — nenhuma regra é reescrita.
    recusa_do_artigo_15 = _bloqueio_por_condenada(
        tabuleiro, regulamento, (tentado,)
    )
    if recusa_do_artigo_15 is not None:
        return recusa_do_artigo_15

    # --- 4. o lance simplesmente não existe ---------------------------------
    #
    # Geometria errada, casa ocupada, salto sobre peça própria, pedra tentando
    # comer de recuo onde a modalidade não deixa. Aqui não há uma regra única a
    # citar — o que ajuda o jogador é ver o que aquela peça PODE fazer.
    da_mesma_peca = tuple(
        lance for lance in legais if lance.origem == tentado.origem
    )
    if da_mesma_peca:
        return RecusaDeLance(
            identificador="lance_inexistente",
            mensagem="Esta peça não pode ir para aí. Ela pode ir para:",
            casas_a_destacar=tuple(sorted({l.destino for l in da_mesma_peca})),
            lances_obrigatorios=da_mesma_peca,
        )

    return RecusaDeLance(
        identificador="peca_sem_lance",
        mensagem="Esta peça não tem nenhum movimento agora.",
        casas_a_destacar=(),
        lances_obrigatorios=(),
    )


def explicar_gesto(
    tabuleiro: Tabuleiro,
    origem: int,
    destino: int,
    regulamento: Regulamento = BRASILEIRAS,
) -> RecusaDeLance | None:
    """A mesma explicação, a partir do que o **app** sabe: duas casas.

    O problema
    ----------
    `explicar_recusa` recebe um `Lance` — caminho inteiro e peças tomadas. A tela
    não tem isso: o jogador toca numa peça e toca numa casa, e pronto. Montar o
    caminho no app seria escrever regra de damas fora do motor, que é justamente
    o que este módulo existe para evitar.

    A saída
    -------
    Todo lance candidato sai do **gerador**. Procura-se, entre o que ele produziu,
    o que casa com o gesto — nesta ordem:

    1. um lance **legal** com esse par de casas → não há o que explicar;
    2. uma **captura completa** que termina nessa casa → é uma captura que algum
       filtro cortou (Lei da Maioria ou da Qualidade);
    3. um **prefixo** de captura múltipla que passa por essa casa → o jogador
       parou no meio. É o caso da casa 10 que o dono encontrou no iPhone em
       17/08: a dama de 19 come duas peças e pousa em 17, e a 10 é só passagem;
    4. nada casa → o gesto vira um lance simples fictício, e a explicação cai no
       ramo de captura obrigatória ou de lance inexistente.

    ``origem == destino`` é caso legítimo, e é como a tela pergunta *"por que esta
    peça não anda?"* quando alguém toca numa peça travada: nenhum lance começa e
    termina na mesma casa, então o gesto cai direto no passo 4.
    """
    legais = gerar_lances(tabuleiro, regulamento)
    if any(l.origem == origem and l.destino == destino for l in legais):
        return None

    todas_as_capturas = _gerar_capturas(tabuleiro, regulamento)

    # 2. Captura completa com esse par de casas. Havendo mais de uma (possível
    #    com dama, por caminhos diferentes), fica a que come mais: é a que o
    #    jogador teria escolhido, e a que produz a explicação mais útil.
    completas = [
        lance for lance in todas_as_capturas
        if lance.origem == origem and lance.destino == destino
    ]
    if completas:
        return explicar_recusa(
            tabuleiro,
            max(completas, key=lambda l: l.quantas_capturas),
            regulamento,
        )

    # 3. Prefixo: a casa é uma parada INTERMEDIÁRIA de alguma captura múltipla.
    #    O `range` exclui a primeira e a última posição do caminho de propósito —
    #    a primeira é a origem e a última já foi coberta pelo passo 2.
    for lance in todas_as_capturas:
        for k in range(1, len(lance.caminho) - 1):
            if lance.caminho[k] == destino:
                return explicar_recusa(
                    tabuleiro,
                    Lance(lance.caminho[: k + 1], lance.capturadas[:k]),
                    regulamento,
                )

    # 3b. O art. 15: o gesto corresponde a uma captura que só existiria se a
    #     peça já comida tivesse saído do tabuleiro na hora do salto.
    #
    #     Aqui não dá para montar um `Lance` e perguntar — o app tem duas casas.
    #     Então os candidatos saem da geração fantasma: todo lance dela que
    #     comece na origem e **passe ou termine** no destino é uma continuação
    #     que o jogador poderia estar tentando.
    fantasmas = _gerar_capturas(tabuleiro, regulamento, False)
    candidatos = tuple(
        lance for lance in fantasmas
        if lance.origem == origem and destino in lance.caminho[1:]
    )
    if candidatos:
        recusa = _bloqueio_por_condenada(tabuleiro, regulamento, candidatos)
        if recusa is not None:
            return recusa

    # 4. O gesto não corresponde a lance nenhum do gerador.
    return explicar_recusa(tabuleiro, Lance((origem, destino)), regulamento)


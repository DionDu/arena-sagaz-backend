"""Tabuleiro de damas 8x8: a geometria das 32 casas, o estado e o formato de texto.

Este é o alicerce do motor de damas. Ele **não** sabe nada sobre regras: não sabe
mover peça, não sabe capturar, não sabe quem ganhou. Ele sabe apenas *onde as
coisas estão*. As regras vêm no módulo seguinte (`regras_damas.py`), e a
separação é proposital — a geometria é idêntica em todas as variantes de damas
8x8, enquanto as regras mudam de uma para outra.

Os três conceitos que este arquivo estabelece
---------------------------------------------

**1. Só metade do tabuleiro existe.** Um tabuleiro de damas tem 64 casas, mas as
peças andam na diagonal e por isso nunca saem das casas escuras. São 32 casas
jogáveis, e as 32 claras não guardam nada, nunca. Guardar 64 posições seria
desperdiçar metade da memória e da velocidade — então guardamos 32.

**2. Cada casa jogável tem um número, de 1 a 32.** Essa numeração não foi
inventada aqui: é a que o mundo inteiro usa em damas, contando as casas escuras
da esquerda para a direita, de cima para baixo. Adotá-la significa que os nossos
textos, testes e exportações falam a mesma língua que qualquer ferramenta de
terceiros. Veja `docs/imagens/01_numeracao_casas.png`.

**3. Uma posição vira texto no formato FEN de damas.** Também padrão de mercado:
``W:W21,22,K23:B1,2,K5`` quer dizer "brancas jogam; brancas têm pedras em 21 e
22 e uma dama em 23; pretas têm pedras em 1 e 2 e uma dama em 5". Isso permite
colar uma posição nossa no lidraughts para conferir, escrever teste com posição
montada à mão sem desenhar matriz, e exportar para programas de terceiros.

Convenção de lados
------------------
As **brancas ficam embaixo** (casas 21 a 32) e sobem o tabuleiro; as **pretas
ficam em cima** (casas 1 a 12) e descem. Quem joga primeiro **muda conforme a
variante** — nas brasileiras começam as brancas, nas anglo-americanas começam as
pretas — por isso a vez é um dado da posição, e não uma constante.
"""
from __future__ import annotations

from enum import IntEnum

import numpy as np

from jogos.jogo_damas.motor.zobrist_damas import (
    MASCARA_64,
    ZOBRIST_PECA,
    ZOBRIST_VEZ_DAS_PRETAS,
)

# ---------------------------------------------------------------------------
# Geometria — os números que descrevem o tabuleiro
# ---------------------------------------------------------------------------

LADO = 8
"""Quantas casas tem o lado do tabuleiro. 8 aqui; 10 nas damas internacionais."""

CASAS_POR_FILEIRA = LADO // 2
"""Casas JOGÁVEIS por fileira: 4. Numa fileira de 8 casas, metade é escura."""

N_CASAS = LADO * LADO // 2
"""Total de casas jogáveis: 32. É o tamanho do vetor que guarda a posição."""

CASA_CLARA = -1
"""Marcador usado só ao converter para matriz 8x8, para desenhar.

Nunca aparece no estado do jogo — é um sinal de "aqui não se joga", que só existe
porque uma figura precisa desenhar as casas claras e o vetor de 32 não as tem.
"""


class Peca(IntEnum):
    """O que pode ocupar uma casa jogável.

    ``IntEnum`` (e não ``Enum``) porque estes valores são guardados como inteiros
    pequenos no vetor da posição e comparados milhões de vezes por segundo na
    busca. Sendo ``IntEnum``, ``Peca.PEDRA_BRANCA == 1`` é verdadeiro e não há
    conversão nenhuma em tempo de execução — ganha-se a legibilidade do nome sem
    pagar por ela.

    Os valores 0 a 4 são os mesmos usados no §5.2 de
    ``docs/como_funciona_a_ia_de_damas.md``, onde se explica como uma janela do
    tabuleiro vira um número. Manter a mesma tabela nos dois lugares evita que o
    documento e o código digam coisas diferentes.
    """

    VAZIA = 0
    PEDRA_BRANCA = 1
    DAMA_BRANCA = 2
    PEDRA_PRETA = 3
    DAMA_PRETA = 4


class Cor(IntEnum):
    """De quem é a vez, e de quem é uma peça.

    Existe como tipo próprio para não cair na armadilha do FEN: lá, ``W`` é
    *white* (brancas) e ``B`` é *black* (pretas). Em português "B" puxa para
    "brancas" — e um código que misturasse as duas convenções trocaria os lados
    em silêncio, que é o pior tipo de bug. Aqui a conversão acontece em um lugar
    só (`_LETRA_FEN_POR_COR`), com esta observação ao lado.
    """

    BRANCAS = 0
    PRETAS = 1


# Peças de cada cor. Serve para perguntar "esta casa é minha?" sem espalhar
# comparações mágicas (`p == 1 or p == 2`) por todo o motor.
PECAS_POR_COR: dict[Cor, tuple[Peca, ...]] = {
    Cor.BRANCAS: (Peca.PEDRA_BRANCA, Peca.DAMA_BRANCA),
    Cor.PRETAS: (Peca.PEDRA_PRETA, Peca.DAMA_PRETA),
}

_COR_POR_PECA: dict[Peca, Cor] = {
    Peca.PEDRA_BRANCA: Cor.BRANCAS,
    Peca.DAMA_BRANCA: Cor.BRANCAS,
    Peca.PEDRA_PRETA: Cor.PRETAS,
    Peca.DAMA_PRETA: Cor.PRETAS,
}

_LETRA_FEN_POR_COR = {Cor.BRANCAS: "W", Cor.PRETAS: "B"}
_COR_POR_LETRA_FEN = {"W": Cor.BRANCAS, "B": Cor.PRETAS}


# ---------------------------------------------------------------------------
# Conversões entre "número da casa" e "linha/coluna"
# ---------------------------------------------------------------------------
#
# A numeração 1..32 é ótima para escrever e falar ("a dama está na 23"), mas
# inútil para desenhar ou para calcular vizinhança na diagonal. Para isso é
# preciso saber a linha e a coluna. Estas duas funções fazem a ponte, e são o
# único lugar do projeto onde essa aritmética aparece.
#
#   linha  0 = fileira do topo (onde as PRETAS começam)
#   linha  7 = fileira de baixo (onde as BRANCAS começam)
#   coluna 0 = extrema esquerda
#
# Nas linhas PARES as casas escuras estão nas colunas ímpares (1,3,5,7);
# nas linhas ÍMPARES, nas colunas pares (0,2,4,6). É o xadrezado.


def e_casa_jogavel(linha: int, coluna: int) -> bool:
    """Diz se a casa (linha, coluna) é escura — ou seja, se alguma peça pode pisar nela.

    A conta é a mesma que dá a cor de uma casa de xadrez: soma linha e coluna e
    olha se é par ou ímpar. Escolhemos ``ímpar = escura`` para que a casa do
    canto inferior esquerdo seja jogável, que é como um tabuleiro de damas é
    montado de verdade (o canto inferior *direito* fica claro).
    """
    return (linha + coluna) % 2 == 1


def numero_da_casa(linha: int, coluna: int) -> int | None:
    """Converte (linha, coluna) no número da casa, de 1 a 32.

    Devolve ``None`` se a casa for clara — assim quem chama é obrigado a tratar o
    caso, em vez de receber um número errado silenciosamente.

    A fórmula: cada linha contribui com 4 casas jogáveis, então a linha ``l``
    começa na casa ``l * 4 + 1``. Dentro da linha, a posição da casa é
    ``coluna // 2`` — a divisão inteira por 2 funciona porque as casas escuras
    estão sempre alternadas, de duas em duas colunas.
    """
    if not (0 <= linha < LADO and 0 <= coluna < LADO):
        return None
    if not e_casa_jogavel(linha, coluna):
        return None
    return linha * CASAS_POR_FILEIRA + coluna // 2 + 1


def linha_coluna(casa: int) -> tuple[int, int]:
    """Converte o número da casa (1 a 32) no par (linha, coluna).

    É a operação inversa de `numero_da_casa`. O ``-1`` no começo existe porque as
    casas são numeradas a partir de 1 (convenção humana) mas a aritmética é mais
    simples a partir de 0.

    O deslocamento dentro da linha depende da paridade: numa linha par a primeira
    casa escura está na coluna 1, numa linha ímpar está na coluna 0.
    """
    if not (1 <= casa <= N_CASAS):
        raise ValueError(f"casa fora do tabuleiro: {casa} (esperado 1 a {N_CASAS})")
    indice = casa - 1
    linha = indice // CASAS_POR_FILEIRA
    posicao_na_linha = indice % CASAS_POR_FILEIRA
    deslocamento = 1 if linha % 2 == 0 else 0
    return linha, posicao_na_linha * 2 + deslocamento


def cor_da_peca(peca: Peca) -> Cor | None:
    """De que cor é esta peça. ``None`` para casa vazia."""
    return _COR_POR_PECA.get(Peca(peca))


# ---------------------------------------------------------------------------
# Diagonais — a geometria de que a geração de lances vive
# ---------------------------------------------------------------------------
#
# Em damas **tudo** anda na diagonal: andar, capturar, coroar. Então o gerador de
# lances não pergunta "quais casas existem?", pergunta "o que há nesta diagonal, a
# partir daqui?". Estas tabelas respondem isso de uma vez, calculadas na carga do
# módulo — em vez de refazer a mesma aritmética milhões de vezes por segundo
# durante a busca.
#
# Um fato que faz tudo funcionar: **vizinho diagonal de casa escura é sempre casa
# escura.** Andando (±1, ±1), a soma linha+coluna muda de 0 ou de 2 — a paridade
# se mantém. Por isso nenhuma destas funções precisa checar cor de casa.


class Direcao(IntEnum):
    """As quatro diagonais, vistas de uma casa.

    "Cima" é a fileira 0, que é onde as **pretas começam** — logo, é para onde as
    **brancas avançam**. Escrever isso aqui, uma vez, evita a confusão que
    aparece toda vez que alguém tenta lembrar quem sobe e quem desce.
    """

    CIMA_ESQUERDA = 0
    CIMA_DIREITA = 1
    BAIXO_ESQUERDA = 2
    BAIXO_DIREITA = 3


# Deslocamento (linha, coluna) de cada direção.
_PASSO: dict[Direcao, tuple[int, int]] = {
    Direcao.CIMA_ESQUERDA: (-1, -1),
    Direcao.CIMA_DIREITA: (-1, +1),
    Direcao.BAIXO_ESQUERDA: (+1, -1),
    Direcao.BAIXO_DIREITA: (+1, +1),
}

# Para onde cada cor AVANÇA. Importa só para a pedra, que anda só para frente —
# a dama vai para os quatro lados, e a captura da pedra também (RESUMO 11).
DIRECOES_DE_AVANCO: dict[Cor, tuple[Direcao, Direcao]] = {
    Cor.BRANCAS: (Direcao.CIMA_ESQUERDA, Direcao.CIMA_DIREITA),
    Cor.PRETAS: (Direcao.BAIXO_ESQUERDA, Direcao.BAIXO_DIREITA),
}

# Fileira em que cada cor coroa: a última do lado do adversário.
CASAS_DE_COROACAO: dict[Cor, frozenset[int]] = {
    Cor.BRANCAS: frozenset(range(1, CASAS_POR_FILEIRA + 1)),                  # 1..4
    Cor.PRETAS: frozenset(range(N_CASAS - CASAS_POR_FILEIRA + 1, N_CASAS + 1)),  # 29..32
}


def _construir_raios() -> dict[int, dict[Direcao, tuple[int, ...]]]:
    """Para cada casa e direção, a lista ordenada de casas até a borda.

    Chamado uma vez, na carga do módulo. O resultado é lido, nunca recalculado.
    """
    raios: dict[int, dict[Direcao, tuple[int, ...]]] = {}
    for casa in range(1, N_CASAS + 1):
        linha, coluna = linha_coluna(casa)
        por_direcao: dict[Direcao, tuple[int, ...]] = {}
        for direcao in Direcao:
            passo_linha, passo_coluna = _PASSO[direcao]
            caminho: list[int] = []
            l, c = linha + passo_linha, coluna + passo_coluna
            while 0 <= l < LADO and 0 <= c < LADO:
                vizinha = numero_da_casa(l, c)
                # Nunca é None: vizinho diagonal de casa escura é casa escura.
                assert vizinha is not None
                caminho.append(vizinha)
                l, c = l + passo_linha, c + passo_coluna
            por_direcao[direcao] = tuple(caminho)
        raios[casa] = por_direcao
    return raios


_RAIOS = _construir_raios()

GRANDE_DIAGONAL: frozenset[int] = frozenset({4, 8, 11, 15, 18, 22, 25, 29})
"""A grande diagonal escura — as 8 casas do canto 4 ao canto 29.

As Regras Oficiais mandam que ela fique **à esquerda de cada damista**, e a nossa
orientação obedece. Ela não é curiosidade: o **art. 100** declara empate o final
de três damas (ou 2 damas + 1 pedra, ou 1 dama + 2 pedras) contra uma dama
**localizada nesta diagonal**. Sem este conjunto, a base de finais daria "vitória"
onde a regra diz empate — ver §6.4 de `docs/proposta_abordagem_damas.md`.
"""

RIO: frozenset[int] = GRANDE_DIAGONAL
"""O **«Rio»** das damas portuguesas (FPD 2.3) — e é a MESMA diagonal de cima.

Por que ganha nome próprio
--------------------------
O regulamento português batiza a grande diagonal de "Rio" e constrói uma regra
inteira em cima dela: a **«Forçada»** (FPD 3.8.a), em que três damas que ocupam o
Rio têm 12 lances para liquidar a dama adversária. Quem lê aquele regulamento
procura "Rio"; quem lê o brasileiro procura "grande diagonal". O apelido existe
para que a busca por qualquer um dos dois termos chegue aqui — e o `=` acima
declara, em código, que são a mesma coisa.

⚠️ Como se descobriu que são a mesma, e por que não era óbvio
--------------------------------------------------------------
A definição do Rio **não está no texto** do regulamento português: está numa
figura da página 7 (a legenda diz *"1. Rio"*, e as outras três linhas do desenho
são os circuitos menor, médio e maior). Nenhuma extração de texto a traria.
Lendo o desenho, o Rio liga o canto **superior esquerdo** ao **inferior direito**
— que na numeração daquele documento são as casas 32 e 1, passando por
32-28-23-19-14-10-5-1.

Traduzir isso para cá exige cuidado, porque os dois tabuleiros são **espelhos**
um do outro: o art. 1.2 português manda a diagonal longa começar **à direita** de
cada jogador, e o brasileiro manda **à esquerda**. O xadrezado, portanto, cai em
colunas trocadas — na fileira de cima, as casas jogáveis do documento estão nas
colunas pares e as nossas nas ímpares.

A conversão que preserva a **geometria do jogo** (casas vizinhas continuam
vizinhas) é o espelho horizontal, e ela leva o Rio deles exatamente sobre a nossa
grande diagonal: 32→4, 28→8, 23→11, 19→15, 14→18, 10→22, 5→25, 1→29.

Ver a figura `docs/imagens/60_o_rio_e_a_forcada.png`, que desenha os dois
tabuleiros lado a lado com a conversão marcada casa a casa.
"""


def raio(casa: int, direcao: Direcao) -> tuple[int, ...]:
    """As casas a partir de `casa` na `direcao`, em ordem, até a borda.

    Vazio se a casa já está na borda daquele lado. É o que a **dama** percorre:
    ela anda "quantas casas quiser dentro da mesma diagonal", então o gerador
    caminha por este raio até topar em alguma peça.

    >>> raio(29, Direcao.CIMA_DIREITA)      # o canto de baixo à esquerda…
    (25, 22, 18, 15, 11, 8, 4)              # …sobe pela grande diagonal
    """
    return _RAIOS[casa][Direcao(direcao)]


def vizinho(casa: int, direcao: Direcao) -> int | None:
    """A casa imediatamente adjacente na diagonal, ou ``None`` se for fora.

    É o passo da **pedra**, que anda uma casa de cada vez.
    """
    caminho = _RAIOS[casa][Direcao(direcao)]
    return caminho[0] if caminho else None


def direcao_entre(origem: int, destino: int) -> Direcao | None:
    """A direção que leva de `origem` a `destino`, se as duas estão na mesma diagonal.

    ``None`` se não estiverem — o que inclui o caso ``origem == destino``.
    """
    for direcao in Direcao:
        if destino in _RAIOS[origem][direcao]:
            return direcao
    return None


def casas_entre(origem: int, destino: int) -> tuple[int, ...]:
    """As casas estritamente entre duas casas da mesma diagonal, em ordem.

    Vazio se forem adjacentes. Levanta ``ValueError`` se não estiverem na mesma
    diagonal — erro alto e cedo, porque quem pergunta isso está descrevendo um
    lance, e um lance que não anda em diagonal é um erro de raciocínio, não um
    caso a tratar.

    Usada para saber **o que há no caminho**: uma dama só captura se houver
    exatamente uma peça adversária entre ela e a casa de destino.
    """
    direcao = direcao_entre(origem, destino)
    if direcao is None:
        raise ValueError(f"casas {origem} e {destino} não estão na mesma diagonal")
    caminho = _RAIOS[origem][direcao]
    return caminho[: caminho.index(destino)]


# ---------------------------------------------------------------------------
# O estado de uma posição
# ---------------------------------------------------------------------------


class Tabuleiro:
    """Uma posição de damas: o que há em cada uma das 32 casas, e de quem é a vez.

    O estado cabe em duas coisas:

    - ``casas``: uma lista de 32 inteiros pequenos. ``casas[0]`` é a **casa 1**,
      ``casas[31]`` é a **casa 32**. Esse "menos um" é a única fonte de confusão
      possível aqui, e por isso ele aparece em exatamente dois lugares — os
      métodos `ler` e `escrever`. Todo o resto do projeto fala em número de casa.
    - ``vez``: de quem é a vez de jogar.

    Deliberadamente **mutável**. Um motor de busca visita milhões de posições por
    segundo aplicando e desfazendo lances no mesmo objeto (o padrão
    *make/unmake*); criar um objeto novo a cada lance seria jogar fora a maior
    parte do desempenho. Quem precisar de uma cópia independente chama `copia`.
    """

    __slots__ = ("casas", "vez")
    # ``__slots__`` impede que se acrescentem atributos novos a um Tabuleiro por
    # engano, e reduz o consumo de memória por objeto — importante porque a busca
    # vai criar muitos. É também documentação: o estado é este, e só este.

    def __init__(self, casas: list[int] | None = None, vez: Cor = Cor.BRANCAS) -> None:
        if casas is None:
            casas = [int(Peca.VAZIA)] * N_CASAS
        if len(casas) != N_CASAS:
            raise ValueError(f"esperadas {N_CASAS} casas, vieram {len(casas)}")
        self.casas = list(casas)
        self.vez = Cor(vez)

    # -- construtores nomeados ---------------------------------------------

    @classmethod
    def vazio(cls, vez: Cor = Cor.BRANCAS) -> "Tabuleiro":
        """Tabuleiro sem nenhuma peça. Útil para montar posição de teste à mão."""
        return cls(vez=vez)

    @classmethod
    def inicial(cls, vez: Cor = Cor.BRANCAS) -> "Tabuleiro":
        """A posição de começo de partida: 12 peças de cada lado.

        As pretas ocupam as casas 1 a 12 (as três fileiras de cima) e as brancas
        as casas 21 a 32 (as três de baixo). As casas 13 a 20 — as duas fileiras
        centrais — começam vazias, e é para elas que o jogo avança.

        O padrão ``vez=BRANCAS`` segue as damas brasileiras. Nas anglo-americanas
        quem começa são as pretas; quem monta a partida passa `vez` de acordo.
        """
        tabuleiro = cls(vez=vez)
        for casa in range(1, 13):
            tabuleiro.escrever(casa, Peca.PEDRA_PRETA)
        for casa in range(21, N_CASAS + 1):
            tabuleiro.escrever(casa, Peca.PEDRA_BRANCA)
        return tabuleiro

    # -- acesso ------------------------------------------------------------

    def ler(self, casa: int) -> Peca:
        """O que há na casa (1 a 32)."""
        if not (1 <= casa <= N_CASAS):
            raise ValueError(f"casa fora do tabuleiro: {casa}")
        return Peca(self.casas[casa - 1])

    def escrever(self, casa: int, peca: Peca) -> None:
        """Põe (ou apaga, com ``Peca.VAZIA``) uma peça na casa (1 a 32)."""
        if not (1 <= casa <= N_CASAS):
            raise ValueError(f"casa fora do tabuleiro: {casa}")
        self.casas[casa - 1] = int(peca)

    def casas_de(self, cor: Cor) -> list[int]:
        """Os números das casas ocupadas por peças de uma cor, em ordem."""
        alvos = {int(p) for p in PECAS_POR_COR[Cor(cor)]}
        return [i + 1 for i, conteudo in enumerate(self.casas) if conteudo in alvos]

    def contar(self) -> dict[Peca, int]:
        """Quantas peças de cada tipo há no tabuleiro.

        Serve para decidir se uma posição já está na base de finais (que é
        indexada por quantidade de peças de cada tipo) e para relatórios.
        """
        contagem = {peca: 0 for peca in Peca if peca is not Peca.VAZIA}
        for conteudo in self.casas:
            if conteudo != Peca.VAZIA:
                contagem[Peca(conteudo)] += 1
        return contagem

    def copia(self) -> "Tabuleiro":
        """Uma cópia independente — mexer nela não mexe nesta."""
        return Tabuleiro(self.casas, self.vez)

    @property
    def hash(self) -> int:
        """O hash de Zobrist desta posição — **o mesmo** número que o app calcula.

        O que é um hash de Zobrist
        --------------------------
        Cada combinação (casa, peça) tem um número aleatório de 64 bits; o hash
        da posição é o ``XOR`` de todos os que estão em jogo, mais um número
        quando é a vez das pretas. Duas posições iguais dão o mesmo número; duas
        diferentes quase nunca dão (a chance de coincidirem é de uma em 2⁶⁴).

        ⚠️ **Os números vêm do motor em Dart**, não são sorteados aqui — ver
        `zobrist_damas.py`. É o que faz este motor e o do aparelho indexarem a
        tabela de transposição na mesma casa e, portanto, **podarem a mesma
        árvore**.

        Por que varre as 32 casas em vez de manter o valor incrementalmente
        ------------------------------------------------------------------
        O motor em Dart atualiza o hash a cada `escrever`, porque lá ele está no
        caminho quente da busca. Aqui a varredura **não custa nada a mais**: a
        chave que este motor usava antes era ``(tuple(casas), vez)``, que também
        percorre as 32 casas a cada nó. E varrer é imune ao furo que o modelo
        incremental tem — qualquer código que mexesse em ``casas`` por fora
        deixaria um hash incremental desatualizado, sem nada acusar.

        O ``& MASCARA_64`` do fim é **cinto de segurança**, não necessidade: o
        XOR de valores que já cabem em 64 bits também cabe, e todos os números da
        tabela cabem. Ele fica porque inteiro de Python não transborda sozinho —
        se um dia entrar aqui um valor maior que 2⁶⁴ (uma tabela regerada errado,
        um número copiado com um dígito a mais), sem o recorte o hash sairia
        maior que o do Dart e do Rust, e a divergência apareceria longe da causa.
        Com ele, o padrão de bits continua sendo o mesmo dos três motores.
        """
        valor = ZOBRIST_VEZ_DAS_PRETAS if self.vez is Cor.PRETAS else 0
        for indice, conteudo in enumerate(self.casas):
            if conteudo != Peca.VAZIA:
                # `indice + 1` porque a tabela é indexada pelo NÚMERO da casa
                # (1 a 32), e `casas[0]` é a casa 1.
                valor ^= ZOBRIST_PECA[indice + 1][conteudo]
        return valor & MASCARA_64

    # -- conversões --------------------------------------------------------

    def para_matriz(self) -> np.ndarray:
        """Devolve uma matriz 8x8 para desenhar, com `CASA_CLARA` nas casas claras.

        Esta matriz existe **só para visualização**. O motor nunca a usa: ele
        trabalha sobre o vetor de 32, que é metade do tamanho e não tem casas
        inúteis no meio. Confundir as duas é o caminho mais curto para um bug de
        índice — daí este parágrafo estar aqui.

        A figura ``docs/imagens/04_estrutura_de_dados.png`` mostra exatamente
        esta correspondência: o tabuleiro que você vê à esquerda, o vetor que a
        máquina guarda à direita.
        """
        matriz = np.full((LADO, LADO), CASA_CLARA, dtype=np.int8)
        for casa in range(1, N_CASAS + 1):
            linha, coluna = linha_coluna(casa)
            matriz[linha, coluna] = self.casas[casa - 1]
        return matriz

    def para_fen(self) -> str:
        """Escreve a posição no formato FEN de damas.

        Formato: ``<vez>:W<peças brancas>:B<peças pretas>``, casas separadas por
        vírgula e damas prefixadas por ``K`` (de *king*). Exemplo::

            W:W21,22,K23:B1,2,K5

        As casas saem em ordem crescente para que a mesma posição produza sempre
        exatamente o mesmo texto — sem isso, comparar dois FENs como strings (que
        é o que os testes fazem) daria falso negativo.
        """
        def lista(peca_simples: Peca, peca_dama: Peca) -> str:
            partes = []
            for casa in range(1, N_CASAS + 1):
                conteudo = self.casas[casa - 1]
                if conteudo == peca_simples:
                    partes.append(str(casa))
                elif conteudo == peca_dama:
                    partes.append(f"K{casa}")
            return ",".join(partes)

        brancas = lista(Peca.PEDRA_BRANCA, Peca.DAMA_BRANCA)
        pretas = lista(Peca.PEDRA_PRETA, Peca.DAMA_PRETA)
        return f"{_LETRA_FEN_POR_COR[self.vez]}:W{brancas}:B{pretas}"

    @classmethod
    def de_fen(cls, texto: str) -> "Tabuleiro":
        """Lê uma posição escrita em FEN de damas.

        Aceita as duas ordens (``:W...:B...`` ou ``:B...:W...``) porque as duas
        aparecem por aí, e tolera lista vazia (``:W:B1``) — que é uma posição
        legítima, com um dos lados sem peça alguma.

        Levanta ``ValueError`` em texto malformado em vez de devolver tabuleiro
        pela metade: uma posição lida errado num teste ou numa base de finais é
        um erro que se propaga longe antes de aparecer.
        """
        partes = [parte.strip() for parte in texto.strip().split(":")]
        if len(partes) != 3:
            raise ValueError(
                f"FEN de damas precisa de 3 partes separadas por ':', veio {texto!r}"
            )

        letra_vez = partes[0].upper()
        if letra_vez not in _COR_POR_LETRA_FEN:
            raise ValueError(f"lado a jogar deve ser 'W' ou 'B', veio {partes[0]!r}")

        tabuleiro = cls(vez=_COR_POR_LETRA_FEN[letra_vez])

        for bloco in partes[1:]:
            if not bloco:
                raise ValueError(f"bloco de peças vazio em {texto!r}")
            letra_cor, resto = bloco[0].upper(), bloco[1:]
            if letra_cor not in _COR_POR_LETRA_FEN:
                raise ValueError(f"bloco deve começar com 'W' ou 'B', veio {bloco!r}")
            cor = _COR_POR_LETRA_FEN[letra_cor]
            peca_simples, peca_dama = PECAS_POR_COR[cor]

            for item in resto.split(","):
                item = item.strip()
                if not item:
                    continue  # lista vazia, ou vírgula sobrando no fim
                e_dama = item[0].upper() == "K"
                numero = item[1:] if e_dama else item
                if not numero.isdigit():
                    raise ValueError(f"casa inválida no FEN: {item!r}")
                casa = int(numero)
                if not (1 <= casa <= N_CASAS):
                    raise ValueError(f"casa fora do tabuleiro no FEN: {casa}")
                if tabuleiro.casas[casa - 1] != Peca.VAZIA:
                    raise ValueError(f"casa {casa} declarada duas vezes em {texto!r}")
                tabuleiro.escrever(casa, peca_dama if e_dama else peca_simples)

        return tabuleiro

    # -- representações ----------------------------------------------------

    _SIMBOLO = {
        Peca.VAZIA: ".",
        Peca.PEDRA_BRANCA: "b",
        Peca.DAMA_BRANCA: "B",
        Peca.PEDRA_PRETA: "p",
        Peca.DAMA_PRETA: "P",
    }

    def __str__(self) -> str:
        """Desenho em texto, para depurar no terminal sem abrir imagem.

        Minúscula é pedra, maiúscula é dama; ``b`` branca, ``p`` preta, ``.``
        casa escura vazia e espaço casa clara. Para explicar qualquer coisa a uma
        pessoa use o PNG — este desenho é para o programador conferir rápido.
        """
        linhas = []
        for linha in range(LADO):
            celulas = []
            for coluna in range(LADO):
                casa = numero_da_casa(linha, coluna)
                if casa is None:
                    celulas.append(" ")
                else:
                    celulas.append(self._SIMBOLO[self.ler(casa)])
            linhas.append(" ".join(celulas))
        nome_vez = "brancas" if self.vez is Cor.BRANCAS else "pretas"
        return "\n".join(linhas) + f"\n(vez das {nome_vez})"

    def __repr__(self) -> str:
        return f"Tabuleiro.de_fen({self.para_fen()!r})"

    def __eq__(self, outro: object) -> bool:
        if not isinstance(outro, Tabuleiro):
            return NotImplemented
        return self.casas == outro.casas and self.vez == outro.vez

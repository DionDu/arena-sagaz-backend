"""Como uma posição de final vira um número — o alicerce da base de finais.

O problema
----------
A base de finais é um vetor gigante com **uma resposta por posição**: vitória,
derrota ou empate. Para consultá-la é preciso transformar a posição num
**índice** — um número entre 0 e o tamanho do vetor. Essa transformação precisa
ser:

- **injetora**: duas posições diferentes nunca caem no mesmo índice, senão a base
  responde pela posição errada;
- **compacta**: índice esparso demais desperdiça memória, e o teto do que cabe no
  celular é justamente o que decide o que embarcar;
- **reversível**: dado o índice, reconstruir a posição. A análise retrógrada
  precisa disso para varrer o vetor inteiro.

Fatias de material
------------------
A base não é um vetor só: é **uma por combinação de material**. Uma fatia é
definida por quantas peças de cada tipo há no tabuleiro — por exemplo
"2 pedras e 1 dama brancas contra 1 dama preta".

Fatiar assim não é organização, é o que torna o cálculo possível: **toda captura
remove uma peça**, então uma fatia de N peças só transita para fatias de N−1 ou
menos (mais as promoções, que ficam em N mas trocam pedra por dama). Isso dá uma
ordem de dependência, e é ela que a análise retrógrada percorre.

O detalhe que enxuga o índice
-----------------------------
**Pedra nunca está na própria fileira de coroação** — ela teria virado dama ao
parar lá. Então pedra branca dispõe de 28 casas (5 a 32), não de 32; pedra preta,
também 28 (1 a 28). Só a dama usa as 32. Ignorar isso incharia o vetor à toa.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import comb

from jogos.jogo_damas.motor.tabuleiro_damas import (
    CASAS_DE_COROACAO,
    N_CASAS,
    Cor,
    Peca,
    Tabuleiro,
)

# As casas em que cada tipo de peça pode estar, em ordem crescente.
CASAS_DE_PEDRA_BRANCA: tuple[int, ...] = tuple(
    casa for casa in range(1, N_CASAS + 1) if casa not in CASAS_DE_COROACAO[Cor.BRANCAS]
)
CASAS_DE_PEDRA_PRETA: tuple[int, ...] = tuple(
    casa for casa in range(1, N_CASAS + 1) if casa not in CASAS_DE_COROACAO[Cor.PRETAS]
)
TODAS_AS_CASAS: tuple[int, ...] = tuple(range(1, N_CASAS + 1))

# Resultados guardados na base. Dois bits bastam — só há três respostas.
DERROTA = 0
"""Quem tem a vez **perde** com jogo perfeito dos dois lados."""
EMPATE = 1
"""Nem um lado nem outro força a vitória."""
VITORIA = 2
"""Quem tem a vez **ganha** com jogo perfeito."""
DESCONHECIDO = 3
"""Ainda não calculado. Só existe durante a análise retrógrada."""

NOME_DO_RESULTADO = {
    DERROTA: "derrota", EMPATE: "empate",
    VITORIA: "vitoria", DESCONHECIDO: "desconhecido",
}


# ---------------------------------------------------------------------------
# Numeração de combinações
# ---------------------------------------------------------------------------
#
# Para colocar k peças iguais em n casas, o que interessa é **qual subconjunto**
# de casas elas ocupam — a ordem entre peças idênticas não existe. Numerar
# subconjuntos de tamanho fixo é um problema resolvido: o "sistema numérico
# combinatório", que dá uma correspondência 1 para 1 entre os subconjuntos e os
# números de 0 a C(n,k)−1.
#
# A conta: para um subconjunto {c₀ < c₁ < … < c_{k−1}} de posições 0-based,
#     número = C(c₀,1) + C(c₁,2) + … + C(c_{k−1},k)
# Não é preciso decorar a fórmula — é preciso saber que ela é reversível, e os
# testes conferem isso para TODOS os subconjuntos das fatias pequenas.


def numerar_combinacao(posicoes: tuple[int, ...]) -> int:
    """Numera um subconjunto ordenado de posições 0-based."""
    return sum(comb(posicao, ordem) for ordem, posicao in enumerate(posicoes, start=1))


def desnumerar_combinacao(numero: int, quantas: int, de_quantas: int) -> tuple[int, ...]:
    """A operação inversa: do número de volta ao subconjunto.

    Percorre de trás para frente escolhendo, em cada casa decimal, a maior
    posição cujo peso ainda cabe no que resta do número.
    """
    posicoes: list[int] = []
    restante = numero
    for ordem in range(quantas, 0, -1):
        posicao = ordem - 1
        while comb(posicao + 1, ordem) <= restante:
            posicao += 1
        posicoes.append(posicao)
        restante -= comb(posicao, ordem)
    return tuple(reversed(posicoes))


# ---------------------------------------------------------------------------
# A fatia de material
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fatia:
    """Uma combinação de material: quantas peças de cada tipo estão no tabuleiro.

    Attributes:
        pedras_brancas, damas_brancas, pedras_pretas, damas_pretas: as contagens.

    O nome curto (`2100` = 2 pedras brancas, 1 dama branca, 0 e 0) é o que vai
    virar nome de arquivo quando a base for gravada em disco.
    """

    pedras_brancas: int
    damas_brancas: int
    pedras_pretas: int
    damas_pretas: int

    def __post_init__(self) -> None:
        if min(self.contagens) < 0:
            raise ValueError(f"contagem negativa em {self}")
        if self.total_de_pecas > N_CASAS:
            raise ValueError(f"mais peças que casas em {self}")

    @property
    def contagens(self) -> tuple[int, int, int, int]:
        return (self.pedras_brancas, self.damas_brancas,
                self.pedras_pretas, self.damas_pretas)

    @property
    def total_de_pecas(self) -> int:
        return sum(self.contagens)

    @property
    def total_de_pedras(self) -> int:
        """Quantas pedras há. É a chave da ordem de dependência: uma promoção
        troca pedra por dama, então uma fatia depende das que têm MENOS pedras."""
        return self.pedras_brancas + self.pedras_pretas

    @property
    def nome(self) -> str:
        """`2100` — pedras brancas, damas brancas, pedras pretas, damas pretas."""
        return "".join(str(c) for c in self.contagens)

    @property
    def tem_os_dois_lados(self) -> bool:
        """Posição sem um dos lados não é final: a partida já acabou."""
        return (self.pedras_brancas + self.damas_brancas > 0
                and self.pedras_pretas + self.damas_pretas > 0)

    # -- tamanho -----------------------------------------------------------

    @property
    def tamanho(self) -> int:
        """Quantos índices esta fatia ocupa, contando os dois lados a jogar.

        ⚠️ É um pouco **maior** que o número de posições legais, de propósito. As
        pedras brancas e as pretas são numeradas em conjuntos que se sobrepõem
        (casas 5 a 28 servem às duas), então algumas combinações de índice
        correspondem a duas pedras na mesma casa — posição que não existe e que
        nunca será consultada.

        A alternativa seria numerar as duas cores em conjunto, o que dá um índice
        justo e uma aritmética bem mais difícil de conferir. Escolhi o desperdício
        (de 3% a ~15% conforme a fatia) em troca de uma numeração que os testes
        conseguem verificar exaustivamente. Base de finais errada é o pior erro
        possível deste projeto.
        """
        return self._passos()[0] * 2

    def _passos(self) -> tuple[int, int, int, int, int]:
        """(total, base das damas pretas, das brancas, das pedras pretas, 1).

        Os multiplicadores do índice posicional, calculados uma vez. Cada tipo de
        peça é uma "casa decimal" do número final.
        """
        livres_para_damas = N_CASAS - self.pedras_brancas - self.pedras_pretas
        n_damas_pretas = comb(livres_para_damas - self.damas_brancas, self.damas_pretas)
        n_damas_brancas = comb(livres_para_damas, self.damas_brancas)
        n_pedras_pretas = comb(len(CASAS_DE_PEDRA_PRETA), self.pedras_pretas)
        n_pedras_brancas = comb(len(CASAS_DE_PEDRA_BRANCA), self.pedras_brancas)

        total = n_pedras_brancas * n_pedras_pretas * n_damas_brancas * n_damas_pretas
        return (total, n_damas_pretas, n_damas_brancas, n_pedras_pretas, 1)

    # -- de posição para índice e de volta ---------------------------------

    def da_posicao(self, tabuleiro: Tabuleiro) -> int:
        """O índice desta posição dentro da fatia.

        Levanta ``ValueError`` se a posição não pertence à fatia — erro alto e
        cedo, porque consultar a fatia errada devolve uma resposta plausível e
        completamente sem relação com o tabuleiro.
        """
        por_tipo = {peca: [] for peca in
                    (Peca.PEDRA_BRANCA, Peca.DAMA_BRANCA,
                     Peca.PEDRA_PRETA, Peca.DAMA_PRETA)}
        for casa in range(1, N_CASAS + 1):
            conteudo = tabuleiro.ler(casa)
            if conteudo is not Peca.VAZIA:
                por_tipo[Peca(conteudo)].append(casa)

        encontrado = (len(por_tipo[Peca.PEDRA_BRANCA]), len(por_tipo[Peca.DAMA_BRANCA]),
                      len(por_tipo[Peca.PEDRA_PRETA]), len(por_tipo[Peca.DAMA_PRETA]))
        if encontrado != self.contagens:
            raise ValueError(
                f"a posição tem material {encontrado}, não {self.contagens}"
            )

        # As pedras são numeradas nos conjuntos restritos; as damas, nas casas
        # que sobraram depois das pedras.
        n_pb = numerar_combinacao(tuple(
            CASAS_DE_PEDRA_BRANCA.index(c) for c in por_tipo[Peca.PEDRA_BRANCA]))
        n_pp = numerar_combinacao(tuple(
            CASAS_DE_PEDRA_PRETA.index(c) for c in por_tipo[Peca.PEDRA_PRETA]))

        ocupadas = set(por_tipo[Peca.PEDRA_BRANCA]) | set(por_tipo[Peca.PEDRA_PRETA])
        livres = [c for c in TODAS_AS_CASAS if c not in ocupadas]
        n_db = numerar_combinacao(tuple(
            livres.index(c) for c in por_tipo[Peca.DAMA_BRANCA]))

        livres_pretas = [c for c in livres if c not in por_tipo[Peca.DAMA_BRANCA]]
        n_dp = numerar_combinacao(tuple(
            livres_pretas.index(c) for c in por_tipo[Peca.DAMA_PRETA]))

        _, base_dp, base_db, base_pp, _ = self._passos()
        indice = (((n_pb * base_pp + n_pp) * base_db + n_db) * base_dp + n_dp)
        return indice * 2 + int(tabuleiro.vez)

    def para_posicao(self, indice: int) -> Tabuleiro | None:
        """Reconstrói o tabuleiro a partir do índice.

        Devolve ``None`` quando o índice cai num dos vãos da numeração — as
        combinações em que uma pedra branca e uma preta ocupariam a mesma casa.
        Ver a nota em `tamanho`.
        """
        if not 0 <= indice < self.tamanho:
            raise ValueError(f"índice {indice} fora da fatia {self.nome}")

        vez = Cor(indice % 2)
        resto = indice // 2
        _, base_dp, base_db, base_pp, _ = self._passos()

        n_dp, resto = resto % base_dp, resto // base_dp
        n_db, resto = resto % base_db, resto // base_db
        n_pp, n_pb = resto % base_pp, resto // base_pp

        pedras_brancas = [CASAS_DE_PEDRA_BRANCA[i] for i in desnumerar_combinacao(
            n_pb, self.pedras_brancas, len(CASAS_DE_PEDRA_BRANCA))]
        pedras_pretas = [CASAS_DE_PEDRA_PRETA[i] for i in desnumerar_combinacao(
            n_pp, self.pedras_pretas, len(CASAS_DE_PEDRA_PRETA))]

        if set(pedras_brancas) & set(pedras_pretas):
            return None                      # o vão: duas pedras na mesma casa

        ocupadas = set(pedras_brancas) | set(pedras_pretas)
        livres = [c for c in TODAS_AS_CASAS if c not in ocupadas]
        damas_brancas = [livres[i] for i in desnumerar_combinacao(
            n_db, self.damas_brancas, len(livres))]

        livres_pretas = [c for c in livres if c not in damas_brancas]
        damas_pretas = [livres_pretas[i] for i in desnumerar_combinacao(
            n_dp, self.damas_pretas, len(livres_pretas))]

        tabuleiro = Tabuleiro.vazio(vez=vez)
        for casa in pedras_brancas:
            tabuleiro.escrever(casa, Peca.PEDRA_BRANCA)
        for casa in damas_brancas:
            tabuleiro.escrever(casa, Peca.DAMA_BRANCA)
        for casa in pedras_pretas:
            tabuleiro.escrever(casa, Peca.PEDRA_PRETA)
        for casa in damas_pretas:
            tabuleiro.escrever(casa, Peca.DAMA_PRETA)
        return tabuleiro

    def __str__(self) -> str:
        def lado(pedras: int, damas: int) -> str:
            partes = []
            if pedras:
                partes.append(f"{pedras} pedra{'s' if pedras > 1 else ''}")
            if damas:
                partes.append(f"{damas} dama{'s' if damas > 1 else ''}")
            return " e ".join(partes) or "nada"

        return (f"{lado(self.pedras_brancas, self.damas_brancas)} × "
                f"{lado(self.pedras_pretas, self.damas_pretas)}")


def fatia_da_posicao(tabuleiro: Tabuleiro) -> Fatia:
    """A fatia a que esta posição pertence."""
    contagem = tabuleiro.contar()
    return Fatia(
        contagem[Peca.PEDRA_BRANCA], contagem[Peca.DAMA_BRANCA],
        contagem[Peca.PEDRA_PRETA], contagem[Peca.DAMA_PRETA],
    )


def fatias_ate(total_de_pecas: int) -> list[Fatia]:
    """Todas as fatias com até N peças, **em ordem de dependência**.

    A ordem é o que torna a análise retrógrada possível, e ela tem dois níveis:

    1. **menos peças primeiro** — toda captura leva a uma fatia menor, que
       portanto precisa estar pronta;
    2. dentro do mesmo número de peças, **menos pedras primeiro** — uma promoção
       troca pedra por dama sem mudar o total, então uma fatia com pedras depende
       das que têm menos.

    Fatias sem um dos lados ficam de fora: não são final, são partida acabada.
    """
    fatias = []
    for total in range(2, total_de_pecas + 1):
        for pb in range(total + 1):
            for db in range(total - pb + 1):
                for pp in range(total - pb - db + 1):
                    dp = total - pb - db - pp
                    fatia = Fatia(pb, db, pp, dp)
                    if fatia.tem_os_dois_lados:
                        fatias.append(fatia)
    return sorted(fatias, key=lambda f: (f.total_de_pecas, f.total_de_pedras))

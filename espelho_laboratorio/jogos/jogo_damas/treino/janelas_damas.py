r"""As **janelas** da avaliação treinada: onde o motor olha, e como isso vira número.

O que esta peça decide
----------------------
A etapa 7 troca a avaliação escrita à mão por notas **aprendidas**. O modelo não
é uma rede: é um punhado de tabelas grandes, uma por região do tabuleiro. Avaliar
uma posição vira ler nove casas de nove vetores e somar — sem multiplicação de
matriz, sem runtime de inferência, sem GPU. É o que permite o motor rodar num
celular simples (§5.5 de `../docs/como_funciona_a_ia_de_damas.md`).

Mas para isso é preciso responder a pergunta que o plano deixou em aberto desde
2026-07-24: **quantas janelas, de que tamanho, e onde**. Este módulo é a
resposta, e ela não saiu de gosto — saiu de medição, registrada no diário do
plano em 2026-07-29.

A escolha, em uma linha
-----------------------
**Nove janelas de 4×4 casas do tabuleiro, deslizando de duas em duas, com oito
casas jogáveis cada — e cinco tabelas, porque a rotação de 180° faz janelas
diferentes verem a mesma coisa.**

Por que 4×4 (oito casas jogáveis), e não sete ou nove
-----------------------------------------------------
Cada casa da janela está num de cinco estados (vazia, minha pedra, minha dama,
pedra dele, dama dele), então uma janela de `k` casas tem `5^k` fotografias
possíveis — e cada fotografia é uma entrada de tabela de dois bytes. O custo
explode:

| casas por janela | entradas | memória (5 tabelas) |
|---|---|---|
| 7 | 78.125 | 0,75 MB |
| **8** | **390.625** | **3,73 MB** |
| 9 | 1.953.125 | 18,63 MB |

Oito é o joelho da curva: nove custa **cinco vezes** mais para ver uma casa a
mais, e sete deixa de enxergar relações que cabem num quadrado de 4×4 — que é o
alcance de uma captura simples. É também o tamanho que o Scan usa, o motor que
ganha os campeonatos mundiais com esta técnica.

Por que nove janelas, e por que deslizando de duas em duas
-----------------------------------------------------------
Medido: as nove **cobrem as 32 casas**, nenhuma fica de fora, e elas se
**sobrepõem** — 16 casas aparecem em duas janelas e 8 aparecem em quatro. A
sobreposição é o ponto: sem ela, uma relação entre casas vizinhas que caísse na
fronteira de duas janelas seria cortada ao meio e nunca aprendida.

⚠️ **A cobertura não é uniforme, e isso é sabido:** as 8 casas das quatro quinas
aparecem em **uma** janela só. Deslizar de uma em uma resolveria — mas daria 25
janelas, e nenhuma economia de simetria salvaria a memória. Fica registrado como
limitação conhecida, não como descuido.

⚠️ A simetria: **só existe UMA, e não é a que se espera**
----------------------------------------------------------
O reflexo é achar que o tabuleiro tem simetria esquerda-direita. **Não tem** —
não para as casas jogáveis. Espelhar a coluna (`c → 7-c`) muda a paridade de
`linha + coluna`, e por isso leva casa **escura em casa clara**: a janela
espelhada simplesmente não existe.

É o mesmo fenômeno que quase estragou a leitura do regulamento português em
2026-07-29 (ver `RIO` em `../motor/tabuleiro_damas.py`), e é bom que apareça duas
vezes: num tabuleiro de damas 8×8, as únicas transformações que preservam as
casas jogáveis **e** o sentido do jogo são a identidade e a **rotação de 180°
com troca de cor** (`casa → 33 - casa`).

Essa rotação é simetria de verdade do jogo, e é a mesma que a base de finais já
usa: a posição girada com as cores trocadas vale o **mesmo**, não o oposto,
porque a nota é do ponto de vista de quem joga.

Aplicada às nove janelas, ela as agrupa em **cinco órbitas** — e órbita é tabela:

| tabela | janelas que a usam |
|---|---|
| `T1` | `L0C0` e `L4C4` |
| `T2` | `L0C2` e `L4C2` |
| `T3` | `L0C4` e `L4C0` |
| `T4` | `L2C0` e `L2C4` |
| `T5` | `L2C2` *(sozinha — ela gira em si mesma)* |

Isso corta a memória de 6,71 MB para **3,73 MB por modalidade**: 45% a menos, e
o dobro de exemplos de treino por entrada, porque duas regiões alimentam a mesma
tabela.

Como uma janela derivada é lida
--------------------------------
A janela `L4C4` não tem tabela própria: ela lê a tabela de `L0C0`. Para o índice
bater, ela precisa ser lida **girada**: as casas na ordem `33 - casa` da janela
canônica, e com o ponto de vista **invertido** (o que era "minha pedra" vira
"pedra dele").

Faz sentido de jogo, e vale ler duas vezes: `L0C0` é o fundo das pretas — onde
as **brancas** coroam. `L4C4` é o fundo das brancas — onde as **pretas** coroam.
São a mesma situação, vista de lados diferentes.

⚠️ **Uma folga assumida:** `L2C2` gira em si mesma, então rigorosamente cada
fotografia dela e a fotografia girada deveriam compartilhar o mesmo peso. **Não
impomos isso.** Amarrar pesos dentro de uma tabela complica o treino e o port em
Dart para economizar meia tabela de cinco. Fica declarado aqui para não passar
por engano.

Onde este módulo é usado
------------------------
- **no treino** (etapa 7), para transformar cada posição de auto-jogo nos nove
  índices que a regressão logística ajusta;
- **na avaliação**, depois de treinado, para somar as nove notas;
- **no port em Dart**, que precisa produzir os **mesmos nove índices** — é
  escrituração dupla, e a bancada confere.
"""
from __future__ import annotations

from dataclasses import dataclass

from jogos.jogo_damas.motor.tabuleiro_damas import (
    LADO,
    N_CASAS,
    Cor,
    Peca,
    Tabuleiro,
    numero_da_casa,
)

LADO_DA_JANELA = 4
"""Quantas casas do tabuleiro (claras e escuras) o quadrado da janela tem de lado."""

PASSO = 2
"""De quanto em quanto a janela desliza. Dois é o que produz sobreposição sem
multiplicar o número de janelas — ver o cabeçalho."""

CASAS_POR_JANELA = 8
"""Casas **jogáveis** dentro de um quadrado 4×4. Metade de 16, como sempre."""

ESTADOS_POR_CASA = 5
"""vazia · minha pedra · minha dama · pedra dele · dama dele.

Cinco, e não três: distinguir pedra de dama é metade do que a avaliação precisa
julgar, e distinguir minha de dele é a outra metade."""

ENTRADAS_POR_TABELA = ESTADOS_POR_CASA ** CASAS_POR_JANELA
"""5⁸ = 390.625 fotografias possíveis de uma janela."""

BYTES_POR_ENTRADA = 2
"""`int16`. A nota cabe em dois bytes porque a unidade é o centésimo de pedra:
±327 pedras de folga é mais do que qualquer posição alcança."""


@dataclass(frozen=True)
class Janela:
    """Uma região do tabuleiro, e como lê-la.

    Attributes:
        identificador: `L<linha>C<coluna>` do canto superior esquerdo do
            quadrado. Nome geométrico de propósito — quem depurar quer saber
            *onde* a janela está, não que ela é a sétima.
        casas: as oito casas jogáveis, **na ordem de leitura**. A ordem é parte
            do contrato: trocá-la muda todos os índices e invalida uma tabela
            já treinada, sem que nada dê erro.
        tabela: qual das cinco tabelas esta janela consulta. Janelas da mesma
            órbita da rotação de 180° dividem tabela.
        inverte_o_ponto_de_vista: se esta janela é a **derivada** da órbita, e
            portanto lê "minha peça" como "peça dele". Ver o cabeçalho.
    """

    identificador: str
    casas: tuple[int, ...]
    tabela: str
    inverte_o_ponto_de_vista: bool

    @property
    def e_canonica(self) -> bool:
        """A janela que dá o nome à tabela — a que se lê sem girar nada."""
        return not self.inverte_o_ponto_de_vista


def _casas_do_quadrado(linha0: int, coluna0: int) -> tuple[int, ...]:
    """As casas jogáveis de um quadrado 4×4, em ordem crescente de número.

    Percorre as 16 casas do quadrado e guarda as escuras — `numero_da_casa`
    devolve `None` para as claras, que não existem no vetor da posição.
    """
    casas = []
    for linha in range(linha0, linha0 + LADO_DA_JANELA):
        for coluna in range(coluna0, coluna0 + LADO_DA_JANELA):
            casa = numero_da_casa(linha, coluna)
            if casa is not None:
                casas.append(casa)
    return tuple(casas)


def _girar(casa: int) -> int:
    """A casa diametralmente oposta — a rotação de 180° do tabuleiro.

    `33 - casa` porque a numeração corre de 1 a 32 de um canto ao outro. É a
    mesma conta que a base de finais usa para o par de posições gêmeas.
    """
    return N_CASAS + 1 - casa


def _montar_janelas() -> tuple[Janela, ...]:
    """As nove janelas, com as tabelas já atribuídas pela simetria.

    O laço é sobre os cantos em ordem de leitura (linha, depois coluna). A
    primeira janela de cada órbita vira a **canônica** e dá nome à tabela; a
    outra recebe as casas giradas, **na ordem que casa com a canônica** — e é
    por isso que elas não saem em ordem crescente.
    """
    cantos = [
        (linha, coluna)
        for linha in range(0, LADO - LADO_DA_JANELA + 1, PASSO)
        for coluna in range(0, LADO - LADO_DA_JANELA + 1, PASSO)
    ]
    quadrados = {canto: _casas_do_quadrado(*canto) for canto in cantos}
    # Índice inverso "conjunto de casas → canto", para achar a janela gêmea.
    canto_por_casas = {frozenset(casas): canto for canto, casas in quadrados.items()}

    janelas: list[Janela] = []
    tabela_por_canto: dict[tuple[int, int], tuple[str, bool]] = {}

    for numero, canto in enumerate(cantos, start=1):
        if canto in tabela_por_canto:
            continue

        nome_da_tabela = f"T{len(set(t for t, _ in tabela_por_canto.values())) + 1}"
        tabela_por_canto[canto] = (nome_da_tabela, False)

        # Onde esta janela vai parar depois da rotação de 180°.
        girada = frozenset(_girar(casa) for casa in quadrados[canto])
        gemea = canto_por_casas[girada]
        if gemea != canto:
            tabela_por_canto[gemea] = (nome_da_tabela, True)

    for canto in cantos:
        nome_da_tabela, invertida = tabela_por_canto[canto]
        if invertida:
            # A gêmea lê as casas na ordem derivada da canônica: a i-ésima casa
            # dela é o giro da i-ésima casa da canônica. Ordenar por número aqui
            # embaralharia o índice e quebraria a simetria em silêncio.
            canonico = next(
                outro for outro, (nome, inverte) in tabela_por_canto.items()
                if nome == nome_da_tabela and not inverte
            )
            casas = tuple(_girar(casa) for casa in quadrados[canonico])
        else:
            casas = quadrados[canto]

        janelas.append(Janela(
            identificador=f"L{canto[0]}C{canto[1]}",
            casas=casas,
            tabela=nome_da_tabela,
            inverte_o_ponto_de_vista=invertida,
        ))
    return tuple(janelas)


JANELAS: tuple[Janela, ...] = _montar_janelas()
"""As nove janelas, na ordem em que a avaliação as soma.

A ordem importa para o **arquivo de pesos**, não para a soma (adição é
comutativa). Ela entra no contrato com o app na etapa 8."""

TABELAS: tuple[str, ...] = tuple(
    dict.fromkeys(janela.tabela for janela in JANELAS)
)
"""As cinco tabelas distintas, em ordem de primeira aparição."""


def memoria_por_modalidade_bytes() -> int:
    """Quanto as tabelas ocupam em RAM, para **uma** modalidade.

    É este o número que importa para o aparelho, e não o total das quatro: o app
    carrega a modalidade que está sendo jogada, não todas. Ver a nota sobre
    compressão no diário do plano — aqui a decisão é o **inverso** da da base de
    finais, e pelo motivo certo.
    """
    return len(TABELAS) * ENTRADAS_POR_TABELA * BYTES_POR_ENTRADA


def estado_da_casa(tabuleiro: Tabuleiro, casa: int, ponto_de_vista: Cor) -> int:
    """O dígito de 0 a 4 que esta casa contribui ao índice.

    "Minha" e "dele" são relativos ao `ponto_de_vista`, e não às cores absolutas.
    É o que faz a mesma tabela servir aos dois lados — sem isso seriam dez
    tabelas, e cada uma veria metade dos exemplos de treino.
    """
    peca = tabuleiro.ler(casa)
    if peca == Peca.VAZIA:
        return 0
    minhas = ponto_de_vista is Cor.BRANCAS
    if peca == Peca.PEDRA_BRANCA:
        return 1 if minhas else 3
    if peca == Peca.DAMA_BRANCA:
        return 2 if minhas else 4
    if peca == Peca.PEDRA_PRETA:
        return 3 if minhas else 1
    return 4 if minhas else 2


def indice_da_janela(
    tabuleiro: Tabuleiro, janela: Janela, ponto_de_vista: Cor
) -> int:
    """A fotografia desta janela, como número de 0 a 390.624.

    Um número na base 5, lido com a primeira casa da janela como dígito **menos**
    significativo::

        índice = d₀·5⁰ + d₁·5¹ + … + d₇·5⁷

    Nas janelas derivadas o ponto de vista se inverte antes da leitura — é o que
    completa a rotação de 180° e permite que elas dividam a tabela com a
    canônica.
    """
    if janela.inverte_o_ponto_de_vista:
        ponto_de_vista = (
            Cor.PRETAS if ponto_de_vista is Cor.BRANCAS else Cor.BRANCAS
        )

    indice = 0
    for posicao, casa in enumerate(janela.casas):
        indice += estado_da_casa(tabuleiro, casa, ponto_de_vista) * (
            ESTADOS_POR_CASA ** posicao
        )
    return indice


def indices(tabuleiro: Tabuleiro, ponto_de_vista: Cor) -> tuple[int, ...]:
    """Os nove índices desta posição, na ordem de `JANELAS`.

    É a **única** função que o treino e a avaliação precisam chamar. Devolver
    tupla, e não lista, é para deixar claro que o resultado não se altera depois
    — um índice mexido em algum canto seria erro sem sintoma.
    """
    return tuple(
        indice_da_janela(tabuleiro, janela, ponto_de_vista) for janela in JANELAS
    )


def cobertura() -> dict[int, int]:
    """Em quantas janelas cada casa aparece. Serve à figura e ao teste.

    Calculado, e não escrito à mão: uma tabela de cobertura decorada envelheceria
    no instante em que alguém mexesse na geometria.
    """
    contagem = {casa: 0 for casa in range(1, N_CASAS + 1)}
    for janela in JANELAS:
        for casa in janela.casas:
            contagem[casa] += 1
    return contagem

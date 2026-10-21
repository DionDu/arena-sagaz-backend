"""A ADOÇÃO de uma versão do app, e a frequência que ela autoriza (T119 da spec 010).

═══════════════════════════════════════════════════════════════════════════
O PROBLEMA QUE ESTE MÓDULO RESOLVE
═══════════════════════════════════════════════════════════════════════════

Um jogo novo no Desafio do Dia só abre num app que o conhece. O Quatro em Linha
pede a versão `1.4.0` (`editorial.VERSAO_MINIMA_DO_QUATRO`); um app `1.3` que
recebesse o desafio dele cairia na tela de atualizar, e a pessoa perderia o dia
(RF-DES-021/024). Se o job pusesse o jogo novo no rodízio pleno no dia do
lançamento, um terço dos dias seria um "atualize o app" para quase todo mundo.

Por isso a frequência do jogo novo **acompanha a adoção** (RF-DES-025, RF-QTR-164,
`research.md` R-23 da spec 010): enquanto pouca gente tem a versão, o jogo novo
aparece raramente; conforme a versão se espalha, ele aparece mais, até entrar no
rodízio sem regra especial. Sem nenhum ajuste manual.

═══════════════════════════════════════════════════════════════════════════
O QUE "ADOÇÃO" QUER DIZER AQUI
═══════════════════════════════════════════════════════════════════════════

A adoção de uma versão mínima é a fração dos **aparelhos** vistos nos últimos
7 dias cuja **maior** versão (nesses 7 dias) é `≥` a mínima. A amostra é
`log.tb004_aparelho_dia` (migração `0036_log_aparelho`), uma linha por aparelho
por dia local, gravada pela rota que a Home chama ao abrir.

⚠️ **Aparelhos, e não pessoas** (§8zzz de `docs/DECISOES-do-dono.md` do app):
quem tem um Android e um iPad conta duas vezes, com a versão de cada um - e é
isso que se quer, porque é em cada aparelho que o desafio abre ou não abre.

⚠️ **As linhas LEGADAS entram, e têm de entrar.** O app `1.3` em campo não manda
o código de instalação; para ele o servidor sintetiza um aparelho
(`api.aparelhos.regras.id_aparelho_legado`). Se a leitura do banco filtrasse
essas linhas, as versões antigas sumiriam da conta e a adoção leria 100% no dia
do lançamento - exatamente o erro que este módulo existe para evitar. Esta
função não as distingue (ela não vê o `ic_legado`); quem lê o banco não pode
filtrá-las.

⚠️ **E a atualização do 1.3 para o 1.4 conta DOIS aparelhos por até 7 dias.** O
mesmo telefone aparece com a linha legada (o 1.3, `uuid5`) e com o código de
instalação novo (o 1.4, `uuid4`), e a amostra não tem como saber que são o mesmo:
a adoção sai um pouco **abaixo** da real enquanto a linha legada não sai da
janela. É o lado conservador (o jogo novo fica mais raro por uns dias, e nunca
aparece a quem não o abre), e some sozinho em uma semana. Juntar as duas linhas
pela conta e pela plataforma esconderia o caso contrário - dois Android da mesma
pessoa, um ainda no 1.3 -, que é justamente o aparelho que não abriria o desafio.

⚠️ **A maior versão do aparelho na JANELA, e não a do último dia.** Quem atualizou
na terça e abriu o app só na segunda-feira continua com a versão nova; o
aparelho entra uma vez só, com a maior. E é a mesma regra que a linha do dia já
usa por dentro (a maior vista no dia, `regras.versao_maior`).

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE ESTE MÓDULO NÃO FAZ
═══════════════════════════════════════════════════════════════════════════

Ele **não lê o banco** e **não escolhe o jogo do dia**. É só a conta e a tabela
de faixas: recebe os avistamentos e devolve a adoção; recebe a adoção e devolve
a frequência. Quem lê `tb004` e quem decide os dias do jogo novo em
`gerador.escolher_jogo` é a T120 - e a regra de "não mudar a fila de
Pontinhos e damas" mora lá. Assim cada limiar se testa com números escolhidos a
dedo, sem Postgres.

⚠️ **Genérico de propósito.** Nada aqui sabe do Quatro em Linha: vale para
qualquer jogo, ou tipo, cuja `co_versao_minima` esteja acima do que há em campo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from typing import Hashable, Iterable, Optional

from api.aparelhos.regras import chave_da_versao

# ═══════════════════════════════════════════════════════════════════════════
# A janela
# ═══════════════════════════════════════════════════════════════════════════

#: Quantos dias de amostra entram na conta.
#:
#: Sete, e não um: o uso do app tem cara de semana (o fim de semana não se parece
#: com a terça), e um dia só faria a adoção oscilar conforme o dia da semana em
#: que o job rodou. E sete, e não trinta: quem largou o app há três semanas não
#: vai abrir o desafio amanhã, e contar o aparelho dele seguraria o jogo novo
#: por uma versão que não está mais em uso.
JANELA_DA_ADOCAO_DIAS = 7


def janela_da_adocao(hoje: date) -> tuple[date, date]:
    """O primeiro e o último dia local da amostra, **os dois incluídos**.

    São os 7 dias **fechados** antes de [hoje]: de `hoje - 7` a `hoje - 1`.

    ⚠️ **Por que o dia de hoje fica de fora.** Ele ainda está sendo escrito: duas
    execuções do job no mesmo dia leriam amostras diferentes e poderiam chegar a
    faixas diferentes. Com os dias fechados, o que muda entre duas execuções do
    mesmo dia é só o resto de "ontem" de quem mora num fuso bem atrás de UTC -
    e, ainda assim, a T120 lê a adoção **uma vez** por execução e a registra no
    log, para a escolha do jogo poder ser refeita.

    Args:
        hoje: a data em que o job roda (o dia UTC da execução).

    Returns:
        A tupla `(primeiro, ultimo)`, pronta para um `BETWEEN` em `dt_dia_local`.
    """
    # `timedelta(days=n)` é um intervalo de n dias; subtraí-lo de uma `date`
    # devolve a data n dias antes.
    return (hoje - timedelta(days=JANELA_DA_ADOCAO_DIAS), hoje - timedelta(days=1))


# ═══════════════════════════════════════════════════════════════════════════
# A conta
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class Adocao:
    """Quantos aparelhos foram vistos, e quantos deles já têm a versão mínima.

    São os **dois números**, e não só a fração: o log da execução registra
    *"312 de 780 aparelhos"*, que diz o tamanho da amostra junto com o resultado.
    Uma adoção de 100% com 3 aparelhos e uma com 3 mil não são a mesma notícia.

    `frozen=True` torna o objeto imutável (nada o altera depois de criado), e
    `slots=True` só economiza memória - os dois são o padrão dos valores do job.
    """

    #: A versão mínima pedida, como veio (`"1.4.0"`).
    versao_minima: str
    #: Os aparelhos distintos vistos na janela (o denominador).
    aparelhos: int
    #: Os que têm a maior versão `≥` a mínima (o numerador).
    adotaram: int

    @property
    def fracao(self) -> Fraction:
        """A adoção como fração **exata**, de 0 a 1.

        `Fraction` é a fração do Python feita de dois inteiros (`Fraction(2, 5)`
        é exatamente 0,4), e compará-la com um limiar não tem arredondamento: um
        aparelho a menos que o limiar fica abaixo dele, sempre, qualquer que
        seja o tamanho da amostra.

        ⚠️ **Sem amostra, a adoção é ZERO.** Nenhum aparelho visto em 7 dias (um
        banco novo, ou a leitura falhando em silêncio) não é prova de que a
        versão chegou: o jogo novo **não aparece** (`frequencia_do_jogo_novo`),
        e nunca vai ao rodízio pleno por falta de dado. Errar para o lado
        conservador custa dias de jogo novo; errar para o outro custa a tela de
        atualizar para todo mundo.
        """
        if self.aparelhos == 0:
            return Fraction(0)
        return Fraction(self.adotaram, self.aparelhos)


def medir_adocao(
    avistamentos: Iterable[tuple[Hashable, Optional[str]]],
    versao_minima: str,
) -> Adocao:
    """A adoção de [versao_minima] numa amostra de avistamentos.

    Args:
        avistamentos: os pares `(id_aparelho, co_versao_app)` das linhas de
            `log.tb004_aparelho_dia` da janela - **uma por aparelho por dia**,
            e portanto até 7 por aparelho. As linhas legadas entram como as
            outras.
        versao_minima: a `co_versao_minima` do jogo ou tipo novo (`"1.4.0"`).

    Returns:
        Os aparelhos distintos e quantos deles alcançam a mínima.

    Raises:
        ValueError: se [versao_minima] não se lê como versão. É defeito do
            catálogo, e não da amostra: sem uma mínima comparável, qualquer
            resposta seria inventada.

    ⚠️ **Versão que não se lê numa linha** (uma gravada antes de a rota passar a
    descartá-las) não alcança a mínima, mas o aparelho **continua contado** no
    denominador: ele foi visto, só não se sabe com o quê. Se o mesmo aparelho
    tiver outra linha legível na janela, vale a legível.
    """
    chave_minima = chave_da_versao(versao_minima)
    if chave_minima is None:
        raise ValueError(f"versão mínima ilegível: {versao_minima!r}")

    # A maior versão de cada aparelho na janela. O valor `None` marca o aparelho
    # visto só com versões ilegíveis - ele entra no denominador assim mesmo.
    maior_por_aparelho: dict[Hashable, Optional[tuple[int, int, int, int]]] = {}
    for id_aparelho, versao in avistamentos:
        chave = chave_da_versao(versao)
        if id_aparelho not in maior_por_aparelho:
            # 1ª linha deste aparelho: ele passa a contar, legível ou não.
            maior_por_aparelho[id_aparelho] = chave
        elif chave is not None:
            # Já visto: só troca para uma versão MAIOR (ou para a 1ª legível).
            # Uma linha ilegível nunca apaga a versão que o aparelho já tem.
            atual = maior_por_aparelho[id_aparelho]
            if atual is None or chave > atual:
                maior_por_aparelho[id_aparelho] = chave

    # A tupla `(maior, menor, correção, build)` compara número a número, então
    # `1.10.0` alcança `1.9.0` - o texto diria o contrário.
    adotaram = sum(
        1 for chave in maior_por_aparelho.values() if chave is not None and chave >= chave_minima
    )
    return Adocao(
        versao_minima=versao_minima,
        aparelhos=len(maior_por_aparelho),
        adotaram=adotaram,
    )


# ═══════════════════════════════════════════════════════════════════════════
# As faixas (ratificadas pelo dono na T003, 13/10/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# | adoção do jogo novo | o jogo novo aparece                       |
# |---------------------|-------------------------------------------|
# | nenhum aparelho     | não aparece (T120, a ratificar)           |
# | < 40%               | 1 dia em 6                                |
# | 40% a < 60%         | 1 dia em 4                                |
# | 60% a < 80%         | 1 dia em 3                                |
# | ≥ 80%               | rodízio pleno (1 em 3)                    |
#
# ⚠️ São PONTO DE PARTIDA (R-23): mudar um número é mudar estas constantes, e o
# teste dos limiares exatos (39,9 / 40 / 59,9 / 60 / 79,9 / 80) acusa a mudança.
# O limite inferior de cada faixa é INCLUÍDO nela: 40% exatos já é 1 em 4.
#
# ⚠️ **A 1ª linha não estava na tabela da T003, e entrou na T120.** Com ZERO
# aparelhos na versão, ninguém consegue abrir o desafio do jogo novo: cada dia
# dele seria a tela de atualizar para todo mundo. É o que acontece no dia em que
# o backend vai ao ar antes do app chegar às lojas - e é o que o cadeado da R-23
# pede ("com adoção 0, 365 dias dão a mesma fila de hoje"). Basta UM aparelho
# para a faixa de 1 em 6 valer.

#: A partir daqui o jogo novo aparece 1 dia em 4.
LIMIAR_UM_EM_QUATRO = Fraction(40, 100)
#: A partir daqui, 1 dia em 3.
LIMIAR_UM_EM_TRES = Fraction(60, 100)
#: A partir daqui, o rodízio pleno.
LIMIAR_RODIZIO_PLENO = Fraction(80, 100)

#: Abaixo de 40% (e com pelo menos um aparelho): 1 dia em 6.
UM_DIA_EM_ABAIXO_DE_40 = 6
#: De 40% a menos de 60%: 1 dia em 4.
UM_DIA_EM_DE_40_A_60 = 4
#: De 60% a menos de 80%: 1 dia em 3.
UM_DIA_EM_DE_60_A_80 = 3
#: No rodízio pleno: 1 dia em 3, a parte de cada um dos três jogos.
#:
#: ⚠️ **O pleno é "1 em 3" pela MESMA regra dos dias, e não o jogo entrando em
#: `gerador.JOGOS_DO_RODIZIO`.** Pôr um 3º jogo naquela tupla mudaria a conta
#: `dias // len(JOGOS_DO_RODIZIO)` de que dependem o tipo, a modalidade e a
#: variante do Pontinhos e das damas - a fila deles inteira mudaria de fase, que
#: é exatamente o que a R-23 (item 4) proíbe. A frequência é a mesma; a fila dos
#: jogos antigos continua a de sempre.
UM_DIA_EM_NO_RODIZIO_PLENO = 3


@dataclass(frozen=True, slots=True)
class Frequencia:
    """Com que frequência o jogo novo pode aparecer.

    ⚠️ **`um_dia_em = None` quer dizer que o jogo novo NÃO APARECE** (nenhum
    aparelho tem a versão). Os outros valores são *"1 dia em N"*, e quem decide
    quais dias são esses é `dia_do_jogo_novo`, logo abaixo.
    """

    #: `N` em "1 dia em N", ou `None` quando o jogo novo não aparece.
    um_dia_em: Optional[int]
    #: `True` na faixa de cima (≥ 80%). Só informa o log: a regra dos dias é a
    #: mesma das outras faixas (ver `UM_DIA_EM_NO_RODIZIO_PLENO`).
    rodizio_pleno: bool = False

    @property
    def aparece(self) -> bool:
        """`True` quando o jogo novo tem algum dia."""
        return self.um_dia_em is not None

    def descrever(self) -> str:
        """A faixa em palavras, para o log da execução."""
        if self.um_dia_em is None:
            return "não aparece"
        if self.rodizio_pleno:
            return f"rodízio pleno (1 dia em {self.um_dia_em})"
        return f"1 dia em {self.um_dia_em}"


#: O jogo novo fora do ar: nenhum aparelho com a versão.
NAO_APARECE = Frequencia(um_dia_em=None)


def frequencia_do_jogo_novo(adocao: Adocao) -> Frequencia:
    """A faixa em que [adocao] cai, conforme a tabela acima.

    A comparação é feita com a fração **exata** (`Adocao.fracao`): 2 de 5
    aparelhos são 40% e já valem 1 em 4; 285 de 715 (39,86%) ainda são 1 em 6.
    """
    if adocao.adotaram == 0:
        # Ninguém abre o desafio do jogo novo (inclui a amostra vazia).
        return NAO_APARECE
    fracao = adocao.fracao
    # Do limiar mais alto para o mais baixo: a primeira faixa que a adoção
    # alcança é a dela.
    if fracao >= LIMIAR_RODIZIO_PLENO:
        return Frequencia(um_dia_em=UM_DIA_EM_NO_RODIZIO_PLENO, rodizio_pleno=True)
    if fracao >= LIMIAR_UM_EM_TRES:
        return Frequencia(um_dia_em=UM_DIA_EM_DE_60_A_80)
    if fracao >= LIMIAR_UM_EM_QUATRO:
        return Frequencia(um_dia_em=UM_DIA_EM_DE_40_A_60)
    return Frequencia(um_dia_em=UM_DIA_EM_ABAIXO_DE_40)


# ═══════════════════════════════════════════════════════════════════════════
# Quais dias são do jogo novo (T120)
# ═══════════════════════════════════════════════════════════════════════════

#: O passo da regra dos dias: a parte fracionária da razão áurea, (√5 − 1) / 2.
#:
#: ⚠️ **Por que um número irracional, e não "o dia é do jogo novo quando
#: `dias % 6 == 0`".** O resto por 6 é sempre par, então o jogo novo tomaria
#: SEMPRE o dia do mesmo jogo antigo (o Pontinhos joga nos dias pares), e dentro
#: dele sempre a mesma vez do rodízio de tipos: `dias // 2` cairia sempre no mesmo
#: resto por 3, e com 6 ou 3 tipos um deles nunca mais sairia. É o travamento em
#: fase de 10/09/2026 (`gerador.escolher_tipo`), por outro caminho.
#:
#: Somar um irracional a cada dia e olhar só a parte fracionária (uma "rotação
#: irracional") nunca repete um ciclo: os dias do jogo novo não têm período
#: nenhum, então não ficam em fase com a paridade, nem com os tipos, nem com as
#: modalidades. E a razão áurea é o irracional que espalha **mais igual**: os
#: intervalos entre dois dias do jogo novo só assumem três tamanhos (3, 5 e 8
#: dias no 1 em 6; 2, 3 e 5 no 1 em 4 e no 1 em 3), e dois dias seguidos nunca
#: saem (o passo, 0,618, é maior que qualquer janela 1/N com N ≥ 2). Medido em
#: 3.650 dias (21/10/2026): metade dos dias do jogo novo cai em dia par e metade
#: em ímpar, e cada tipo do Pontinhos (7) e das damas (4) perde a mesma parte.
#:
#: Escrito por extenso, e não calculado, para nenhuma plataforma arredondar
#: diferente: `float` do Python é IEEE 754 em todo lugar.
PASSO_DOS_DIAS = 0.6180339887498949


def dia_do_jogo_novo(dias: int, frequencia: Frequencia, *, deslocamento: float = 0.0) -> bool:
    """`True` quando o dia número [dias] (desde a época do rodízio) é do jogo novo.

    Args:
        dias: os dias desde `gerador.EPOCA_DO_RODIZIO`.
        frequencia: a faixa da adoção.
        deslocamento: de 0 a 1, para dois jogos em adoção ao mesmo tempo não
            caírem nos mesmos dias (cada um começa a sua janela num ponto).

    A conta: a parte fracionária de `dias × PASSO_DOS_DIAS + deslocamento` cai
    na janela `[0, 1/N)` uma vez a cada N dias, em média. É uma função **só da
    data e da faixa**: duas execuções do job com a mesma adoção escolhem os
    mesmos dias (a idempotência da T038).
    """
    if frequencia.um_dia_em is None:
        return False
    # `% 1.0` fica só com a parte fracionária (5,37 → 0,37).
    posicao = (dias * PASSO_DOS_DIAS + deslocamento) % 1.0
    return posicao < 1.0 / frequencia.um_dia_em

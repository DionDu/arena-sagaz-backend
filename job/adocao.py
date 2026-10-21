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
        versão chegou: o jogo novo fica na faixa mais rara, e não no rodízio
        pleno. Errar para o lado conservador custa dias de jogo novo; errar para
        o outro custa a tela de atualizar para todo mundo.
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
# | < 40%               | 1 dia em 6                                |
# | 40% a < 60%         | 1 dia em 4                                |
# | 60% a < 80%         | 1 dia em 3                                |
# | ≥ 80%               | rodízio pleno, sem regra especial         |
#
# ⚠️ São PONTO DE PARTIDA (R-23): mudar um número é mudar estas constantes, e o
# teste dos limiares exatos (39,9 / 40 / 59,9 / 60 / 79,9 / 80) acusa a mudança.
# O limite inferior de cada faixa é INCLUÍDO nela: 40% exatos já é 1 em 4.

#: A partir daqui o jogo novo aparece 1 dia em 4.
LIMIAR_UM_EM_QUATRO = Fraction(40, 100)
#: A partir daqui, 1 dia em 3.
LIMIAR_UM_EM_TRES = Fraction(60, 100)
#: A partir daqui, o rodízio pleno.
LIMIAR_RODIZIO_PLENO = Fraction(80, 100)

#: Abaixo de 40%: 1 dia em 6.
UM_DIA_EM_ABAIXO_DE_40 = 6
#: De 40% a menos de 60%: 1 dia em 4.
UM_DIA_EM_DE_40_A_60 = 4
#: De 60% a menos de 80%: 1 dia em 3.
UM_DIA_EM_DE_60_A_80 = 3


@dataclass(frozen=True, slots=True)
class Frequencia:
    """Com que frequência o jogo novo pode aparecer.

    ⚠️ **`um_dia_em = None` quer dizer RODÍZIO PLENO**, e não "nunca": o jogo novo
    entra na tupla do rodízio como os outros, sem regra especial. Os outros
    valores são *"1 dia em N"*, e quem distribui esses dias pela fila (sem
    mudar a dos jogos antigos) é `gerador.escolher_jogo`, na T120.

    ⚠️ O "1 em 3" da faixa de 60 a 80% e o rodízio pleno com três jogos dão o
    mesmo número, e ainda assim não são a mesma coisa: o pleno é a regra de
    sempre (a data e os vizinhos), e a faixa é a regra do jogo novo.
    """

    #: `N` em "1 dia em N", ou `None` no rodízio pleno.
    um_dia_em: Optional[int]

    @property
    def rodizio_pleno(self) -> bool:
        """`True` quando o jogo novo já não precisa de regra especial."""
        return self.um_dia_em is None


def frequencia_do_jogo_novo(adocao: Adocao) -> Frequencia:
    """A faixa em que [adocao] cai, conforme a tabela ratificada na T003.

    A comparação é feita com a fração **exata** (`Adocao.fracao`): 2 de 5
    aparelhos são 40% e já valem 1 em 4; 285 de 715 (39,86%) ainda são 1 em 6.
    """
    fracao = adocao.fracao
    # Do limiar mais alto para o mais baixo: a primeira faixa que a adoção
    # alcança é a dela.
    if fracao >= LIMIAR_RODIZIO_PLENO:
        return Frequencia(um_dia_em=None)
    if fracao >= LIMIAR_UM_EM_TRES:
        return Frequencia(um_dia_em=UM_DIA_EM_DE_60_A_80)
    if fracao >= LIMIAR_UM_EM_QUATRO:
        return Frequencia(um_dia_em=UM_DIA_EM_DE_40_A_60)
    return Frequencia(um_dia_em=UM_DIA_EM_ABAIXO_DE_40)

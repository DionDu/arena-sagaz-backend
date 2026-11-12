"""A agenda do card do dia: QUANDO se publica e O QUE vai em cada story.

Este módulo é **puro** (sem banco, sem relógio, sem FastAPI): recebe o dia e os
números do Magno, devolve a agenda. Toda regra de calendário mora aqui, num
lugar só, e se testa com uma chamada de função.

PRD: `docs/PRD_Cards_de_Compartilhamento.md` (raiz), §2 e §3.

═══════════════════════════════════════════════════════════════════════════
O "DIA DE PUBLICAÇÃO" É O DIA DE BRASÍLIA EM QUE O DESAFIO COMEÇOU
═══════════════════════════════════════════════════════════════════════════

O desafio do dia é um dia **UTC**: começa às 00:00 UTC, que são as **21h de
Brasília do dia anterior** (`api/desafios/modelos_evento.py`,
`encerramento_do_dia`). O dono publica às 21h, no instante em que o desafio novo
começa a valer. Então o desafio de **quinta (UTC)** é o post de **quarta à noite**.

    dia de publicação = dia UTC do desafio - 1 dia

E é sobre o dia de publicação que valem as regras do dono (quarta, sexta,
sábado e domingo; o Magno às quartas; o pedido de ajuda no domingo).

⚠️ Brasília é UTC-3 o ano inteiro desde 2019 (o horário de verão acabou), e por
isso a conta acima é exata. Se o horário de verão voltar, as 21h viram 22h no
verão, e esta regra continua certa: ela segue o desafio, não o relógio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal, Optional

# ── Os dias da semana em que se publica (decisão do dono, 12/11/2026) ────────
#
# `date.weekday()` numera a semana de 0 (segunda) a 6 (domingo).
QUARTA, SEXTA, SABADO, DOMINGO = 2, 4, 5, 6
DIAS_DE_PUBLICAR = frozenset({QUARTA, SEXTA, SABADO, DOMINGO})

# ── O card do Magno: a cada duas semanas, numa quarta ────────────────────────
#
# "A cada duas semanas" precisa de um ponto de partida: as quartas do Magno são
# as que distam um múltiplo de 14 dias desta. Uma data fixa, e não "semana ISO
# par", porque o ano de 53 semanas ISO quebraria a alternância na virada.
# ⚠️ A QUARTA é sugestão minha aceita como provisória (PRD §8, em aberto): os
# fins de semana ficam com o desafio, que é o que traz instalação.
PRIMEIRA_QUARTA_DO_MAGNO = date(2026, 11, 18)

# ── A rotação visual ─────────────────────────────────────────────────────────
#
# Três layouts do card C e quatro papéis (os da moldura do vídeo da loja). A
# rotação anda UM passo por dia de publicação, e não por dia do calendário: assim
# dois posts seguidos nunca repetem o layout nem o papel. Como 3 e 4 não têm
# divisor comum, a mesma combinação só volta depois de 12 publicações (~3 semanas).
LAYOUTS_CONVITE = (1, 2, 3)
PAPEIS = ("caderno", "damas", "quatro", "pontinhos")
#: O ponto zero da contagem de publicações (uma quarta qualquer do passado).
ORIGEM_DA_CONTAGEM = date(2026, 11, 4)

# ── O link que vai nos stories ───────────────────────────────────────────────
#
# `?o=story` é a origem que o `/baixar` repassa à loja (`api/site/baixar.py`,
# `ORIGENS`). Os stories são em português, por isso o endereço em português.
LINK_DOS_STORIES = "https://arenasagaz.santiagodata.com/baixar?o=story"

# ── As legendas prontas ──────────────────────────────────────────────────────
#
# ⚠️ RASCUNHO À ESPERA DO DONO (PRD §8: "os textos prontos, que o dono aprova
# depois de escritos"). Regras: português, sem travessão longo, sem "o app que
# eu criei", e o link sempre no fim, numa linha só dele (no status do WhatsApp
# ele fica tocável; no story do Instagram vai na figurinha).
#
# As do convite têm duas lacunas que a PÁGINA preenche, porque é ela que tem o
# texto de cada objetivo (o mesmo do app, em `AppLocalizations`):
#   {objetivo} - a frase do desafio, com maiúscula ("Feche 4 caixas em 2 turnos contra a Pita");
#   {jogo}     - o nome do jogo ("Jogo dos Pontinhos").
LEGENDAS_CONVITE = (
    "Desafio do Dia, no {jogo}: {objetivo}. Você consegue? Vale até amanhã às 21h.",
    "Saiu o desafio de hoje, no {jogo}. {objetivo}. Topa? É de graça.",
    "Duvido você resolver este. {objetivo}, no {jogo}. Tem até amanhã às 21h.",
)
LEGENDA_AJUDA = (
    "Uma ajuda? Baixe a Arena Sagaz, jogue uma partida e, se curtir, deixe sua "
    "avaliação na loja. Faz muita diferença pra um app pequeno."
)
LEGENDAS_MAGNO = (
    "Alguém se habilita a vencer o Magno? Ele é o mais difícil dos quatro.",
    "Será que você é quem vai quebrar a sequência do Magno?",
)

# ── Quando os números do Magno "impressionam" (PRD §8, EM ABERTO) ────────────
#
# ⚠️ VALORES PROVISÓRIOS, à espera dos números reais do prd (consulta em
# `ferramentas/consultas_sql/card_do_dia_magno.sql`, na raiz). Abaixo disso, o
# card do Magno não sai, e a quarta dele vira um convite comum.
LIMITE_DIAS_SEM_PERDER = 14
LIMITE_PARTIDAS_NO_PERIODO = 50

Card = Literal["convite", "magno", "ajuda"]


@dataclass(frozen=True)
class NumerosDoMagno:
    """Os números de UM escopo (um jogo, ou os quatro juntos, com `jogo` None).

    `frozen=True` torna o objeto imutável: depois de criado, nenhum campo muda,
    e dá para usá-lo como dado puro sem medo de alguém o alterar no caminho.
    """

    jogo: Optional[str]
    dias_sem_perder: int
    recorde_dias: int
    partidas_no_periodo: int
    derrotas_no_periodo: int


@dataclass(frozen=True)
class EscolhaDoMagno:
    """O que o card D vai mostrar: a variante e os números do escopo escolhido."""

    variante: Literal["placa", "placar"]
    numeros: NumerosDoMagno


@dataclass(frozen=True)
class Story:
    """Um story do dia, na ordem de publicação."""

    card: Card
    papel: str
    legenda: str
    #: Só no convite (1, 2 ou 3).
    layout: Optional[int] = None


@dataclass(frozen=True)
class Agenda:
    """A resposta da agenda para um dia de publicação."""

    dia_publicacao: date
    publica_hoje: bool
    proxima_publicacao: date
    stories: list[Story] = field(default_factory=list)
    magno: Optional[EscolhaDoMagno] = None


def dia_de_publicacao(dia_utc_do_desafio: date) -> date:
    """O dia de Brasília em que o desafio deste dia UTC começou (às 21h)."""
    return dia_utc_do_desafio - timedelta(days=1)


def publica_em(dia: date) -> bool:
    """Se este dia de publicação é um dos quatro da semana."""
    return dia.weekday() in DIAS_DE_PUBLICAR


def proxima_publicacao(dia: date) -> date:
    """O próximo dia de publicação DEPOIS de `dia` (nunca o próprio `dia`)."""
    seguinte = dia + timedelta(days=1)
    while not publica_em(seguinte):
        seguinte += timedelta(days=1)
    return seguinte


def e_quarta_do_magno(dia: date) -> bool:
    """Se este dia é uma das quartas quinzenais do card D."""
    return dia.weekday() == QUARTA and (dia - PRIMEIRA_QUARTA_DO_MAGNO).days % 14 == 0


def numero_da_publicacao(dia: date) -> int:
    """Quantos dias de publicação há entre a origem da contagem e `dia`.

    É o "passo" da rotação: um a mais a cada dia de publicação, e não a cada dia
    do calendário. Os dias de folga contam como o passo da próxima publicação,
    para que "ver o card de hoje mesmo assim" mostre algo plausível.

    A semana tem exatamente 4 publicações, então a conta é por semanas inteiras
    (`// 7`, a divisão inteira) mais as publicações da semana corrente.
    """
    dias = (dia - ORIGEM_DA_CONTAGEM).days
    semanas, resto = divmod(dias, 7)
    inicio = ORIGEM_DA_CONTAGEM + timedelta(days=semanas * 7)
    na_semana = sum(1 for i in range(resto) if publica_em(inicio + timedelta(days=i)))
    return semanas * len(DIAS_DE_PUBLICAR) + na_semana


def escolher_magno(
    escopos: list[NumerosDoMagno], *, ocorrencia: int
) -> Optional[EscolhaDoMagno]:
    """Escolhe a variante e o escopo do card D, ou `None` se nada impressiona.

    `escopos` traz os quatro jogos juntos (`jogo` None) e cada jogo à parte.

    - **D1, a placa** ("estamos há N dias sem o Magno perder"): vale quando os
      dias sem perder chegam ao limite.
    - **D2, o placar do período** ("N partidas, 0 derrotas"): vale quando o
      período tem partidas suficientes e **nenhuma** derrota. Com uma derrota que
      seja, o placar não impressiona, e ele não sai.

    Preferência: os quatro jogos juntos antes de um jogo só (é o feito maior);
    entre jogos, o de número maior. A variante alterna a cada ocorrência (par = a
    placa, ímpar = o placar), para o mesmo card não sair duas vezes seguidas; se a
    preferida não vale, vale a outra.
    """

    # A chave de ordenação é uma tupla: o Python compara o 1º item e, no empate,
    # o 2º. `n.jogo is not None` é False (0) para os quatro juntos, que vêm
    # primeiro; o número com sinal de menos põe o MAIOR na frente.
    placas = sorted(
        (n for n in escopos if n.dias_sem_perder >= LIMITE_DIAS_SEM_PERDER),
        key=lambda n: (n.jogo is not None, -n.dias_sem_perder),
    )
    placares = sorted(
        (
            n
            for n in escopos
            if n.partidas_no_periodo >= LIMITE_PARTIDAS_NO_PERIODO
            and n.derrotas_no_periodo == 0
        ),
        key=lambda n: (n.jogo is not None, -n.partidas_no_periodo),
    )
    opcoes = [("placa", placas), ("placar", placares)]
    if ocorrencia % 2 == 1:
        opcoes.reverse()
    for variante, lista in opcoes:
        if lista:
            return EscolhaDoMagno(variante=variante, numeros=lista[0])
    return None


def montar_agenda(
    dia: date, *, escopos_do_magno: Optional[list[NumerosDoMagno]] = None
) -> Agenda:
    """A agenda de um dia de publicação.

    Os stories saem **sempre**, mesmo num dia de folga (com `publica_hoje`
    falso): a página tem o botão "ver o card de hoje mesmo assim".

    - Quarta do Magno, com números que impressionam: o card D no lugar do C.
    - Domingo: o C e, em segundo, o E (o pedido de ajuda).
    - Os outros: só o C.
    """
    n = numero_da_publicacao(dia)
    papel = PAPEIS[n % len(PAPEIS)]
    escolha = None
    if e_quarta_do_magno(dia) and escopos_do_magno:
        # A ocorrência do Magno (0, 1, 2...) decide a variante preferida.
        ocorrencia = (dia - PRIMEIRA_QUARTA_DO_MAGNO).days // 14
        escolha = escolher_magno(escopos_do_magno, ocorrencia=ocorrencia)

    if escolha is not None:
        primeiro = Story(
            card="magno", papel=papel, legenda=LEGENDAS_MAGNO[n % len(LEGENDAS_MAGNO)]
        )
    else:
        primeiro = Story(
            card="convite",
            papel=papel,
            layout=LAYOUTS_CONVITE[n % len(LAYOUTS_CONVITE)],
            legenda=LEGENDAS_CONVITE[n % len(LEGENDAS_CONVITE)],
        )
    stories = [primeiro]
    if dia.weekday() == DOMINGO:
        # O E vai noutro papel, para os dois stories do domingo não se repetirem.
        stories.append(
            Story(card="ajuda", papel=PAPEIS[(n + 1) % len(PAPEIS)], legenda=LEGENDA_AJUDA)
        )
    return Agenda(
        dia_publicacao=dia,
        publica_hoje=publica_em(dia),
        proxima_publicacao=proxima_publicacao(dia),
        stories=stories,
        magno=escolha,
    )

"""O JUIZ: liga a linha de chegada aos motores de cada jogo (T029).

⚠️ **Este arquivo se chamava `juiz_do_desafio.py`, e o cadeado 2 o recusou** — com
razao. A camada de motores **nao conhece desafio** (RF-DES-165): ela julga uma
fita contra uma linha de chegada, e quem chama isso de "desafio" e a coleção que
a consome. O nome novo diz o que a peca faz, nao para quem ela serve.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO MORA AQUI, E NAO EM `nucleo/`
═══════════════════════════════════════════════════════════════════════════

`motores/nucleo/` **nao conhece jogo nenhum** — e o cadeado 2 garante isso. Ele
tem o avaliador de chegada (que so sabe comparar números) e o medidor por fita
(que so sabe fechar janelas), e nenhum dos dois importa Pontinhos ou damas.

Alguém, porém, precisa saber que `co_jogo = "pontinhos"` significa reproduzir uma
sequência de traços, e que `"damas"` significa aplicar lances sobre uma FEN. Esse
alguém e este arquivo, e ele mora **um nível acima** do núcleo, ao lado das pastas
dos jogos — a mesma posição que `app_router.dart` ocupa no aplicativo, importando
as telas dos jogos sem que elas o conheçam.

⛔ **E ele continua nao sendo rota** (RF-DES-166). `motores/` e camada
**importada** pelo job; nada aqui serve HTTP.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE ARQUIVO NAO FAZ
═══════════════════════════════════════════════════════════════════════════

⛔ **Ele nao compara a fita com o gabarito.** O árbitro julga o **objetivo**, nao
a semelhança com a solução de referência: um caminho diferente do gabarito que
cumpra o objetivo cumpriu o objetivo. O gabarito serve para ensinar depois, e nao
para julgar.

⛔ **Ele nao decide XP.** Devolve medidas; quem converte e a coleção.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .damas import feitos_damas
from .damas.motor_damas import EstadoDamas, MotorDamas
from .nucleo.chegada import LinhaDeChegada
from .nucleo.medidor_por_fita import Julgamento, julgar
from .pontinhos import feitos_pontinhos
from .pontinhos.motor_pontinhos import EstadoPontinhos


class JogoDesconhecido(ValueError):
    """`co_jogo` que este juiz nao sabe reproduzir.

    ⚠️ Falha alto de propósito. Um jogo novo que chegasse aqui sem medidor
    devolveria "nao cumpriu" para todo mundo — um desafio impossível, sem erro
    nenhum no log.
    """


def _medidor_do_pontinhos(
    posicao: Mapping[str, Any],
    fita: Sequence[Mapping[str, Any]],
    jogador: int,
):
    """Devolve a função `medir_ate` do Pontinhos.

    A posição inicial e uma **sequência de lances** (`co_formato_posicao =
    'sequencia_lances'`), e a fita continua essa mesma sequência: as duas viram
    uma lista só, reproduzida pelo motor do começo.

    ⚠️ E por isso que o Pontinhos nao cabe numa matriz: a posse de uma caixa e
    **histórico**, e de quem e a vez depende de quem fechou caixa no caminho.
    """
    preparacao = tuple(lance["lance"] for lance in posicao["lances"])
    base = EstadoPontinhos(lances=preparacao)
    # Força a reprodução agora: uma posição inicial inválida e defeito do
    # DESAFIO, e precisa estourar antes de a fita de alguém ser julgada.
    base.placar

    def medir_ate(quantos: int) -> dict[str, float]:
        estado = EstadoPontinhos(
            lances=preparacao + tuple(l["lance"] for l in fita[:quantos])
        )
        # Quantos desses lances foram do jogador do desafio.
        meus = sum(1 for l in fita[:quantos] if l["jogador"] == jogador)
        return feitos_pontinhos.medir(
            base, estado, jogador=jogador, lances_do_jogador=meus
        )

    return medir_ate


def _medidor_das_damas(
    posicao: Mapping[str, Any],
    fita: Sequence[Mapping[str, Any]],
    jogador: int,
    co_modalidade: str,
):
    """Devolve a função `medir_ate` das damas.

    A posição inicial e uma **FEN**, e nao uma sequência: nas damas cada peça
    carrega a sua cor na própria casa, e a FEN já traz de quem e a vez no prefixo.
    """
    motor = MotorDamas(co_modalidade=co_modalidade)
    inicial = EstadoDamas(co_modalidade=co_modalidade, fen_inicial=posicao["fen"])

    def medir_ate(quantos: int) -> dict[str, float]:
        return feitos_damas.medir(
            motor,
            inicial,
            [l["lance"] for l in fita[:quantos]],
            jogador=jogador,
        )

    return medir_ate


def julgar_desafio(
    *,
    co_jogo: str,
    js_posicao_inicial: Mapping[str, Any],
    js_chegada: Mapping[str, Any],
    fita: Sequence[Mapping[str, Any]],
    jogador: int = 1,
    co_modalidade: str = "brasileira",
    predicados: Mapping[str, Any] | None = None,
) -> Julgamento:
    """Julga uma tentativa: reproduz a fita e responde se o objetivo caiu.

    Args:
        co_jogo: `pontinhos` ou `damas`.
        js_posicao_inicial: a posição de onde a fita parte.
        js_chegada: a linha de chegada, no formato de `desafio.tb001_desafio`.
        fita: os lances, no vocabulário do log.
        jogador: de quem e o desafio. `+1` por padrão — o desafio e sempre de
            quem esta jogando, e o `-1` existe para os casos de damas em que a
            posição inicial põe a pessoa com as pretas.
        co_modalidade: só para as damas.
        predicados: as respostas dos predicados, quando a chegada os consulta.

    Returns:
        O [Julgamento], com veredito, feitos e o lance em que o objetivo caiu.

    ⚠️ **A validação da chegada acontece aqui, uma vez.** Se `js_chegada` estiver
    malformada, sobe `ChegadaInvalida` — e isso e defeito do desafio, nao da
    tentativa de quem jogou.
    """
    chegada = LinhaDeChegada.de_dado(js_chegada)

    if co_jogo == "pontinhos":
        medir_ate = _medidor_do_pontinhos(js_posicao_inicial, fita, jogador)
    elif co_jogo == "damas":
        medir_ate = _medidor_das_damas(
            js_posicao_inicial, fita, jogador, co_modalidade
        )
    else:
        raise JogoDesconhecido(
            f"nao ha medidor para o jogo {co_jogo!r}. ⚠️ Jogo novo entra com "
            "medidor e com vetores de verificação, ou nao e publicável."
        )

    return julgar(
        chegada=chegada,
        fita=fita,
        jogador=jogador,
        medir_ate=medir_ate,
        predicados=predicados,
    )

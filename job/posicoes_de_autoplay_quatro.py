"""T117 (spec 010) - de onde vem a POSICAO DE PARTIDA de um desafio do Quatro.

═══════════════════════════════════════════════════════════════════════════
DO AUTOPLAY MAGNO × TEX, E NAO DE LANCES SORTEADOS (RF-QTR-162)
═══════════════════════════════════════════════════════════════════════════

A mesma licao do Pontinhos (`posicoes_de_autoplay_pontinhos.py`, §8h): uma
posicao montada com lances ao acaso e uma posicao que dois jogadores quase
nunca alcancam, e um desafio tirado dela ensina a resolver uma partida que
ninguem joga. O acervo deste modulo sao partidas inteiras do **Magno contra o
Tex**, jogadas pelo executavel do motor (o mesmo codigo do aparelho), e quem o
constroi e `scripts/extrair_posicoes_de_autoplay_quatro.py`.

═══════════════════════════════════════════════════════════════════════════
⚠️ O ACERVO GUARDA A PARTIDA INTEIRA, E NAO SO A POSICAO
═══════════════════════════════════════════════════════════════════════════

No Pontinhos bastava o conjunto de tracos. Aqui a posicao e um PREFIXO da
partida, e o resto dela - a **continuacao** - tambem serve: a prova do
`quatro_bloquear` (`job/provas_quatro.py`) conta, nessa continuacao, quantas
ameacas o lado de quem resolve bloqueou. Sem ela o tipo nao teria como dizer
que o tabuleiro gera ameacas a bloquear.

⚠️ E como a posicao e um prefixo, cada partida de N lances entrega N-1 posicoes
(o tabuleiro vazio e a posicao final nao servem: uma nao tem nada jogado, a
outra ja acabou). Partidas diferentes com a mesma abertura dividem os prefixos
curtos - por isso o sorteio e de PARTIDA e de COMPRIMENTO, e o script imprime
quantas posicoes DISTINTAS ha por comprimento.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE ESTE MODULO NAO FAZ
═══════════════════════════════════════════════════════════════════════════

⛔ **Nao sorteia a semente**: o `random.Random` chega pronto, semeado pelo dia,
como no Pontinhos (a idempotencia de T038).
⛔ **Nao valida a sequencia**: quem reproduz lance a lance e
`posicao_inicial.do_quatro()`, pelo arbitro. Uma segunda validacao aqui seria a
segunda fonte da verdade.
"""

from __future__ import annotations

import functools
import json
import random
from dataclasses import dataclass
from pathlib import Path

from motores.quatro.motor_quatro import ler_sequencia

# `parents[1]` sobe de `job/este_arquivo.py` para a raiz do backend.
RAIZ = Path(__file__).resolve().parents[1]

#: A pasta dos acervos do Quatro. Um arquivo por modalidade: partidas de uma
#: modalidade nao sao posicoes de outra (o tabuleiro e as regras mudam).
PASTA_DO_ACERVO = RAIZ / "dados" / "jogo_quatro"

#: A versao do formato do arquivo. ⚠️ Sobe quando a FORMA muda; o conteudo
#: (outras partidas) nao sobe nada.
VERSAO_DO_ACERVO = 1


def caminho_do_acervo(co_modalidade: str) -> Path:
    """O arquivo das partidas daquela modalidade."""
    return PASTA_DO_ACERVO / f"partidas_de_autoplay_{co_modalidade}.json"


class SemPosicaoDeAutoplay(RuntimeError):
    """Nenhuma partida do acervo alcanca o comprimento pedido sem ter acabado.

    ⚠️ **Falha alto de proposito**, como no Pontinhos: o caminho natural para
    este erro e um editorial pedindo um preparo que as partidas reais nao
    alcancam (o Magno costuma vencer o Tex antes do lance 30). Cair num sorteio
    as cegas reintroduziria o defeito que este modulo veio evitar.
    """


@dataclass(frozen=True, slots=True)
class PartidaDeAutoplay:
    """Uma partida inteira do acervo.

    Atributos:
        lances: os lances desde o tabuleiro vazio (`("s4", "s5", ...)`).
        magno: de que lado jogou o Magno (`+1` = jogador 1, quem abre).
        vencedor: `+1`, `-1` ou `0` (empate), como o arbitro o declarou.
    """

    lances: tuple[str, ...]
    magno: int
    vencedor: int


@dataclass(frozen=True, slots=True)
class PosicaoDeAutoplay:
    """Uma posicao sorteada: o prefixo da partida e o resto dela.

    Atributos:
        lances: a posicao de partida do desafio (o prefixo).
        continuacao: o que o autoplay jogou dali ate o fim. ⚠️ E jogo do Magno
            contra o Tex, e nao da pessoa contra o adversario do dia: serve para
            dizer o que o tabuleiro COMPORTA (as ameacas do `quatro_bloquear`),
            e nao o que vai acontecer.
    """

    lances: tuple[str, ...]
    continuacao: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcervoQuatro:
    """As partidas de uma modalidade, prontas para o sorteio.

    Atributos:
        co_modalidade: a modalidade das partidas.
        co_versao_motor: o motor que as jogou (procedencia; um motor novo nao as
            invalida - continuam partidas legais -, mas diz de onde vieram).
        partidas: na ordem do arquivo. ⚠️ A ordem faz parte do sorteio: a mesma
            semente escolhe a mesma partida so enquanto a lista for a mesma.
    """

    co_modalidade: str
    co_versao_motor: str
    partidas: tuple[PartidaDeAutoplay, ...]


@functools.lru_cache(maxsize=None)
def carregar(co_modalidade: str) -> AcervoQuatro:
    """Le o acervo da modalidade do disco, uma vez por processo.

    Raises:
        FileNotFoundError: com a receita de como reconstruir o arquivo.
        ValueError: o arquivo e de outra modalidade ou de outro formato.
    """
    caminho = caminho_do_acervo(co_modalidade)
    if not caminho.is_file():
        raise FileNotFoundError(
            f"o acervo de partidas do Quatro nao esta no disco ({caminho}).\n"
            "Reconstrua com, na raiz do backend:\n"
            "  .venv\\Scripts\\python -u scripts\\extrair_posicoes_de_autoplay_quatro.py"
        )
    dado = json.loads(caminho.read_text(encoding="utf-8"))
    if dado.get("versao") != VERSAO_DO_ACERVO:
        raise ValueError(
            f"{caminho.name}: formato {dado.get('versao')!r}, e este modulo le o "
            f"{VERSAO_DO_ACERVO}."
        )
    if dado.get("co_modalidade") != co_modalidade:
        # ⛔ Um arquivo renomeado a mao entregaria posicoes de outro tabuleiro, e
        # o arbitro so as recusaria se o lance caisse fora dele.
        raise ValueError(
            f"{caminho.name} traz partidas de {dado.get('co_modalidade')!r}, e "
            f"foi pedido {co_modalidade!r}."
        )
    return AcervoQuatro(
        co_modalidade=co_modalidade,
        co_versao_motor=dado["co_versao_motor"],
        partidas=tuple(
            PartidaDeAutoplay(
                lances=ler_sequencia(p["lances"]),
                magno=int(p["magno"]),
                vencedor=int(p["vencedor"]),
            )
            for p in dado["partidas"]
        ),
    )


def sortear(
    sorteio: random.Random,
    *,
    co_modalidade: str,
    minimo: int,
    maximo: int,
    acervo: AcervoQuatro | None = None,
) -> PosicaoDeAutoplay:
    """Uma posicao de autoplay com entre [minimo] e [maximo] lances jogados.

    Args:
        sorteio: o `random.Random` **ja semeado pelo dia**.
        co_modalidade: de que acervo sortear.
        minimo, maximo: a faixa de comprimento da posicao, inclusive.
        acervo: so para os testes; sem ele, `carregar(co_modalidade)`.

    ⚠️ **Uma FAIXA, e nao um numero so.** Com um comprimento fixo a vez seria
    sempre do mesmo jogador (a paridade decide quem joga), e os prefixos curtos
    de partidas com a mesma abertura seriam a mesma posicao. A faixa da as duas
    cores e mais posicoes distintas.

    ⚠️ **Primeiro a partida, depois o comprimento**, e so entre as partidas que
    vao alem do minimo: a posicao precisa de um lance a jogar, entao o prefixo
    tem de ser mais curto que a partida inteira.

    Raises:
        SemPosicaoDeAutoplay: nenhuma partida passa do minimo.
        ValueError: faixa invertida ou que comeca no tabuleiro vazio.
    """
    if minimo < 1 or maximo < minimo:
        raise ValueError(f"faixa de comprimento invalida: [{minimo}, {maximo}]")
    if acervo is None:
        acervo = carregar(co_modalidade)
    candidatas = [p for p in acervo.partidas if len(p.lances) > minimo]
    if not candidatas:
        mais_longa = max((len(p.lances) for p in acervo.partidas), default=0)
        raise SemPosicaoDeAutoplay(
            f"nenhuma partida do acervo de {co_modalidade} passa de {minimo} lances "
            f"(a mais longa tem {mais_longa}). Ajuste `nu_lances_de_preparo` no "
            "editorial."
        )
    partida = candidatas[sorteio.randrange(len(candidatas))]
    # O prefixo vai ate um lance antes do fim (`len - 1`), e nunca alem do maximo.
    teto = min(maximo, len(partida.lances) - 1)
    comprimento = sorteio.randint(minimo, teto)
    return PosicaoDeAutoplay(
        lances=partida.lances[:comprimento],
        continuacao=partida.lances[comprimento:],
    )


def posicoes_distintas_por_comprimento(acervo: AcervoQuatro) -> dict[int, int]:
    """Quantas posicoes DIFERENTES o acervo tem com cada comprimento.

    E o numero que o script de extracao imprime: prefixos curtos se repetem
    entre partidas com a mesma abertura, e o que importa para a fila e quantas
    posicoes distintas existem, e nao quantas partidas.
    """
    vistas: dict[int, set[tuple[str, ...]]] = {}
    for partida in acervo.partidas:
        for comprimento in range(1, len(partida.lances)):
            vistas.setdefault(comprimento, set()).add(partida.lances[:comprimento])
    return {n: len(prefixos) for n, prefixos in sorted(vistas.items())}

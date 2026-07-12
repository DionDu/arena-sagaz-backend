"""Reconstrói as matrizes do tabuleiro a partir da SEQUÊNCIA DE ARESTAS.

**Por que isto existe.** Até a migração 0006, cada lance guardava no banco as duas
matrizes do tabuleiro (`ar_tabuleiro_antes` e `ar_tabuleiro_apos`) — ~316 bytes por
lance, 31 lances por partida. Só que elas são **100% deriváveis**: dado o tamanho do
tabuleiro e a sequência ordenada de arestas (quem jogou o quê, em que ordem), o
estado em qualquer ponto da partida é uma consequência determinística das regras do
jogo. Guardá-las era pagar disco por algo que sabemos recalcular — e era o **maior**
item da conta (a 5.000 partidas/dia, sozinho respondia por ~1,9 GB/mês).

Então: o banco guarda só as **arestas**, e este módulo devolve as matrizes quando
elas forem necessárias — na exportação do dataset de treino e, no futuro, num
relatório Web da partida.

**O contrato da CNN NÃO muda.** A codificação (0=vazio, ±1=jogador, 8=ponto) é a
mesma de sempre, definida em ``contrato_codificacao_pontinhos.json``. Nós apenas
deixamos de PERSISTIR o que dá para recalcular. A "lei da física" do jogo vive em
``EstadoTabuleiro.aplicar_traco`` — que é reaproveitada aqui, e não reimplementada:
duas cópias da regra do jogo divergiriam silenciosamente um dia.

**Integridade.** Sem as matrizes gravadas, uma jogada faltante deixa de ser
detectável de qualquer outra forma — a reconstrução simplesmente produziria um
tabuleiro *plausível porém errado*, e o erro entraria calado no dataset de treino.
Por isso a validação aqui é **estrita** e a falha é **barulhenta**
(``PartidaInconsistenteError``): é melhor recusar uma partida do que envenenar o
treino da rede.

Ver o contrato completo em ``docs/redesenho_schema_log_treino.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

import numpy as np

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import TAMANHOS, EstadoTabuleiro


class PartidaInconsistenteError(ValueError):
    """A sequência de arestas não descreve uma partida válida.

    Levantada quando a reconstrução é impossível ou seria enganosa: ordens
    faltando, aresta repetida, aresta que não existe naquele tabuleiro. Nunca
    "conserte" a partida em silêncio — o dado ruim precisa aparecer.
    """


@dataclass(frozen=True)
class JogadaReconstruida:
    """Um lance com as duas matrizes recalculadas.

    - [nu_ordem]: a ordem do lance na partida (1 = primeiro).
    - [co_aresta]: o traço jogado (`'H_0_1'`).
    - [co_jogador]: +1 ou −1 (valores CONTRATUAIS da matriz da CNN).
    - [tabuleiro_antes]: o estado ANTES deste lance (o que a CNN "viu" para decidir).
    - [tabuleiro_apos]: o estado DEPOIS deste lance.
    - [nu_caixas_fechadas]: quantas caixas o lance fechou (0, 1 ou 2).
    """

    nu_ordem: int
    co_aresta: str
    co_jogador: int
    tabuleiro_antes: np.ndarray
    tabuleiro_apos: np.ndarray
    nu_caixas_fechadas: int


def reconstruir_partida(
    co_variante: str,
    jogadas: Iterable[tuple[int, str, int]],
) -> list[JogadaReconstruida]:
    """Recalcula as matrizes de TODOS os lances de uma partida.

    [co_variante] é o tamanho do tabuleiro (`'pequeno'`/`'medio'`/`'grande'`), que
    vem de ``partida.tb001_partida.co_variante``. [jogadas] são as tuplas
    `(nu_ordem, co_aresta, co_jogador)` de ``jogo_pontinhos.tb002_jogada`` — em
    qualquer ordem: nós ordenamos e conferimos.

    Levanta [PartidaInconsistenteError] se a sequência não fizer sentido.
    """
    return list(iter_reconstruir_partida(co_variante, jogadas))


def iter_reconstruir_partida(
    co_variante: str,
    jogadas: Iterable[tuple[int, str, int]],
) -> Iterator[JogadaReconstruida]:
    """Versão preguiçosa de [reconstruir_partida] — devolve um lance por vez.

    Útil na exportação do dataset: milhões de lances não precisam caber na memória
    de uma vez só.
    """
    if co_variante not in TAMANHOS:
        raise PartidaInconsistenteError(
            f"Variante de tabuleiro desconhecida: {co_variante!r}. "
            f"Esperado um de {sorted(TAMANHOS)}."
        )

    ordenadas = sorted(jogadas, key=lambda j: j[0])
    _validar_ordens(ordenadas)

    estado = EstadoTabuleiro.de_tamanho(co_variante)
    # Todas as arestas que existem NESTE tabuleiro. Serve para acusar uma aresta
    # inválida com uma mensagem clara, em vez de deixar o numpy estourar um
    # IndexError críptico (ou, pior, gravar num índice que existe mas é outra coisa).
    validas = set(estado.tracos_disponiveis())

    for nu_ordem, co_aresta, co_jogador in ordenadas:
        if co_aresta not in validas:
            raise PartidaInconsistenteError(
                f"Lance {nu_ordem}: a aresta {co_aresta!r} não existe no tabuleiro "
                f"{co_variante!r}."
            )
        if co_jogador not in (1, -1):
            # ±1 é contratual (é o que aparece na matriz da CNN). Um 0 ou um 2 aqui
            # corromperia o tensor de treino sem levantar erro nenhum.
            raise PartidaInconsistenteError(
                f"Lance {nu_ordem}: co_jogador={co_jogador!r}; esperado +1 ou -1."
            )

        # O "antes" é o estado atual — precisa ser uma CÓPIA: `estado.matriz` é
        # mutado no lugar pelo `aplicar_traco`, e sem a cópia todos os lances
        # devolveriam a mesma matriz (a final).
        antes = estado.matriz.copy()
        try:
            fechadas = estado.aplicar_traco(co_aresta, co_jogador)
        except ValueError as erro:
            # aplicar_traco recusa traço já ocupado — aresta repetida na partida.
            raise PartidaInconsistenteError(
                f"Lance {nu_ordem}: {erro}"
            ) from erro

        yield JogadaReconstruida(
            nu_ordem=nu_ordem,
            co_aresta=co_aresta,
            co_jogador=co_jogador,
            tabuleiro_antes=antes,
            tabuleiro_apos=estado.matriz.copy(),
            nu_caixas_fechadas=fechadas,
        )


def _validar_ordens(ordenadas: Sequence[tuple[int, str, int]]) -> None:
    """Exige `nu_ordem` contígua de 1 a N, sem furos nem repetições.

    **Este é o cheque mais importante do módulo.** Uma jogada que não chegou à nuvem
    (falha de rede, evento perdido) produziria um tabuleiro *plausível mas errado* —
    e nada denunciaria isso, já que as matrizes originais não existem mais. A
    contiguidade das ordens é a única testemunha de que a partida está inteira.
    """
    if not ordenadas:
        raise PartidaInconsistenteError("Partida sem nenhuma jogada.")

    ordens = [j[0] for j in ordenadas]
    esperado = list(range(1, len(ordens) + 1))
    if ordens != esperado:
        faltando = sorted(set(esperado) - set(ordens))
        repetidas = sorted({o for o in ordens if ordens.count(o) > 1})
        detalhe = []
        if faltando:
            detalhe.append(f"faltam as ordens {faltando}")
        if repetidas:
            detalhe.append(f"ordens repetidas {repetidas}")
        if not detalhe:
            detalhe.append(f"ordens fora do esperado: {ordens}")
        raise PartidaInconsistenteError(
            "Sequência de jogadas incompleta — " + "; ".join(detalhe) + ". "
            "A partida NÃO pode ser reconstruída com segurança."
        )

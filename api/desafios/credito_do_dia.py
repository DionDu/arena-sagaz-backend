"""O CREDITO NA CONTA — pontuar e uma coisa, creditar e outra (T082).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO DECIDE, EM UMA FRASE
═══════════════════════════════════════════════════════════════════════════

Quanto de um XP **ja pontuado** entra na conta da pessoa hoje — e quanto o teto
de 30/dia do Desafio do Dia corta (RF-DES-047, RF-DES-181).

═══════════════════════════════════════════════════════════════════════════
⚠️ O TETO E DA COLECAO, E NUNCA DO DESAFIO (RF-DES-155)
═══════════════════════════════════════════════════════════════════════════

A resolucao pontua de 18 a 30 e **nao tem teto nenhum**: o `nu_xp` gravado em
`tb003_resolucao` e o que o quadro ordena, e ele nunca e cortado. O teto de 30 e
atributo do **Desafio do Dia**, a colecao — e por isso ele e aplicado aqui, no
credito, e entra no extrato como uma linha de `ajuste` **negativa**. E o que
deixa a tela dizer *"voce fez 37, o teto do dia cortou 7"* em vez de esconder a
conta.

O caso que o teto existe para cortar e um so, e acontece todo dia: a pessoa
tenta, falha (+10 de consolo, RF-DES-041), tenta de novo e resolve (18 a 30).
Sem o teto, o mesmo desafio pagaria ate 40 a quem errou e 30 a quem acertou de
primeira — errar de proposito viraria estrategia.

═══════════════════════════════════════════════════════════════════════════
⚠️ A CONTA NAO DEPENDE DA ORDEM DE CHEGADA
═══════════════════════════════════════════════════════════════════════════

A fila do aparelho nao garante que o consolo chegue antes da resolucao. Por
isso cada credito e `min(valor, espaco que sobra no dia)`: consolo e depois
resolucao dao `10 + 20`, resolucao e depois consolo dao `27 + 3` — e o dia
fecha em 30 nos dois casos.

Puro de proposito: sem banco, sem rede. Recebe inteiros, devolve inteiros.
"""

from __future__ import annotations

from dataclasses import dataclass

from api.desafios.modelos_evento import XP_TETO_DO_DIA


@dataclass(frozen=True, slots=True)
class CreditoDoDia:
    """O que um evento do dia (consolo ou resolucao) poe na conta.

    Atributos:
        valor: o XP que o evento **pontuou** — 10 no consolo, 18 a 30 na
            resolucao. ⛔ Nunca cortado: e ele que o quadro e o extrato mostram.
        corte: quanto o teto do dia tirou dele, sempre >= 0. ⚠️ Vira a linha de
            `ajuste` com o sinal trocado — e so existe linha quando e > 0.
    """

    valor: int
    corte: int

    @property
    def creditado(self) -> int:
        """O que de fato entra em `nu_xp_total`: o valor menos o corte."""
        return self.valor - self.corte


def credito_do_dia(
    *, ja_creditado: int, valor: int, teto: int = XP_TETO_DO_DIA
) -> CreditoDoDia:
    """Quanto de [valor] cabe no dia, dado o que ja entrou.

    Args:
        ja_creditado: o que o Desafio do Dia ja pos na conta **neste dia**,
            antes deste evento — consolo, resolucao e ajustes somados.
        valor: o que este evento pontuou.
        teto: o teto da colecao. ⚠️ Parametro so para o teste poder conferir
            que a conta segue o teto, e nao um `30` escrito nela.

    Returns:
        O valor intacto e o corte que o teto impoe.

    Raises:
        ValueError: valor negativo. ⚠️ E defeito de quem chamou: nenhum evento
            do dia pontua negativo (o consolo e constante, e a resolucao ja
            passou pelo piso de 18 no modelo do envio).

    ⚠️ **Um dia que ja passou do teto NAO e recusado**: ele credita zero. So
    chega aqui com a soma do dia montada errado — e esta funcao roda dentro da
    rota do envio, onde recusar faria o outbox do aparelho tentar de novo ate
    desistir, por um defeito que nao e da pessoa. Zero e a resposta que nunca
    paga acima do teto.
    """
    if valor < 0:
        raise ValueError(f"um evento do dia nao pontua negativo; veio {valor}")
    # Os dois `max(0, ...)`: um `ja_creditado` negativo nao abre espaco acima do
    # teto, e um acima do teto nao deixa o espaco negativo.
    espaco = max(0, teto - max(0, ja_creditado))
    return CreditoDoDia(valor=valor, corte=max(0, valor - espaco))

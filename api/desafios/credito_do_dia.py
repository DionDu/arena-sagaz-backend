"""O CREDITO NA CONTA — pontuar e uma coisa, creditar e outra (T082).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO DECIDE, EM UMA FRASE
═══════════════════════════════════════════════════════════════════════════

Quanto de um XP **ja pontuado** entra na conta da pessoa hoje — e quanto vira a
linha de `ajuste`, negativa, para o extrato fechar com a conta.

═══════════════════════════════════════════════════════════════════════════
⚠️ O DIA VALE O MAIOR DOS SEUS EVENTOS (o consolo e PISO, e nao soma)
═══════════════════════════════════════════════════════════════════════════

Decisao do dono em 02/10/2026 (`arena-sagaz-frontend/docs/DECISOES-do-dono.md`
§8zp). Um dia tem no maximo dois eventos que creditam: o **consolo** de 10 da
primeira falha (RF-DES-041) e a **resolucao**, de 12 a 30. O que entra na conta
e o **maior** deles — e nunca a soma:

* so tentou: 10;
* resolveu de primeira com 27: 27;
* falhou, e depois resolveu com 25: 10 na falha, mais 15 na resolucao = 25.

Ate 02/10/2026 os dois SOMAVAM, cortados num teto de 30 (§8o). O dono achou
injusto, com razao: a mesma partida resolvida de primeira punha 27 na conta, e
resolvida na segunda tentativa punha 30 — falhar de proposito pagava mais.

⚠️ **E quem resolve fica sempre acima de quem so tentou**, por mais tentativas
que gaste: a pontuacao tem piso de 12 por construcao (`12 + 18 x Q`, `Q >= 0`),
e 12 > 10.

A resolucao continua pontuando de 12 a 30 e **nao e alterada**: o `nu_xp` de
`tb003_resolucao` e o que o quadro ordena. O que a regra muda e so o credito, e
o que o extrato mostra a mais (o consolo ja contado) vira a linha de `ajuste`.

O teto de 30 por dia (RF-DES-047) continua aqui como parametro: e atributo da
colecao, e hoje nada o alcanca (a pontuacao vai ate 30).

═══════════════════════════════════════════════════════════════════════════
⚠️ A CONTA NAO DEPENDE DA ORDEM DE CHEGADA
═══════════════════════════════════════════════════════════════════════════

A fila do aparelho nao garante que o consolo chegue antes da resolucao. Por
isso cada evento credita **so o que falta para chegar ao valor dele**:
`max(0, valor - ja_creditado)`. Consolo e depois resolucao de 25 dao `10 + 15`;
resolucao e depois consolo dao `25 + 0` — e o dia fecha em 25 nos dois casos.

Puro de proposito: sem banco, sem rede. Recebe inteiros, devolve inteiros.
"""

from __future__ import annotations

from dataclasses import dataclass

from api.desafios.modelos_evento import XP_TETO_DO_DIA


@dataclass(frozen=True, slots=True)
class CreditoDoDia:
    """O que um evento do dia (consolo ou resolucao) poe na conta.

    Atributos:
        valor: o XP que o evento **pontuou** — 10 no consolo, 12 a 30 na
            resolucao. ⛔ Nunca cortado: e ele que o quadro e o extrato mostram.
        corte: quanto dele nao entrou na conta, sempre >= 0 — o que ja estava
            creditado no dia (o consolo, quando a resolucao chega depois dele;
            a resolucao inteira, quando o consolo chega depois dela). ⚠️ Vira
            a linha de `ajuste` com o sinal trocado, e so existe linha quando
            e > 0.
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
    """Quanto de [valor] entra no dia, dado o que ja entrou: o que falta.

    Args:
        ja_creditado: o que o Desafio do Dia ja pos na conta **neste dia**,
            antes deste evento — consolo, resolucao e ajustes somados.
        valor: o que este evento pontuou.
        teto: o teto da colecao. ⚠️ Parametro so para o teste poder conferir
            que a conta segue o teto, e nao um `30` escrito nela.

    Returns:
        O valor intacto e o corte: o que dele ja estava creditado.

    Raises:
        ValueError: valor negativo. ⚠️ E defeito de quem chamou: nenhum evento
            do dia pontua negativo (o consolo e constante, e a resolucao ja
            passou pelo piso de 12 no modelo do envio).

    ⚠️ **Um evento que chega com o dia ja acima do valor dele NAO e recusado**:
    ele credita zero. E o caminho normal do consolo que chega depois da
    resolucao, e e tambem o de uma soma do dia montada errado — e esta funcao
    roda dentro da rota do envio, onde recusar faria o outbox do aparelho tentar
    de novo ate desistir, por um defeito que nao e da pessoa.
    """
    if valor < 0:
        raise ValueError(f"um evento do dia nao pontua negativo; veio {valor}")
    # O dia vale o MAIOR evento (preso no teto da colecao): este evento so
    # credita o que falta para o dia chegar ao valor dele. `max(0, ...)` por
    # fora: um evento menor que o ja creditado entra com zero, e nunca tira XP.
    # O `max(0, ja_creditado)` de dentro: uma soma negativa (defeito) nao faz o
    # evento pagar acima do proprio valor.
    creditado = max(0, min(valor, teto) - max(0, ja_creditado))
    return CreditoDoDia(valor=valor, corte=valor - creditado)

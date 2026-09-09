"""Orçamento de busca: teto de nós, teto de tempo e cancelamento (RF-DES-163).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE HOJE, E NÃO "QUANDO PRECISAR"
═══════════════════════════════════════════════════════════════════════════

**Hoje** protege o job de uma posição patológica. O gerador mede dezenas de
candidatos × 20 execuções × 4 níveis (Bloco D): basta uma posição em que a busca
exploda para o container passar da janela e o desafio do dia não sair. Um teto que
não existe é um teto infinito.

**Amanhã** é o que permite responder dentro do prazo de um turno, quando a jogada
automática entrar (RF-DES-167). Acrescentar orçamento depois exigiria mexer no
laço de busca de cada motor — que é justamente o código que não se quer tocar.

═══════════════════════════════════════════════════════════════════════════
"SEM DEIXAR ESTADO SUJO" — O QUE ISSO SIGNIFICA AQUI
═══════════════════════════════════════════════════════════════════════════

O cancelamento é **cooperativo**: ninguém mata a busca por fora. O motor consulta
`cancelado()` no seu laço e **devolve o melhor lance que já encontrou**. Não há
`thread` interrompida no meio de uma escrita, nem estrutura pela metade — porque
o estado do motor é por valor (RF-DES-162) e o `Orcamento` não guarda nada do
jogo, só contagem e relógio.

⚠️ **O orçamento é de uso único.** Depois de estourar, ele continua estourado; um
lance novo pede um objeto novo (`para_o_proximo_lance()`). Reaproveitar um
orçamento zerando o contador seria o caminho mais curto para o teto silenciosamente
virar "por lance" quando alguém quis "por partida".

⚠️ **O relógio entra por parâmetro.** Sem isso, testar "estourou o tempo" exigiria
esperar de verdade — e um teste que dorme é um teste que alguém marca para pular.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

# Um relógio é qualquer função que devolva segundos crescentes. O padrão é
# `time.monotonic`, e não `time.time`: o monotônico não anda para trás quando o
# sistema operacional acerta a hora, e um teto de tempo que anda para trás vira
# um teto que não vale.
Relogio = Callable[[], float]


class BuscaCancelada(Exception):
    """Levantada por `verificar()` quando o orçamento acabou.

    ⚠️ É a alternativa para o motor que **não tem** um laço onde consultar
    `cancelado()` a cada passo — recursão profunda, por exemplo. O motor que puder
    cooperar deve preferir `cancelado()`, porque devolver o melhor lance
    encontrado é sempre melhor que não devolver nenhum.
    """


@dataclass(slots=True)
class Orcamento:
    """Quanto uma consulta ao papel *jogador* pode gastar.

    Satisfaz o protocolo `LimiteDeBusca` de `papeis.py` — estruturalmente, sem
    herdar dele.

    Atributos:
        nos_maximos: teto de nós visitados. `0` ou negativo é recusado na
            construção: um teto de zero nós não é "sem limite", é uma busca que
            não pode nem começar, e quase sempre é um parâmetro esquecido.
        segundos_maximos: teto de tempo de parede.
        relogio: de onde vem o tempo. Trocável em teste.

    Campos internos (com `_`): a contagem de nós, o instante de início e a
    marca de cancelamento externo.
    """

    nos_maximos: int
    segundos_maximos: float
    relogio: Relogio = time.monotonic

    # `field(init=False)` mantém estes fora do construtor: quem cria um orçamento
    # diz o teto, nunca o estado interno.
    _nos_gastos: int = field(default=0, init=False)
    _inicio: float | None = field(default=None, init=False)
    _cancelado_por_fora: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Recusa tetos que não fazem sentido, no momento da construção.

        Falhar aqui é muito mais barato que falhar no meio da geração do desafio
        do dia, quando a mensagem seria "nenhum candidato encontrado".
        """
        if self.nos_maximos <= 0:
            raise ValueError(
                f"nos_maximos precisa ser positivo (veio {self.nos_maximos}). "
                "Teto zero não é 'sem limite'."
            )
        if self.segundos_maximos <= 0:
            raise ValueError(
                f"segundos_maximos precisa ser positivo (veio {self.segundos_maximos})."
            )

    # ── O que o protocolo LimiteDeBusca pede ────────────────────────────────

    def cancelado(self) -> bool:
        """`True` quando a busca deve parar e devolver o que já tem.

        Três motivos, nesta ordem de custo: cancelamento externo (uma variável),
        teto de nós (uma comparação) e teto de tempo (uma leitura de relógio).
        A ordem importa porque este método é chamado milhares de vezes por lance.
        """
        if self._cancelado_por_fora:
            return True
        if self._nos_gastos >= self.nos_maximos:
            return True
        return self.segundos_gastos >= self.segundos_maximos

    # ── O que o motor usa durante a busca ───────────────────────────────────

    def contar_no(self, quantos: int = 1) -> None:
        """Registra nós visitados. O motor chama isto no seu laço.

        Aceita `quantos` para o motor que conta em lote (a cada N nós), o que
        custa menos que uma chamada por nó.
        """
        self._nos_gastos += quantos

    def verificar(self) -> None:
        """Levanta `BuscaCancelada` se o orçamento acabou.

        Para motores recursivos, onde não há um laço único em que consultar
        `cancelado()`.
        """
        if self.cancelado():
            raise BuscaCancelada(
                f"orçamento esgotado: {self._nos_gastos}/{self.nos_maximos} nós, "
                f"{self.segundos_gastos:.3f}/{self.segundos_maximos:.3f} s"
            )

    def cancelar(self) -> None:
        """Cancela por fora — o job desistindo deste candidato, por exemplo.

        Não interrompe nada sozinho: a busca só para quando **ela** consultar.
        """
        self._cancelado_por_fora = True

    # ── Leituras ────────────────────────────────────────────────────────────

    @property
    def nos_gastos(self) -> int:
        """Quantos nós já foram contados. Vai para o carimbo da medição."""
        return self._nos_gastos

    @property
    def segundos_gastos(self) -> float:
        """Há quanto tempo a busca começou. `0.0` antes do primeiro uso."""
        if self._inicio is None:
            return 0.0
        return self.relogio() - self._inicio

    def iniciar(self) -> "Orcamento":
        """Marca o instante zero e devolve a si mesmo, para encadear.

        ⚠️ **Chamar duas vezes é erro**, e é recusado: reiniciar o relógio no meio
        da busca daria à posição patológica exatamente o fôlego extra que o teto
        existe para negar.
        """
        if self._inicio is not None:
            raise RuntimeError(
                "este orçamento já foi iniciado. Para o lance seguinte, use "
                "para_o_proximo_lance()."
            )
        self._inicio = self.relogio()
        return self

    def para_o_proximo_lance(self) -> "Orcamento":
        """Um orçamento novo, com os mesmos tetos e o mesmo relógio.

        É como o teto vira "por lance" sem que ninguém precise zerar contador à
        mão — zerar à mão é o que transformaria, em silêncio, um teto de partida
        num teto de lance.
        """
        return Orcamento(
            nos_maximos=self.nos_maximos,
            segundos_maximos=self.segundos_maximos,
            relogio=self.relogio,
        )

    def resumo(self) -> dict[str, float | int | bool]:
        """O que gastou, em forma serializável — entra no carimbo da medição.

        Sem isto, "o Sagaz jogou mal nesta posição" e "o Sagaz não teve tempo de
        pensar nesta posição" ficariam indistinguíveis no banco.
        """
        return {
            "nos_maximos": self.nos_maximos,
            "nos_gastos": self._nos_gastos,
            "segundos_maximos": self.segundos_maximos,
            "segundos_gastos": round(self.segundos_gastos, 6),
            "estourou": self.cancelado(),
        }

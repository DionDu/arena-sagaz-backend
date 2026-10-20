"""O ADVERSÁRIO do Quatro em Linha no job: o personagem, com a política (T116).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA CLASSE EXISTE
═══════════════════════════════════════════════════════════════════════════

O job conversa com os motores por papéis (`motores/nucleo/papeis.py`): quem
prova o término e quem mede a régua pedem um JOGADOR com
`escolher_lance(estado, nivel, limite, semente)`, e um ÁRBITRO com as regras.
No Quatro as duas coisas moram em lugares diferentes, de propósito:

    o lance     →  o executável Dart (`JogadorDartQuatro.decidir`): byte a byte o
                   código que o aparelho joga, sem segunda escrita;
    as regras   →  o árbitro Python (`MotorQuatro`), que valida e não escolhe.

Esta classe é a costura, no molde de `motores/pontinhos/politica.JogadorPontinhos`:
ela satisfaz o papel de jogador e entrega o árbitro por uma propriedade, para
quem precisa SÓ das regras não receber um objeto que joga por acidente.

⚠️ **O `limite` é ignorado, e de propósito.** O teto de nós de cada personagem
mora no contrato do jogo (`contrato_quatro.parametros_do_personagem`), e é o
`decidir` quem o lê: um orçamento vindo do job faria a Pita do servidor pensar
diferente da Pita do aparelho, e o gabarito deixaria de ser o lance que a pessoa
vê. O orçamento só é contado (um nó por lance), como no Pontinhos.
"""

from __future__ import annotations

from typing import Any

from motores.nucleo.papeis import NivelDeMotor

from .jogador_dart_quatro import JogadorDartQuatro, jogador_compartilhado
from .motor_quatro import EstadoQuatro, MotorQuatro


class JogadorQuatro:
    """O personagem do Quatro em Linha, jogando pelo executável Dart.

    Args:
        co_modalidade: a modalidade do desafio. ⚠️ Sem valor padrão: um padrão
            faria o gabarito ser buscado por um regulamento enquanto o desafio
            publicado diz outro (o defeito do `MotorDamas()` sem modalidade).
        motor_dart: o processo do executável. `None` usa o da thread
            (`jogador_compartilhado`), que é o caminho do job.
    """

    co_jogo = "quatro"

    def __init__(
        self, co_modalidade: str, motor_dart: JogadorDartQuatro | None = None
    ) -> None:
        self._arbitro = MotorQuatro(co_modalidade)
        self._motor_dart = motor_dart

    @property
    def arbitro(self) -> MotorQuatro:
        """As REGRAS, para quem não escolhe lance (ver `JogadorPontinhos.arbitro`)."""
        return self._arbitro

    @property
    def motor_dart(self) -> JogadorDartQuatro:
        """O processo do executável, aberto na primeira vez que alguém pede."""
        if self._motor_dart is None:
            self._motor_dart = jogador_compartilhado()
        return self._motor_dart

    def decidir(
        self, estado: EstadoQuatro, nivel: NivelDeMotor, semente: int
    ) -> dict[str, Any]:
        """A resposta inteira do motor (lance, ação, nós), para quem a grava."""
        return self.motor_dart.decidir(
            lances=estado.sequencia,
            co_modalidade=estado.co_modalidade,
            nivel=nivel,
            semente=semente,
        )

    def escolher_lance(
        self,
        estado: EstadoQuatro,
        nivel: NivelDeMotor,
        limite=None,
        semente: int | None = None,
    ) -> str:
        """O lance daquele nível, reprodutível pela semente.

        Raises:
            ValueError: sem semente. ⚠️ O Pontinhos aceita `None`; aqui não, porque
                o `decidir` do executável a exige (sem ela, a Cacau jogaria
                diferente a cada pergunta, e a régua deixaria de medir).
        """
        if semente is None:
            raise ValueError("o Quatro em Linha joga só com a semente do lance")
        if limite is not None and hasattr(limite, "contar_no"):
            limite.contar_no(1)
        return self.decidir(estado, nivel, semente)["lance"]

    def aplicar(self, estado: EstadoQuatro, lance: str) -> EstadoQuatro:
        """Delega ao árbitro: é ele quem confere a legalidade."""
        return self._arbitro.aplicar(estado, lance)

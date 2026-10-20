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

from dataclasses import dataclass
from typing import Any

from motores.nucleo.papeis import NivelDeMotor

from .jogador_dart_quatro import JogadorDartQuatro, jogador_compartilhado
from .motor_quatro import EstadoQuatro, MotorQuatro


@dataclass(frozen=True, slots=True)
class DecisaoQuatro:
    """O lance escolhido e COMO ele foi escolhido (T117).

    A mesma forma da `Decisao` do Pontinhos (`lance` + `co_acao`), e é por ela
    que o gerador lê o motivo de cada lance do gabarito sem perguntar o jogo:
    `co_acao` é o código da política do motor (`busca_melhor`,
    `epsilon_aleatorio`, `bloqueio_perdido`...), o mesmo de
    `jogo_quatro.tb901_jogada_acao`. É ele que mostra, na curadoria, que um
    lance do adversário foi um descuido sorteado, e não o melhor que ele via.

    Atributos:
        lance: o lance na notação (`s4`).
        co_acao: o motivo, como o motor o devolveu.
        resposta: a resposta inteira do motor (nós, profundidade, avaliação),
            para quem a grava ou a compara.
    """

    lance: str
    co_acao: str
    resposta: dict[str, Any]


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
        """O processo do executável: o injetado, ou o DA THREAD que pergunta.

        ⛔ **O da thread não é guardado no objeto, e é isso que deixa a régua
        rodar em paralelo** (T117). A régua entrega o MESMO jogador a várias
        threads; se o 1º processo aberto ficasse guardado aqui, todas
        escreveriam no mesmo `stdin` e leriam respostas trocadas, sem erro
        nenhum. Pedir `jogador_compartilhado()` a cada lance custa a leitura de
        uma variável local da thread.
        """
        if self._motor_dart is not None:
            return self._motor_dart
        return jogador_compartilhado()

    def decidir(
        self, estado: EstadoQuatro, nivel: NivelDeMotor, semente: int
    ) -> DecisaoQuatro:
        """O lance do [nivel], com o motivo e a resposta inteira do motor."""
        resposta = self.motor_dart.decidir(
            lances=estado.sequencia,
            co_modalidade=estado.co_modalidade,
            nivel=nivel,
            semente=semente,
        )
        return DecisaoQuatro(
            lance=resposta["lance"], co_acao=resposta["acao"], resposta=resposta
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
        return self.decidir(estado, nivel, semente).lance

    def aplicar(self, estado: EstadoQuatro, lance: str) -> EstadoQuatro:
        """Delega ao árbitro: é ele quem confere a legalidade."""
        return self._arbitro.aplicar(estado, lance)

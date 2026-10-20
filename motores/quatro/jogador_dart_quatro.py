"""O JOGADOR do Quatro em Linha: o motor Dart do aparelho, compilado (T109).

═══════════════════════════════════════════════════════════════════════════
POR QUE O SERVIDOR NÃO TEM UM JOGADOR PYTHON
═══════════════════════════════════════════════════════════════════════════

O gabarito de um desafio é uma partida contra Cacau, Pita, Tex ou Magno, e a
pessoa tem de poder segui-la no aparelho lance a lance. As damas e o Pontinhos
chegaram a ter uma segunda escrita da política no servidor, e as duas
divergiram (no Pontinhos, sem erro nenhum). O Quatro em Linha nasce sem ela:
quem escolhe lance aqui é o executável `servidor_de_lances_quatro`, compilado
do mesmo pacote que o app embarca (`contracts/motor-quatro.md` §4).

═══════════════════════════════════════════════════════════════════════════
AS DUAS TRAVAS DA ABERTURA
═══════════════════════════════════════════════════════════════════════════

1. **O carimbo dos fontes**: o executável anuncia o SHA-256 dos arquivos de
   `lib/` com que foi compilado, e `ProcessoDart` o compara com o resumo dos
   fontes do ESPELHO. Divergiu: `MotorDartDivergente`, nomeando o arquivo.
2. **O contrato**: o executável recebe o contrato por `--contrato` e anuncia o
   SHA-256 dos bytes que leu; este módulo compara com o do espelho
   (`contrato_quatro.sha256_do_contrato`). Um executável apontado para outro
   contrato jogaria outro tabuleiro, ou o Magno com o teto da Cacau.

═══════════════════════════════════════════════════════════════════════════
O PEDIDO
═══════════════════════════════════════════════════════════════════════════

Os números do personagem (teto, ε, `percebe`, abertura do Magno) saem do
contrato pelo `contrato_quatro.parametros_do_personagem`, e não de quem chama:
quem chama diz o NÍVEL, e não os números. E o `limiteMs` vai sempre `null`: o
servidor joga só por nós, para o lance não depender da máquina.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from motores.nucleo import recursos_por_thread
from motores.nucleo.papeis import NivelDeMotor
from motores.nucleo.processo_dart import (
    MotorDartDivergente,
    MotorDartIndisponivel,
    ProcessoDart,
    caminho_do_executavel as _caminho_do_executavel,
    resumo_dos_fontes as _resumo_dos_fontes,
)
from motores.quatro import contrato_quatro

__all__ = [
    "MotorDartDivergente",
    "MotorDartIndisponivel",
    "JogadorDartQuatro",
    "caminho_do_executavel",
    "jogador_compartilhado",
    "resumo_dos_fontes",
]

RAIZ = Path(__file__).resolve().parents[2]

#: Os fontes do motor Dart do Quatro, espelhados do laboratório: a REFERÊNCIA
#: contra a qual o carimbo do executável é conferido.
FONTES_DO_MOTOR_DART = (
    RAIZ / "espelho_laboratorio" / "jogos" / "jogo_quatro" / "motor_dart" / "lib"
)

#: A versão do protocolo que este módulo fala. Tem de bater com
#: `versaoDoProtocoloQuatro` em `bin/servidor_de_lances_quatro.dart`.
VERSAO_DO_PROTOCOLO = 1

#: O que dizer a quem tem um executável ausente ou divergente.
RECEITA_DE_CONSERTO = (
    "Recompile o motor e espelhe de novo:\n"
    "  cd ..\\ia\\jogos\\jogo_quatro\\motor_dart\n"
    "  dart run bin\\compilar_servidor_de_lances_quatro.dart\n"
    "  cd ..\\..\\..\\..\\arena-sagaz-backend\n"
    "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
)


def resumo_dos_fontes(pasta: Path = FONTES_DO_MOTOR_DART) -> str:
    """O resumo dos fontes Dart do Quatro (a conta é a de `processo_dart`)."""
    return _resumo_dos_fontes(pasta)


def caminho_do_executavel() -> Path:
    """Onde está o executável: a variável `MOTOR_DART_QUATRO` ou o laboratório.

    Raises:
        MotorDartIndisponivel: com a receita de como compilar.
    """
    return _caminho_do_executavel(
        variavel_de_ambiente="MOTOR_DART_QUATRO",
        nome_do_binario="servidor_de_lances_quatro",
        vizinho=RAIZ.parent / "ia" / "jogos" / "jogo_quatro" / "motor_dart" / "bin",
        receita=RECEITA_DE_CONSERTO,
    )


class JogadorDartQuatro(ProcessoDart):
    """Um processo do motor Dart do Quatro, vivo, respondendo a pedidos.

    Use como contexto, para o processo ser encerrado mesmo se algo estourar::

        with JogadorDartQuatro() as motor:
            resposta = motor.decidir(lances="s4", co_modalidade=m,
                                     nivel=NivelDeMotor.TEX, semente=7)

    Args:
        caminho: o executável; sem ele, `caminho_do_executavel()`.
        fontes: a pasta dos fontes de referência. ⚠️ Só os testes a trocam
            (é como se prova que o carimbo divergente é recusado).
    """

    def __init__(
        self, caminho: Path | None = None, fontes: Path = FONTES_DO_MOTOR_DART
    ) -> None:
        super().__init__(
            caminho=caminho or caminho_do_executavel(),
            fontes=fontes,
            versao_do_protocolo=VERSAO_DO_PROTOCOLO,
            receita_de_conserto=RECEITA_DE_CONSERTO,
            argumentos=("--contrato", str(contrato_quatro.CAMINHO_DO_CONTRATO)),
        )
        esperado = contrato_quatro.sha256_do_contrato()
        recebido = self.abertura.get("sha256_do_contrato")
        if recebido != esperado:
            # Encerrar antes de recusar: senão o processo ficaria órfão.
            self.encerrar()
            raise MotorDartDivergente(
                "o executável leu outro contrato que o do espelho.\n"
                f"  esperado: {esperado[:16]}\n  recebido: {str(recebido)[:16]}"
            )

    def _exigir(self, resposta: dict[str, Any]) -> dict[str, Any]:
        """Devolve a resposta, ou levanta o erro que o motor recusou.

        ⚠️ Falha alto: um pedido malformado que virasse um lance qualquer seria
        indistinguível de uma jogada de verdade no banco.
        """
        if "erro" in resposta:
            raise ValueError(f"o motor Dart do Quatro recusou: {resposta['erro']}")
        return resposta

    def decidir(
        self, *, lances: str, co_modalidade: str, nivel: NivelDeMotor, semente: int
    ) -> dict[str, Any]:
        """O lance do personagem do [nivel], e COMO ele foi decidido.

        Args:
            lances: a partida inteira na notação (`s4s4s3`), inclusive a posição
                publicada.
            semente: a do LANCE (`job/semente.py`). ⚠️ Obrigatória: sem ela, duas
                medições da mesma posição divergiriam.

        Returns:
            A `RespostaDeLanceQuatro` inteira (`lance`, `acao`, `nosVisitados`,
            `profundidadeAtingida`, `motivoParada`, `tempoBuscaMs`,
            `avaliacaoJ1`): é comparando os nós que a bancada descobre que dois
            lados concordaram no lance por sorte.

        Raises:
            ValueError: o motor recusou (lance ilegal, partida terminada).
            contrato_quatro.ContratoQuatroInvalido: o nível não joga nesta
                modalidade (o Sagaz sem o Magno, o marcador de não medido).
        """
        parametros = contrato_quatro.parametros_do_personagem(co_modalidade, nivel)
        return self._exigir(
            self.pedir(
                {
                    "comando": "decidir",
                    "lances": lances,
                    "modalidade": co_modalidade,
                    **parametros.para_pedido(),
                    "semente": semente,
                    "limiteMs": None,
                }
            )
        )

    def buscar(self, *, lances: str, co_modalidade: str, teto_de_nos: int) -> dict[str, Any]:
        """Só a busca, sem política: o melhor lance que [teto_de_nos] acha.

        É o que as provas do job usam ("há vitória forçada daqui?"), e não o que
        um personagem joga. `motivoParada == "decidido"` quer dizer que a busca
        provou o resultado (vitória, derrota ou empate forçados).
        """
        return self._exigir(
            self.pedir(
                {
                    "comando": "buscar",
                    "lances": lances,
                    "modalidade": co_modalidade,
                    "tetoDeNos": teto_de_nos,
                }
            )
        )


# ⛔ UM MOTOR POR THREAD, e não um por processo: duas threads dividindo o mesmo
# `stdin`/`stdout` receberiam as respostas trocadas, sem erro nenhum. A limpeza
# das threads mortas é a de `recursos_por_thread`, a mesma das damas e do
# Pontinhos (sem ela, gerar 7 dias pelo painel deixou 81 motores parados).
_por_thread = threading.local()


def jogador_compartilhado() -> JogadorDartQuatro:
    """O motor Dart do Quatro **desta thread**, subindo-o na primeira vez.

    ⚠️ Preguiçoso de propósito: quem só usa o árbitro (o auditor de resoluções)
    nunca escolhe lance, e não deve pagar um executável nem falhar sem ele.
    """
    meu = getattr(_por_thread, "jogador", None)
    if meu is not None and not meu.morreu:
        return meu
    recursos_por_thread.liberar_de_threads_mortas()
    meu = JogadorDartQuatro()
    _por_thread.jogador = meu
    recursos_por_thread.registrar(meu)
    return meu

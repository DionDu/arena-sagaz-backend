"""O JOGADOR do xadrez: o motor Rust do aparelho, compilado (spec 012, T063).

═══════════════════════════════════════════════════════════════════════════
POR QUE O SERVIDOR NÃO TEM XADREZ EM PYTHON
═══════════════════════════════════════════════════════════════════════════

O gabarito de um desafio é uma partida contra Cacau, Pita, Tex ou Magno, e a
pessoa tem de poder segui-la no aparelho lance a lance. Aqui não há nem o
árbitro em Python que o Quatro ainda tem: toda pergunta de regra (o lance é
legal? por que não? acabou? quem venceu?) vai ao executável
`servidor_de_lances_xadrez`, compilado do MESMO crate que o app embarca
(RF-XDR-043, `research.md` R-20).

═══════════════════════════════════════════════════════════════════════════
AS TRÊS TRAVAS DA ABERTURA
═══════════════════════════════════════════════════════════════════════════

1. **O carimbo dos fontes**: o executável anuncia o resumo dos fontes com que
   foi compilado (`resumo_do_motor`, gravado pela `CARIMBO_MOTOR_XADREZ` de
   `scripts/compilar_motor_xadrez.py`), e o `ProcessoDart` o compara com o
   resumo do crate do ESPELHO (`PADROES_RUST`). Divergiu, ou veio
   `"sem_carimbo"` (um `cargo build` à mão): `MotorDartDivergente`.
2. **O contrato**: o executável recebe o contrato por `--contrato` e anuncia o
   SHA-256 dos bytes que leu; este módulo compara com o do espelho.
3. **A versão**: o executável anuncia a versão do crate (`versao`), e ela tem de
   ser a do `Cargo.toml` espelhado. Com o carimbo certo isso já vale; a
   conferência existe para a mensagem dizer "recompile" em vez de mostrar dois
   resumos.

═══════════════════════════════════════════════════════════════════════════
O PEDIDO
═══════════════════════════════════════════════════════════════════════════

Quem chama diz o NÍVEL (`NivelDeMotor`), e não os números: o executável lê os
números do contrato que recebeu. Este módulo só confere, antes de pedir, que o
build oferece aquele nível (o Sagaz some com `magno_no_build: false`).
A posição vai sempre como `fen_inicial` + `lances` (`contracts/motor-xadrez.md`
§2), e o lance é a notação interna (`e2e4`, `e7e8q`).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Sequence

from motores.nucleo import recursos_por_thread
from motores.nucleo.papeis import NivelDeMotor
from motores.nucleo.processo_dart import (
    PADROES_RUST,
    MotorDartDivergente,
    MotorDartIndisponivel,
    ProcessoDart,
    caminho_do_executavel as _caminho_do_executavel,
    resumo_dos_fontes as _resumo_dos_fontes,
)
from motores.xadrez import contrato_xadrez

__all__ = [
    "MotorDartDivergente",
    "MotorDartIndisponivel",
    "MotorXadrezRecusou",
    "JogadorXadrez",
    "caminho_do_executavel",
    "jogador_compartilhado",
    "resumo_dos_fontes",
]

RAIZ = Path(__file__).resolve().parents[2]

#: O crate do xadrez espelhado do laboratório: a REFERÊNCIA contra a qual o
#: carimbo do executável é conferido.
FONTES_DO_MOTOR = RAIZ / "espelho_laboratorio" / "jogos" / "jogo_xadrez" / "motor_rust"

#: Onde `scripts/compilar_motor_xadrez.py` põe a compilação (fora do Git). O
#: executável fica em `release/` dentro dela.
PASTA_DA_COMPILACAO = RAIZ / "build" / "motor_xadrez"

#: O nome do executável, sem extensão (o `.exe` entra sozinho no Windows).
NOME_DO_BINARIO = "servidor_de_lances_xadrez"

#: A variável de ambiente que aponta o executável (a imagem do job a define).
VARIAVEL_DO_EXECUTAVEL = "MOTOR_XADREZ"

#: A versão do protocolo que este módulo fala. Tem de bater com
#: `VERSAO_DO_PROTOCOLO` em `src/bin/servidor_de_lances_xadrez.rs`.
VERSAO_DO_PROTOCOLO = 1

#: O que dizer a quem tem um executável ausente ou divergente.
RECEITA_DE_CONSERTO = (
    "Espelhe o laboratório e compile o executável com o carimbo:\n"
    "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py\n"
    "  .venv\\Scripts\\python scripts\\compilar_motor_xadrez.py"
)


class MotorXadrezRecusou(ValueError):
    """O executável respondeu `{"ok": false}`: o pedido não vale naquela posição.

    É `ValueError` como a recusa do Quatro, e carrega o **código** do erro
    (`lance_ilegal`, `partida_terminada`, `lance_legal`...): o job decide pelo
    código, e não pelo texto.
    """

    def __init__(self, codigo: str, detalhe: str) -> None:
        super().__init__(f"o motor do xadrez recusou: {codigo} ({detalhe})")
        self.codigo = codigo
        self.detalhe = detalhe


def resumo_dos_fontes(pasta: Path = FONTES_DO_MOTOR) -> str:
    """O resumo do crate do xadrez (a conta é a de `processo_dart`)."""
    return _resumo_dos_fontes(pasta, PADROES_RUST)


def caminho_do_executavel() -> Path:
    """Onde está o executável: a variável `MOTOR_XADREZ` ou a compilação local.

    Raises:
        MotorDartIndisponivel: com a receita de como compilar.
    """
    return _caminho_do_executavel(
        variavel_de_ambiente=VARIAVEL_DO_EXECUTAVEL,
        nome_do_binario=NOME_DO_BINARIO,
        vizinho=PASTA_DA_COMPILACAO / "release",
        receita=RECEITA_DE_CONSERTO,
    )


class JogadorXadrez(ProcessoDart):
    """Um processo do executável do xadrez, vivo, respondendo a pedidos.

    Use como contexto, para o processo ser encerrado mesmo se algo estourar::

        with JogadorXadrez() as motor:
            resposta = motor.buscar(modalidade=m, fen_inicial=fen, lances=[],
                                    nivel=NivelDeMotor.TEX, semente=7)

    Args:
        caminho: o executável; sem ele, `caminho_do_executavel()`.
        fontes: o crate de referência. ⚠️ Só os testes o trocam (é como se
            prova que o carimbo divergente é recusado).
    """

    def __init__(self, caminho: Path | None = None, fontes: Path = FONTES_DO_MOTOR) -> None:
        super().__init__(
            caminho=caminho or caminho_do_executavel(),
            fontes=fontes,
            versao_do_protocolo=VERSAO_DO_PROTOCOLO,
            receita_de_conserto=RECEITA_DE_CONSERTO,
            argumentos=("--contrato", str(contrato_xadrez.CAMINHO_DO_CONTRATO)),
            padroes_dos_fontes=PADROES_RUST,
        )
        problemas = []
        if self.abertura.get("jogo") != "xadrez":
            problemas.append(f"o executável diz ser do jogo {self.abertura.get('jogo')!r}")
        esperado = contrato_xadrez.sha256_do_contrato()
        recebido = self.abertura.get("sha256_do_contrato")
        if recebido != esperado:
            problemas.append(
                "o executável leu outro contrato que o do espelho "
                f"(esperado {esperado[:16]}, recebido {str(recebido)[:16]})"
            )
        versao = contrato_xadrez.versao_do_crate()
        if self.abertura.get("versao") != versao:
            problemas.append(
                f"o executável é da versão {self.abertura.get('versao')!r}, e o crate "
                f"espelhado é a {versao!r}"
            )
        if problemas:
            # Encerrar antes de recusar: senão o processo ficaria órfão.
            self.encerrar()
            raise MotorDartDivergente("; ".join(problemas) + ".\n" + RECEITA_DE_CONSERTO)

    # ── O pedido ───────────────────────────────────────────────────────────

    def _pedir_ok(
        self,
        operacao: str,
        modalidade: str,
        fen_inicial: str,
        lances: Sequence[str],
        **campos: Any,
    ) -> dict[str, Any]:
        """Manda um pedido no formato do contrato §2 e devolve a resposta `ok`.

        Raises:
            MotorXadrezRecusou: a resposta veio `{"ok": false}`, com o código.
        """
        resposta = self.pedir(
            {
                "operacao": operacao,
                "modalidade": modalidade,
                "posicao": {"fen_inicial": fen_inicial, "lances": list(lances)},
                **campos,
            }
        )
        if resposta.get("ok") is not True:
            raise MotorXadrezRecusou(
                str(resposta.get("erro")), str(resposta.get("detalhe", ""))
            )
        return resposta

    # ── As sete operações (`contracts/motor-xadrez.md` §2.1 a §2.7) ─────────

    def estado(self, *, modalidade: str, fen_inicial: str, lances: Sequence[str]) -> dict[str, Any]:
        """A posição depois dos [lances]: os lances legais, os fatos, o fim (§2.1)."""
        return self._pedir_ok("estado", modalidade, fen_inicial, lances)

    def aplicar(
        self, *, modalidade: str, fen_inicial: str, lances: Sequence[str], lance: str
    ) -> dict[str, Any]:
        """Aplica um lance e devolve os fatos dele, inclusive o fim (§2.2).

        Raises:
            MotorXadrezRecusou: `lance_ilegal`, `partida_terminada`...
        """
        return self._pedir_ok("aplicar", modalidade, fen_inicial, lances, lance=lance)

    def recusa(
        self,
        *,
        modalidade: str,
        fen_inicial: str,
        lances: Sequence[str],
        de: str,
        para: str | None = None,
    ) -> str:
        """Por que o lance `de`→`para` não vale: o código da regra (§2.3).

        Sem `para`, a pergunta é "por que essa peça não tem lance?".

        Raises:
            MotorXadrezRecusou: `lance_legal` (o lance vale), `pedido_invalido`.
        """
        campos: dict[str, Any] = {"de": de}
        if para is not None:
            campos["para"] = para
        return str(self._pedir_ok("recusa", modalidade, fen_inicial, lances, **campos)["regra"])

    def buscar(
        self,
        *,
        modalidade: str,
        fen_inicial: str,
        lances: Sequence[str],
        nivel: NivelDeMotor,
        semente: int,
    ) -> dict[str, Any]:
        """O lance do personagem do [nivel], e COMO ele foi decidido (§2.4).

        Args:
            semente: a do LANCE (a fórmula do contrato). ⚠️ Obrigatória: sem
                ela, duas medições da mesma posição divergiriam.

        Returns:
            A resposta inteira (`lance`, `acao`, `nos`, `fatos`...): é
            comparando os nós que se descobre que dois lados concordaram no
            lance por sorte.

        Raises:
            contrato_xadrez.ContratoXadrezInvalido: o build não oferece o nível.
            MotorXadrezRecusou: `partida_terminada`, `semente_invalida`...
        """
        # Confere ANTES de pedir: o executável jogaria o Magno mesmo num build
        # sem ele (o nível existe no contrato), e o job gravaria um desafio
        # contra um personagem que o app não tem.
        personagem = contrato_xadrez.parametros_do_nivel(modalidade, nivel).personagem
        return self._pedir_ok(
            "buscar", modalidade, fen_inicial, lances, nivel=personagem, semente=semente
        )

    def jogada_ideal(
        self, *, modalidade: str, fen_inicial: str, lances: Sequence[str]
    ) -> dict[str, Any]:
        """O lance do poder "jogada ideal": a busca do Magno, sem ruído (§2.5)."""
        return self._pedir_ok("jogada_ideal", modalidade, fen_inicial, lances)

    def radar(
        self, *, modalidade: str, fen_inicial: str, lances: Sequence[str], lado: str
    ) -> list[str]:
        """As casas das peças do [lado] que o adversário pode comer (§2.6)."""
        return list(self._pedir_ok("radar", modalidade, fen_inicial, lances, lado=lado)["ameacadas"])

    def perft(
        self, *, modalidade: str, fen_inicial: str, lances: Sequence[str], profundidade: int
    ) -> int:
        """Quantas posições há a [profundidade] meios-lances (§2.7, de 1 a 6)."""
        return int(
            self._pedir_ok(
                "perft", modalidade, fen_inicial, lances, profundidade=profundidade
            )["nos"]
        )


# ⛔ UM MOTOR POR THREAD, e não um por processo: duas threads dividindo o mesmo
# `stdin`/`stdout` receberiam as respostas trocadas, sem erro nenhum. A limpeza
# das threads mortas é a de `recursos_por_thread`, a mesma dos motores Dart.
_por_thread = threading.local()


def jogador_compartilhado() -> JogadorXadrez:
    """O executável do xadrez **desta thread**, subindo-o na primeira vez."""
    meu = getattr(_por_thread, "jogador", None)
    if meu is not None and not meu.morreu:
        return meu
    recursos_por_thread.liberar_de_threads_mortas()
    meu = JogadorXadrez()
    _por_thread.jogador = meu
    recursos_por_thread.registrar(meu)
    return meu

"""A FRONTEIRA com um motor Dart compilado - a parte que ⛔ é de jogo nenhum.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE MÓDULO EXISTE (T093, 28/09/2026)
═══════════════════════════════════════════════════════════════════════════

Desde 25/09/2026 o servidor joga **damas** com o motor Dart do aparelho,
compilado; desde 28/09/2026 ele decide os lances do **Pontinhos** do mesmo jeito.
Os dois falam com um executável pela mesma fronteira - uma linha de texto por
pedido, uma por resposta - e os dois são protegidos pela mesma trava: o
executável carimba dentro de si o SHA-256 dos fontes com que foi compilado, e
este lado recalcula o resumo a partir do espelho e **recusa a conversa** se
divergirem.

⛔ **E a trava ⛔ pode existir duas vezes.** Uma segunda escrita da fórmula do
resumo é exatamente o tipo de coisa que esta tarefa existe para acabar: duas
fórmulas dariam dois jeitos de estar certo, e o dia em que uma mudasse o motor do
outro jogo passaria a ser recusado por um motivo que ⛔ é o dele.

⚠️ **A fórmula continua escrita duas vezes no total** - aqui e do lado Dart, em
`bin/compilar_servidor_de_lances*.dart` -, e ⛔ há como evitar: são linguagens
diferentes conferindo uma à outra. O que impede as duas de divergirem em silêncio
é que **divergir é justamente o que elas detectam**: uma fórmula mudada de um
lado só faz a abertura falhar na hora.

═══════════════════════════════════════════════════════════════════════════
O QUE ⛔ MORA AQUI
═══════════════════════════════════════════════════════════════════════════

⛔ **Nenhum parâmetro de jogo, e nenhum pedido de domínio.** Este módulo abre o
processo, confere quem ele é e leva um dicionário até ele. O que se pede, e com
que números, é de quem conhece o jogo: `motores/damas/jogador_dart.py` e
`motores/pontinhos/jogador_dart_pontinhos.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


class MotorDartIndisponivel(RuntimeError):
    """Não há executável utilizável — e a mensagem diz como fazer um."""


class MotorDartDivergente(RuntimeError):
    """O executável não saiu dos fontes que este backend tem.

    ⛔ **Não é aviso, é recusa.** Gerar desafios com um motor que não é o do
    aparelho é o defeito que esta corrente existe para impedir.
    """


def sha256_do_arquivo(caminho: Path) -> str:
    """O SHA-256 de um arquivo, em hexadecimal.

    ⚠️ Lê em **bytes**: ler como texto passaria pela tradução de fim de linha do
    Windows, e o hash descreveria algo que não está no disco.
    """
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def hashes_dos_fontes(pasta: Path) -> dict[str, str]:
    """O SHA-256 de cada `.dart` da pasta, por nome, em ordem alfabética.

    A ordem é a do **nome**, e não a do sistema de arquivos: sem isso o mesmo
    conjunto de arquivos daria resumos diferentes em máquinas diferentes.
    """
    return {
        arquivo.name: sha256_do_arquivo(arquivo)
        for arquivo in sorted(pasta.glob("*.dart"), key=lambda a: a.name)
    }


def resumo_dos_fontes(pasta: Path) -> str:
    """O resumo do conjunto - a MESMA fórmula do lado Dart.

    ⚠️ **Resume a LISTA, e não um arquivo concatenado.** Assim o resumo muda
    quando um arquivo é renomeado ou removido, e não só quando o conteúdo muda -
    um motor a que falte um arquivo é outro motor.

    Raises:
        MotorDartIndisponivel: a pasta dos fontes não está no disco. ⚠️ É o caso
            de quem nunca rodou `scripts/espelhar_laboratorio.py`, e a mensagem
            diz isso.
    """
    if not pasta.is_dir():
        raise MotorDartIndisponivel(
            f"não achei os fontes do motor Dart em {pasta}.\n"
            "Rode, na máquina do dono:\n"
            "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
        )
    material = "\n".join(
        f"{nome}:{hash_}" for nome, hash_ in hashes_dos_fontes(pasta).items()
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def caminho_do_executavel(
    *,
    variavel_de_ambiente: str,
    nome_do_binario: str,
    vizinho: Path,
    receita: str,
) -> Path:
    """Onde está o executável do motor Dart.

    A ordem de procura, e cada degrau tem um motivo:

      1. a **variável de ambiente** — é como a máquina de outra pessoa (ou um
         contêiner) aponta para o binário dela sem editar código;
      2. o **laboratório vizinho** — o caso normal na máquina do dono, onde os
         três repositórios moram lado a lado.

    Args:
        nome_do_binario: sem extensão. O `.exe` entra sozinho no Windows, e é
            por isso que este argumento ⛔ o traz: o mesmo código sobe o motor
            no PC do dono e dentro da imagem `linux/amd64`.
        receita: o que dizer a quem não tem o executável. ⚠️ **Entra por
            parâmetro** porque a receita é por jogo, e uma mensagem genérica
            ("compile o motor") manda procurar em que pasta?

    Raises:
        MotorDartIndisponivel: com a receita de como compilar.
    """
    do_ambiente = os.environ.get(variavel_de_ambiente)
    if do_ambiente:
        caminho = Path(do_ambiente)
        if caminho.is_file():
            return caminho
        raise MotorDartIndisponivel(
            f"{variavel_de_ambiente} aponta para {caminho}, que não existe."
        )

    nome = f"{nome_do_binario}.exe" if os.name == "nt" else nome_do_binario
    candidato = vizinho / nome
    if candidato.is_file():
        return candidato

    raise MotorDartIndisponivel(
        f"não achei o motor Dart compilado (procurei em {candidato}).\n{receita}"
    )


class ProcessoDart:
    """Um processo do motor Dart, vivo, respondendo a pedidos.

    ⚠️ **O processo fica vivo de propósito.** A régua mede 20 execuções por
    mascote, e uma partida tem dezenas de lances: subir um processo por lance
    pagaria a partida do executável milhares de vezes.

    ⚠️ **Um processo por THREAD.** A fronteira é um `stdin`/`stdout` de linha
    única: quem escreve um pedido espera a resposta antes do próximo, e duas
    threads dividindo o mesmo processo receberiam as respostas **trocadas** - e
    trocadas sem erro nenhum, que é o pior modo de falha possível.

    Use como contexto, para o processo ser encerrado mesmo se algo estourar::

        with ProcessoDart(...) as motor:
            resposta = motor.pedir({...})
    """

    def __init__(
        self,
        *,
        caminho: Path,
        fontes: Path,
        versao_do_protocolo: int,
        receita_de_conserto: str,
    ) -> None:
        self._caminho = caminho
        self._fontes = fontes
        self._versao_do_protocolo = versao_do_protocolo
        self._receita = receita_de_conserto
        self._processo = subprocess.Popen(
            [str(caminho)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # ⛔ O stderr fica SEPARADO. Juntá-lo ao stdout misturaria um aviso
            # solto do runtime do Dart com as respostas JSON, e o cliente leria
            # lixo no lugar de um lance.
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._abertura = self._conferir_a_abertura()

    # ── A trava ──────────────────────────────────────────────────────────────

    def _conferir_a_abertura(self) -> dict[str, Any]:
        """Lê a linha de apresentação e recusa um executável que não seja o nosso."""
        linha = self._processo.stdout.readline()  # type: ignore[union-attr]
        if not linha:
            erro = self._processo.stderr.read()  # type: ignore[union-attr]
            raise MotorDartIndisponivel(
                f"o motor Dart em {self._caminho} não respondeu na abertura.\n{erro}"
            )
        abertura = json.loads(linha)

        if abertura.get("versao_do_protocolo") != self._versao_do_protocolo:
            raise MotorDartDivergente(
                f"o executável fala o protocolo "
                f"{abertura.get('versao_do_protocolo')} e este backend fala o "
                f"{self._versao_do_protocolo}. Recompile o motor.\n{self._receita}"
            )

        esperado = resumo_dos_fontes(self._fontes)
        recebido = abertura.get("resumo_do_motor")
        if recebido != esperado:
            # ⚠️ A mensagem nomeia **quais** arquivos divergiram. "O resumo não
            # bate" manda procurar na pasta inteira; o nome manda direto ao que
            # mudou - e costuma responder sozinho se falta recompilar ou falta
            # espelhar.
            do_exe: dict[str, str] = abertura.get("arquivos_do_motor", {})
            daqui = hashes_dos_fontes(self._fontes)
            diferentes = sorted(
                nome
                for nome in set(do_exe) | set(daqui)
                if do_exe.get(nome) != daqui.get(nome)
            )
            raise MotorDartDivergente(
                f"o executável em {self._caminho} não saiu dos fontes deste "
                f"backend.\n"
                f"  divergem: {', '.join(diferentes) or '(a lista de arquivos)'}\n"
                f"  esperado: {esperado[:16]}\n"
                f"  recebido: {str(recebido)[:16]}\n"
                f"{self._receita}"
            )
        return abertura

    @property
    def abertura(self) -> dict[str, Any]:
        """A linha de apresentação inteira, para quem precisar de mais que o resumo."""
        return self._abertura

    @property
    def resumo_do_motor(self) -> str:
        """O resumo dos fontes com que este executável foi compilado.

        ⚠️ Serve para ir ao BANCO, junto do desafio: é o que responde, meses
        depois, *"este gabarito saiu de que motor?"* sem depender do Git.
        """
        return self._abertura["resumo_do_motor"]

    @property
    def morreu(self) -> bool:
        """O processo saiu (por erro, ou porque alguém o encerrou).

        ⚠️ Serve ao processo compartilhado: um motor morto precisa ser
        substituído, e não reusado até o pedido seguinte estourar com
        `MotorDartIndisponivel` no meio de uma medição de horas.
        """
        return self._processo.poll() is not None

    # ── O uso ────────────────────────────────────────────────────────────────

    def pedir(self, pedido: dict[str, Any]) -> dict[str, Any]:
        """Manda um pedido e devolve a resposta decodificada."""
        if self._processo.poll() is not None:
            raise MotorDartIndisponivel(
                f"o motor Dart morreu (código {self._processo.returncode}). "
                f"stderr: {self._processo.stderr.read()}"  # type: ignore[union-attr]
            )
        self._processo.stdin.write(json.dumps(pedido) + "\n")  # type: ignore[union-attr]
        self._processo.stdin.flush()  # type: ignore[union-attr]
        linha = self._processo.stdout.readline()  # type: ignore[union-attr]
        if not linha:
            raise MotorDartIndisponivel(
                "o motor Dart não respondeu ao pedido. "
                f"stderr: {self._processo.stderr.read()}"  # type: ignore[union-attr]
            )
        return json.loads(linha)

    # ── O fim ────────────────────────────────────────────────────────────────

    def encerrar(self) -> None:
        """Fecha a entrada e espera o processo sair."""
        if self._processo.poll() is None:
            try:
                self._processo.stdin.close()  # type: ignore[union-attr]
                self._processo.wait(timeout=5)
            except Exception:
                self._processo.kill()

    def __enter__(self) -> "ProcessoDart":
        return self

    def __exit__(self, *_) -> None:
        self.encerrar()

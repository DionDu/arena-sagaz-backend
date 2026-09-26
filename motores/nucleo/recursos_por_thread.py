"""Recursos caros que existem **um por thread**, e como fechá-los quando a thread morre.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE MÓDULO EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 25/09/2026 a régua passou a medir as 60 execuções de um candidato de damas em
8 threads, e cada thread abre o **seu** processo do motor Dart (a fronteira é um
`stdin`/`stdout` de linha única: duas threads no mesmo processo receberiam as
respostas trocadas, e trocadas sem erro nenhum).

O motor por thread está certo. O que faltava era o fim: um `ThreadPoolExecutor`
cria threads novas a cada `with`, e quando o bloco fecha as threads morrem — mas
o processo do motor **não**. O `threading.local()` da thread morta é coletado,
só que a lista que guardava os motores para a saída do programa continuava
apontando para eles, então nem coletados eram.

Medido no PC do dono, depois de gerar 7 dias pelo painel de curadoria:
**81 processos do motor vivos, 5,4 GB de RAM, zero de CPU em 15 s** — um pool de
8 por candidato, nunca fechado, num uvicorn que fica no ar por horas. Com o job
em processo curto (`rodar_job_local.py`) ninguém percebia: o `atexit` fechava
tudo na saída.

═══════════════════════════════════════════════════════════════════════════
O DESENHO: GENÉRICO DE PROPÓSITO
═══════════════════════════════════════════════════════════════════════════

Quem chama a limpeza é a **régua**, que mede qualquer jogo e ⛔ não pode conhecer
o motor de damas. Por isso o registro é uma coisa do `motores/nucleo/`: quem cria
um recurso por thread se anota aqui, e a régua fecha os de threads mortas sem
saber o que são. No dia em que o Pontinhos tiver um processo por thread, ele entra
aqui e a régua não muda.

⚠️ **E a defesa principal não depende de ninguém lembrar de chamar.** Quem cria um
recurso novo varre os mortos primeiro ([liberar_de_threads_mortas] é chamada de
dentro do próprio criador), então o pico fica no número de threads **vivas**, e
não no total histórico. A chamada explícita da régua é o que zera entre candidatos.
"""

from __future__ import annotations

import atexit
import sys
import threading
from typing import Protocol


class Fechavel(Protocol):
    """Qualquer coisa que saiba se encerrar.

    `Protocol` é a tipagem estrutural do Python: não é preciso herdar nada, basta
    ter o método `encerrar()`. É o que permite este módulo não importar o motor.
    """

    def encerrar(self) -> None: ...


#: Os recursos abertos, com a thread que os criou: `(thread, recurso)`.
#:
#: ⚠️ **A thread entra aqui, e não o nome dela.** Um objeto `Thread` responde
#: `is_alive()` — é ele que diz se o dono do recurso ainda existe. Guardar o
#: `ident` não serviria: o sistema **reaproveita** identificadores de thread, e um
#: recurso órfão passaria por vivo porque outra thread nasceu com o mesmo número.
#:
#: ⚠️ Uma lista e **um** `atexit.register`, e não um registro por recurso: com 81
#: motores seriam 81 registros pendurados na saída do processo.
_abertos: list[tuple[threading.Thread, Fechavel]] = []
_cadeado = threading.Lock()


def registrar(recurso: Fechavel) -> None:
    """Anota que a thread atual abriu `recurso`, para poder fechá-lo depois."""
    with _cadeado:
        _abertos.append((threading.current_thread(), recurso))


def liberar_de_threads_mortas() -> int:
    """Fecha os recursos cujas threads donas já morreram. Devolve quantos fechou.

    ⚠️ **Nunca toca no recurso de uma thread viva**, nem no da thread que chama:
    fechar o motor de quem está no meio de uma busca daria uma resposta truncada.
    O critério é só `is_alive()`.

    ⚠️ **Uma falha ao fechar não pode derrubar quem pediu a limpeza.** Isto roda
    no fim de uma medição que já terminou; um motor que não morre limpo vira aviso
    no `stderr`, e o recurso sai da lista de qualquer jeito (insistir nele o
    manteria pendurado para sempre).
    """
    with _cadeado:
        # Duas listas numa passada: quem fica e quem fecha. Fechar dentro da
        # travessia da lista que se está alterando é como se perde item.
        mortos = [(t, r) for t, r in _abertos if not t.is_alive()]
        _abertos[:] = [(t, r) for t, r in _abertos if t.is_alive()]

    for _, recurso in mortos:
        try:
            recurso.encerrar()
        except Exception as erro:  # noqa: BLE001 — limpeza não propaga falha
            print(
                f"⚠️ [recursos] um recurso de thread morta nao fechou limpo: {erro}",
                file=sys.stderr,
            )
    return len(mortos)


def _liberar_tudo() -> None:
    """Fecha **todos** os recursos — só na saída do processo.

    Aqui o critério de thread viva não vale: o programa está terminando, e um
    processo filho que sobrevive ao pai fica órfão no sistema.
    """
    with _cadeado:
        todos = list(_abertos)
        _abertos.clear()
    for _, recurso in todos:
        try:
            recurso.encerrar()
        except Exception:  # noqa: BLE001 — na saída, nada mais há a fazer
            pass


atexit.register(_liberar_tudo)


def quantos_abertos() -> int:
    """Quantos recursos estão registrados agora. Existe para os testes medirem."""
    with _cadeado:
        return len(_abertos)

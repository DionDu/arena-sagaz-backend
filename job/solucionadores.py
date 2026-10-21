"""Os SOLUCIONADORES proprios: quem escolhe o lance de quem resolve, quando nao e o personagem.

═══════════════════════════════════════════════════════════════════════════
POR QUE UM CONTEXTO, E NAO `(arbitro, estado)` (T124c da spec 010, 21/10/2026)
═══════════════════════════════════════════════════════════════════════════

Ate a T124c o solucionador recebia so o arbitro e o estado, e isso bastava ao
unico que existia, o arquiteto da cadeia longa do Pontinhos: ele nao tem nivel
nem le o objetivo, so monta cadeias. ⚠️ Era uma limitacao declarada em
`job/regua.py`: *"o solucionador proprio nao tem nivel, e a escada daquele tipo
passa a depender so do adversario"*.

O perseguidor do Quatro (`motores/quatro/perseguir_objetivo_quatro.py`) precisa
de mais: o NIVEL de quem esta resolvendo (a escada da regua e Cacau < Pita <
Tex < Magno), a SEMENTE do lance (a mesma partida a cada execucao), o lance que
o motor daria naquele nivel (a mistura), o JOGADOR (a busca do executavel, que
prova as vitorias) e a LINHA DE CHEGADA (o que perseguir). O [ContextoDoSolucionador]
leva tudo isso, e os dois lugares que chamam um solucionador - a geracao
(`gerador._resolver`) e a regua (`regua.tentativa_com_motor`) - o montam do
mesmo jeito.

⛔ **A linha de chegada entra por [com_chegada]**, no lugar que conhece o
candidato (a geracao e a bancada da regua), e nao como parametro novo de quem
chama a regua: assim o `__main__` do job e o medidor de variantes nao mudam, e
nao ha um terceiro caminho que pudesse esquece-la.
"""

from __future__ import annotations

import dataclasses
import random
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from motores.nucleo.papeis import NivelDeMotor
from motores.pontinhos import cadeia_longa
from motores.quatro import perseguir_objetivo_quatro as perseguir

from . import provas_quatro as provas_quatro_mod

#: Quantos nos a busca pode gastar para provar cada lance candidato do
#: perseguidor. ⚠️ O mesmo da medicao pareada (`scripts/medir_perseguir_vs_vencer_quatro.py`,
#: `TETO_DA_PROVA_DO_MAGNO`): mudar um sem o outro faria a regua medir um
#: perseguidor diferente do que passou no controle.
TETO_DA_PROVA_DO_PERSEGUIDOR = 200_000


@dataclass(frozen=True)
class ContextoDoSolucionador:
    """Tudo o que um solucionador pode precisar para escolher UM lance.

    Atributos:
        arbitro: quem conhece as regras (no Quatro, o `MotorQuatro`).
        jogador: quem joga pelo motor (no Quatro, o `JogadorQuatro`, que tem a
            busca do executavel).
        estado_inicial: a posicao publicada do desafio.
        estado: a posicao agora (a publicada mais os lances desde ela).
        nivel: o degrau de quem resolve. Na geracao e o Sagaz; na regua, o
            personagem medido.
        semente: a semente DESTE lance (a mesma partida a cada execucao).
        lance_do_nivel: devolve o lance que o motor daria a quem resolve, neste
            nivel e com esta semente - o lance de quando nao ha solucionador.
            Uma funcao, e nao o lance: so custa a ida ao motor se for usada.
        js_chegada: a linha de chegada do desafio (ver [com_chegada]).
    """

    arbitro: Any
    jogador: Any
    estado_inicial: Any
    estado: Any
    nivel: NivelDeMotor
    semente: int
    lance_do_nivel: Callable[[], str]
    js_chegada: Mapping[str, Any] | None = None


#: Um solucionador: recebe o contexto e devolve o rotulo do lance. Levanta
#: `ValueError` quando nao ha lance (a partida acabou), como o motor.
Solucionador = Callable[[ContextoDoSolucionador], str]


def com_chegada(
    solucionador: Solucionador | None, js_chegada: Mapping[str, Any]
) -> Solucionador | None:
    """O mesmo solucionador, com a linha de chegada do candidato no contexto.

    `None` continua `None`: tipo sem solucionador proprio nao ganha um.
    """
    if solucionador is None:
        return None

    def com_a_chegada(contexto: ContextoDoSolucionador) -> str:
        # `dataclasses.replace` faz uma copia do contexto com um campo trocado
        # (o contexto e `frozen`, imutavel).
        return solucionador(dataclasses.replace(contexto, js_chegada=js_chegada))

    return com_a_chegada


def arquiteto_da_cadeia_longa(contexto: ContextoDoSolucionador) -> str:
    """O solucionador da cadeia longa do Pontinhos (16/09/2026), como era.

    ⚠️ Sem nivel e sem objetivo: ele so monta cadeias. A escada desse tipo
    continua dependendo do adversario (o mesmo de antes da T124c).
    """
    return cadeia_longa.lance_do_arquiteto(contexto.arbitro, contexto.estado)


def perseguidor_do_quatro(co_tipo: str) -> Solucionador:
    """O perseguidor do objetivo do Quatro, para um tipo.

    ⚠️ **Ligado so onde a medicao pareada mostrou ganho e escada** (diagonal e
    encostadas, 21/10/2026; historico do backend, "2026-10-21 (9)"): o registro
    `gerador.SOLUCIONADOR_POR_TIPO` e a lista.
    """

    def solucionar(contexto: ContextoDoSolucionador) -> str:
        if contexto.js_chegada is None:
            # ⛔ Sem a chegada nao ha o que perseguir; jogar o lance do nivel
            # aqui esconderia o defeito de um caminho que esqueceu `com_chegada`.
            raise RuntimeError(
                f"o perseguidor de {co_tipo} foi chamado sem a linha de chegada "
                "(falta `solucionadores.com_chegada` em quem o montou)"
            )
        motor = contexto.arbitro
        iniciais = tuple(contexto.estado_inicial.lances)
        fita = tuple(contexto.estado.lances)[len(iniciais):]
        desafio = perseguir.desafio_de(motor, co_tipo, iniciais, contexto.js_chegada)
        provador = provas_quatro_mod.ProvadorQuatro(
            motor.co_modalidade,
            contexto.jogador.motor_dart,
            teto_de_nos=TETO_DA_PROVA_DO_PERSEGUIDOR,
        )
        return perseguir.lance_de_quem_persegue(
            motor,
            desafio,
            fita,
            nivel=contexto.nivel,
            # Um sorteio NOVO por lance, da semente do lance: o mesmo lance a
            # cada execucao, sem depender de quantos sorteios vieram antes.
            sorteio=random.Random(contexto.semente),
            lance_do_nivel=contexto.lance_do_nivel,
            prova=lambda estado: provador.resultado(estado).vencedor,
        )

    return solucionar

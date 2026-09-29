"""🔒 T093 - o ARBITRO do servidor e o do aplicativo contam a mesma partida.

═══════════════════════════════════════════════════════════════════════════
A COSTURA QUE ESTE CADEADO GUARDA
═══════════════════════════════════════════════════════════════════════════

Desde a T093 (28/09/2026) quem **decide** o lance do Pontinhos no servidor e o
motor Dart. Mas o servidor continua com um arbitro proprio em Python - o
`EstadoTabuleiro` do laboratorio, dentro de `EstadoPontinhos` -, e ele ⛔ e
decorativo: e ele que responde *quais tracos estao livres*, *de quem e a vez* e
*a partida acabou?* ao job, ao juiz e a regua.

⚠️ **E ficar em Python e decisao, nao esquecimento**: esse e o mesmo codigo que
gerou o dataset de treino da CNN, e trocá-lo por uma chamada ao Dart a cada
`lances_legais` poria um round-trip no caminho mais quente do job para responder
o que uma varredura de matriz responde em microssegundos.

⛔ **O preco dessa decisao e este arquivo.** Duas escritas da mesma regra e o que
produziu todos os episodios de divergencia do projeto - entao a regra que ficou
escrita duas vezes passa a ser **conferida** partida inteira, lance a lance:

  * os **tracos disponiveis**, e na mesma ordem (e sobre ela que a Fase A
    sorteia: duas listas com os mesmos tracos em ordens diferentes escolhem
    lances diferentes com a mesma semente);
  * **de quem e a vez** - que no Pontinhos depende da historia, e nao do desenho
    do tabuleiro, porque quem fecha caixa joga de novo;
  * o **placar** e o **fim de partida**;
  * e o **tensor dos 12 canais**, que o Dart monta a partir da mesma matriz.

⚠️ As partidas sao sorteadas com semente fixa: sao sempre as mesmas, e o caso
falha sempre no mesmo lugar.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from motores.pontinhos import jogador_dart_pontinhos  # noqa: E402
from motores.pontinhos.motor_pontinhos import (  # noqa: E402
    EstadoPontinhos,
    MotorPontinhos,
)

#: Quantas partidas aleatorias percorrer.
#:
#: ⚠️ Doze partidas inteiras sao 372 posicoes, e o caso leva menos de um segundo:
#: o que custa aqui e um round-trip por posicao, e ⛔ uma busca. Um numero maior
#: nao acrescentaria cobertura - o tabuleiro 4x3 tem 31 tracos, e as posicoes
#: visitadas ja cobrem cadeias, lacos e caixas de tres lados.
QUANTAS_PARTIDAS = 12

#: A semente do sorteio das partidas. ⛔ **Fixa**: um caso que muda de entrada a
#: cada execucao falha em dias diferentes por motivos diferentes, e vira o teste
#: que "as vezes quebra" - o primeiro a ser desligado.
SEMENTE = 20260928


def test_o_arbitro_python_e_o_motor_dart_contam_a_mesma_partida() -> None:
    motor = MotorPontinhos()
    sorteio = random.Random(SEMENTE)

    with jogador_dart_pontinhos.JogadorDartPontinhos() as dart:
        for numero_da_partida in range(QUANTAS_PARTIDAS):
            estado = EstadoPontinhos()
            while True:
                disponiveis = motor.lances_legais(estado)
                do_dart = dart.canais(estado.lances)

                onde = (
                    f"partida {numero_da_partida + 1}, "
                    f"depois de {len(estado.lances)} lance(s) "
                    f"({', '.join(estado.lances) or 'nenhum'})"
                )
                assert do_dart["disponiveis"] == disponiveis, (
                    f"{onde}: os tracos disponiveis divergiram.\n"
                    f"  python: {disponiveis}\n"
                    f"  dart  : {do_dart['disponiveis']}"
                )
                assert do_dart["vez_de"] == estado.vez_de, (
                    f"{onde}: a vez divergiu (python {estado.vez_de}, "
                    f"dart {do_dart['vez_de']}). Quem fecha caixa joga de novo - "
                    f"um dos dois contou as caixas de outro jeito."
                )
                assert do_dart["placar"] == {
                    "1": estado.placar[1],
                    "-1": estado.placar[-1],
                }, f"{onde}: o placar divergiu."
                assert do_dart["acabou"] is (not disponiveis), (
                    f"{onde}: um dos dois acha que a partida acabou e o outro nao."
                )

                if not disponiveis:
                    break
                estado = motor.aplicar(estado, sorteio.choice(disponiveis))


def test_o_tensor_dos_12_canais_e_o_mesmo_dos_dois_lados() -> None:
    """A conta que ⛔ se reescreve - e que, ate a T093, estava escrita duas vezes.

    ⚠️ A extracao dos 12 canais tem BFS no grafo dual das caixas. Ela sai
    plausivel mesmo quando esta errada: o tensor tem a forma certa, a rede
    responde, e o adversario do desafio passa a ser outro sem nada acusar.

    Desde a T093 quem monta o tensor no servidor e o motor Dart. Este caso
    confere que ele concorda com `extrair_canais`, do laboratorio, que e o codigo
    que gerou o dataset de treino - se um dia divergirem, o que vale e o
    laboratorio, porque foi contra ele que a rede aprendeu.
    """
    import numpy as np

    from motores.pontinhos.motor_pontinhos import ESPELHO, partida_para_dataset

    if str(ESPELHO) not in sys.path:
        sys.path.insert(0, str(ESPELHO))
    from jogos.jogo_pontinhos.motor.analisador_estrutural_pontinhos import (
        extrair_canais,
    )

    motor = MotorPontinhos()
    sorteio = random.Random(SEMENTE + 1)

    with jogador_dart_pontinhos.JogadorDartPontinhos() as dart:
        for numero_da_partida in range(QUANTAS_PARTIDAS):
            estado = EstadoPontinhos()
            while True:
                disponiveis = motor.lances_legais(estado)
                do_dart = np.asarray(
                    dart.canais(estado.lances)["tensor"], dtype=np.float32
                ).reshape(4, 3, 12)
                do_laboratorio = np.asarray(
                    extrair_canais(partida_para_dataset(estado.tabuleiro.matriz)),
                    dtype=np.float32,
                )
                assert np.array_equal(do_dart, do_laboratorio), (
                    f"partida {numero_da_partida + 1}, depois de "
                    f"{len(estado.lances)} lance(s) "
                    f"({', '.join(estado.lances) or 'nenhum'}): o tensor de 12 "
                    f"canais divergiu.\n"
                    f"  canais diferentes: "
                    f"{sorted(set(np.argwhere(do_dart != do_laboratorio)[:, 2].tolist()))}"
                )
                if not disponiveis:
                    break
                estado = motor.aplicar(estado, sorteio.choice(disponiveis))

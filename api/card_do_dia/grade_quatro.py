"""A grade do Quatro em Linha da posição inicial, pronta para a página desenhar.

⚠️ **Por que o servidor desenha a grade, e não a página.** A página é Flutter
web, e o motor do Quatro do app usa inteiros de 64 bits (o tabuleiro em bits),
que não existem no JavaScript: o build web recusa compilá-lo. Nos outros jogos
a página reproduz a posição com o código do app; no Quatro, quem reproduz é o
árbitro daqui, o mesmo que o painel de curadoria já usa para desenhar
(`api/desafios/painel/desenho.py`).

A notação é a de `GradeQuatro.deTexto` no app (e a `q4Grade` do Claude Design):
uma linha de texto por linha do tabuleiro, **de cima para baixo**, com `.`
vazia, `a` azul e `v` vermelho. ⚠️ **A pessoa é sempre o azul**, como na tela
do Quatro do app, mesmo quando a posição publicada dá a vez ao 2º jogador do
motor: a cor segue quem resolve, e não o J1 do árbitro.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from api.nucleo.log import obter_logger

log = obter_logger("api.card_do_dia")


def _lances(posicao: Mapping[str, Any]) -> list[str]:
    """Os lances publicados (`["s4", "s4", ...]`), como o painel os lê."""
    lista = posicao.get("sequencia_lances")
    if isinstance(lista, list):
        return [str(lance) for lance in lista]
    concatenada = posicao.get("co_lances")
    if isinstance(concatenada, str):
        # Letra seguida de dígitos: `s4s10s3` → `["s4", "s10", "s3"]`.
        return re.findall(r"[a-z]\d+", concatenada)
    return []


def grade_do_quatro(linha: Mapping[str, Any]) -> Optional[list[str]]:
    """A grade da posição inicial de um desafio do Quatro, ou `None`.

    `None` também quando o árbitro recusa a posição: a página desenha o card sem
    tabuleiro, e o post do dia não cai por causa disso (o erro vai para o log).
    """
    if linha.get("co_jogo") != "quatro":
        return None
    posicao = linha.get("js_posicao_inicial") or {}
    modalidade = linha.get("co_modalidade") or posicao.get("co_modalidade") or ""
    try:
        # Importado aqui dentro, como no painel: o motor só é carregado quando
        # o desafio do dia é do Quatro.
        from motores.quatro.motor_quatro import MotorQuatro

        motor = MotorQuatro(str(modalidade))
        tabuleiro = motor.tabuleiro(motor.estado_de_sequencia("".join(_lances(posicao))))
        dimensoes = motor.regras.dimensoes
    except Exception:  # noqa: BLE001 - o card sai sem tabuleiro, e não um 500
        log.exception("grade do Quatro recusada pelo árbitro")
        return None
    # Quem resolve é quem tem a vez na posição publicada: as peças dele, azuis.
    pessoa = tabuleiro.vez
    cor = {pessoa: "a", -pessoa: "v", 0: "."}
    # `range(altura, 0, -1)`: as linhas 6, 5, ..., 1 - a de cima primeiro (a
    # linha 1 do árbitro é o chão).
    return [
        "".join(cor[tabuleiro.peca((coluna, linha))] for coluna in range(1, dimensoes.largura + 1))
        for linha in range(dimensoes.altura, 0, -1)
    ]

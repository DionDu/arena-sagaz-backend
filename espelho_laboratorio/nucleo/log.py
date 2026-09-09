"""Logger do laboratório de IA.

Por que este arquivo existe
---------------------------
Até 2026-07-21 os módulos do laboratório importavam ``obter_logger`` de
``api.nucleo.log`` — ou seja, um gerador de dataset puxava código do servidor
FastAPI só para ter um ``print`` organizado. Era o **último** laço entre o
laboratório e a API, e era o que impedia separar os dois repositórios.

Este módulo devolve a mesma função com o mesmo nome e a mesma assinatura, de
modo que a troca no laboratório foi só o caminho do import.

Diferença proposital em relação ao logger da API
------------------------------------------------
O da API emite **JSON** numa linha só, porque quem lê é a Railway (agregador de
logs). Aqui quem lê é uma pessoa, olhando o terminal enquanto um treino de horas
avança — então o formato é texto legível, com hora, nível e módulo. Nenhum dos
dois está errado: eles têm leitores diferentes.
"""
from __future__ import annotations

import logging
import sys

# Formato de uma linha de log:
#   14:07:33 INFO     geracao.gerador_pontinhos | 12.480 amostras geradas
#
# `%(name)-38s` alinha o nome do módulo em 38 colunas, para a mensagem começar
# sempre na mesma coluna e o olho conseguir varrer a saída na vertical.
_FORMATO = "%(asctime)s %(levelname)-8s %(name)-38s | %(message)s"
_FORMATO_HORA = "%H:%M:%S"


def obter_logger(nome: str) -> logging.Logger:
    """Devolve um logger pronto para uso, criando-o só na primeira chamada.

    O ``if not logger.handlers`` é o detalhe que importa: ``getLogger`` com o
    mesmo nome devolve **sempre o mesmo objeto**, então sem essa guarda cada
    chamada acrescentaria mais um handler e a mesma mensagem sairia duplicada,
    triplicada, e assim por diante. É um erro clássico e silencioso — a saída
    parece só "estranha", não quebrada.

    Args:
        nome: normalmente ``__name__`` do módulo que chama.

    Returns:
        Um ``logging.Logger`` que escreve em ``stderr``, em texto legível.
    """
    logger = logging.getLogger(nome)

    if not logger.handlers:
        # `stderr` e não `stdout`: em notebook e em pipe, a saída de dados
        # (stdout) fica separada da saída de diagnóstico (stderr). Assim dá para
        # redirecionar um sem perder o outro.
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMATO, datefmt=_FORMATO_HORA))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # `propagate = False` impede que a mensagem suba também para o logger
        # raiz. Sem isso, quem já tivesse chamado `logging.basicConfig()` — o
        # Jupyter faz isso sozinho — veria tudo duas vezes.
        logger.propagate = False

    return logger

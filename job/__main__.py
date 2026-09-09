"""Ponto de entrada do job em batch — o que `python -m job` executa.

⚠️ **ESTE ARQUIVO AINDA É UM ESQUELETO, E FALHA ALTO DE PROPÓSITO.**

A T018 entrega a **imagem** e o **serviço** do Railway; quem preenche o miolo são
as tarefas seguintes do BLOCO 2:

| tarefa | o que ela traz |
|---|---|
| T031 | a posição inicial nos dois formatos (`sequencia_lances` · `fen`) |
| T032 | o gabarito (`js_solucao`) no vocabulário de lance do log |
| T033 | a semente publicada e derivada por lance |
| T034 | o gerador de candidatos (rodízio de jogo, tipo, personagem do dia) |
| T035 | a régua dos mascotes |
| T037 | as medidas de saída do XP |
| T038 | a gravação idempotente, com folga de 7 a 30 dias |

Enquanto elas não chegam, rodar o container **sai com erro e diz o porquê**. É
melhor que um `ImportError` seco: quem construir a imagem hoje descobre na
primeira linha do log que o gerador ainda não existe, em vez de investigar um
traceback de módulo faltando.

⚠️ **Não troque isto por um `pass` que sai com 0.** Um job que "termina bem" sem
gerar nada é indistinguível, no painel do Railway, de um job que funcionou — e a
fila de desafios secaria em silêncio até alguém abrir o aplicativo e ver o dia
vazio.
"""

from __future__ import annotations

import sys

# O código de saída 2 é a convenção de "não dá para trabalhar" deste projeto
# (0 = fez, 1 = fez e algo divergiu, 2 = nem começou).
CODIGO_AINDA_NAO_IMPLEMENTADO = 2

MENSAGEM = """\
[job] O job do Desafio do Dia ainda NAO tem gerador.

A imagem e o servico do Railway existem (T018), e o portao de runtime do build
passou - senao esta imagem nem teria sido construida. O que falta e o miolo:
T031 a T038 do specs/009-desafio-do-dia/tasks.md.

Nada foi gravado no banco. Saindo com codigo 2.\
"""


def principal() -> int:
    """Roda o job. Hoje, apenas explica que ele ainda não existe.

    Devolve o código de saída do processo, em vez de chamar `sys.exit` aqui
    dentro: função que devolve número é testável; função que encerra o processo
    derruba o pytest junto.
    """
    # `print(..., file=sys.stderr)` manda para a saída de erro, que é onde o
    # Railway destaca as linhas no log.
    print(MENSAGEM, file=sys.stderr)
    return CODIGO_AINDA_NAO_IMPLEMENTADO


if __name__ == "__main__":
    sys.exit(principal())

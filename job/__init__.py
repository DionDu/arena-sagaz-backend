"""`job/` — O JOB EM BATCH DO DESAFIO DO DIA (RF-DES-010, RF-DES-011a).

Esta pasta é o **terceiro serviço** do Railway. Não é a API, e não vive dentro
dela: é um programa que acorda pelo cron, faz o trabalho pesado e **termina**.

═══════════════════════════════════════════════════════════════════════════
O QUE ELE FAZ, EM UMA FRASE
═══════════════════════════════════════════════════════════════════════════

Escolhe o jogo do dia, gera vários candidatos a desafio jogando de verdade com
os motores de `motores/`, **mede** cada candidato com os mascotes, e grava no
Postgres os melhores — com folga de 7 a 30 dias à frente.

═══════════════════════════════════════════════════════════════════════════
AS TRÊS REGRAS QUE ESTA CAMADA NÃO PODE QUEBRAR
═══════════════════════════════════════════════════════════════════════════

1. ⛔ **Ele não fala HTTP.** Nem serve, nem chama a API. Não há porta, rota nem
   `healthcheckPath`. A conversa entre o job e a API acontece **pelo Postgres**,
   que já é a fronteira entre os dois (RF-DES-011a). Um `import fastapi` aqui
   dentro é sinal de que alguém confundiu as duas metades.

2. ⛔ **Ele não julga ninguém.** O job **calibra**: mede quão difícil um
   candidato é. Quem julga a resolução de uma pessoa é o avaliador, e ele roda
   noutro lugar, com o **árbitro** — que não sabe escolher lance (RF-DES-161).

3. ⚠️ **Terminar é sucesso.** A política de reinício do serviço é `NEVER`. Sair
   com código 0 é o comportamento correto; um processo que fica de pé aqui
   significa que o Railway leu o `railway.json` errado (ver
   `docs/historico_decisoes.md`, 09/09/2026).

═══════════════════════════════════════════════════════════════════════════
COMO ELE ROLA
═══════════════════════════════════════════════════════════════════════════

    python -m job          # é literalmente o `CMD` do `Dockerfile.job`

O ponto de entrada está em `job/__main__.py` — o nome `__main__` é a convenção
do Python para "o que roda quando alguém executa o pacote com `-m`".
"""

import sys

# ═══════════════════════════════════════════════════════════════════════════
# ⛔ O JOB NÃO MORRE POR CAUSA DE UMA MENSAGEM
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **O console do Windows é cp1252**, e o log deste job é cheio de `⚠️` e `⛔` —
# eles são o que faz uma execução de sete dias ser legível de relance. No
# Railway não há problema (o stdout é UTF-8), mas **localmente o primeiro emoji
# derruba o processo**:
#
#     UnicodeEncodeError: 'charmap' codec can't encode characters
#
# ⛔ **E ele derruba no meio do trabalho**, depois de gerar e medir — perdendo o
# dia inteiro por causa de uma linha de aviso. Aconteceu em 11/09/2026, num
# `print` de descarte de posição.
#
# ⚠️ **Aqui, e não em cada ponto de entrada.** O job é rodado de quatro lugares
# (`python -m job`, os scripts de caçada e de medição, os testes, e o
# `Dockerfile.job`); uma chamada em cada um envelheceria torto — bastaria um
# script novo esquecer, e o defeito voltaria exatamente onde ninguém olha.
#
# ⚠️ `errors="replace"` de propósito: um caractere que o terminal não saiba
# desenhar vira `?`, e ⛔ **nunca uma exceção**. A mensagem degradada continua
# dizendo o que precisa dizer.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # Fluxo redirecionado para algo que não é um `TextIOWrapper` (um teste
        # que captura a saída, por exemplo). Não há o que reconfigurar, e isso
        # não é erro.
        pass


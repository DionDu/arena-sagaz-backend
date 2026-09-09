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

"""O MODO DE TESTE DO PAINEL: o que so o banco `des` deixa fazer (27/10/2026).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Pedido do dono, para testar no aparelho todos os tipos de desafio do Quatro em
Linha antes da 1.4.0: resolver o desafio de hoje, apagar as resolucoes dele,
trazer outro tipo para hoje, resolver de novo, e assim ate esgotar os tipos.

Tres travas do painel impedem esse ciclo, e todas tem razao de ser em
producao (o porque de cada uma esta em `servico.py` e em
`api/desafios/janela_baixada.py`):

  1. **o dia ja jogado** nao se move (as tentativas mudariam de data);
  2. **o que ja esta nos aparelhos** nao sai do dia dele;
  3. **ninguem apaga resolucao** - ela e a historia de quem jogou.

No modo de teste, a 2 deixa de valer para trocar datas e esvaziar o
calendario, e a 3 ganha um botao ("Limpar resolucoes"). ⛔ A 1 continua: um
dia ja PASSADO nunca e tocado, e o dia de hoje com tentativa so se move
depois de limpo.

═══════════════════════════════════════════════════════════════════════════
⛔ AS DUAS TRAVAS DO MODO DE TESTE
═══════════════════════════════════════════════════════════════════════════

O painel roda em dois lugares: na API do Railway (`des` e `prd`) e na maquina
do dono (`painel\\painel.cmd`), que aponta para o banco que ele ESCOLHER no
portico - inclusive o `prd`. Uma variavel so nao basta, e por isso sao duas:

  1. **`PAINEL_MODO_DE_TESTE` ligada.** O supervisor do portico a liga
     sozinho, e so quando o banco escolhido e o `des`
     (`painel/servidor/supervisor.py`). No Railway, so se alguem a criar no
     servico `des`.
  2. **A API nao se diz producao** (`configuracoes.eh_producao`, que le
     `AMBIENTE=producao`, definida no servico `prd` do Railway desde a spec 006).

⛔ Basta uma das duas faltar para o modo de teste nao existir: o botao some
**e** o servico recusa. Esconder o botao sem fechar a rota e seguranca de
fachada (a mesma regra de `PAINEL_PODE_GERAR`).
"""

from __future__ import annotations

import os

from api.configuracao import configuracoes

#: A variavel que liga o modo de teste. ⛔ Nunca no servico `prd` do Railway.
ENV_MODO_DE_TESTE = "PAINEL_MODO_DE_TESTE"


def modo_de_teste_ligado() -> bool:
    """O modo de teste vale neste processo?

    ⚠️ Le o ambiente **a cada chamada**, e nao uma vez no import: assim o teste
    liga e desliga com `monkeypatch`, e o valor nao fica preso ao instante em
    que o modulo foi carregado (a mesma escolha de `execucao_do_job.pode_gerar`).

    Returns:
        `True` so com a variavel ligada **e** fora de producao.
    """
    ligada = os.environ.get(ENV_MODO_DE_TESTE, "").strip() not in (
        "",
        "0",
        "false",
        "False",
    )
    # ⛔ A segunda trava: em producao, nem a variavel liga.
    return ligada and not configuracoes.eh_producao

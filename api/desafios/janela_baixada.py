"""A JANELA BAIXADA: os dias cujo desafio ja pode estar guardado nos aparelhos.

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

O aplicativo baixa o desafio de hoje e os dos proximos dias (`/v1/desafios/proximos`,
`DIAS_DE_CACHE`) e os guarda para jogar **sem rede**. Em 07/10/2026 o dono
perguntou o que acontece se ele trocar no servidor um desafio que um aparelho ja
baixou, enquanto esse aparelho esta sem rede. A leitura do codigo deu dois
defeitos silenciosos:

  · **Descartar** apaga o vinculo do dia. A pessoa resolve a versao antiga, ve
    "resolvido" no aparelho, e o envio volta com 400 (`vinculo_invalido`): o
    aplicativo o tira da fila, ela nao entra no quadro e o XP do desafio nao e
    creditado. Nada lhe diz isso.
  · **Trocar a data** (no painel, ou a compactacao do job) mantem o vinculo e muda
    o dia. O envio e ACEITO, e a pessoa aparece no quadro de um dia que ela nao
    jogou.

A guarda de "dia ja jogado" (`painel/servico.py`) nao pega nenhum dos dois: ela
olha as tentativas que o SERVIDOR tem, e as de quem esta sem rede estao presas no
aparelho.

⛔ **A decisao do dono** (`DECISOES-do-dono.md` §8zx do app): nada que ja esta na
janela baixada sai do dia dele - nem descarte, nem troca de data, nem tirar do
calendario. A curadoria fica restrita aos dias seguintes.

═══════════════════════════════════════════════════════════════════════════
ONDE A JANELA TERMINA
═══════════════════════════════════════════════════════════════════════════

No MAIOR destes dois dias:

  1. **hoje + `DIAS_DE_CACHE`** - a conta simples, quando a fila nao tem buraco;
  2. **o ultimo dos `DIAS_DE_CACHE` proximos dias publicados** - a mesma consulta
     do `/proximos`. ⚠️ E ela que importa quando ha buraco: com amanha vazio, o
     `/proximos` entrega D+2, D+3 e **D+4**, e a conta simples deixaria o D+4
     destravado estando ele no aparelho de alguem.

⚠️ **Por que basta olhar o que o servidor entrega HOJE**, se um aparelho pode ter
sincronizado ha dias: o fim da janela so anda para a frente. O que alguem baixou
ontem estava entre os proximos de ontem, e esses dias sao hoje (ou antes) ou estao
entre os proximos de hoje - desde que nada saia de dentro da janela, que e
justamente o que esta regra garante.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE CONTINUA PERMITIDO DENTRO DA JANELA: OCUPAR UM DIA VAZIO
═══════════════════════════════════════════════════════════════════════════

Um dia vazio da janela nao esta no aparelho de ninguem (o `/proximos` o pula).
Por-lhe um desafio que esta FORA da janela nao invalida nada que alguem guardou: o
aparelho sem rede simplesmente nao tem aquele dia, como ja nao tinha. E recusar
seria pior: deixaria um dia em branco no aplicativo, o defeito que o painel mais
evita. Por isso a trava e sobre a ORIGEM do movimento, e nao sobre o destino.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

from sqlalchemy import text

from api.desafios.modelos_evento import VW_DESAFIO_DIA
from api.desafios.modelos_producao import VW_DESAFIO
from api.desafios.repositorio import DIAS_DE_CACHE

#: Os dias dos proximos desafios que o `/proximos` entrega - so as datas.
#:
#: ⛔ **O mesmo filtro e a mesma ordem de `repositorio.SQL_PROXIMOS`** (aprovado,
#: depois de hoje, do mais perto ao mais longe, `LIMIT`). Se aquela consulta mudar,
#: esta muda junto: a janela e, por definicao, o que aquela entrega. O cadeado
#: `test_janela_baixada.py` confere as duas lado a lado.
#:
#: ⚠️ A subconsulta tem nome (`proximo`) porque o `LIMIT` vale para a lista e o
#: `MAX` para o resultado dela: sem a subconsulta, o `MAX` agregaria a tabela
#: inteira antes de o `LIMIT` cortar qualquer coisa.
SQL_FIM_DOS_PROXIMOS = f"""
SELECT MAX(proximo.dt_dia) AS dt_fim
  FROM (SELECT dia.dt_dia
          FROM {VW_DESAFIO_DIA} dia
          JOIN {VW_DESAFIO} d
            ON d.id_desafio = dia.id_desafio
         WHERE dia.dt_dia > :dt_hoje
           AND d.co_curadoria = 'aprovado'
         ORDER BY dia.dt_dia ASC
         LIMIT :limite) proximo
"""


def fim_da_janela_baixada(dt_hoje: date, proximos_publicados: Iterable[date]) -> date:
    """O ultimo dia (inclusive) cujo desafio pode estar guardado num aparelho.

    Args:
        dt_hoje: o dia corrente, em UTC (o dia do Desafio do Dia e UTC).
        proximos_publicados: as datas que o `/proximos` entrega agora. Pode vir
            vazio (fila sem nada a frente); a conta simples vale sozinha.

    Returns:
        O maior entre `dt_hoje + DIAS_DE_CACHE` e a ultima data entregue.

    ⚠️ Funcao pura, sem banco: e aqui que mora a regra, e o teste a mede sem
    precisar de uma consulta de mentira.
    """
    simples = dt_hoje + timedelta(days=DIAS_DE_CACHE)
    # `default=simples`: sem proximos publicados, o `max` de uma lista vazia
    # daria erro; a conta simples e a resposta certa nesse caso.
    return max(simples, max(proximos_publicados, default=simples))


async def ler_fim_da_janela_baixada(sessao: Any, dt_hoje: date) -> date:
    """`fim_da_janela_baixada`, com os proximos lidos do banco.

    Args:
        sessao: a sessao do SQLAlchemy de quem chama (a do painel ou a do job).
        dt_hoje: o dia corrente, em UTC.
    """
    resultado = await sessao.execute(
        text(SQL_FIM_DOS_PROXIMOS), {"dt_hoje": dt_hoje, "limite": DIAS_DE_CACHE}
    )
    linha = resultado.mappings().first()
    # `MAX` de nenhuma linha devolve UMA linha com `NULL`, e nao zero linhas.
    # Os dois casos querem dizer "nada publicado a frente".
    dt_fim = linha["dt_fim"] if linha else None
    return fim_da_janela_baixada(dt_hoje, [dt_fim] if dt_fim else [])


def na_janela_baixada(dt_dia: date, *, dt_hoje: date, dt_fim: date) -> bool:
    """O dia esta na janela? Hoje conta; o passado nao (tem a guarda dele)."""
    return dt_hoje <= dt_dia <= dt_fim

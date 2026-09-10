"""O JOB DE EXPIRACAO — o terceiro caminho de saida de `em_andamento` (T046).

═══════════════════════════════════════════════════════════════════════════
POR QUE ELE EXISTE
═══════════════════════════════════════════════════════════════════════════

Quando a linha de chegada cai **antes** do fim, o desafio fecha no objetivo e ⛔
**o aplicativo NAO interrompe a partida** de quem quiser continuar. Quem para ali
deixa a partida **sem fim** — e sao tres os caminhos de saida de `em_andamento`
(determinacao do dono, 08/09/2026):

    fim natural       → `concluida`, pelo proprio aplicativo
    sair da tela      → `abandonada`, pelo proprio aplicativo
    **este job**      → `abandonada`, depois de 7 dias

⚠️ **O terceiro existe porque o aplicativo pode nunca mais falar.** Desinstalar,
trocar de aparelho, ficar sem rede para sempre — em qualquer um desses casos a
partida ficaria `em_andamento` eternamente, e ⛔ **sem replay** (RF-DES-187):
`GET /replay` recusa partida sem desfecho, e o quadro do dia teria uma linha que
nao abre.

═══════════════════════════════════════════════════════════════════════════
⚠️ SETE DIAS, E O NUMERO TEM MOTIVO
═══════════════════════════════════════════════════════════════════════════

**A fila do aplicativo segura eventos sem rede.** Fechar antes correria o risco de
marcar como abandonada uma partida que ainda vai chegar completa — e ai o
`WHERE co_status = 'em_andamento'` do ingestor (T045) barraria a completacao, que
e exatamente o que ele deve barrar. O dado chegaria e seria descartado, com
razao, por causa de uma decisao tomada cedo demais.

═══════════════════════════════════════════════════════════════════════════
⛔ ABANDONAR NAO DESFAZ NADA
═══════════════════════════════════════════════════════════════════════════

Resolucao, XP e a linha do quadro foram creditados **no instante do objetivo**, e
continuam valendos. Este job muda **uma** coluna de estado e preenche `dh_fim`;
⛔ nao toca em `desafio_dia`, nao mexe em XP e nao tira ninguem do quadro.

⚠️ **`dh_fim = COALESCE(dh_fim, dh_inicio)`**, e nao `now()`. A partida nao
terminou agora — ela parou quando a pessoa parou. Carimbar o instante da
expiracao poria no log uma partida de sete dias de duracao, e qualquer analise de
tempo passaria a mentir.
"""

from __future__ import annotations

from typing import Any

#: Quantos dias uma partida de desafio pode ficar parada em `em_andamento`.
DIAS_ATE_EXPIRAR = 7

#: ⛔ **Só `co_modo = 'desafio'`.** Partida comum nunca sobe `em_andamento` — o
#: aplicativo so a envia no fim —, e uma que estivesse assim seria sintoma de
#: outro defeito, que este job apagaria ao "consertar".
#:
#: ⚠️ **A conta e sobre `dh_inicio`**, e nao sobre `dh_registro`: o que importa e
#: ha quanto tempo a **partida** parou, e nao ha quanto tempo o servidor soube
#: dela. Um lote antigo que chega hoje nao ganha sete dias novos.
#:
#: ⚠️ `RETURNING` traz o que mudou para o log poder dizer **quais** partidas
#: fechou — um numero sozinho nao permite investigar nada.
SQL_EXPIRAR = f"""
UPDATE partida.tb001_partida
   SET co_status = 'abandonada',
       dh_fim    = COALESCE(dh_fim, dh_inicio)
 WHERE co_modo   = 'desafio'
   AND co_status = 'em_andamento'
   AND dh_inicio < (now() - INTERVAL '{DIAS_ATE_EXPIRAR} days')
RETURNING id_partida, id_usuario, dh_inicio
"""


async def expirar(sessao: Any) -> list[dict[str, Any]]:
    """Fecha as partidas de desafio paradas ha mais de sete dias.

    Args:
        sessao: uma `AsyncSession` (ou duble com `execute`/`commit`).

    Returns:
        As partidas fechadas — ⚠️ a **lista**, e nao a contagem: quem le o log
        precisa poder abrir uma delas quando o numero surpreender.

    ⚠️ **Um `UPDATE` so, e nao um laco.** Ler as candidatas e atualizar uma a uma
    abriria uma janela entre a leitura e a escrita em que uma partida poderia ser
    completada pelo ingestor — e o job a fecharia como abandonada logo depois de
    ela ter terminado de verdade.
    """
    from sqlalchemy import text

    resultado = await sessao.execute(text(SQL_EXPIRAR))
    fechadas = [dict(m) for m in resultado.mappings().all()]
    await sessao.commit()
    return fechadas


def resumo(fechadas: list[dict[str, Any]]) -> str:
    """A linha de log da execucao.

    ⚠️ **Zero e uma informacao boa**, e por isso ela tambem e impressa: significa
    que todo mundo esta completando as partidas, que e o estado saudavel. Um job
    silencioso quando nao faz nada e indistinguivel de um job que nao rodou.
    """
    if not fechadas:
        return (
            "[expiracao] nenhuma partida de desafio parada ha mais de "
            f"{DIAS_ATE_EXPIRAR} dias. ✅"
        )
    return (
        f"[expiracao] {len(fechadas)} partida(s) de desafio fechada(s) como "
        f"abandonada apos {DIAS_ATE_EXPIRAR} dias. ⛔ Isso NAO desfaz resolucao, "
        "XP nem linha do quadro."
    )

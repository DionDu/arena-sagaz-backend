"""O INGESTOR COM `DO UPDATE` E O JOB DE EXPIRACAO — T045 e T046.

Os dois resolvem **o mesmo problema por lados opostos**: uma partida de desafio
que parou no objetivo e ficou `em_andamento`.

    T045 → o aplicativo volta e a completa
    T046 → o aplicativo nunca mais fala, e o servidor a fecha em 7 dias

⚠️ Juntos, eles sao o que torna RF-DES-187 (*"toda partida de desafio esta
fechada"*) verdadeiro — e e por isso que a rota de resolucao pode aceitar
partida em andamento sem quebrar a promessa.

O que estes casos protegem:

  · ⛔ **o `WHERE co_status = 'em_andamento'`** — sem ele, a idempotencia do
    `co_evento` viraria "o ultimo envio manda", e um reenvio antigo **reabriria**
    uma partida concluida;
  · ⚠️ **`xmax = 0`** distingue INSERT de UPDATE — sem isso, a completacao
    gravaria o XP de novo e **dobraria** o da partida;
  · ⛔ **abandonar nao desfaz nada** — o job muda uma coluna de estado e o
    `dh_fim`, e mais nada;
  · ⚠️ **`dh_fim = COALESCE(dh_fim, dh_inicio)`**, e nao `now()`: carimbar a
    expiracao poria no log uma partida de sete dias.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from api.sincronizacao import repositorio as repo_sync
from job import expirar_partidas
from job.expirar_partidas import DIAS_ATE_EXPIRAR, expirar, resumo
from tests.unitarios.fakes_desafio import FakeSessaoSQL

AGORA = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O ingestor (T045, RF-DES-213)
# ═══════════════════════════════════════════════════════════════════════════


def _fonte() -> str:
    """O arquivo do repositorio de sincronizacao, inteiro."""
    from pathlib import Path

    return Path(repo_sync.__file__).read_text(encoding="utf-8")


def _sql_da_partida() -> str:
    """**Somente** o comando `INSERT` da partida, recortado do arquivo.

    ⚠️ Lido do codigo, e nao copiado para ca: uma copia envelheceria e o
    cadeado passaria a conferir uma consulta que ninguem executa.

    ⚠️ **E recortado, e nao o arquivo todo**: a docstring do modulo descreve
    as tres formas de idempotencia que ele usa, e um cadeado que lesse o arquivo
    inteiro confundiria a **descricao** com o **comando** — exatamente o defeito
    que ja apareceu cinco vezes neste projeto (ver `leitura_de_migracao.py`).
    """
    fonte = _fonte()
    depois = fonte.split("INSERT INTO partida.tb001_partida", 1)[1]
    return depois.split('"""', 1)[0]


def test_o_ingestor_usa_DO_UPDATE_e_nao_DO_NOTHING():
    """⚠️ RF-DES-213: com `DO NOTHING`, o envio que **completava** a partida era
    descartado em silencio.

    A partida ficava `em_andamento` para sempre, sem replay (RF-DES-187) e sem
    `dh_fim` — e nada no sistema acusava.
    """
    sql = _sql_da_partida()
    assert "ON CONFLICT (co_evento) DO UPDATE" in sql
    # ⚠️ `DO NOTHING` continua correto para o merge de convidado e para as
    # jogadas — por isso a busca e no comando, e nao no arquivo.
    assert "DO NOTHING" not in sql


def test_o_WHERE_impede_que_isso_vire_o_ultimo_envio_manda():
    """⛔ **A linha mais importante desta tarefa.**

    Sem o `WHERE`, um reenvio antigo do outbox **reabriria** uma partida ja
    concluida — pior que o defeito que isto conserta. Com ele, a mudanca e de mao
    unica: `em_andamento → concluida/abandonada`, e nunca de volta.
    """
    assert (
        "WHERE partida.tb001_partida.co_status = 'em_andamento'"
        in _sql_da_partida()
    )


def test_as_cinco_colunas_do_requisito_estao_no_UPDATE():
    """`co_status`, `dh_fim`, os dois placares e `qt_usos_poder`.

    ⚠️ **E so elas.** `co_modo`, `ic_pontua` e `dh_inicio` ficam de fora de
    proposito: um envio que mudasse o modo de uma partida ja gravada trocaria a
    natureza dela depois do fato.
    """
    trecho = _sql_da_partida().split("ON CONFLICT (co_evento) DO UPDATE")[1].split(
        "RETURNING"
    )[0]
    for coluna in (
        "co_status",
        "dh_fim",
        "nu_placar_j1",
        "nu_placar_j2",
        "qt_usos_poder",
    ):
        assert coluna in trecho, f"{coluna} ficou de fora do UPDATE"
    assert "co_modo" not in trecho
    assert "ic_pontua" not in trecho


def test_xmax_distingue_insert_de_update():
    """⚠️ Sem isso nao daria para saber se este envio e o primeiro ou a
    completacao — e gravar tudo de novo **dobraria o XP da partida**.

    E o truque do Postgres: na linha recem-inserida `xmax` e zero; na atualizada,
    carrega a transacao que a travou.
    """
    assert "(xmax = 0) AS ic_inserida" in _sql_da_partida()


def test_as_jogadas_sao_append_only():
    """⚠️ O aplicativo reenvia a **fita inteira** na completacao.

    ⛔ `ON CONFLICT DO NOTHING` **sem nomear a constraint**: o reenvio traz o
    mesmo `id_jogada`, e esse conflito e na **chave primaria** — nomear so
    `(id_partida, nu_ordem)` deixaria o erro passar e o evento inteiro seria
    rejeitado.
    """
    # ⚠️ Aqui o alvo e o `INSERT` da JOGADA, e nao o da partida — por isso o
    # arquivo inteiro, com o trecho exato o bastante para nao casar com outro.
    assert "ON CONFLICT DO NOTHING\n                RETURNING id_jogada" in _fonte()


def test_o_xp_tem_sentinela_contra_gravacao_dupla():
    """⛔ `tb003_xp_partida` **nao tem chave natural**.

    Nada no banco impede gravar as mesmas parcelas duas vezes, e o efeito seria
    XP dobrado, sem erro nenhum. A sentinela e a propria ausencia de parcelas.
    """
    fonte = _fonte()
    assert "async def _ja_tem_xp" in fonte
    assert "if not await self._ja_tem_xp(id_partida):" in fonte


# ═══════════════════════════════════════════════════════════════════════════
# 2. O job de expiracao (T046)
# ═══════════════════════════════════════════════════════════════════════════


def test_so_partida_de_DESAFIO_expira():
    """⛔ Partida comum nunca sobe `em_andamento`.

    O aplicativo so a envia no fim, e uma que estivesse assim seria sintoma de
    **outro** defeito — que este job apagaria ao "consertar".
    """
    assert "co_modo   = 'desafio'" in expirar_partidas.SQL_EXPIRAR


def test_expira_so_o_que_esta_em_andamento():
    """A mudanca e de mao unica, como no ingestor."""
    assert "co_status = 'em_andamento'" in expirar_partidas.SQL_EXPIRAR


def test_sao_sete_dias_e_a_conta_e_sobre_dh_inicio():
    """⚠️ **A fila do aplicativo segura eventos sem rede.**

    Fechar antes marcaria como abandonada uma partida que ainda vai chegar
    completa — e ai o `WHERE` do ingestor barraria a completacao, com razao, por
    causa de uma decisao tomada cedo demais.

    ⚠️ E a conta e sobre `dh_inicio`, e nao `dh_registro`: importa ha quanto
    tempo a **partida** parou, e nao ha quanto tempo o servidor soube dela.
    """
    assert DIAS_ATE_EXPIRAR == 7
    assert "INTERVAL '7 days'" in expirar_partidas.SQL_EXPIRAR
    assert "dh_inicio < (now()" in expirar_partidas.SQL_EXPIRAR


def test_o_dh_fim_nao_e_now():
    """⚠️ A partida nao terminou agora — ela parou quando a pessoa parou.

    Carimbar o instante da expiracao poria no log uma partida de **sete dias de
    duracao**, e qualquer analise de tempo passaria a mentir.
    """
    assert "dh_fim    = COALESCE(dh_fim, dh_inicio)" in expirar_partidas.SQL_EXPIRAR
    assert "dh_fim    = now()" not in expirar_partidas.SQL_EXPIRAR


def test_abandonar_nao_desfaz_nada():
    """⛔ Resolucao, XP e a linha do quadro foram creditados **no instante do
    objetivo**, e continuam valendo.

    O `UPDATE` toca duas colunas de `partida.tb001_partida`, e nenhuma tabela de
    `desafio_dia` aparece nele.
    """
    sql = expirar_partidas.SQL_EXPIRAR
    assert "desafio_dia" not in sql
    assert "tb003_resolucao" not in sql
    assert "tb004_xp_desafio" not in sql
    assert sql.count("UPDATE") == 1


@pytest.mark.asyncio
async def test_expirar_devolve_a_LISTA_e_nao_a_contagem():
    """⚠️ Quem le o log precisa poder **abrir uma delas** quando o numero
    surpreender."""
    fechadas = [
        {"id_partida": uuid4(), "id_usuario": "uid-1", "dh_inicio": AGORA},
        {"id_partida": uuid4(), "id_usuario": "uid-2", "dh_inicio": AGORA},
    ]
    sessao = FakeSessaoSQL(respostas={"SET co_status = 'abandonada'": fechadas})

    devolvidas = await expirar(sessao)

    assert len(devolvidas) == 2
    assert "id_partida" in devolvidas[0]
    assert sessao.commits == 1


@pytest.mark.asyncio
async def test_um_UPDATE_so_e_nao_um_laco():
    """⚠️ Ler as candidatas e atualizar uma a uma abriria uma janela entre a
    leitura e a escrita.

    Nela, uma partida poderia ser completada pelo ingestor — e o job a fecharia
    como abandonada logo depois de ela ter terminado de verdade.
    """
    sessao = FakeSessaoSQL(respostas={"SET co_status = 'abandonada'": []})
    await expirar(sessao)

    assert len(sessao.executadas) == 1


def test_zero_tambem_e_informacao():
    """⚠️ Um job silencioso quando nao faz nada e indistinguivel de um job que
    nao rodou."""
    assert "nenhuma partida" in resumo([])
    assert "1 partida" in resumo([{"id_partida": uuid4()}])


def test_o_resumo_lembra_que_nada_foi_desfeito():
    """A frase existe para quem le o log as 3h da manha e se assusta."""
    texto = resumo([{"id_partida": uuid4()}])
    assert "NAO desfaz resolucao" in texto

"""🔒 CADEADO 8 — TODA PARTIDA DE DESAFIO CHEGA A ESTADO TERMINAL (RF-DES-187).

═══════════════════════════════════════════════════════════════════════════
O QUE A PROMESSA SIGNIFICA, E O QUE ELA NAO SIGNIFICA
═══════════════════════════════════════════════════════════════════════════

⚠️ **E sobre o JOGO ter fim, e nao sobre a pessoa jogar ate la.** Quem para no
objetivo deixa a partida sem fim, e isso e esperado: o desafio fecha na chegada, e
⛔ **o aplicativo NAO interrompe a partida** de quem quiser continuar.

Sao **tres** os caminhos de saida de `em_andamento` (determinacao do dono,
08/09/2026), e a promessa so e verdadeira porque os tres existem:

    fim natural       → `concluida`, pelo aplicativo
    sair da tela      → `abandonada`, pelo aplicativo
    job de expiracao  → `abandonada`, 7 dias depois (T046)

⚠️ **Sem o terceiro, a promessa seria falsa**, e de um jeito que ninguem veria: o
aplicativo pode nunca mais falar (desinstalado, aparelho trocado), e a partida
ficaria `em_andamento` para sempre — sem `dh_fim` e **sem replay**.

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTE ARQUIVO E A METADE ESTRUTURAL. A OUTRA MORA NO BANCO.
═══════════════════════════════════════════════════════════════════════════

T048 pede que *"toda resolucao aponte para partida em estado terminal, e **sem
resolucao para conferir e falha**"*. Essa segunda metade e sobre **dados**, e nao
sobre codigo: ela precisa de resolucoes de verdade, e so o banco as tem.

  · **aqui (CI)** — as tres saidas existem, e nada no codigo as contorna;
  · **`scripts/conferir_desafio_no_banco.py`** — a consulta que cobra as linhas,
    e que **falha quando nao ha resolucao nenhuma para conferir**. E o portao
    T050 que a executa.

⛔ **E ha um caso aqui que falha se aquele script sumir.** Sem isso, a metade de
dados poderia desaparecer num commit e o CI continuaria verde — que e exatamente
a cegueira que os cadeados existem para impedir.
"""

from __future__ import annotations

from pathlib import Path

from api.desafios import quadro, servico_quadro
from api.sincronizacao import repositorio as repo_sync
from job import expirar_partidas

RAIZ = Path(__file__).resolve().parents[2]
CONFERIDOR = RAIZ / "scripts" / "conferir_desafio_no_banco.py"


# ═══════════════════════════════════════════════════════════════════════════
# 1. As tres saidas de `em_andamento`
# ═══════════════════════════════════════════════════════════════════════════


def test_o_ingestor_permite_a_saida_pelo_aplicativo():
    """A 1a e a 2a saidas: o aplicativo volta e fecha a partida.

    ⚠️ Com `DO NOTHING`, o envio que a completava era descartado **em silencio**
    (T045). O `DO UPDATE` e o que faz esses dois caminhos existirem de fato.
    """
    fonte = Path(repo_sync.__file__).read_text(encoding="utf-8")
    sql = fonte.split("INSERT INTO partida.tb001_partida", 1)[1].split('"""', 1)[0]

    assert "ON CONFLICT (co_evento) DO UPDATE" in sql
    assert "co_status" in sql
    # ⛔ E de mao unica: nunca reabre o que ja fechou.
    assert "WHERE partida.tb001_partida.co_status = 'em_andamento'" in sql


def test_a_terceira_saida_existe_e_e_o_job_de_expiracao():
    """⚠️ **Sem ela a promessa seria falsa**, e ninguem veria.

    O aplicativo pode nunca mais falar; a partida ficaria `em_andamento` para
    sempre, sem `dh_fim` e sem replay.
    """
    assert expirar_partidas.DIAS_ATE_EXPIRAR == 7
    sql = expirar_partidas.SQL_EXPIRAR
    assert "co_status = 'abandonada'" in sql
    assert "co_modo   = 'desafio'" in sql
    assert "co_status = 'em_andamento'" in sql


def test_abandonar_nao_desfaz_resolucao_xp_nem_quadro():
    """⛔ Eles foram creditados **no instante do objetivo**, e continuam valendo.

    Se este cadeado falhar porque alguem acrescentou `desafio_dia` ao job, o
    conserto e tirar de la — e nao ampliar o teste.
    """
    sql = expirar_partidas.SQL_EXPIRAR
    assert "desafio_dia" not in sql
    assert "tb003_resolucao" not in sql
    assert "tb004_xp_desafio" not in sql


# ═══════════════════════════════════════════════════════════════════════════
# 2. E o que NAO existe sem partida fechada
# ═══════════════════════════════════════════════════════════════════════════


def test_o_replay_recusa_partida_em_andamento():
    """⛔ RF-DES-187/SC-024: sem desfecho nao ha replay.

    ⚠️ **A recusa e do SERVIDOR**, e nao da tela: a rota le `co_status` e
    responde 404 com codigo proprio. Servir meia partida seria pior — a pessoa
    veria um replay que termina no nada e concluiria que o aplicativo perdeu
    lances.
    """
    fonte = Path(servico_quadro.__file__).read_text(encoding="utf-8")
    assert 'linha["co_status"] == "em_andamento"' in fonte
    assert "partida_em_andamento" in fonte
    # ⚠️ E a consulta traz `co_status` — sem isso a checagem acima nao teria o
    # que ler, e passaria a comparar `None` com a string, sempre falso.
    assert "p.co_status" in quadro.SQL_PARTIDA_DO_SUJEITO


def test_a_resolucao_aponta_para_a_partida_pela_TENTATIVA():
    """⚠️ **A tentativa precede a resolucao**, e nao o contrario.

    `id_partida` nao e conveniencia de replay: e **condicao de leitura do log**.
    A reconstrucao do tabuleiro de Pontinhos a partir das arestas assume comecar
    de um tabuleiro vazio, e um desafio nao comeca vazio — a posicao inicial so e
    alcancavel por `tentativa → dia → desafio`.
    """
    assert "JOIN desafio_dia.tb002_tentativa" in _sql_da_view_de_resolucao()
    assert "t.id_partida" in _sql_da_view_de_resolucao()


def _sql_da_view_de_resolucao() -> str:
    """O DDL de `vw003_resolucao`, lido da migracao com `ast`."""
    from tests.unitarios.leitura_de_migracao import sql_da_migracao

    sql = sql_da_migracao(
        RAIZ / "migrations" / "versions" / "0019_schema_desafio_dia.py"
    )
    return sql.split("CREATE VIEW desafio_dia.vw003_resolucao AS", 1)[1].split(
        "CREATE VIEW", 1
    )[0]


# ═══════════════════════════════════════════════════════════════════════════
# 3. ⛔ A metade de dados nao pode sumir
# ═══════════════════════════════════════════════════════════════════════════


def test_o_conferidor_de_dados_existe():
    """⛔ **Sem este caso, a metade de dados poderia desaparecer num commit** e o
    CI continuaria verde — a cegueira que os cadeados existem para impedir.

    O que so o banco sabe (*"toda resolucao aponta para partida terminal"*, e
    *"sem resolucao para conferir e falha"*) vive em
    `scripts/conferir_desafio_no_banco.py`, e o portao T050 o executa.
    """
    assert CONFERIDOR.is_file(), (
        f"{CONFERIDOR} sumiu. ⛔ Ele e a metade de DADOS do cadeado 8: sem ele, "
        "'toda resolucao aponta para partida em estado terminal' deixa de ser "
        "conferido em lugar nenhum, e este arquivo passa a proteger so metade do "
        "que promete."
    )


def test_o_conferidor_falha_quando_nao_ha_o_que_conferir():
    """⚠️ **Nada a varrer e FALHA, e nao sucesso** — o texto de T048.

    Um conferidor que aprova o banco vazio ensina a confiar nele exatamente
    quando ele nao esta olhando nada.
    """
    fonte = CONFERIDOR.read_text(encoding="utf-8")
    assert "sem resolucao" in fonte.lower()
    # A promessa esta no codigo, e nao so no comentario: ha um caminho que
    # devolve reprovacao quando a contagem e zero.
    assert "REPROVOU" in fonte or "reprovou" in fonte

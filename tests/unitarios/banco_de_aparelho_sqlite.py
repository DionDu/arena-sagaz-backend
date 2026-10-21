"""O banco de mentira do registro do aparelho - um SQLite de memória (T118).

⚠️ **Não é um arquivo de teste**: não tem caso nenhum. É a peça que os testes do
repositório e das rotas do aparelho compartilham, para que os dois rodem o SQL
DE VERDADE sobre o mesmo desenho de tabelas.

═══════════════════════════════════════════════════════════════════════════
POR QUE SQLITE, E O QUE ELE NÃO PROVA
═══════════════════════════════════════════════════════════════════════════

O que o registro do dia entrega são **as cláusulas do SQL**: a chave do
`ON CONFLICT`, a trava `WHERE co_versao_app = :versao_lida`, os `COALESCE` que
não apagam o que outra rota gravou. Uma sessão falsa provaria só que um texto
foi enviado - e deixaria passar exatamente a mutação que importa, a de alguém
apagar uma condição. Então o SQL do repositório roda aqui, sem cópia.

O SQLite entende `ON CONFLICT ... DO NOTHING/DO UPDATE`, `RETURNING`, `COALESCE`
e `CASE`, e o `ATTACH` dá a ele schemas com nome (`log.`, `conta.`,
`partida.`), como o Postgres tem. ⚠️ **O que ele NÃO prova** é o que é só do
Postgres: os tipos `UUID`, `NUMERIC(4,2)` e `JSONB`, e o `CAST(... AS JSONB)`.
Esse último é a ÚNICA troca feita no SQL do repositório (ver
`trocar_cast_jsonb`); os tipos são conferidos contra o documento validado pelo
dono em `test_migracao_aparelho_bate_com_data_model.py`.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.aparelhos import repositorio

# O `sqlite3` do Python não sabe guardar `date` nem `Decimal` sem um adaptador
# (o de `date` existia e foi depreciado no 3.12). O repositório manda os dois
# tipos que o asyncpg espera; aqui eles viram texto, que é como o SQLite os
# guarda de qualquer forma.
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_adapter(Decimal, str)

#: O trecho que o SQLite não entende, e o que entra no lugar dele.
CAST_JSONB = "CAST(:js_espaco_app AS JSONB)"


def trocar_cast_jsonb(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tira o `CAST(... AS JSONB)` das duas escritas do dia, e só ele.

    ⚠️ **Confere antes de trocar**: se o trecho sumir do repositório (alguém
    mudou como o JSONB é gravado), o `assert` falha aqui, em vez de o teste
    passar a rodar um SQL que já não é o de produção. No SQLite o
    `CAST(x AS JSONB)` não dá erro: ele vira `NUMERIC` e grava ZERO no lugar do
    texto - o pior jeito de um teste mentir.
    """
    for nome in ("SQL_INSERIR_DIA", "SQL_ATUALIZAR_DIA"):
        original = getattr(repositorio, nome)
        assert CAST_JSONB in original, f"{nome} já não grava o JSONB com CAST"
        monkeypatch.setattr(repositorio, nome, original.replace(CAST_JSONB, ":js_espaco_app"))


#: As tabelas, na forma mais próxima da `0036` que o SQLite aceita. A ordem e os
#: nomes das colunas são os da migração; os tipos são os do SQLite.
_ESQUEMA = (
    "ATTACH DATABASE ':memory:' AS log",
    "ATTACH DATABASE ':memory:' AS conta",
    "ATTACH DATABASE ':memory:' AS partida",
    """
    CREATE TABLE log.tb003_aparelho (
        id_aparelho             TEXT PRIMARY KEY,
        ic_legado               BOOLEAN NOT NULL DEFAULT FALSE,
        co_plataforma           TEXT NOT NULL
            CHECK (co_plataforma IN ('android', 'ios', 'web')),
        no_fabricante           TEXT,
        no_modelo               TEXT,
        co_abi                  TEXT,
        no_processador          TEXT,
        qt_nucleos              INTEGER,
        nu_ram_mb               INTEGER,
        nu_tela_largura_dp      INTEGER,
        nu_tela_altura_dp       INTEGER,
        nu_densidade_tela       TEXT,
        co_instancia_analytics  TEXT,
        dh_registro             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE log.tb004_aparelho_dia (
        id_aparelho       TEXT NOT NULL REFERENCES tb003_aparelho(id_aparelho),
        dt_dia_local      TEXT NOT NULL,
        id_usuario        TEXT,
        co_versao_app     TEXT NOT NULL,
        co_versao_so      TEXT,
        co_idioma         TEXT,
        nu_espaco_app_kb  INTEGER,
        js_espaco_app     TEXT,
        dh_registro       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id_aparelho, dt_dia_local)
    )
    """,
    # As views moram no MESMO banco anexado das tabelas, e por isso as citam
    # sem o prefixo: no SQLite uma view de um banco anexado só enxerga o
    # próprio banco.
    "CREATE VIEW log.vw003_aparelho AS SELECT * FROM tb003_aparelho",
    "CREATE VIEW log.vw004_aparelho_dia AS SELECT * FROM tb004_aparelho_dia",
    # A conta: a view que o repositório lê, e as quatro tabelas que a exclusão
    # apaga (`api/conta/repositorio.py::remover_dados_vinculados`).
    "CREATE TABLE conta.vw001_usuario (id_usuario TEXT, co_identidade_externa TEXT)",
    "CREATE TABLE conta.tb002_provedor_login (id_usuario TEXT)",
    "CREATE TABLE conta.tb004_consentimento (id_usuario TEXT)",
    "CREATE TABLE conta.tb005_dispositivo_notificacao (id_usuario TEXT)",
    "CREATE TABLE conta.tb006_preferencia_notificacao (id_usuario TEXT)",
    # A partida: só as três colunas que o fuso da pessoa lê.
    """
    CREATE TABLE partida.vw001_partida (
        id_usuario           TEXT,
        nu_offset_minuto_j1  INTEGER,
        dh_inicio            TEXT
    )
    """,
)


async def abrir_banco():
    """`(engine, sessão)` de um SQLite de memória com o desenho do aparelho.

    `StaticPool` + uma conexão só é o que faz o `:memory:` sobreviver: cada
    conexão nova de um SQLite em memória é um banco **vazio** e diferente, e
    sem isto o `ATTACH` e as consultas veriam bancos distintos.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    sessao = fabrica()
    for comando in _ESQUEMA:
        await sessao.execute(text(comando))
    await sessao.commit()
    return engine, sessao


async def linhas(sessao, sql: str, **parametros) -> list[dict]:
    """As linhas de uma consulta como dicionários - o jeito curto de conferir."""
    resultado = await sessao.execute(text(sql), parametros)
    return [dict(linha) for linha in resultado.mappings().all()]

"""As conquistas do Desafio do Dia no SERVIDOR (05/10/2026): os dias resolvidos
que a progressão devolve.

⚠️ O bônus de XP creditado ao inserir a conquista morava aqui também. Desde a
T167 da spec 010 (30/10/2026) ele vale para TODAS as conquistas, e os casos dele
(o crédito e os cadeados da tabela) estão em ``test_bonus_das_conquistas.py``.

═══════════════════════════════════════════════════════════════════════════
O QUE O DONO PEDIU
═══════════════════════════════════════════════════════════════════════════

*"Estas quantidades de desafios concluídos não podem ficar apenas salvos no
aparelho do usuário. [...] o usuário pode fazer logoff no seu aparelho e outro
usuário se logar no mesmo aparelho. Também um usuário pode usar mais de 1
dispositivo."* E: *"não misture vitória em partidas com desafio resolvido"*.

Por isso o servidor devolve **os dias** (``dias_desafio_resolvido``), derivados
da tabela de resolução - nunca da de partidas -, e o app une com os que ele viu.
E o bônus das conquistas do desafio é creditado pelo servidor, uma vez, pelo
valor da tabela dele (decisão do dono, 05/10/2026) - ver
``test_bonus_das_conquistas.py``.

═══════════════════════════════════════════════════════════════════════════
COMO CADA PARTE É PROVADA
═══════════════════════════════════════════════════════════════════════════

* A consulta dos dias roda **de verdade**, num SQLite de memória com o schema
  ``desafio_dia`` anexado - o mesmo truque de ``test_vitorias_por_jogo.py``. Uma
  sessão falsa provaria só que linhas viram lista, e deixaria passar quem
  apagasse o ``WHERE``.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.sincronizacao.repositorio import RepositorioSincronizacao

DONO = "63385354-1e03-44bc-b2a3-82fdb8e34547"
OUTRA_PESSOA = "00000000-0000-0000-0000-000000000001"


# ═══════════════════════════════════════════════════════════════════════════
# Os dias resolvidos - o SQL de verdade
# ═══════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def sessao_sqlite():
    """SQLite de memória com o schema ``desafio_dia`` e as duas VIEWs imitadas.

    ``StaticPool`` mantém uma conexão só: cada conexão nova a um ``:memory:``
    seria um banco vazio e diferente, e o ``ATTACH`` se perderia.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        # `ATTACH` dá o apelido `desafio_dia` a um segundo banco - é o que torna
        # `desafio_dia.vw003_resolucao` um nome válido aqui, como o schema é lá.
        await s.execute(text("ATTACH DATABASE ':memory:' AS desafio_dia"))
        await s.execute(
            text(
                "CREATE TABLE desafio_dia.vw001_desafio_dia "
                "(id_desafio_dia TEXT, dt_dia TEXT)"
            )
        )
        await s.execute(
            text(
                "CREATE TABLE desafio_dia.vw003_resolucao "
                "(id_desafio_dia TEXT, id_usuario TEXT)"
            )
        )
        yield s
    await engine.dispose()


async def _publicar(sessao: Any, id_desafio_dia: str, dia: str) -> None:
    """Um dia de desafio publicado."""
    await sessao.execute(
        text(
            "INSERT INTO desafio_dia.vw001_desafio_dia (id_desafio_dia, dt_dia) "
            "VALUES (:id, :dia)"
        ),
        {"id": id_desafio_dia, "dia": dia},
    )


async def _resolver(sessao: Any, id_desafio_dia: str, quem: str = DONO) -> None:
    """[quem] resolveu o desafio [id_desafio_dia]."""
    await sessao.execute(
        text(
            "INSERT INTO desafio_dia.vw003_resolucao (id_desafio_dia, id_usuario) "
            "VALUES (:id, :quem)"
        ),
        {"id": id_desafio_dia, "quem": quem},
    )


@pytest.mark.asyncio
async def test_os_dias_saem_em_ordem_e_so_os_da_pessoa(sessao_sqlite):
    """Os quatro dias reais do dono no ``des`` (consultados em 05/10/2026: 30/09
    a 04/10, com um buraco), mais uma resolução de outra pessoa que não pode
    vazar para ele."""
    for i, dia in enumerate(
        ["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]
    ):
        await _publicar(sessao_sqlite, f"d{i}", dia)
    # Gravados fora de ordem, de propósito: a ordem da resposta é do `ORDER BY`.
    await _resolver(sessao_sqlite, "d4")
    await _resolver(sessao_sqlite, "d0")
    await _resolver(sessao_sqlite, "d2")
    await _resolver(sessao_sqlite, "d1")
    await _resolver(sessao_sqlite, "d3", quem=OUTRA_PESSOA)

    repo = RepositorioSincronizacao(sessao_sqlite)

    assert await repo.dias_com_desafio_resolvido(DONO) == [
        "2026-09-30",
        "2026-10-01",
        "2026-10-02",
        "2026-10-04",
    ]
    assert await repo.dias_com_desafio_resolvido(OUTRA_PESSOA) == ["2026-10-03"]


@pytest.mark.asyncio
async def test_quem_nunca_resolveu_recebe_lista_vazia(sessao_sqlite):
    """⚠️ **Vazio, e não ausente**: o app lê a AUSÊNCIA do campo como "servidor
    antigo, não sei", e a lista vazia como "o servidor não conhece dia nenhum".
    Nenhuma das duas apaga o que o aparelho sabe - lá a junção é união."""
    await _publicar(sessao_sqlite, "d0", "2026-10-04")
    repo = RepositorioSincronizacao(sessao_sqlite)
    assert await repo.dias_com_desafio_resolvido(DONO) == []

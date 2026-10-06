"""As conquistas do Desafio do Dia no SERVIDOR (05/10/2026): os dias resolvidos
que a progressão devolve, e o bônus de XP creditado ao inserir a conquista.

═══════════════════════════════════════════════════════════════════════════
O QUE O DONO PEDIU
═══════════════════════════════════════════════════════════════════════════

*"Estas quantidades de desafios concluídos não podem ficar apenas salvos no
aparelho do usuário. [...] o usuário pode fazer logoff no seu aparelho e outro
usuário se logar no mesmo aparelho. Também um usuário pode usar mais de 1
dispositivo."* E: *"não misture vitória em partidas com desafio resolvido"*.

Por isso o servidor devolve **os dias** (``dias_desafio_resolvido``), derivados
da tabela de resolução - nunca da de partidas -, e o app une com os que ele viu.
E o bônus das conquistas do desafio é creditado **aqui**, uma vez, pelo valor da
tabela do servidor (decisão do dono, 05/10/2026).

═══════════════════════════════════════════════════════════════════════════
COMO CADA PARTE É PROVADA
═══════════════════════════════════════════════════════════════════════════

* A consulta dos dias roda **de verdade**, num SQLite de memória com o schema
  ``desafio_dia`` anexado - o mesmo truque de ``test_vitorias_por_jogo.py``. Uma
  sessão falsa provaria só que linhas viram lista, e deixaria passar quem
  apagasse o ``WHERE``.
* O crédito usa SQL do Postgres (``xmax``, ``gen_random_uuid()``) que o SQLite
  não roda; ali uma sessão que ANOTA cada comando prova a regra que importa:
  credita na inserção nova, e só nela, e só conquista de desafio.
* O cadeado final lê o catálogo do APP e compara os bônus código a código.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.sincronizacao.conquistas_do_desafio import (
    BONUS_DAS_CONQUISTAS_DO_DESAFIO,
    bonus_da_conquista_do_desafio,
)
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


# ═══════════════════════════════════════════════════════════════════════════
# O bônus - a regra do crédito, com uma sessão que anota
# ═══════════════════════════════════════════════════════════════════════════


class _Resultado:
    """O que ``sessao.execute`` devolve: só o que o repositório lê dele."""

    def __init__(self, valor: Any) -> None:
        self._valor = valor

    def scalar(self) -> Any:
        return self._valor

    def first(self) -> Any:
        return self._valor


class _SessaoQueAnota:
    """Anota cada comando e responde à INSERÇÃO da conquista com [inserido].

    ``gravar_conquista`` lê ``scalar()`` (o ``xmax = 0``); a migração do
    convidado lê ``first()`` (uma linha no ``RETURNING`` = inseriu). A mesma
    resposta serve aos dois: ``True``/uma linha quando inseriu, ``None`` quando
    a conquista já estava lá.
    """

    def __init__(self, *, inserido: bool) -> None:
        self.inserido = inserido
        self.comandos: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, comando: Any, parametros: dict[str, Any]) -> _Resultado:
        sql = str(comando)
        self.comandos.append((sql, parametros))
        if "tb002_conquista_usuario" in sql:
            return _Resultado(True if self.inserido else None)
        if "tb003_lote_migracao" in sql:
            # O lote é novo: a migração segue até as conquistas.
            return _Resultado(("lote",))
        return _Resultado(None)

    def creditos(self) -> list[int]:
        """Os XP somados à conta pelo crédito do desafio, na ordem."""
        return [
            p["xp"]
            for sql, p in self.comandos
            if "nu_xp_total = prog.nu_xp_total + EXCLUDED.nu_xp_total" in sql
            and "nu_partidas = prog.nu_partidas" not in sql
        ]


def _evento(co_conquista: str) -> dict[str, Any]:
    return {"conquista": {"co_conquista": co_conquista, "dh_desbloqueio": None}}


@pytest.mark.asyncio
async def test_a_conquista_do_desafio_paga_o_bonus_ao_ser_inserida():
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    inserido = await repo.gravar_conquista(
        id_usuario=DONO, co_evento="e1", payload=_evento("desafio_resolvidos_10")
    )

    assert inserido is True
    assert sessao.creditos() == [100]


@pytest.mark.asyncio
async def test_o_reenvio_nao_paga_de_novo():
    """O mesmo evento duas vezes, ou a mesma conquista de um segundo aparelho:
    a linha já existe, ``xmax`` não é zero, e o bônus fica onde estava."""
    sessao = _SessaoQueAnota(inserido=False)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    inserido = await repo.gravar_conquista(
        id_usuario=DONO, co_evento="e1", payload=_evento("desafio_primeiro")
    )

    assert inserido is False
    assert sessao.creditos() == []


@pytest.mark.asyncio
async def test_conquista_de_jogo_nao_paga_por_este_caminho():
    """⚠️ O bônus das conquistas dos JOGOS já subiu como parcela da partida.
    Creditar aqui também pagaria duas vezes - e em silêncio, porque o número
    só apareceria no ranking."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    await repo.gravar_conquista(
        id_usuario=DONO, co_evento="e1", payload=_evento("pontinhos_vitorias_10")
    )

    assert sessao.creditos() == []


@pytest.mark.asyncio
async def test_a_migracao_do_convidado_tambem_paga_e_so_o_que_inseriu():
    """O merge do convidado grava as conquistas dele ANTES de a fila subir; se
    só o evento pagasse, ele acharia a linha pronta e o bônus se perderia."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    aplicado = await repo.aplicar_merge_se_novo(
        id_usuario=DONO,
        co_lote_migracao="lote-1",
        progressao_convidado={
            "conquistas": ["desafio_primeiro", "nivel_5", "desafio_semana_completa"]
        },
    )

    assert aplicado is True
    # 40 + 120; o `nivel_5` é de conta e não paga por aqui.
    assert sessao.creditos() == [40, 120]


@pytest.mark.asyncio
async def test_a_migracao_nao_paga_o_que_ja_existia():
    sessao = _SessaoQueAnota(inserido=False)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    await repo.aplicar_merge_se_novo(
        id_usuario=DONO,
        co_lote_migracao="lote-1",
        progressao_convidado={"conquistas": ["desafio_mes_completo"]},
    )

    assert sessao.creditos() == []


@pytest.mark.asyncio
async def test_a_reconciliacao_nunca_paga_o_bonus():
    """⚠️ A reconciliação aplica ``GREATEST`` com o total do APARELHO, que já
    inclui o bônus. Somar depois disso passaria do número certo - por isso ela,
    de propósito, não chama o crédito, nem quando a conquista é nova."""
    sessao = _SessaoQueAnota(inserido=True)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]

    await repo.reconciliar_progressao(
        id_usuario=DONO,
        snapshot={"nu_xp_total": 500, "conquistas": ["desafio_primeiro"]},
    )

    assert sessao.creditos() == []


def test_codigo_que_nao_e_texto_da_zero():
    """O código sai de um payload JSON: um número ou ``None`` ali não pode
    estourar a ingestão nem pagar nada."""
    assert bonus_da_conquista_do_desafio(None) == 0
    assert bonus_da_conquista_do_desafio(42) == 0
    assert bonus_da_conquista_do_desafio("desafio_primeiro") == 40


def test_todo_codigo_cabe_na_coluna():
    """``co_conquista`` é ``VARCHAR(40)``: um código maior seria recusado na
    sincronização, e a conquista viveria num aparelho só."""
    for codigo in BONUS_DAS_CONQUISTAS_DO_DESAFIO:
        assert len(codigo) <= 40, codigo


# ═══════════════════════════════════════════════════════════════════════════
# O cadeado: a tabela do servidor = o catálogo do app
# ═══════════════════════════════════════════════════════════════════════════

#: O catálogo do app, no repositório irmão. `parents[3]` sobe de
#: `tests/unitarios/` até a raiz do ecossistema (`arena-sagaz/`).
_CATALOGO_DO_APP = (
    Path(__file__).resolve().parents[3]
    / "arena-sagaz-frontend"
    / "lib"
    / "core"
    / "progressao"
    / "conquistas.dart"
)


def test_os_bonus_batem_com_o_catalogo_do_app():
    """O app soma o bônus na hora da celebração; o servidor soma quando o evento
    chega. Se os números divergirem, o total do aparelho e o do ranking param de
    bater - e ninguém vê, porque cada lado está "certo" sozinho.

    Lê cada ``Conquista(id: 'desafio_...', ..., xpBonus: N)`` do arquivo do app.
    ⚠️ Pula (e diz por quê) quando o repositório irmão não está ao lado - é o
    caso de uma máquina que só clonou o backend.
    """
    if not _CATALOGO_DO_APP.exists():
        pytest.skip(f"catálogo do app não encontrado em {_CATALOGO_DO_APP}")

    fonte = _CATALOGO_DO_APP.read_text(encoding="utf-8")
    # `id: 'desafio_x'` e o primeiro `xpBonus: N` depois dele, dentro do mesmo
    # construtor (`[^)]*?` não atravessa o parêntese que fecha a `Conquista`).
    no_app = {
        codigo: int(bonus)
        for codigo, bonus in re.findall(
            r"id:\s*'(desafio_[a-z0-9_]+)'[^)]*?xpBonus:\s*(\d+)", fonte
        )
    }

    assert no_app == BONUS_DAS_CONQUISTAS_DO_DESAFIO

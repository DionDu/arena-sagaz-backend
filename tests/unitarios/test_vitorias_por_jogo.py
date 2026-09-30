"""O servidor passa a devolver `vitorias_por_jogo` - o CARIMBO DO JOGO viajando
junto com o número de vitórias (T098, 30/09/2026).

═══════════════════════════════════════════════════════════════════════════
O RELATO QUE ORIGINOU ESTE ARQUIVO
═══════════════════════════════════════════════════════════════════════════

O dono venceu uma partida de **damas** e recebeu a conquista *"100 vitórias no
Pontinhos"*, tendo **11** vitórias reais no Pontinhos. Provado no banco `des`: a
conquista nasceu no mesmo microssegundo em que aquela partida de damas terminou.

A causa está do lado do app, mas a raiz está aqui: o **total** de vitórias
(`nu_vitorias`) é coluna no servidor e chega a qualquer aparelho novo, enquanto
o **detalhe por jogo** morava só no rascunho local (`js_estado_local`), que
nunca sobe. Numa instalação nova o total chegava sem carimbo de jogo, e o app
adivinhava o carimbo por subtração - *"o que não está atribuído a jogo nenhum só
pode ser do Pontinhos"*, verdade em 08/2026, quando havia um jogo só.

O dossiê completo está em
`arena-sagaz-frontend/specs/009-desafio-do-dia/CONSERTO-vitorias-por-jogo.md`.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTES TESTES RODAM O SQL DE VERDADE
═══════════════════════════════════════════════════════════════════════════

O que este conserto entrega são **os filtros** da consulta: tirar o desafio,
tirar o PvP local, contar só a vitória do J1. Uma sessão falsa provaria apenas
que linhas viram dicionário - e deixaria passar exatamente a mutação que
importa, a de alguém apagar um `AND`.

Então a consulta roda **de verdade**, num SQLite de memória com um schema
chamado `partida` anexado (`ATTACH`), sobre uma tabela com o nome da VIEW. O
SQL executado é o do repositório, sem cópia: se um filtro sair de lá, um caso
daqui fica vermelho.

⚠️ **Os números não são inventados:** são os da conta do dono no `des`, medidos
em 30/09/2026 - inclusive as 2 partidas de desafio no Pontinhos e as 5 de
desafio nas damas, que são justamente o que o filtro de modo tira.
"""

from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.sincronizacao.repositorio import RepositorioSincronizacao

# O dono do relato. Qualquer texto serve; ter um segundo id é o que prova que a
# consulta não devolve as vitórias do vizinho.
DONO = "63385354-1e03-44bc-b2a3-82fdb8e34547"
OUTRA_PESSOA = "00000000-0000-0000-0000-000000000001"


@pytest_asyncio.fixture
async def sessao():
    """Um SQLite de memória com o schema `partida` anexado e a VIEW imitada.

    `StaticPool` + uma conexão só é o que faz o `:memory:` sobreviver: cada
    conexão nova de um SQLite em memória é um banco **vazio** e diferente, então
    sem isto o `ATTACH` e a consulta veriam bancos distintos.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        # `ATTACH` dá ao SQLite um segundo banco com apelido - e é esse apelido
        # que faz `partida.vw001_partida` ser um nome válido aqui, como o schema
        # do Postgres é lá.
        await s.execute(text("ATTACH DATABASE ':memory:' AS partida"))
        await s.execute(
            text(
                """
                CREATE TABLE partida.vw001_partida (
                    id_usuario   TEXT,
                    co_jogo      TEXT,
                    co_modo      TEXT,
                    co_status    TEXT,
                    co_resultado TEXT
                )
                """
            )
        )
        yield s
    await engine.dispose()


async def _gravar(
    sessao: Any,
    *,
    quantas: int,
    jogo: str,
    modo: str = "vs_cpu",
    status: str = "concluida",
    resultado: str = "venceu_j1",
    dono: str = DONO,
) -> None:
    """Grava [quantas] partidas iguais. Os defaults são a partida que CONTA -
    assim cada caso só escreve o que ele quer mudar."""
    for _ in range(quantas):
        await sessao.execute(
            text(
                "INSERT INTO partida.vw001_partida "
                "(id_usuario, co_jogo, co_modo, co_status, co_resultado) "
                "VALUES (:dono, :jogo, :modo, :status, :resultado)"
            ),
            {
                "dono": dono,
                "jogo": jogo,
                "modo": modo,
                "status": status,
                "resultado": resultado,
            },
        )


@pytest.mark.asyncio
async def test_o_mapa_traz_um_numero_por_jogo(sessao):
    """O caso feliz: três jogos, três contagens - e o carimbo junto do número."""
    await _gravar(sessao, quantas=11, jogo="pontinhos")
    await _gravar(sessao, quantas=9, jogo="damas")
    await _gravar(sessao, quantas=42, jogo="velha")

    repo = RepositorioSincronizacao(sessao)
    mapa = await repo.vitorias_por_jogo(DONO)

    assert mapa == {"pontinhos": 11, "damas": 9, "velha": 42}


@pytest.mark.asyncio
async def test_o_desafio_fica_de_fora(sessao):
    """⚠️ **O desafio não incrementa vitórias** - é o que o app faz hoje (as
    telas de partida saem antes de avaliar conquistas) e o que o dono confirmou
    em 30/09/2026 (`docs/DECISOES-do-dono.md` §8k-9). Se o servidor contasse o
    desafio, o número que chega ao aparelho ficaria MAIOR que o de lá, e o
    GREATEST do app adotaria o número inflado - devolvendo em silêncio a
    contagem que aquela decisão existe para impedir.

    Os números são os reais do `des`: 2 desafios vencidos no Pontinhos e 5 nas
    damas, ao lado das 11 e 9 vitórias de verdade."""
    await _gravar(sessao, quantas=11, jogo="pontinhos")
    await _gravar(sessao, quantas=9, jogo="damas")
    await _gravar(sessao, quantas=2, jogo="pontinhos", modo="desafio")
    await _gravar(
        sessao, quantas=5, jogo="damas", modo="desafio", status="em_andamento"
    )

    repo = RepositorioSincronizacao(sessao)
    mapa = await repo.vitorias_por_jogo(DONO)

    assert mapa == {"pontinhos": 11, "damas": 9}


@pytest.mark.asyncio
async def test_o_pvp_local_fica_de_fora(sessao):
    """Duas pessoas no mesmo aparelho combinariam o vencedor - por isso o PvP
    local nunca pagou XP nem contou vitória, e não é aqui que ele vai começar."""
    await _gravar(sessao, quantas=11, jogo="pontinhos")
    await _gravar(sessao, quantas=30, jogo="pontinhos", modo="pvp_local")

    repo = RepositorioSincronizacao(sessao)
    mapa = await repo.vitorias_por_jogo(DONO)

    assert mapa == {"pontinhos": 11}


@pytest.mark.asyncio
async def test_derrota_e_empate_nao_contam(sessao):
    """Contra a CPU **o humano é sempre o J1** (regra canônica: J1 = azul =
    humano). Sem o filtro de resultado, o mapa contaria partidas jogadas em vez
    de partidas vencidas - e a escada de conquistas subiria perdendo."""
    await _gravar(sessao, quantas=11, jogo="pontinhos")
    await _gravar(sessao, quantas=7, jogo="pontinhos", resultado="venceu_j2")
    await _gravar(sessao, quantas=3, jogo="pontinhos", resultado="empate")

    repo = RepositorioSincronizacao(sessao)
    mapa = await repo.vitorias_por_jogo(DONO)

    assert mapa == {"pontinhos": 11}


@pytest.mark.asyncio
async def test_a_partida_em_andamento_nao_conta(sessao):
    """`co_resultado` é DERIVADO do placar pela VIEW: uma partida ainda aberta,
    com o humano à frente, já se parece com uma vitória. Contra a CPU a linha só
    sobe terminada, então este filtro fecha uma porta antes de ela existir - o
    mesmo recorte que `recalcular_chama` usa."""
    await _gravar(sessao, quantas=11, jogo="pontinhos")
    await _gravar(sessao, quantas=4, jogo="pontinhos", status="em_andamento")
    await _gravar(sessao, quantas=2, jogo="pontinhos", status="abandonada")

    repo = RepositorioSincronizacao(sessao)
    mapa = await repo.vitorias_por_jogo(DONO)

    assert mapa == {"pontinhos": 11}


@pytest.mark.asyncio
async def test_cada_um_recebe_as_suas(sessao):
    """O mapa é de UMA pessoa. Sem o filtro de dono, quem abrisse o app receberia
    as vitórias de todo mundo - e a conquista de 100 sairia na primeira leitura."""
    await _gravar(sessao, quantas=11, jogo="pontinhos")
    await _gravar(sessao, quantas=93, jogo="pontinhos", dono=OUTRA_PESSOA)

    repo = RepositorioSincronizacao(sessao)

    assert await repo.vitorias_por_jogo(DONO) == {"pontinhos": 11}
    assert await repo.vitorias_por_jogo(OUTRA_PESSOA) == {"pontinhos": 93}


@pytest.mark.asyncio
async def test_quem_nunca_venceu_recebe_o_mapa_vazio(sessao):
    """⚠️ **Vazio, e não ausente.** O campo vai sempre, como o `nu_dias_jogados`:
    é do lado do app que "ausente" (servidor antigo) se distingue de "vazio"
    (não venceu nada) - e lá a adoção é por GREATEST, chave a chave, então um
    mapa vazio não apaga o que o aparelho sabe."""
    repo = RepositorioSincronizacao(sessao)

    assert await repo.vitorias_por_jogo(DONO) == {}

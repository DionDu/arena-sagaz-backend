"""A recusa da reconciliação e do merge do convidado vai para o log (T166, spec 010).

═══════════════════════════════════════════════════════════════════════════
O DEFEITO QUE ESTE ARQUIVO VIGIA (30/10/2026)
═══════════════════════════════════════════════════════════════════════════

Em 9 contas do ``prd`` o bônus de XP das conquistas dos jogos não chegava ao
ranking, porque a reconciliação delas era recusada com 422 a cada sincronização
(``progressao_inconsistente``: vitórias + derrotas + empates passavam das
partidas). Ninguém via: só os eventos do LOTE iam para
``log.tb001_evento_sync_rejeitado``, e a tabela estava vazia no ``prd``. O
diagnóstico está em
``arena-sagaz-frontend/specs/010-jogo-quatro-em-linha/RETOMADA-progressao-1.4.0.md``.

A correção é de diagnóstico, e não de regra: ⛔ a validação continua a mesma, o
422 continua o mesmo, e a recusa passa a deixar uma linha no log.

═══════════════════════════════════════════════════════════════════════════
COMO CADA PARTE É PROVADA
═══════════════════════════════════════════════════════════════════════════

1. **O contrato** (repositório e sessão falsos, como os outros testes desta
   pasta): o que vai em cada coluna, um caso por código de recusa, e que o 422
   que o app recebe é exatamente o de antes - inclusive quando o log falha.
2. **A ordem**: arquivar, confirmar, e só então levantar o erro. Uma inversão
   (confirmar antes de arquivar) passaria pelos casos do item 1, que só contam.
3. **O SQL de verdade**, num SQLite de memória: a requisição passa pela rota
   real e pelo repositório real, a sessão fecha SEM o ``commit`` da rota (é o
   que o 422 faz), e uma sessão nova encontra a linha. É o único caso que prova
   que o registro sobrevive ao rollback; um falso que só conta ``commit`` não
   distingue "confirmou a linha" de "confirmou outra coisa".

Cada grupo tem o seu **controle** - o caso em que nada deve ser arquivado, ou em
que a linha deve sumir -, para que um instrumento quebrado não saia como verde.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.main import app
from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias import ContextoRequisicao
from api.nucleo.dependencias_conta_nuvem import (
    UsuarioAutenticado,
    usuario_autenticado,
)
from api.nucleo.excecoes import ErroNegocio
from api.sincronizacao.rotas import obter_servico_sync
from api.sincronizacao.servico import ServicoSincronizacao
from api.sincronizacao.validacao import MAX_CONQUISTAS_MERGE, MAX_PARTIDAS_MERGE
from tests.contratos.fakes_sync import FakeRepoSincronizacao
from tests.unitarios.fakes_conta import FakeSession

#: O dono que a autenticação falsa devolve (o mesmo dos outros contratos).
DONO = "id-u1"

#: A linha local da conta A no iPhone do dono, extraída em 30/10/2026
#: (``RETOMADA-progressao-1.4.0.md`` §0): 47 + 97 + 19 = 163 resultados para 157
#: partidas. É o retrato que o servidor recusava a cada sincronização. As 30
#: conquistas são códigos reais do catálogo do app.
RETRATO_DA_CONTA_A: dict[str, Any] = {
    "nu_xp_total": 5960,
    "nu_partidas": 157,
    "nu_vitorias": 47,
    "nu_derrotas": 97,
    "nu_empates": 19,
    "nu_sequencia_atual": 7,
    "dt_ultimo_dia_jogado": "2026-10-30",
    "conquistas": [
        "nivel_5", "nivel_10", "nivel_20", "nivel_35", "primeira_vitoria",
        "vitorias_10", "sequencia_3", "sequencia_7", "dias_10", "dias_30",
        "pontinhos_vitorias_1", "pontinhos_vitorias_10",
        "pontinhos_derrotar_cacau", "pontinhos_derrotar_pita",
        "pontinhos_derrotar_tex", "pontinhos_derrotar_cacau_com_poder",
        "pontinhos_derrotar_pita_com_poder", "velha_vitorias_1",
        "velha_derrotar_cacau", "velha_derrotar_pita", "damas_vitorias_1",
        "damas_vitorias_10", "damas_derrotar_cacau", "damas_derrotar_pita",
        "damas_derrotar_tex", "damas_derrotar_tex_com_poder",
        "damas_segurou_magno_com_poder", "damas_primeira_dama",
        "desafio_primeiro", "desafio_semana_completa",
    ],
}

#: O mesmo retrato com a soma fechando (19 empates → 13): o caso de CONTROLE.
#: É o que a reconciliação aceita, e então não há o que arquivar.
RETRATO_QUE_FECHA: dict[str, Any] = {**RETRATO_DA_CONTA_A, "nu_empates": 13}


def _copia(retrato: dict[str, Any], **troca: Any) -> dict[str, Any]:
    """Uma cópia do [retrato] com os campos de [troca] substituídos.

    Copiar a lista de conquistas também é de propósito: o falso guarda o
    payload por referência, e um teste que alterasse a constante contaminaria
    os seguintes."""
    copia = json.loads(json.dumps(retrato))
    copia.update(troca)
    return copia


#: Um retrato para cada código de recusa da ``validacao.py`` (a função de
#: progressão tem exatamente estes quatro). ⚠️ Se a validação ganhar um código
#: novo, ele entra aqui - o caso parametrizado é o que garante que TODA recusa
#: deixa linha, e não só a que motivou a tarefa.
RECUSAS: list[tuple[str, Any]] = [
    ("progressao_inconsistente", _copia(RETRATO_DA_CONTA_A)),
    # Contador que não é inteiro (o app manda int; texto é forjado ou quebrado).
    ("progressao_invalida", _copia(RETRATO_QUE_FECHA, nu_xp_total="5960")),
    # O próprio retrato não é um objeto.
    ("progressao_invalida", [1, 2, 3]),
    ("progressao_excede_teto",
     _copia(RETRATO_QUE_FECHA, nu_partidas=MAX_PARTIDAS_MERGE + 1)),
    ("conquistas_invalidas",
     _copia(RETRATO_QUE_FECHA,
            conquistas=["x"] * (MAX_CONQUISTAS_MERGE + 1))),
]


# ═══════════════════════════════════════════════════════════════════════════
# Montagem (o mesmo molde de test_sync_eventos.py)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client():
    """Cliente síncrono do app; as trocas de dependência são desfeitas no fim."""
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _usuario() -> UsuarioAutenticado:
    """O dono fixo, sem token nem banco."""
    return UsuarioAutenticado(
        id_usuario=DONO,
        co_usuario="ABC12345",
        contexto=ContextoRequisicao(
            versao_app="1.3.1", plataforma="ios", idioma="pt"
        ),
    )


def _montar(repo: FakeRepoSincronizacao, sessao: FakeSession) -> None:
    """Liga a autenticação falsa e o serviço com o repositório falso."""
    app.dependency_overrides[usuario_autenticado] = _usuario
    app.dependency_overrides[obter_servico_sync] = lambda: ServicoSincronizacao(
        repo, sessao
    )


def _reconciliar(client: TestClient, retrato: Any):
    """``POST /reconciliar`` com o corpo que o app monta (``{"progressao": ...}``)."""
    return client.post("/v1/sincronizacao/reconciliar", json={"progressao": retrato})


def _merge(client: TestClient, retrato: Any, lote: str = "lote-convidado-1"):
    """``POST /merge-convidado`` com o lote e o retrato do convidado."""
    return client.post(
        "/v1/sincronizacao/merge-convidado",
        json={"co_lote_migracao": lote, "progressao_convidado": retrato},
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. A reconciliação recusada
# ═══════════════════════════════════════════════════════════════════════════


def test_a_recusa_da_conta_a_fica_no_log_e_o_422_continua(client):
    """O caso do relato: o retrato real da conta A é recusado como sempre, e
    agora deixa uma linha com o tipo, o código e o retrato inteiro."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)

    r = _reconciliar(client, RETRATO_DA_CONTA_A)

    assert r.status_code == 422
    assert r.json() == {
        "detalhe": "Progressão inválida ou fora dos limites.",
        "codigo": "progressao_inconsistente",
    }
    assert repo.arquivados_completos == [
        {
            "id_usuario": DONO,
            # A reconciliação não tem identificador próprio.
            "co_evento": None,
            "co_tipo": "reconciliacao",
            # A categoria é a de toda reprovação na validação (a mesma das
            # linhas do lote); o código específico vai em `de_codigo`.
            "co_motivo": "rejeitado_contrato",
            "de_codigo": "progressao_inconsistente",
            "payload": RETRATO_DA_CONTA_A,
        }
    ]
    # Confirmado pelo serviço: a rota não chega ao `commit` dela no 422.
    assert sessao.commits == 1
    # E a recusa continua recusa: nada da progressão foi tocado.
    assert repo._progressao == {}


@pytest.mark.parametrize(
    ("codigo", "retrato"),
    RECUSAS,
    ids=[f"{c}-{i}" for i, (c, _) in enumerate(RECUSAS)],
)
def test_toda_recusa_da_reconciliacao_deixa_linha(client, codigo, retrato):
    """Cada código que a validação pode devolver chega ao log, e o 422 leva o
    mesmo código que a linha."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)

    r = _reconciliar(client, retrato)

    assert r.status_code == 422
    assert r.json()["codigo"] == codigo
    assert len(repo.arquivados_completos) == 1
    linha = repo.arquivados_completos[0]
    assert linha["co_tipo"] == "reconciliacao"
    assert linha["de_codigo"] == codigo
    assert linha["payload"] == retrato
    assert sessao.commits == 1


def test_controle_a_reconciliacao_aceita_nao_arquiva_nada(client):
    """CONTROLE: o mesmo retrato com a soma fechando passa, e o log fica vazio.
    Sem este caso, um serviço que arquivasse TODA reconciliação passaria pelos
    de cima."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)

    r = _reconciliar(client, RETRATO_QUE_FECHA)

    assert r.status_code == 200
    assert r.json()["progressao"]["nu_empates"] == 13
    assert repo.arquivados_completos == []
    # Um só commit: o da rota, como antes da T166.
    assert sessao.commits == 1


def test_controle_corpo_sem_progressao_continua_aceito(client):
    """CONTROLE: o app nunca manda corpo vazio, mas ele já era aceito (vira
    zeros, que o GREATEST ignora). A T166 não muda isso."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)

    r = client.post("/v1/sincronizacao/reconciliar", json={})

    assert r.status_code == 200
    assert repo.arquivados_completos == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. O merge do convidado recusado
# ═══════════════════════════════════════════════════════════════════════════


def test_a_recusa_do_merge_fica_no_log_com_o_lote(client):
    """O merge recusado deixa a linha com o lote no lugar do ``co_evento`` - é
    o lote que liga o log ao convidado que tentou migrar."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)
    retrato = _copia(RETRATO_QUE_FECHA, nu_partidas=2, nu_vitorias=5,
                     nu_derrotas=0, nu_empates=0)

    r = _merge(client, retrato, lote="lote-da-conta-a")

    assert r.status_code == 422
    assert r.json() == {
        "detalhe": "Progressão do convidado inválida ou fora dos limites.",
        "codigo": "progressao_inconsistente",
    }
    assert repo.arquivados_completos == [
        {
            "id_usuario": DONO,
            "co_evento": "lote-da-conta-a",
            "co_tipo": "merge_convidado",
            "co_motivo": "rejeitado_contrato",
            "de_codigo": "progressao_inconsistente",
            "payload": retrato,
        }
    ]
    assert sessao.commits == 1
    # O lote NÃO foi carimbado: um merge recusado não pode virar "já aplicado"
    # e impedir a migração correta depois.
    assert repo.lotes_aplicados == set()


@pytest.mark.parametrize(
    ("codigo", "retrato"),
    RECUSAS,
    ids=[f"{c}-{i}" for i, (c, _) in enumerate(RECUSAS)],
)
def test_toda_recusa_do_merge_deixa_linha(client, codigo, retrato):
    """A validação do merge é a mesma da reconciliação: os mesmos códigos."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)

    r = _merge(client, retrato)

    assert r.status_code == 422
    assert r.json()["codigo"] == codigo
    assert [(a["co_tipo"], a["de_codigo"]) for a in repo.arquivados_completos] == [
        ("merge_convidado", codigo)
    ]


def test_controle_o_merge_aceito_nao_arquiva_nada(client):
    """CONTROLE: o corpo que o app de verdade manda (contadores em zero, só a
    chama e as conquistas) passa e não deixa linha."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)
    retrato = _copia(RETRATO_DA_CONTA_A, nu_xp_total=0, nu_partidas=0,
                     nu_vitorias=0, nu_derrotas=0, nu_empates=0)

    r = _merge(client, retrato)

    assert r.status_code == 200
    assert r.json()["aplicado"] is True
    assert repo.arquivados_completos == []
    assert sessao.commits == 1


def test_controle_merge_sem_lote_continua_400_e_sem_linha(client):
    """CONTROLE de escopo: o 400 de corpo malformado (sem lote) não é recusa de
    progressão e continua sem linha - a T166 trata só os 422."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/merge-convidado",
        json={"progressao_convidado": RETRATO_DA_CONTA_A},
    )

    assert r.status_code == 400
    assert repo.arquivados_completos == []
    assert sessao.commits == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3. O log que falha não troca a resposta
# ═══════════════════════════════════════════════════════════════════════════


class _SessaoQueNaoConfirma(FakeSession):
    """Sessão cujo ``commit`` explode (o banco caiu entre o INSERT e o commit)."""

    async def commit(self):
        self.commits += 1
        raise RuntimeError("falha simulada no commit")


@pytest.mark.parametrize("rota", ["reconciliar", "merge"])
def test_arquivar_que_falha_responde_o_mesmo_422(client, rota):
    """Se o INSERT do log explode, o app recebe o 422 de sempre (e não um 500),
    e a sessão é desfeita."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    repo.falhar_ao_arquivar = True
    _montar(repo, sessao)

    r = (_reconciliar if rota == "reconciliar" else _merge)(
        client, RETRATO_DA_CONTA_A
    )

    assert r.status_code == 422
    assert r.json()["codigo"] == "progressao_inconsistente"
    assert repo.arquivados_completos == []
    assert sessao.commits == 0
    assert sessao.rollbacks == 1


@pytest.mark.parametrize("rota", ["reconciliar", "merge"])
def test_commit_que_falha_responde_o_mesmo_422(client, rota):
    """Se o ``commit`` do log explode, idem: 422 igual, e o rollback tentado."""
    repo, sessao = FakeRepoSincronizacao(), _SessaoQueNaoConfirma()
    _montar(repo, sessao)

    r = (_reconciliar if rota == "reconciliar" else _merge)(
        client, RETRATO_DA_CONTA_A
    )

    assert r.status_code == 422
    assert r.json()["codigo"] == "progressao_inconsistente"
    assert sessao.rollbacks == 1


def test_controle_o_lote_de_eventos_continua_como_antes(client):
    """CONTROLE: a reprovação no LOTE (``POST /eventos``) continua com o tipo da
    partida, responde 200 e tem um commit só - o da rota. A T166 não passou a
    confirmar nada a mais nesse caminho."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _montar(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/eventos",
        json={
            "eventos": [
                {
                    "co_evento": "evt-fraude",
                    "co_tipo": "partida",
                    "payload": {
                        "partida": {"nu_placar_j1": 3, "nu_placar_j2": 2,
                                    "ic_pontua": True},
                        "xp": [{"nu_xp": 999_999}],
                    },
                }
            ]
        },
    )

    assert r.status_code == 200
    assert [(a["co_tipo"], a["de_codigo"]) for a in repo.arquivados_completos] == [
        ("partida", "xp_excede_teto")
    ]
    assert sessao.commits == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. A ordem: arquivar, confirmar, recusar
# ═══════════════════════════════════════════════════════════════════════════


class _Diario:
    """Anota, numa lista só, o que o repositório e a sessão fizeram, na ordem."""

    def __init__(self) -> None:
        self.passos: list[str] = []


class _RepoComDiario(FakeRepoSincronizacao):
    def __init__(self, diario: _Diario) -> None:
        super().__init__()
        self._diario = diario

    async def arquivar_evento_rejeitado(self, **kwargs: Any) -> None:
        self._diario.passos.append("arquivar")
        await super().arquivar_evento_rejeitado(**kwargs)


class _SessaoComDiario(FakeSession):
    def __init__(self, diario: _Diario) -> None:
        super().__init__()
        self._diario = diario

    async def commit(self):
        self._diario.passos.append("commit")
        await super().commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("caso", ["reconciliar", "merge"])
async def test_arquiva_depois_confirma_e_so_entao_recusa(caso):
    """Chamando o serviço direto: ``commit`` antes do arquivamento confirmaria
    uma sessão vazia e deixaria a linha para o rollback - e os casos que só
    contam ``commit`` não perceberiam."""
    diario = _Diario()
    servico = ServicoSincronizacao(_RepoComDiario(diario), _SessaoComDiario(diario))

    with pytest.raises(ErroNegocio) as erro:
        if caso == "reconciliar":
            await servico.reconciliar_progressao(
                _usuario(), {"progressao": _copia(RETRATO_DA_CONTA_A)}
            )
        else:
            await servico.merge_convidado(
                _usuario(),
                {"co_lote_migracao": "lote-1",
                 "progressao_convidado": _copia(RETRATO_DA_CONTA_A)},
            )
        diario.passos.append("não levantou")

    assert diario.passos == ["arquivar", "commit"]
    assert erro.value.codigo == "progressao_inconsistente"
    assert erro.value.status_http == 422


# ═══════════════════════════════════════════════════════════════════════════
# 5. O SQL de verdade: a linha sobrevive ao 422
# ═══════════════════════════════════════════════════════════════════════════

#: A tabela de ``0005_log_evento_sync_rejeitado`` com as mesmas colunas e a
#: mesma obrigatoriedade (``co_motivo`` não aceita nulo), nos tipos do SQLite.
SQL_CRIAR_LOG = """
CREATE TABLE log.tb001_evento_sync_rejeitado (
    id_log      TEXT PRIMARY KEY,
    id_usuario  TEXT,
    co_evento   TEXT,
    co_tipo     TEXT,
    co_motivo   TEXT NOT NULL,
    de_codigo   TEXT,
    js_payload  TEXT,
    dh_registro TEXT NOT NULL
)
"""


@pytest_asyncio.fixture
async def fabrica_sqlite():
    """Fábrica de sessões sobre um SQLite de memória com o schema ``log``.

    ``StaticPool`` mantém uma conexão só - cada conexão nova a um ``:memory:``
    seria outro banco, vazio. O ``ATTACH`` dá ao segundo banco o apelido
    ``log``, e é isso que torna ``log.tb001_...`` um nome válido aqui.

    O ``INSERT`` real do repositório usa duas funções do Postgres que o SQLite
    não tem, ``gen_random_uuid()`` e ``now()``; elas são registradas na conexão
    (``create_function``) com o mesmo papel: um UUID novo e o instante atual.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # `event.listens_for(..., "connect")`: roda a cada conexão aberta pelo
    # motor (aqui, uma só). `sync_engine` porque os eventos de conexão moram
    # no motor síncrono que o assíncrono embrulha.
    @event.listens_for(engine.sync_engine, "connect")
    def _funcoes_do_postgres(conexao_dbapi, _registro):
        conexao_dbapi.create_function("gen_random_uuid", 0, lambda: str(uuid4()))
        conexao_dbapi.create_function("now", 0, lambda: "2026-10-30T14:25:00Z")

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        await s.execute(text("ATTACH DATABASE ':memory:' AS log"))
        await s.execute(text(SQL_CRIAR_LOG))
        await s.commit()
    yield fabrica
    await engine.dispose()


async def _linhas_do_log(fabrica) -> list[dict[str, Any]]:
    """Lê o log numa sessão NOVA - o que outra requisição veria."""
    async with fabrica() as s:
        resultado = await s.execute(
            text(
                "SELECT id_usuario, co_evento, co_tipo, co_motivo, de_codigo, "
                "js_payload FROM log.tb001_evento_sync_rejeitado"
            )
        )
        return [dict(linha) for linha in resultado.mappings()]


@pytest_asyncio.fixture
async def cliente_com_sqlite(fabrica_sqlite):
    """O app com a rota, o serviço e o repositório REAIS sobre o SQLite.

    Só a sessão e o dono são trocados. A sessão nasce e morre como a de
    produção (``async with SessaoLocal() as sessao: yield sessao``): ao sair
    sem ``commit``, o SQLAlchemy desfaz o que estava pendente.
    """

    async def _sessao_da_requisicao():
        async with fabrica_sqlite() as sessao:
            yield sessao

    app.dependency_overrides[obter_sessao] = _sessao_da_requisicao
    app.dependency_overrides[usuario_autenticado] = _usuario
    transporte = ASGITransport(app=app)
    async with AsyncClient(transport=transporte, base_url="http://teste") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_controle_sem_commit_a_linha_some(fabrica_sqlite):
    """CONTROLE do instrumento: uma linha gravada numa sessão que fecha sem
    ``commit`` não aparece na sessão seguinte. Sem este caso, um SQLite que
    confirmasse tudo sozinho faria os dois de baixo passarem com qualquer
    serviço."""
    async with fabrica_sqlite() as s:
        await s.execute(
            text(
                "INSERT INTO log.tb001_evento_sync_rejeitado "
                "(id_log, co_motivo, dh_registro) "
                "VALUES (gen_random_uuid(), 'x', now())"
            )
        )
        # Fecha sem commit, como a rota no 422.

    assert await _linhas_do_log(fabrica_sqlite) == []


@pytest.mark.asyncio
async def test_a_recusa_da_reconciliacao_sobrevive_ao_422(cliente_com_sqlite,
                                                         fabrica_sqlite):
    """O retrato real da conta A pela rota real: 422, e a linha está lá."""
    r = await cliente_com_sqlite.post(
        "/v1/sincronizacao/reconciliar", json={"progressao": RETRATO_DA_CONTA_A}
    )

    assert r.status_code == 422
    assert r.json()["codigo"] == "progressao_inconsistente"
    linhas = await _linhas_do_log(fabrica_sqlite)
    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["id_usuario"] == DONO
    assert linha["co_evento"] is None
    assert linha["co_tipo"] == "reconciliacao"
    assert linha["co_motivo"] == "rejeitado_contrato"
    assert linha["de_codigo"] == "progressao_inconsistente"
    # O retrato inteiro, legível de volta - é o que o dono vai consultar.
    assert json.loads(linha["js_payload"]) == RETRATO_DA_CONTA_A


@pytest.mark.asyncio
async def test_a_recusa_do_merge_sobrevive_ao_422(cliente_com_sqlite,
                                                  fabrica_sqlite):
    """O mesmo para o merge do convidado, com o lote em ``co_evento``."""
    r = await cliente_com_sqlite.post(
        "/v1/sincronizacao/merge-convidado",
        json={
            "co_lote_migracao": "lote-real",
            "progressao_convidado": RETRATO_DA_CONTA_A,
        },
    )

    assert r.status_code == 422
    linhas = await _linhas_do_log(fabrica_sqlite)
    assert [(l["co_tipo"], l["co_evento"], l["de_codigo"]) for l in linhas] == [
        ("merge_convidado", "lote-real", "progressao_inconsistente")
    ]


@pytest.mark.asyncio
async def test_duas_recusas_sao_duas_linhas(cliente_com_sqlite, fabrica_sqlite):
    """Uma linha por recusa, sem filtrar repetição (decisão do dono, 30/10/2026):
    a contagem diz quantas vezes o aparelho tentou."""
    for _ in range(2):
        await cliente_com_sqlite.post(
            "/v1/sincronizacao/reconciliar", json={"progressao": RETRATO_DA_CONTA_A}
        )

    assert len(await _linhas_do_log(fabrica_sqlite)) == 2

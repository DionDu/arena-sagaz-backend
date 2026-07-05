"""Contract test do POST /v1/sincronizacao/eventos (US1, T023).

Sem banco: trocamos (`dependency_overrides`) a resolução do usuário e o serviço
por versões com repositório FALSO. Valida o contrato (status/corpo), a
idempotência por `co_evento` e o XP dentro do evento.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.nucleo.dependencias import ContextoRequisicao
from api.nucleo.dependencias_conta_nuvem import (
    UsuarioAutenticado,
    usuario_autenticado,
)
from api.sincronizacao.rotas import obter_servico_sync
from api.sincronizacao.servico import ServicoSincronizacao
from tests.contratos.fakes_sync import FakeRepoSincronizacao
from tests.unitarios.fakes_conta import FakeSession


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _autenticar() -> None:
    """Faz a dependência de usuário devolver um dono fixo (sem token/DB real)."""
    app.dependency_overrides[usuario_autenticado] = lambda: UsuarioAutenticado(
        id_usuario="id-u1",
        co_usuario="ABC12345",
        co_anonimo="anon-1",
        dt_nascimento=None,
        contexto=ContextoRequisicao(
            versao_app="1.0.0", plataforma="android", idioma="pt"
        ),
    )


def _usar_repo(repo: FakeRepoSincronizacao, sessao: FakeSession) -> None:
    app.dependency_overrides[obter_servico_sync] = lambda: ServicoSincronizacao(
        repo, sessao
    )


def _evento_partida(co_evento: str, xp: int) -> dict:
    """Monta um evento de partida `vs_cpu` que PONTUA (vitória 3x2)."""
    return {
        "co_evento": co_evento,
        "co_tipo": "partida",
        "payload": {
            "partida": {
                "id_partida": f"p-{co_evento}",
                "co_jogo": "pontinhos",
                "co_variante": "pequeno",
                "co_modo": "vs_cpu",
                "nu_placar_j1": 3,
                "nu_placar_j2": 2,
                "ic_pontua": True,
                "co_status": "concluida",
                "dh_inicio": "2026-07-01T10:00:00Z",
            },
            "jogadas": [],
            "xp": [{"co_tipo_xp": "resultado", "nu_xp": xp}],
        },
    }


def test_ingerir_evento_novo_pontua_e_confirma(client):
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_partida("evt-1", 40)]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["aceitos"] == ["evt-1"]
    assert body["ignorados"] == []
    # XP dentro do evento aplicado à progressão.
    assert body["progressao"]["nu_xp_total"] == 40
    assert body["progressao"]["nu_vitorias"] == 1
    assert body["progressao"]["nu_partidas"] == 1
    # A rota confirmou a transação.
    assert sessao.commits == 1


def test_reenvio_do_mesmo_co_evento_nao_duplica_xp(client):
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_partida("evt-1", 40)]},
    )
    # Reenvia o MESMO co_evento (retry).
    r = client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_partida("evt-1", 40)]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["aceitos"] == []
    assert body["ignorados"] == ["evt-1"]
    # XP NÃO dobrou (idempotência).
    assert body["progressao"]["nu_xp_total"] == 40


def test_corpo_sem_eventos_responde_400(client):
    _autenticar()
    _usar_repo(FakeRepoSincronizacao(), FakeSession())
    r = client.post("/v1/sincronizacao/eventos", json={})
    assert r.status_code == 400
    assert r.json()["codigo"] == "eventos_invalidos"


def test_sem_token_nao_ingere(client):
    # NÃO autenticamos: a dependência real exige token → 401.
    _usar_repo(FakeRepoSincronizacao(), FakeSession())
    r = client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_partida("evt-1", 40)]},
    )
    assert r.status_code == 401


def test_xp_acima_do_teto_e_rejeitado_nao_pontua(client):
    """XP absurdo (fraude) é REJEITADO por evento e NÃO entra na progressão (SEG-05)."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_partida("evt-fraude", 999_999_999)]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["aceitos"] == []
    assert body["rejeitados"] == [{"co_evento": "evt-fraude", "codigo": "xp_excede_teto"}]
    assert body["progressao"]["nu_xp_total"] == 0


def test_evento_malformado_e_rejeitado_sem_derrubar_o_bom(client):
    """Um evento malformado entra em 'rejeitados' e o evento bom é aceito (SEG-06/10)."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/eventos",
        json={
            "eventos": [
                "isso-nao-e-um-objeto",  # malformado
                _evento_partida("evt-ok", 40),  # válido
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["aceitos"] == ["evt-ok"]
    assert body["rejeitados"] == [
        {"co_evento": None, "codigo": "evento_malformado"}
    ]
    assert body["progressao"]["nu_xp_total"] == 40


def test_xp_nao_inteiro_e_rejeitado_sem_500(client):
    """nu_xp string não estoura 500 — é rejeitado com motivo (SEG-06)."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    evento = _evento_partida("evt-x", 10)
    evento["payload"]["xp"] = [{"co_tipo_xp": "resultado", "nu_xp": "abc"}]
    r = client.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
    assert r.status_code == 200
    assert r.json()["rejeitados"] == [{"co_evento": "evt-x", "codigo": "xp_invalido"}]


def test_lote_grande_demais_responde_413(client):
    from api.sincronizacao.validacao import MAX_EVENTOS_POR_LOTE

    _autenticar()
    _usar_repo(FakeRepoSincronizacao(), FakeSession())
    eventos = [_evento_partida(f"e{i}", 1) for i in range(MAX_EVENTOS_POR_LOTE + 1)]
    r = client.post("/v1/sincronizacao/eventos", json={"eventos": eventos})
    assert r.status_code == 413
    assert r.json()["codigo"] == "lote_grande_demais"


def test_pvp_local_nao_altera_xp_anti_farm(client):
    """SC-007 (T042): partida pvp_local (ic_pontua=False) é aceita/registrada
    mas NÃO incrementa XP nem contadores — anti-farm."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    evento = {
        "co_evento": "evt-pvp",
        "co_tipo": "partida",
        "payload": {
            "partida": {
                "id_partida": "p-pvp",
                "co_jogo": "pontinhos",
                "co_variante": "pequeno",
                "co_modo": "pvp_local",
                "nu_placar_j1": 6,
                "nu_placar_j2": 6,
                "ic_pontua": False,  # não pontua
                "co_status": "concluida",
                "dh_inicio": "2026-07-01T10:00:00Z",
            },
            "jogadas": [],
            "xp": [{"co_tipo_xp": "resultado", "nu_xp": 15}],  # ignorado
        },
    }
    r = client.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
    assert r.status_code == 200
    body = r.json()
    assert body["aceitos"] == ["evt-pvp"]  # a partida é registrada…
    assert body["progressao"]["nu_xp_total"] == 0  # …mas XP não muda
    assert body["progressao"]["nu_partidas"] == 0

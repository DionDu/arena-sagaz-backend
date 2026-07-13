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


def test_parcela_ajuste_negativa_e_aceita(client):
    """REGRESSÃO: a parcela `ajuste` fica NEGATIVA quando o teto diário de XP
    apara o ganho bruto (bônus somam mais do que o dia admitia). Antes, isso
    derrubava a partida inteira (`xp_invalido`) e o evento era ABANDONADO no app
    sem nunca chegar ao servidor. Agora o total é o que importa: parcela negativa
    é aceita desde que o total fique em [0, teto]."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    evento = _evento_partida("evt-ajuste", 0)
    # Vitória com bônus (108 bruto) aparada pelo teto diário para +74 reais.
    evento["payload"]["xp"] = [
        {"co_tipo_xp": "resultado", "nu_xp": 30},
        {"co_tipo_xp": "caixas", "nu_xp": 28},
        {"co_tipo_xp": "primeira_vitoria", "nu_xp": 50},
        {"co_tipo_xp": "ajuste", "nu_xp": -34},  # apara ao ganho real
    ]
    r = client.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
    assert r.status_code == 200
    body = r.json()
    assert body["aceitos"] == ["evt-ajuste"]
    assert body["rejeitados"] == []
    assert body["progressao"]["nu_xp_total"] == 74


def test_xp_total_negativo_e_rejeitado(client):
    """Uma partida NUNCA retira XP: se a soma das parcelas fica negativa, o
    evento é rejeitado (contadores forjados)."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    evento = _evento_partida("evt-neg", 0)
    evento["payload"]["xp"] = [
        {"co_tipo_xp": "resultado", "nu_xp": 10},
        {"co_tipo_xp": "ajuste", "nu_xp": -50},  # total = -40
    ]
    r = client.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
    assert r.status_code == 200
    body = r.json()
    assert body["aceitos"] == []
    assert body["rejeitados"] == [{"co_evento": "evt-neg", "codigo": "xp_excede_teto"}]


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


def test_rejeitado_por_contrato_e_arquivado_no_log(client):
    """Um evento rejeitado na validação é ARQUIVADO (motivo rejeitado_contrato)
    para diagnóstico — o servidor já tinha o payload em mãos ao rejeitar."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_partida("evt-fraude", 999_999_999)]},
    )
    assert r.status_code == 200
    assert r.json()["rejeitados"] == [
        {"co_evento": "evt-fraude", "codigo": "xp_excede_teto"}
    ]
    # Ficou no log com o motivo certo.
    assert repo.arquivados == [
        {
            "co_evento": "evt-fraude",
            "co_motivo": "rejeitado_contrato",
            "de_codigo": "xp_excede_teto",
        }
    ]


def test_falha_no_processamento_e_arquivada_sem_derrubar_o_bom(client):
    """Blindagem por SAVEPOINT: se um evento EXPLODE ao gravar (erro inesperado
    que viraria 500), ele é revertido sozinho, arquivado como falha_processamento
    e entra em 'falhas' — o evento bom do MESMO lote é aplicado normalmente."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    repo.falhar_em = {"evt-veneno"}  # este co_evento lança ao gravar
    _autenticar()
    _usar_repo(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/eventos",
        json={
            "eventos": [
                _evento_partida("evt-veneno", 40),  # explode ao gravar
                _evento_partida("evt-bom", 40),  # válido
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    # O bom foi aplicado; o veneno foi para 'falhas' (não 'rejeitados').
    assert body["aceitos"] == ["evt-bom"]
    assert body["falhas"] == ["evt-veneno"]
    assert body["rejeitados"] == []
    # A progressão só contou o evento bom (o veneno foi revertido).
    assert body["progressao"]["nu_xp_total"] == 40
    # Usou o SAVEPOINT por evento e arquivou o veneno para diagnóstico.
    assert sessao.savepoints >= 2
    assert repo.arquivados[0]["co_evento"] == "evt-veneno"
    assert repo.arquivados[0]["co_motivo"] == "falha_processamento"
    # A transação da rota foi confirmada mesmo com o evento venenoso no lote.
    assert sessao.commits == 1


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


def _evento_conquista(co_evento: str, co_conquista: str) -> dict:
    """Monta um evento de CONQUISTA desbloqueada."""
    return {
        "co_evento": co_evento,
        "co_tipo": "conquista",
        "payload": {
            "conquista": {
                "co_conquista": co_conquista,
                "dh_desbloqueio": "2026-07-01T10:00:00Z",
            }
        },
    }


def test_evento_conquista_registra_e_e_idempotente(client):
    """Conquista sobe como evento próprio; reenviar não duplica (SC — fallback)."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_conquista("cq-1", "primeira_vitoria")]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["aceitos"] == ["cq-1"]
    assert body["progressao"]["conquistas"] == ["primeira_vitoria"]

    # Reenvia o MESMO evento (retry) → ignorado, sem duplicar.
    r2 = client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_conquista("cq-1", "primeira_vitoria")]},
    )
    assert r2.json()["ignorados"] == ["cq-1"]
    assert r2.json()["progressao"]["conquistas"] == ["primeira_vitoria"]


def test_evento_conquista_sem_codigo_e_rejeitado(client):
    """Conquista sem co_conquista é rejeitada por contrato (não estoura 500)."""
    _autenticar()
    _usar_repo(FakeRepoSincronizacao(), FakeSession())
    evento = _evento_conquista("cq-x", "ok")
    evento["payload"]["conquista"]["co_conquista"] = ""  # vazio
    r = client.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
    assert r.json()["rejeitados"] == [
        {"co_evento": "cq-x", "codigo": "conquista_invalida"}
    ]


def test_evento_tipo_desconhecido_e_rejeitado(client):
    """Tipo que este backend não conhece é rejeitado (app novo × backend antigo)."""
    _autenticar()
    _usar_repo(FakeRepoSincronizacao(), FakeSession())
    evento = {"co_evento": "evt-?", "co_tipo": "missao_diaria", "payload": {}}
    r = client.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
    assert r.json()["rejeitados"] == [
        {"co_evento": "evt-?", "codigo": "tipo_desconhecido"}
    ]


def test_reconciliar_repara_xp_conquistas_e_dt(client):
    """A reconciliação aplica o snapshot autoritativo (XP/conquistas/dt) — o
    fallback contra perda quando um evento é abandonado."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    r = client.post(
        "/v1/sincronizacao/reconciliar",
        json={
            "progressao": {
                "nu_xp_total": 120,
                "nu_partidas": 3,
                "nu_vitorias": 2,
                "nu_derrotas": 1,
                "nu_empates": 0,
                "nu_sequencia_atual": 2,
                "dt_ultimo_dia_jogado": "2026-07-07",
                "conquistas": ["primeira_vitoria", "streak_3"],
            }
        },
    )
    assert r.status_code == 200
    prog = r.json()["progressao"]
    assert prog["nu_xp_total"] == 120
    assert prog["conquistas"] == ["primeira_vitoria", "streak_3"]
    assert prog["dt_ultimo_dia_jogado"] == "2026-07-07"
    assert sessao.commits == 1


def test_reconciliar_nao_regride_xp(client):
    """GREATEST: se o servidor já tem MAIS XP (eventos), a reconciliação com um
    valor menor NÃO derruba o total."""
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    # Servidor ganha 40 XP por um evento de partida.
    client.post(
        "/v1/sincronizacao/eventos",
        json={"eventos": [_evento_partida("evt-1", 40)]},
    )
    # Reconcilia com um XP MENOR (10) — não deve regredir.
    r = client.post(
        "/v1/sincronizacao/reconciliar",
        json={"progressao": {"nu_xp_total": 10, "nu_partidas": 1}},
    )
    assert r.json()["progressao"]["nu_xp_total"] == 40


def test_reconciliar_fora_do_teto_e_422(client):
    """Snapshot abusivo (fraude) é recusado com 422 (mesmos tetos do merge)."""
    _autenticar()
    _usar_repo(FakeRepoSincronizacao(), FakeSession())
    r = client.post(
        "/v1/sincronizacao/reconciliar",
        json={"progressao": {"nu_xp_total": 999_999_999_999, "nu_partidas": 1}},
    )
    assert r.status_code == 422


def test_reconciliar_sem_token_401(client):
    _usar_repo(FakeRepoSincronizacao(), FakeSession())
    r = client.post(
        "/v1/sincronizacao/reconciliar",
        json={"progressao": {"nu_xp_total": 10}},
    )
    assert r.status_code == 401


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

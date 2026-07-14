"""Contract test do GET /v1/ranking/leaderboard (US3, T041).

Valida: Top-N público, a linha 'eu' SEMPRE presente (posição real), e que
opt-out e menores de 13 saem do público mas continuam vendo a própria posição.
Também cobre PUT /visibilidade e GET /perfil. Sem banco (repo falso).
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.nucleo.dependencias import ContextoRequisicao
from api.nucleo.dependencias_conta_nuvem import (
    UsuarioAutenticado,
    usuario_autenticado,
    usuario_opcional,
)
from api.ranking.cache import limpar_tudo
from api.ranking.rotas import obter_servico_ranking
from api.ranking.servico import ServicoRanking
from tests.contratos.fakes_ranking import FakeRepoRanking
from tests.unitarios.fakes_conta import FakeSession


def _usuarios():
    return [
        {"id_usuario": "id-u1", "co_usuario": "ABC11111", "no_exibicao": "Um",
         "nu_xp_total": 500, "ic_visivel_placar": True, "idade": 20},
        {"id_usuario": "id-u2", "co_usuario": "ABC22222", "no_exibicao": "Dois",
         "nu_xp_total": 300, "ic_visivel_placar": True, "idade": 20},
        {"id_usuario": "id-u3", "co_usuario": "ABC33333", "no_exibicao": "Tres",
         "nu_xp_total": 400, "ic_visivel_placar": False, "idade": 20},  # opt-out
        {"id_usuario": "id-u4", "co_usuario": "ABC44444", "no_exibicao": "Quatro",
         "nu_xp_total": 200, "ic_visivel_placar": True, "idade": 10},  # <13
        {"id_usuario": "id-u5", "co_usuario": "ABC55555", "no_exibicao": "Cinco",
         "nu_xp_total": 0, "ic_visivel_placar": True, "idade": 20},  # sem XP
    ]


@pytest.fixture(autouse=True)
def _cache_limpo():
    """O leaderboard tem cache de 30 s (ver `api/ranking/cache.py`). Sem esvaziar
    entre os testes, o segundo teste receberia a resposta MONTADA PELO PRIMEIRO —
    com o repositório falso do outro caso — e passaria (ou falharia) por engano."""
    limpar_tudo()
    yield
    limpar_tudo()


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _autenticar(id_usuario: str, co_usuario: str = "ABC11111") -> None:
    """Finge um usuário logado.

    Sobrescreve as DUAS dependências: `usuario_autenticado` (visibilidade/perfil,
    que exigem token) e `usuario_opcional` (leaderboard, que aceita convidado).
    São dependências distintas para o FastAPI — sobrescrever só uma deixaria a
    outra rodando de verdade, e o teste falharia por falta de cabeçalhos, não pelo
    que ele quer checar."""
    usuario = UsuarioAutenticado(
        id_usuario=id_usuario,
        co_usuario=co_usuario,
        dt_nascimento=None,
        contexto=ContextoRequisicao(
            versao_app="1.0.0", plataforma="android", idioma="pt"
        ),
    )
    app.dependency_overrides[usuario_autenticado] = lambda: usuario
    app.dependency_overrides[usuario_opcional] = lambda: usuario


def _convidado() -> None:
    """Finge um CONVIDADO: sem conta, sem token. `usuario_opcional` devolve None."""
    app.dependency_overrides[usuario_opcional] = lambda: None


def _usar_repo(repo: FakeRepoRanking, sessao: FakeSession) -> None:
    app.dependency_overrides[obter_servico_ranking] = lambda: ServicoRanking(
        repo, sessao
    )


def test_leaderboard_publico_exclui_optout_e_menores(client):
    _autenticar("id-u1")
    _usar_repo(FakeRepoRanking(_usuarios()), FakeSession())

    r = client.get("/v1/ranking/leaderboard")
    assert r.status_code == 200
    body = r.json()
    # Público = só visíveis e ≥13: u1 (pos 1) e u2 (pos 3). u3 (opt-out) e
    # u4 (<13) ficam de fora; u5 (0 XP) nem entra no ranking.
    codigos = [linha["co_usuario"] for linha in body["top"]]
    assert codigos == ["ABC11111", "ABC22222"]
    posicoes = [linha["nu_posicao"] for linha in body["top"]]
    assert posicoes == [1, 3]  # ranking denso deixa "buracos" visíveis à frente
    # 'eu' presente com a posição real.
    assert body["eu"]["nu_posicao"] == 1


def test_optout_some_do_publico_mas_ve_propria_posicao(client):
    _autenticar("id-u3", "ABC33333")
    _usar_repo(FakeRepoRanking(_usuarios()), FakeSession())

    body = client.get("/v1/ranking/leaderboard").json()
    # u3 não aparece na lista pública…
    assert "ABC33333" not in [l["co_usuario"] for l in body["top"]]
    # …mas vê a própria posição (real, 2º) marcada como não-pública.
    assert body["eu"]["nu_posicao"] == 2
    assert body["eu"]["ic_publico"] is False


def test_menor_de_13_fora_do_publico_mas_com_posicao(client):
    _autenticar("id-u4", "ABC44444")
    _usar_repo(FakeRepoRanking(_usuarios()), FakeSession())

    body = client.get("/v1/ranking/leaderboard").json()
    assert "ABC44444" not in [l["co_usuario"] for l in body["top"]]
    assert body["eu"]["nu_posicao"] == 4
    assert body["eu"]["ic_publico"] is False


def test_usuario_sem_xp_nao_tem_entrada(client):
    _autenticar("id-u5", "ABC55555")
    _usar_repo(FakeRepoRanking(_usuarios()), FakeSession())

    body = client.get("/v1/ranking/leaderboard").json()
    assert body["eu"] is None  # ainda não pontuou


def test_put_visibilidade_desliga_e_confirma(client):
    _autenticar("id-u1")
    repo, sessao = FakeRepoRanking(_usuarios()), FakeSession()
    _usar_repo(repo, sessao)

    r = client.put(
        "/v1/ranking/visibilidade", json={"ic_visivel_placar": False}
    )
    assert r.status_code == 200
    assert r.json()["ic_visivel_placar"] is False
    assert repo.visibilidade_alterada["id-u1"] is False
    assert sessao.commits == 1


def test_perfil_devolve_progressao(client):
    _autenticar("id-u1")
    _usar_repo(FakeRepoRanking(_usuarios()), FakeSession())

    body = client.get("/v1/ranking/perfil").json()
    assert body["progressao"]["nu_xp_total"] == 500


# ── Convidado (sem conta) ────────────────────────────────────────────────────
def test_convidado_ve_o_topN_publico_e_nao_tem_linha_eu(client):
    """O Top-N é PÚBLICO. Antes esta rota exigia token e o convidado levava um
    401 — que a tela do app traduzia como "sem conexão", uma mentira. Agora ele
    vê o placar (é o principal motivo para criar conta) e `eu` volta `null`."""
    _convidado()
    _usar_repo(FakeRepoRanking(_usuarios()), FakeSession())

    r = client.get("/v1/ranking/leaderboard")
    assert r.status_code == 200
    body = r.json()
    assert [l["co_usuario"] for l in body["top"]] == ["ABC11111", "ABC22222"]
    assert body["eu"] is None  # sem conta, não há posição própria


def test_convidado_nao_altera_visibilidade_nem_ve_perfil(client):
    """A ABERTURA é só do leaderboard. As outras duas rotas continuam exigindo
    token — um convidado não tem o que tornar público nem progressão na nuvem."""
    _convidado()
    _usar_repo(FakeRepoRanking(_usuarios()), FakeSession())

    assert client.put(
        "/v1/ranking/visibilidade", json={"ic_visivel_placar": False}
    ).status_code in (400, 401)
    assert client.get("/v1/ranking/perfil").status_code in (400, 401)


# ── Cache ────────────────────────────────────────────────────────────────────
def test_segunda_chamada_nao_toca_o_banco(client):
    """Montar o ranking varre e ORDENA a tabela inteira (a VIEW usa DENSE_RANK,
    que não é indexável). O cache existe para que N acessos virem 1 consulta —
    é o que torna seguro dar ao usuário um botão de atualizar."""
    repo = FakeRepoRanking(_usuarios())
    _autenticar("id-u1")
    _usar_repo(repo, FakeSession())

    client.get("/v1/ranking/leaderboard")
    client.get("/v1/ranking/leaderboard")
    client.get("/v1/ranking/leaderboard")

    assert repo.chamadas_top == 1  # três acessos, UMA consulta
    assert repo.chamadas_eu == 1


def test_mudar_visibilidade_invalida_o_cache(client):
    """Entrar ou sair do placar reposiciona todo mundo abaixo de mim, e o usuário
    está olhando para a tela: ele precisa ver o efeito AGORA, não daqui a 30 s."""
    repo = FakeRepoRanking(_usuarios())
    _autenticar("id-u1")
    _usar_repo(repo, FakeSession())

    client.get("/v1/ranking/leaderboard")
    assert repo.chamadas_top == 1

    client.put("/v1/ranking/visibilidade", json={"ic_visivel_placar": False})
    client.get("/v1/ranking/leaderboard")
    assert repo.chamadas_top == 2  # consultou de novo, não serviu o cache velho


def test_usuario_sem_xp_nao_reconsulta_a_cada_acesso(client):
    """Quem ainda não pontuou não tem linha ('eu' = None). Se guardássemos esse
    `None` como "não consultei ainda", ele refaria a consulta CARA toda vez —
    justamente o caso mais comum de quem acabou de chegar."""
    repo = FakeRepoRanking(_usuarios())
    _autenticar("id-u5", "ABC55555")
    _usar_repo(repo, FakeSession())

    assert client.get("/v1/ranking/leaderboard").json()["eu"] is None
    assert client.get("/v1/ranking/leaderboard").json()["eu"] is None
    assert repo.chamadas_eu == 1

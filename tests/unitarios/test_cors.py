"""Testes do CORS — o preflight de PATCH/DELETE precisa passar para o Flutter Web
(Chrome) conseguir editar perfil e excluir conta em dev."""
from fastapi.testclient import TestClient

from api.main import app


def _preflight(metodo: str, caminho: str, origem: str):
    return TestClient(app).options(
        caminho,
        headers={
            "Origin": origem,
            "Access-Control-Request-Method": metodo,
        },
    )


def test_preflight_patch_perfil_localhost_ok():
    # Porta aleatória de localhost (como o `flutter run -d chrome` usa).
    r = _preflight("PATCH", "/v1/conta/perfil", "http://localhost:54321")
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:54321"


def test_preflight_delete_conta_localhost_ok():
    r = _preflight("DELETE", "/v1/conta", "http://127.0.0.1:9999")
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:9999"


def test_origem_nao_permitida_nao_recebe_cabecalho():
    # Um site aleatório não ganha permissão de CORS.
    r = _preflight("PATCH", "/v1/conta/perfil", "https://site-malicioso.example")
    assert r.headers.get("access-control-allow-origin") is None


def test_eh_producao_detecta_variacoes():
    # A flag que decide NÃO liberar localhost no CORS em produção (SEG-02).
    from api.configuracao import Configuracoes

    assert Configuracoes(AMBIENTE="producao").eh_producao is True
    assert Configuracoes(AMBIENTE="Production").eh_producao is True
    assert Configuracoes(AMBIENTE="prod").eh_producao is True
    assert Configuracoes(AMBIENTE="desenvolvimento").eh_producao is False
    assert Configuracoes(AMBIENTE="dev").eh_producao is False

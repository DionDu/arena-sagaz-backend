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

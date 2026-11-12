"""A página do card do dia montada em `/card-do-dia/` (`api/site/pagina_card_do_dia.py`).

Os casos montam a página num app FastAPI de teste, apontando para uma pasta
temporária (`tmp_path`, um recurso do pytest que cria uma pasta nova por teste):
assim não dependem de o build Flutter estar ou não em `site/card-do-dia/`.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.site import pagina_card_do_dia


def _app_com(pasta, monkeypatch) -> tuple[FastAPI, bool]:
    monkeypatch.setattr(pagina_card_do_dia, "PASTA", pasta)
    app = FastAPI()
    return app, pagina_card_do_dia.montar(app)


def test_serve_o_index_e_os_arquivos_com_noindex(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>card do dia</html>", encoding="utf-8")
    (tmp_path / "main.dart.js").write_text("// js", encoding="utf-8")
    app, montou = _app_com(tmp_path, monkeypatch)
    assert montou
    cliente = TestClient(app)
    r = cliente.get("/card-do-dia/")
    assert r.status_code == 200
    assert "card do dia" in r.text
    # Ferramenta do dono: fora dos buscadores, e sempre conferida (build novo
    # chega na hora).
    assert r.headers["x-robots-tag"] == "noindex"
    assert r.headers["cache-control"] == "no-cache"
    assert cliente.get("/card-do-dia/main.dart.js").status_code == 200


def test_sem_o_build_nao_monta_nada(tmp_path, monkeypatch):
    """Um deploy sem a pasta: a página não existe, e nada mais quebra."""
    app, montou = _app_com(tmp_path / "nao-existe", monkeypatch)
    assert not montou
    assert TestClient(app).get("/card-do-dia/").status_code == 404


def test_o_mount_e_so_do_prefixo(tmp_path, monkeypatch):
    """Fora de `/card-do-dia`, o mount não responde (o site não tem catch-all)."""
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    app, _ = _app_com(tmp_path, monkeypatch)
    assert TestClient(app).get("/outra-coisa").status_code == 404

"""Testes da hospedagem de documentos legais (G3): renderizador + rotas."""
import pytest
from fastapi.testclient import TestClient

from api.legal.markdown_html import renderizar_markdown
from api.legal.rotas import VERSAO_LEGAL
from api.main import app


# ── renderizador Markdown → HTML ─────────────────────────────────────────────


def test_titulos():
    assert "<h1>Olá</h1>" in renderizar_markdown("# Olá")
    assert "<h2>Seção</h2>" in renderizar_markdown("## Seção")


def test_negrito():
    assert "<strong>forte</strong>" in renderizar_markdown("isto é **forte**")


def test_link_md_vira_relativo_sem_extensao():
    html = renderizar_markdown("veja [aqui](exclusao-conta.md)")
    assert '<a href="exclusao-conta">aqui</a>' in html


def test_link_perigoso_vira_so_texto():
    html = renderizar_markdown("[x](javascript:alert(1))")
    assert "javascript:" not in html
    assert "x" in html


def test_comentario_html_removido():
    html = renderizar_markdown("<!-- rascunho -->\n# Título")
    assert "rascunho" not in html
    assert "<h1>Título</h1>" in html


def test_paragrafo_junta_linhas():
    html = renderizar_markdown("linha um\nlinha dois")
    assert "<p>linha um linha dois</p>" in html


def test_lista_nao_ordenada():
    html = renderizar_markdown("- a\n- b")
    assert "<ul><li>a</li><li>b</li></ul>" in html


def test_lista_ordenada():
    html = renderizar_markdown("1. um\n2. dois")
    assert "<ol><li>um</li><li>dois</li></ol>" in html


def test_citacao():
    html = renderizar_markdown("> aviso importante")
    assert "<blockquote><p>aviso importante</p></blockquote>" in html


def test_escapa_html():
    # Um '<' no texto não pode virar tag.
    html = renderizar_markdown("a < b e c > d")
    assert "&lt;" in html and "&gt;" in html


# ── rotas ────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return TestClient(app)


def test_recente_200_html(client):
    r = client.get("/legal/pt/privacidade")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Política de Privacidade" in r.text
    # "Mais recente" tem cache curto (não imutável).
    assert "immutable" not in r.headers.get("cache-control", "")


def test_versionado_imutavel(client):
    r = client.get(f"/legal/{VERSAO_LEGAL}/pt/privacidade")
    assert r.status_code == 200
    assert "immutable" in r.headers.get("cache-control", "")


def test_idioma_invalido_404(client):
    r = client.get("/legal/xx/privacidade")
    assert r.status_code == 404


def test_documento_invalido_404(client):
    r = client.get("/legal/pt/inexistente")
    assert r.status_code == 404


def test_versao_inexistente_404(client):
    r = client.get("/legal/9.9/pt/termos")
    assert r.status_code == 404


def test_indice_200(client):
    r = client.get("/legal")
    assert r.status_code == 200
    assert "Documentos legais" in r.text


def test_todos_documentos_idiomas(client):
    # Os 3 documentos × 3 idiomas existem e abrem (200).
    for idioma in ("pt", "en", "es"):
        for doc in ("termos", "privacidade", "exclusao-conta"):
            r = client.get(f"/legal/{idioma}/{doc}")
            assert r.status_code == 200, f"{idioma}/{doc}"


# ── API JSON para o app (/v1/legal) ──────────────────────────────────────────
#
# É por esta rota que o app deixa de depender do texto EMBUTIDO na build. Sem
# ela, publicar termos novos não mudaria nada em nenhum aparelho já instalado.


def test_api_devolve_markdown_cru_e_versao(client):
    r = client.get("/v1/legal/pt/termos")
    assert r.status_code == 200
    corpo = r.json()

    assert corpo["co_documento"] == "termos"
    assert corpo["co_idioma"] == "pt"
    assert corpo["co_versao"] == VERSAO_LEGAL
    # Markdown CRU, não HTML — o app renderiza com o próprio tema.
    assert corpo["tx_conteudo"].lstrip().startswith(("<!--", "#"))
    assert "# Termos de Uso" in corpo["tx_conteudo"]
    assert "<h1" not in corpo["tx_conteudo"]


def test_api_e_a_pagina_publica_servem_o_MESMO_texto(client):
    # Se divergissem, a pessoa aceitaria no app um texto diferente do que está
    # publicado — que é justamente o que a versão do documento deveria impedir.
    api = client.get("/v1/legal/pt/privacidade").json()["tx_conteudo"]
    html = client.get("/legal/pt/privacidade").text
    # Uma frase que só existe no texto revisado, presente nos dois.
    assert "pseudonimização" in api
    assert "pseudonimiza" in html


def test_api_sem_token_nem_cabecalhos(client):
    # Documento público: exigir token aqui só quebraria o convidado e o 1º acesso.
    r = client.get("/v1/legal/en/privacidade")
    assert r.status_code == 200


def test_api_todos_documentos_idiomas(client):
    for idioma in ("pt", "en", "es"):
        for doc in ("termos", "privacidade", "exclusao-conta"):
            r = client.get(f"/v1/legal/{idioma}/{doc}")
            assert r.status_code == 200, f"{idioma}/{doc}"
            assert r.json()["tx_conteudo"]


def test_api_idioma_ou_documento_invalido_404(client):
    assert client.get("/v1/legal/xx/termos").status_code == 404
    assert client.get("/v1/legal/pt/inexistente").status_code == 404

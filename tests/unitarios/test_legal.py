"""Testes da hospedagem de documentos legais (G3): renderizador + rotas."""
import pytest
from fastapi.testclient import TestClient

from api.legal.markdown_html import renderizar_markdown
from api.legal.rotas import (
    VERSAO_LEGAL,
    detectar_versao_vigente,
    versoes_publicadas,
)
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
    # A rota vigente manda `no-cache` para que ajustes entrem em vigor na hora
    # sem ficarem retidos em cache do navegador ou de robôs das lojas.
    assert r.headers.get("cache-control") == "no-cache"


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


# Títulos principais por idioma (1.6.0) e lista completa de títulos/entidades que
# TODA página legal deve citar (1.6.0 nos três idiomas + 1.4.0 ainda no ar na
# transição da publicação gerenciada + marcas + desenvolvedor + pacote).
# Repetidos aqui de propósito (e não importados de `rotas.py`): se alguém apagar
# o bloco de lá, o teste precisa falhar em vez de apagar junto.
_TITULO_PRINCIPAL_POR_IDIOMA = {
    "pt": "Xadrez, Damas e Jogo da Velha",
    "en": "Chess, Checkers &amp; Tic Tac Toe",
    "es": "Ajedrez, Damas y Tres en Raya",
}

_TODAS_AS_ENTIDADES = (
    # Títulos da 1.6.0 nos 3 idiomas (o link de Segurança de Dados na Play é
    # único e global, mas o e-mail de recusa cruza com o título em pt-BR).
    "Xadrez, Damas e Jogo da Velha",
    "Chess, Checkers &amp; Tic Tac Toe",
    "Ajedrez, Damas y Tres en Raya",
    # Títulos da 1.4.0 ainda publicados enquanto a publicação gerenciada segura a 1.6.0.
    "Arena Sagaz: Damas e Velha",
    "Sharp Arena: Checkers &amp; Dots",
    "Arena Sagaz: Damas y Raya",
    # Marcas, desenvolvedor, empresa e pacote.
    "Arena Sagaz",
    "Sharp Arena",
    "Fernando da Silva",
    "Santiago Data",
    "com.santiagodata.arenasagaz",
)


@pytest.mark.parametrize("idioma", ["pt", "en", "es"])
@pytest.mark.parametrize("doc", ["termos", "privacidade", "exclusao-conta"])
def test_pagina_cita_o_app_e_o_desenvolvedor_da_ficha(client, idioma, doc):
    """A Google Play recusou a 1.6.0 duas vezes (26/11/2026): o link global de
    exclusão de conta (`/legal/en/exclusao-conta`) precisava trazer a entidade da
    ficha tanto nos elementos principais (`<title>` e `<h1>` único) quanto para
    qualquer idioma/versão da ficha (1.6.0 em revisão e 1.4.0 no ar).
    """
    import re

    html = client.get(f"/legal/{idioma}/{doc}").text

    # Deve existir exatamente UM `<h1>` na página (o do Markdown foi substituído
    # pelo cabeçalho completo, evitando dois `<h1>` conflitantes).
    h1s = re.findall(r"<h1>(.*?)</h1>", html, flags=re.DOTALL)
    assert len(h1s) == 1, (idioma, doc, h1s)
    titulos_head = re.findall(r"<title>(.*?)</title>", html, flags=re.DOTALL)
    assert len(titulos_head) == 1, (idioma, doc, titulos_head)

    # Tanto `<title>` quanto `<h1>` precisam citar o título da loja daquele
    # idioma, as duas marcas e o desenvolvedor.
    titulo_esperado = _TITULO_PRINCIPAL_POR_IDIOMA[idioma]
    for elemento in (titulos_head[0], h1s[0]):
        assert titulo_esperado in elemento, (idioma, doc, elemento)
        assert "Arena Sagaz" in elemento, (idioma, doc, elemento)
        assert "Sharp Arena" in elemento, (idioma, doc, elemento)
        assert "Fernando da Silva" in elemento, (idioma, doc, elemento)

    # O corpo da página cita todos os títulos (1.6.0 e 1.4.0), marcas e pacote.
    for trecho in _TODAS_AS_ENTIDADES:
        assert trecho in html, (idioma, doc, trecho)

    # Regra expressa do dono: na moldura (`<title>`, `<h1>`, `<p class="app">` e
    # `<footer>`) manter "Fernando da Silva", sem adicionar o sobrenome do meio
    # onde ainda não existia (`termos.md` e `privacidade.md` já trazem o nome
    # civil completo no corpo do documento por exigência da LGPD; `exclusao-conta`
    # não traz).
    bloco_app = re.findall(r'<p class="app">(.*?)</p>', html, flags=re.DOTALL)
    rodape = re.findall(r"<footer>(.*?)</footer>", html, flags=re.DOTALL)
    assert len(bloco_app) == 1 and len(rodape) == 1
    for moldura in (titulos_head[0], h1s[0], bloco_app[0], rodape[0]):
        assert "Fernando Santiago da Silva" not in moldura, (idioma, doc, moldura)
    if doc == "exclusao-conta":
        assert "Fernando Santiago da Silva" not in html, idioma


def test_rotas_legais_respondem_head(client):
    """Robôs de verificação de link testam `HEAD` antes de `GET`. `@router.get`
    sozinho devolveria 405; `@router.head` devolve 200 sem corpo."""
    for caminho in (
        "/legal",
        "/legal/",
        "/legal/en/exclusao-conta",
        "/legal/en/privacidade",
        f"/legal/{VERSAO_LEGAL}/en/exclusao-conta",
    ):
        r = client.head(caminho)
        assert r.status_code == 200, caminho
        assert r.content == b"", caminho


def test_identificacao_nao_entra_no_texto_versionado(client):
    """O bloco do app é MOLDURA da página, e não texto do documento.

    O app compara a versão do texto (`co_versao`) para pedir um novo aceite dos
    termos. Se o bloco entrasse no markdown, a recusa da Play teria custado um
    re-aceite de todos os jogadores por uma linha que não muda nenhum direito.
    """
    api = client.get("/v1/legal/en/exclusao-conta").json()
    assert "Fernando da Silva" not in api["tx_conteudo"]
    assert api["co_versao"] == VERSAO_LEGAL


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


# ── Versão vigente detectada pela PASTA (nada de editar código) ───────────────
#
# A partir de 14/07 ninguém edita VERSAO_LEGAL na mão: o backend lê legal/ e usa a
# maior pasta. Publicar termos novos é só criar a pasta e subir.


def test_detecta_a_maior_versao(tmp_path):
    for v in ("1.0", "1.1", "1.2"):
        (tmp_path / v).mkdir()
    assert detectar_versao_vigente(tmp_path) == "1.2"


def test_ordena_por_numero_e_nao_por_texto(tmp_path):
    # '1.10' é MAIOR que '1.9' — a ordem alfabética (que muitos escrevem sem pensar)
    # erraria e serviria a versão antiga como se fosse a nova.
    for v in ("1.9", "1.10"):
        (tmp_path / v).mkdir()
    assert detectar_versao_vigente(tmp_path) == "1.10"


def test_ignora_o_que_nao_e_pasta_de_versao(tmp_path):
    (tmp_path / "1.0").mkdir()
    (tmp_path / "1.1").mkdir()
    (tmp_path / "backup").mkdir()
    (tmp_path / "1.1-rascunho").mkdir()
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    assert versoes_publicadas(tmp_path) == ["1.0", "1.1"]
    assert detectar_versao_vigente(tmp_path) == "1.1"


def test_sem_nenhuma_pasta_cai_no_fallback_seguro(tmp_path):
    # Não deve acontecer (a 1.0 está no repo), mas um valor seguro é melhor do que
    # derrubar o boot da API por causa de uma pasta faltando.
    assert detectar_versao_vigente(tmp_path) == "1.0"


def test_o_repo_de_verdade_tem_ao_menos_a_1_0():
    # Âncora do estado atual do repositório: a 1.0 existe e é a vigente hoje. Se
    # alguém adicionar uma pasta 1.1 amanhã, VERSAO_LEGAL passa a ser "1.1"
    # SOZINHO — que é o ponto: não há nada para lembrar de mexer.
    assert "1.0" in versoes_publicadas()
    assert VERSAO_LEGAL in versoes_publicadas()

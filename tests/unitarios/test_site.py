"""Testes do site de apresentação (landing + app-ads.txt).

Além de checar que as duas rotas respondem, estes testes guardam as DUAS
armadilhas que quase nos pegaram ao colocar o site no mesmo serviço da API:

1. o site NÃO pode sombrear as rotas da API (o 404 dela tem de continuar JSON);
2. o ``app-ads.txt`` NÃO pode ser barrado pelo rate limit — se o rastreador do
   AdMob levar um 429, a validação dos vendedores falha em silêncio.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.nucleo.rate_limit import _ISENTOS


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(app)


# ── A landing ────────────────────────────────────────────────────────────────


def test_landing_responde_na_raiz(cliente: TestClient):
    r = cliente.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_landing_tem_o_conteudo_esperado(cliente: TestClient):
    """A página precisa trazer o que as lojas vão procurar: o nome, a âncora de
    suporte (a "Support URL" que a Apple exige) e os links das duas lojas."""
    html = cliente.get("/").text
    assert "Arena Sagaz" in html
    assert 'id="suporte"' in html            # âncora da Support URL da Apple
    assert "play.google.com" in html          # botão da Play
    assert "apps.apple.com" in html           # botão da App Store


def test_landing_nao_depende_de_CDN(cliente: TestClient):
    """A página tem de ser AUTOCONTIDA: fontes embutidas, sem script/estilo
    externo. Se alguém colar um `<script src="https://cdn...">` numa revisão
    futura, este teste pega — um CDN fora do ar derrubaria a nossa vitrine (e a
    Support URL que a Apple exige) sem aviso."""
    html = cliente.get("/").text
    # As fontes precisam vir em base64, dentro do próprio arquivo.
    assert "@font-face" in html
    assert "data:font/woff" in html
    # Nada de recurso remoto: os ÚNICOS domínios externos permitidos são os das
    # lojas (links de download) e o namespace do SVG (que não é um download).
    import re
    permitidos = ("play.google.com", "apps.apple.com", "www.w3.org")
    for url in re.findall(r'https?://[^\s"\'()]+', html):
        assert any(p in url for p in permitidos), f"recurso externo proibido: {url}"


# ── O app-ads.txt ────────────────────────────────────────────────────────────


def test_app_ads_na_raiz_do_dominio(cliente: TestClient):
    """O AdMob busca em `/app-ads.txt` — na RAIZ, não em subpasta."""
    r = cliente.get("/app-ads.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")


def test_app_ads_declara_o_nosso_id_de_editor(cliente: TestClient):
    """A linha precisa estar no formato do IAB e citar o NOSSO id de editor (o
    mesmo de `config/prod.json` do app). Um id errado aqui = anúncio não vende."""
    texto = cliente.get("/app-ads.txt").text
    assert "google.com, pub-7502939199237784, DIRECT, f08c47fec0942fa0" in texto


def test_app_ads_e_a_landing_estao_isentos_do_rate_limit():
    """⚠️ O teste que guarda o achado mais traiçoeiro desta rodada.

    O `RateLimitMiddleware` é a camada mais externa e vale para TODO caminho
    (120 GET/min por IP). Sem a isenção, o rastreador do AdMob pode levar `429`
    ao buscar o `app-ads.txt` — e a validação dos vendedores falha **sem
    nenhum erro visível**, semanas depois, quebrando exatamente o arquivo que
    motiva a existência do site.
    """
    assert "/app-ads.txt" in _ISENTOS
    assert "/" in _ISENTOS


# ── O site não pode atrapalhar a API ─────────────────────────────────────────


def test_api_continua_respondendo_json_em_404(cliente: TestClient):
    """A razão de NÃO montarmos um `StaticFiles` em "/".

    Um mount na raiz casaria qualquer caminho não atendido — inclusive um
    `/v1/rota-inexistente` — e o 404 da API viraria o 404 do servidor de
    arquivos. Apps já publicados esperam o JSON. Este teste trava isso.
    """
    r = cliente.get("/v1/rota-que-nao-existe")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_rotas_da_api_e_legal_continuam_vivas(cliente: TestClient):
    """O roteador do site é registrado por ÚLTIMO. Se alguém o mover para cima,
    ou trocá-lo por um mount na raiz, isto aqui cai."""
    assert cliente.get("/v1/health").status_code == 200
    assert cliente.get("/legal/pt/privacidade").status_code == 200
    assert cliente.get("/legal/pt/exclusao-conta").status_code == 200

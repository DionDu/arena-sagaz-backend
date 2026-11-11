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


def test_os_dois_selos_de_loja_estao_visiveis(cliente: TestClient):
    """Os selos das DUAS lojas têm de estar no ar, não comentados.

    O teste acima (`..._conteudo_esperado`) não pega isto: ele procura os
    domínios no texto do HTML, e `play.google.com` continua aparecendo dentro de
    um `<!-- ... -->`. O selo da Play ficou comentado de 04 a 06/08/2026, à
    espera da publicação; agora que os dois apps estão publicados, esconder um
    deles de novo é regressão — o visitante de Android não teria por onde
    baixar. Por isso a varredura aqui é feita SEM os comentários.
    """
    import re

    sem_comentarios = re.sub(r"<!--.*?-->", "", cliente.get("/").text, flags=re.DOTALL)
    assert 'id="linkApple"' in sem_comentarios
    assert 'id="seloApple"' in sem_comentarios
    assert 'id="linkPlay"' in sem_comentarios
    assert 'id="seloPlay"' in sem_comentarios


def test_landing_nao_depende_de_CDN(cliente: TestClient):
    """A página tem de ser AUTOCONTIDA: fontes embutidas, sem script/estilo
    externo. Se alguém colar um `<script src="https://cdn...">` numa revisão
    futura, este teste pega — um CDN fora do ar derrubaria a nossa vitrine (e a
    Support URL que a Apple exige) sem aviso."""
    import re

    html = cliente.get("/").text
    # As fontes precisam vir em base64, dentro do próprio arquivo.
    assert "@font-face" in html
    assert "data:font/woff" in html

    # Comentários HTML saem da varredura: o navegador nunca busca uma URL que
    # está dentro de `<!-- ... -->`. Eles guardam instruções para nós (ex.: onde
    # baixar os selos oficiais das lojas), e contá-las como "recurso externo"
    # seria um alarme falso.
    sem_comentarios = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    # Nada de recurso remoto: os ÚNICOS domínios externos permitidos são os das
    # lojas (links de download) e o namespace do SVG (que não é um download).
    permitidos = ("play.google.com", "apps.apple.com", "www.w3.org")
    for url in re.findall(r'https?://[^\s"\'()]+', sem_comentarios):
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


# ── As imagens da vitrine ────────────────────────────────────────────────────


def test_imagens_da_vitrine_respondem(cliente: TestClient):
    """As capturas e os selos das lojas são servidos de `/img/`, não embutidos.

    A landing deixou de ser um HTML único em 04/08/2026: 9 capturas (3 telas × 3
    idiomas) e 6 selos de loja em base64 levariam o HTML de 210 KB para ~450 KB,
    que todo visitante baixaria inteiro — inclusive os idiomas que ele não vê.
    Desde o site dos quatro jogos (11/11/2026) são 33 telas, e o argumento só
    ficou mais forte.
    """
    for nome, tipo in [
        ("vitrine_hub_pt.webp", "image/webp"),
        ("vitrine_rivais_en_escuro.webp", "image/webp"),
        ("jogo_quatro_es.webp", "image/webp"),
        ("appstore_pt.svg", "image/svg+xml"),
        ("googleplay_pt.png", "image/png"),
    ]:
        r = cliente.get(f"/img/{nome}")
        assert r.status_code == 200, nome
        assert r.headers["content-type"].startswith(tipo), nome
        assert len(r.content) > 1000, nome


def test_todo_idioma_tem_captura_e_selo(cliente: TestClient):
    """O site troca as imagens junto com o idioma. Um arquivo faltando não
    quebraria a página — só deixaria uma moldura vazia naquele idioma, que é
    justamente o tipo de defeito que ninguém percebe (quem revisa lê em pt).

    A lista de telas sai do PRÓPRIO HTML (`data-tela="..."`), e não de uma cópia
    escrita aqui: assim uma tela nova na página que esqueceu os arquivos de um
    idioma derruba o teste, em vez de passar porque a lista do teste também
    esqueceu. As que têm `data-tema` precisam também da versão `_escuro`.
    """
    import re

    # O `<script>` sai da varredura: o comentário do JS cita `<img data-tela=...>`
    # como EXEMPLO, e isso não é uma tela da página.
    html = re.sub(r"<script>.*?</script>", "", cliente.get("/").text, flags=re.DOTALL)
    telas = re.findall(r'<img data-tela="([a-z_]+)"( data-tema)?', html)
    # Os 4 jogos + o Desafio do Dia + o trio "por dentro".
    assert len(telas) == 8, telas
    for idioma in ("pt", "en", "es"):
        for chave, tem_tema in telas:
            assert cliente.get(f"/img/{chave}_{idioma}.webp").status_code == 200, (chave, idioma)
            if tem_tema:
                assert cliente.get(f"/img/{chave}_{idioma}_escuro.webp").status_code == 200, (chave, idioma)
        assert cliente.get(f"/img/appstore_{idioma}.svg").status_code == 200
        assert cliente.get(f"/img/googleplay_{idioma}.png").status_code == 200


def test_os_quatro_jogos_estao_na_pagina(cliente: TestClient):
    """O site nasceu quando só existia o Jogo dos Pontinhos e ficou três versões
    do app falando só dele. Este teste trava a vitrine dos quatro jogos: cada um
    tem o seu cartão, com captura, nome e descrição."""
    html = cliente.get("/").text
    for jogo in ("damas", "velha", "pontinhos", "quatro"):
        assert f'data-tela="jogo_{jogo}"' in html, jogo
        assert f'data-i="jogo_{jogo}_d"' in html, jogo
    assert 'id="desafio"' in html  # a seção do Desafio do Dia


def test_pagina_sem_travessao_longo(cliente: TestClient):
    """Decisão do dono (11/11/2026): nenhum travessão longo na página, só o
    hífen comum. Vale para o texto visível nos três idiomas (o dicionário `T`
    mora no próprio HTML) e, por simplicidade, para o arquivo inteiro."""
    assert "—" not in cliente.get("/").text


def test_nome_de_terceiros_fora_do_site(cliente: TestClient):
    """O jogo de alinhar quatro é sempre "Quatro em Linha / Four in a Row /
    Cuatro en Raya": o nome comercial de terceiros tirou a versão 1.3.0 da
    análise da loja (`arena-sagaz-frontend/docs/DECISOES-do-dono.md` §8zzd), e o
    site é a página de marketing que as duas lojas visitam."""
    import re

    html = cliente.get("/").text.lower()
    assert not re.search(r"connect\s*-?\s*4|connect four|lig\s*-?\s*4|conecta\s*-?\s*4", html)


# ── O vídeo da vitrine ───────────────────────────────────────────────────────


def test_video_existe_nos_tres_idiomas(cliente: TestClient):
    """A prévia do hero troca com o idioma, como as capturas."""
    for idioma in ("pt", "en", "es"):
        r = cliente.get(f"/video/previa_app_{idioma}.mp4", headers={"Range": "bytes=0-1023"})
        assert r.status_code == 206, idioma
        assert r.headers["content-type"].startswith("video/mp4"), idioma


def test_video_atende_faixa_de_bytes(cliente: TestClient):
    """⚠️ O Safari do iPhone NÃO toca vídeo de servidor que ignora `Range`.

    Sem esta garantia o vídeo funcionaria no computador de quem testa e ficaria
    preto justamente no aparelho do público do app. O pedido de uma faixa tem
    de voltar `206`, com exatamente os bytes pedidos e o `Content-Range`.
    """
    r = cliente.get("/video/previa_app_pt.mp4", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206
    assert len(r.content) == 100
    assert r.headers["content-range"].startswith("bytes 0-99/")
    assert r.headers.get("accept-ranges") == "bytes"
    # Os bytes 4..8 de um MP4 são o tipo da 1ª caixa: "ftyp".
    assert r.content[4:8] == b"ftyp"


def test_video_so_serve_o_que_esta_na_pasta(cliente: TestClient):
    """A rota de vídeo também é consulta a dicionário: nada de caminho livre."""
    assert cliente.get("/video/nao_existe.mp4").status_code == 404
    assert cliente.get("/video/%2e%2e%2findex.html").status_code == 404
    assert cliente.get("/video/%2e%2e%2f%2e%2e%2fapi%2fmain.py").status_code == 404


def test_img_so_serve_o_que_esta_na_pasta(cliente: TestClient):
    """A rota é uma CONSULTA A DICIONÁRIO, não um caminho de arquivo: o que não
    foi carregado de `site/img/` no import simplesmente não existe. Sem isto,
    `/img/` seria a porta de entrada para leitura de arquivo arbitrário."""
    assert cliente.get("/img/nao_existe.webp").status_code == 404
    assert cliente.get("/img/index.html").status_code == 404
    # ⚠️ Escrever `/img/../app-ads.txt` aqui NÃO testa nada: o cliente HTTP
    # resolve o `..` antes de enviar, e o servidor recebe `/app-ads.txt` — que
    # responde 200 por ser uma rota legítima. Para o `..` chegar de verdade ao
    # parâmetro, ele tem de ir percent-encoded, como abaixo.
    assert cliente.get("/img/%2e%2e%2fapp-ads.txt").status_code == 404
    assert cliente.get("/img/%2e%2e%2f%2e%2e%2fapi%2fmain.py").status_code == 404

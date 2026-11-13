"""Testes do site de apresentação (landing, app-ads.txt, imagens, vídeo e /baixar).

Além de checar que as rotas respondem, estes testes guardam as DUAS
armadilhas que quase nos pegaram ao colocar o site no mesmo serviço da API:

1. o site NÃO pode sombrear as rotas da API (o 404 dela tem de continuar JSON);
2. o ``app-ads.txt`` NÃO pode ser barrado pelo rate limit — se o rastreador do
   AdMob levar um 429, a validação dos vendedores falha em silêncio.

Os testes do ``/baixar`` (o link das redes sociais) estão no fim do arquivo.
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


def test_moldura_de_celular_sem_notch_proprio(cliente: TestClient):
    """As capturas e o vídeo são telas cruas do iPhone, já com a Dynamic Island.
    A moldura `.fone` desenhava uma pílula própria no topo, e a tela aparecia
    com DOIS notches (visto pelo dono em 11/11/2026). Ela não pode voltar."""
    assert ".fone::before" not in cliente.get("/").text


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


# ── O /baixar: um link só para as redes sociais ──────────────────────────────
#
# User-Agents no formato real de cada app. O que importa em todos: o navegador
# interno do Instagram/Facebook/Threads ACRESCENTA a marca dele ("Instagram ...",
# "FBAN/FBIOS", "FB_IAB/FB4A", "Barcelona"), mas mantém o "iPhone"/"Android" do
# sistema, e é por ele que a rota decide.
#
# O WhatsApp não tem navegador próprio com marca: o link do Status abre no
# navegador do sistema (Safari no iPhone, aba do Chrome no Android), então quem
# toca chega com o User-Agent desses. O único User-Agent com "WhatsApp" é o do
# ROBÔ que monta a prévia do link, e ele tem de receber a página (com as tags
# og:), não um redirecionamento.

UA_IPHONE_SAFARI = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
)
UA_IPAD_ANTIGO = (  # iOS 12: antes de o iPad passar a se dizer "Macintosh"
    "Mozilla/5.0 (iPad; CPU OS 12_5_7 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/12.1.2 Mobile/15E148 Safari/604.1"
)
UA_ANDROID_CHROME = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Mobile Safari/537.36"
)
UA_INSTAGRAM_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 Instagram 337.0.3.23.54 (iPhone14,5; iOS 17_5; "
    "pt_BR; pt; scale=3.00; 1170x2532; 614950592; IABMV/1)"
)
UA_INSTAGRAM_ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; SM-S918B Build/UP1A.231005.007; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/125.0.6422.165 Mobile "
    "Safari/537.36 Instagram 334.0.0.42.95 Android (34/14; 480dpi; 1080x2340; samsung; "
    "SM-S918B; dm3q; qcom; pt_BR; 609343004)"
)
UA_FACEBOOK_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/21E236 [FBAN/FBIOS;FBAV/459.0.0.31.110;"
    "FBBV/612383011;FBDV/iPhone15,2;FBMD/iPhone;FBSN/iOS;FBSV/17.4;FBSS/3;FBID/phone;"
    "FBLC/pt_BR;FBOP/5;FBRV/614091822]"
)
UA_FACEBOOK_ANDROID = (
    "Mozilla/5.0 (Linux; Android 13; SM-A536E Build/TP1A.220624.014; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.6367.179 Mobile "
    "Safari/537.36 [FB_IAB/FB4A;FBAV/464.0.0.58.110;]"
)
UA_THREADS_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 Barcelona 352.0.0.30.79 (iPhone16,2; iOS 18_0; "
    "pt_BR; pt; scale=3.00; 1290x2796; 651108221)"
)
UA_WHATSAPP_ROBO_PREVIA = "WhatsApp/2.23.20.0 A"
UA_WINDOWS_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)
# Um Mac com Safari. O iPad moderno manda EXATAMENTE este mesmo texto.
UA_MAC_SAFARI = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.1 Safari/605.1.15"
)

APPLE = "https://apps.apple.com/app/id6790198320"
PLAY = "https://play.google.com/store/apps/details?id=com.santiagodata.arenasagaz"


def _confere_cabecalhos_sem_cache(r) -> None:
    """Toda resposta do /baixar: nenhum cache guarda, e ela depende do aparelho."""
    assert r.headers["cache-control"] == "no-store"
    assert "User-Agent" in r.headers["vary"]


@pytest.mark.parametrize(
    "user_agent, loja",
    [
        (UA_IPHONE_SAFARI, APPLE),
        (UA_IPAD_ANTIGO, APPLE),
        (UA_INSTAGRAM_IPHONE, APPLE),
        (UA_FACEBOOK_IPHONE, APPLE),
        (UA_THREADS_IPHONE, APPLE),
        (UA_ANDROID_CHROME, PLAY),
        (UA_INSTAGRAM_ANDROID, PLAY),
        (UA_FACEBOOK_ANDROID, PLAY),
    ],
    ids=[
        "iphone_e_status_whatsapp", "ipad_antigo", "instagram_iphone",
        "facebook_iphone", "threads_iphone", "android_e_status_whatsapp",
        "instagram_android", "facebook_android",
    ],
)
def test_baixar_leva_o_celular_para_a_loja_dele(cliente: TestClient, user_agent: str, loja: str):
    """Celular → 302 direto para a loja certa, inclusive de dentro dos apps."""
    r = cliente.get("/baixar", headers={"User-Agent": user_agent}, follow_redirects=False)
    # 302, e NUNCA 301: o 301 fica guardado e congelaria o destino para sempre.
    assert r.status_code == 302
    assert r.headers["location"] == loja
    _confere_cabecalhos_sem_cache(r)


@pytest.mark.parametrize(
    "user_agent",
    [UA_WINDOWS_CHROME, UA_MAC_SAFARI, UA_WHATSAPP_ROBO_PREVIA, ""],
    ids=["windows", "mac", "robo_previa_whatsapp", "sem_user_agent"],
)
def test_baixar_no_computador_mostra_os_dois_selos(cliente: TestClient, user_agent: str):
    """Sem como saber o celular → 200 com a página dos dois selos e dos dois links.
    Inclui o robô da prévia do WhatsApp: ele precisa da página para ler as og:."""
    r = cliente.get("/baixar", headers={"User-Agent": user_agent}, follow_redirects=False)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    _confere_cabecalhos_sem_cache(r)
    assert f'href="{APPLE}"' in r.text
    assert f'href="{PLAY}"' in r.text
    assert 'property="og:title"' in r.text
    # Nenhuma lacuna do modelo pode sobrar sem preencher (o comentário do topo
    # do modelo cita "{{chave}}" como exemplo, por isso a busca começa depois dele).
    assert "{{" not in r.text.split("-->", 1)[1]


@pytest.mark.parametrize(
    "accept_language, idioma",
    [
        ("pt-BR,pt;q=0.9,en;q=0.8", "pt"),
        ("en-US,en;q=0.9", "en"),
        ("es-419,es;q=0.9", "es"),
        # Francês primeiro (não temos), inglês depois: fica o inglês.
        ("fr-FR,fr;q=0.9,en;q=0.5", "en"),
        # O peso manda, não a ordem: espanhol com peso maior que inglês.
        ("en;q=0.3,es;q=0.8", "es"),
        ("de-DE", "pt"),  # nada que tenhamos → padrão
        ("", "pt"),
    ],
)
def test_pagina_de_escolha_segue_o_accept_language(cliente: TestClient, accept_language: str, idioma: str):
    """O idioma da página (e dos selos, que trazem o texto desenhado) vem do
    navegador. Padrão: português."""
    r = cliente.get(
        "/baixar",
        headers={"User-Agent": UA_WINDOWS_CHROME, "Accept-Language": accept_language},
    )
    assert f'<html lang="{idioma}"' in r.text
    assert f"/img/appstore_{idioma}.svg" in r.text
    assert f"/img/googleplay_{idioma}.png" in r.text
    assert "Accept-Language" in r.headers["vary"]


def test_pagina_de_escolha_sem_travessao_longo(cliente: TestClient):
    """A mesma regra do site (decisão do dono, 11/11/2026), nos três idiomas."""
    for idioma in ("pt", "en", "es"):
        r = cliente.get("/baixar", headers={"User-Agent": "", "Accept-Language": idioma})
        assert "—" not in r.text, idioma


def test_ipad_que_se_diz_mac_e_resolvido_no_navegador(cliente: TestClient):
    """O iPad moderno manda o User-Agent de um Mac: o servidor mostra a página, e
    ela traz o script que reconhece a tela de toque e vai para a App Store.

    O endereço da loja vai num ATRIBUTO do <html> (o script o lê de lá), e não
    escrito dentro do <script>: no atributo o navegador decodifica `&amp;`, e a
    URL da loja ganha `&` quando houver marcação de campanha.
    """
    r = cliente.get("/baixar", headers={"User-Agent": UA_MAC_SAFARI})
    assert r.status_code == 200
    assert "navigator.maxTouchPoints > 1" in r.text
    assert "indexOf('Macintosh')" in r.text
    assert "location.replace" in r.text
    assert f'data-loja-apple="{APPLE}"' in r.text


@pytest.mark.parametrize("caminho", ["/download", "/descargar"])
def test_apelidos_do_baixar(cliente: TestClient, caminho: str):
    """/download (en) e /descargar (es) fazem exatamente o mesmo que /baixar."""
    r = cliente.get(caminho, headers={"User-Agent": UA_INSTAGRAM_ANDROID}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == PLAY
    _confere_cabecalhos_sem_cache(r)
    r = cliente.get(caminho, headers={"User-Agent": UA_WINDOWS_CHROME})
    assert r.status_code == 200


def test_baixar_responde_head(cliente: TestClient):
    """Alguns apps conferem o link com HEAD antes de abrir. O `@router.get` do
    FastAPI não atende HEAD sozinho (daria 405), por isso a rota declara os dois."""
    r = cliente.head("/baixar", headers={"User-Agent": UA_IPHONE_SAFARI}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == APPLE
    r = cliente.head("/baixar", headers={"User-Agent": UA_WINDOWS_CHROME})
    assert r.status_code == 200
    assert r.content == b""  # HEAD não leva corpo


def test_baixar_nao_virou_catch_all(cliente: TestClient):
    """Três caminhos explícitos, nada de padrão: o resto continua com o 404 em
    JSON da API (o contrato dos apps em campo)."""
    for caminho in ("/v1/nao-existe", "/baixar/qualquer-coisa", "/baixarr"):
        r = cliente.get(caminho, headers={"User-Agent": UA_IPHONE_SAFARI}, follow_redirects=False)
        assert r.status_code == 404, caminho
        assert r.headers["content-type"].startswith("application/json"), caminho


def test_baixar_esta_isento_do_rate_limit():
    """Um story que viraliza manda muita gente ao mesmo tempo, e a operadora põe
    milhares de celulares atrás do mesmo IP (CGNAT). Um `429` no link da bio é
    uma instalação perdida sem erro visível. Ver o comentário em `_ISENTOS`."""
    for caminho in ("/baixar", "/download", "/descargar"):
        assert caminho in _ISENTOS


# ── A origem de cada instalação (`?o=`, decisão de 12/11/2026) ──────────────
#
# O `/baixar` repassa a origem da lista fechada à loja; quem conta são as lojas.
# Os testes usam `monkeypatch` (um recurso do pytest que troca um valor só
# durante o teste e o devolve no fim) para simular o `pt` da Apple preenchido.

from api.site import baixar as modulo_baixar  # noqa: E402 (import junto dos testes que o usam)


@pytest.mark.parametrize("origem", ["story", "app-desafio", "app-partida"])
def test_baixar_repassa_a_origem_a_google_play(cliente: TestClient, origem: str):
    """Android: a origem vira `referrer=utm_source%3D<origem>`, com o `=` de
    dentro codificado (senão a Play o leria como parâmetro dela)."""
    r = cliente.get(f"/baixar?o={origem}", headers={"User-Agent": UA_ANDROID_CHROME}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == f"{PLAY}&referrer=utm_source%3D{origem}"
    _confere_cabecalhos_sem_cache(r)


def test_baixar_repassa_a_origem_a_app_store_quando_ha_provedor(cliente: TestClient, monkeypatch):
    """iPhone: com o `pt` da conta preenchido, vai `pt` + `ct` + `mt=8`."""
    monkeypatch.setattr(modulo_baixar, "APPLE_PROVEDOR", "123456")
    r = cliente.get("/download?o=story", headers={"User-Agent": UA_INSTAGRAM_IPHONE}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == f"{APPLE}?pt=123456&ct=story&mt=8"


def test_sem_provedor_a_app_store_vai_sem_campanha(cliente: TestClient, monkeypatch):
    """Sem o `pt`, a Apple ignoraria o `ct`: melhor mandar o endereço puro."""
    monkeypatch.setattr(modulo_baixar, "APPLE_PROVEDOR", None)
    r = cliente.get("/baixar?o=story", headers={"User-Agent": UA_IPHONE_SAFARI}, follow_redirects=False)
    assert r.headers["location"] == APPLE


@pytest.mark.parametrize(
    "consulta",
    ["?o=inventada", "?o=", "?o=story%26x%3D1", "?o=<script>", "?outra=story"],
    ids=["fora_da_lista", "vazia", "tentativa_de_injetar", "html", "parametro_errado"],
)
def test_origem_fora_da_lista_e_ignorada(cliente: TestClient, consulta: str):
    """Qualquer coisa fora da lista fechada: o link funciona, só sem marcação."""
    r = cliente.get(f"/baixar{consulta}", headers={"User-Agent": UA_ANDROID_CHROME}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == PLAY


def test_origem_perdoa_maiusculas_e_espacos():
    """Quem digita o link à mão escreve `Story`; vale o mesmo que `story`."""
    assert modulo_baixar.origem_valida(" Story ") == "story"
    assert modulo_baixar.origem_valida("APP-DESAFIO") == "app-desafio"
    assert modulo_baixar.origem_valida(None) is None


def test_pagina_de_escolha_leva_a_origem_nos_selos(cliente: TestClient):
    """No computador, os selos da página também levam a origem. O `&` aparece
    como `&amp;`, a forma correta dentro de um atributo HTML."""
    r = cliente.get("/baixar?o=app-partida", headers={"User-Agent": UA_WINDOWS_CHROME})
    assert r.status_code == 200
    assert f'href="{PLAY}&amp;referrer=utm_source%3Dapp-partida"' in r.text
    # Sem origem, os selos continuam puros (a página da bio do Instagram).
    r = cliente.get("/baixar", headers={"User-Agent": UA_WINDOWS_CHROME})
    assert f'href="{PLAY}"' in r.text


def test_as_origens_sao_as_que_o_app_e_a_pagina_escrevem():
    """Trava a lista: o app (cards A e B) e a página do card do dia escrevem
    estes nomes. Mudar aqui exige mudar lá, senão a origem some dos relatórios."""
    assert modulo_baixar.ORIGENS == {"story", "app-desafio", "app-partida"}


def test_provedor_da_apple_e_o_da_conta():
    """O ``pt`` é o da conta da Arena Sagaz (o link de campanha de 12/11/2026).

    Cadeado contra um número trocado ou apagado sem querer: com ``None`` o
    iPhone continua chegando à loja, mas as origens somem dos relatórios da
    Apple sem erro nenhum.
    """
    assert modulo_baixar.APPLE_PROVEDOR == "129098190"
    assert modulo_baixar.com_origem(modulo_baixar.LOJA_APPLE, "app-partida") == (
        "https://apps.apple.com/app/id6790198320?pt=129098190&ct=app-partida&mt=8"
    )

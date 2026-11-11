"""Site de apresentação do Arena Sagaz (landing page pública).

POR QUE O SITE EXISTE — e não é marketing opcional:

1. **A Apple exige uma "Support URL"**, e ela tem de ser uma *página* (o Google
   aceita um e-mail; a Apple, não). Sai da âncora ``/#suporte``.
2. **O ``app-ads.txt``**: o AdMob busca esse arquivo na **raiz do domínio** que
   declaramos como "site do desenvolvedor" na ficha das lojas. Sem ele, os
   compradores não confirmam que o nosso inventário é legítimo e a receita cai.
3. A vitrine em si (o "marketing URL" das duas lojas).

POR QUE MORA AQUI, no mesmo serviço da API (decisão de 2026-07-13):
as URLs legais que as lojas exigem (``/legal/...``) **já dependem do Railway**.
Hospedar a landing em outro lugar (GitHub Pages foi cogitado) não removeria essa
dependência — só criaria um segundo lugar para manter, um segundo domínio e um
segundo deploy, sem ganho nenhum. E o FastAPI já renderiza HTML: as páginas
legais são exatamente isso.

⚠️ POR QUE **NÃO** USAMOS ``StaticFiles`` MONTADO EM ``/``:
um ``app.mount("/", StaticFiles(...))`` casaria **qualquer** caminho que nenhuma
rota anterior pegasse — inclusive um ``/v1/rota-que-nao-existe``. O 404 da API
deixaria de ser o JSON do FastAPI e viraria o 404 do servidor de arquivos,
mudando o contrato para os apps em campo. Rotas explícitas resolvem — sem
catch-all e sem risco para a API.

AS IMAGENS (``/img/...``), decisão de 2026-08-04: até a publicação, o site era um
HTML **único e autocontido**. Com as capturas de tela entrando na vitrine isso
deixou de compensar: são 9 arquivos (3 telas × 3 idiomas) e 6 selos de loja, e
embuti-los em base64 inflaria o HTML de 210 KB para ~500 KB — que **todo** visitante
baixaria inteiro, inclusive os idiomas que ele não vê. Como arquivos, o navegador
busca só os do idioma ativo e ainda os guarda em cache por um dia.

A rota de imagens **não é um catch-all**: o dicionário ``_IMAGENS`` é montado no
import a partir do que existe em ``site/img/``, e serve **apenas** o que está nele.
Um nome fora da lista leva 404 — não há caminho para ``..`` nem para fora da pasta.

O VÍDEO (``/video/...``), decisão de 2026-11-11: a prévia do app (a mesma da
App Store, ~4,5 MB por idioma) toca dentro da moldura de celular do hero. Ele
segue a mesma regra das imagens (lista de permissão montada no import, nada de
catch-all), com duas diferenças, ambas de propósito:

- **é servido do DISCO, não da memória.** São ~13 MB nos três idiomas; segurar
  isso na RAM de cada processo da API para um botão que pouca gente aperta não
  compensa. O dicionário guarda só o *caminho*.
- **responde a pedidos de faixa de bytes** (``Range: bytes=...``, status 206).
  O Safari do iPhone **se recusa a tocar** um vídeo cujo servidor não aceita
  faixa, e todos os navegadores usam faixa para pular para o meio do vídeo. O
  ``FileResponse`` do Starlette já faz isso; um ``Response`` com os bytes, não.

O ``/baixar`` (e os apelidos ``/download`` e ``/descargar``), decisão de
2026-11-11: é **a porta de entrada das redes sociais**. A bio do Instagram, o
sticker de link dos Stories, o Threads e a legenda do Status do WhatsApp aceitam
UM link, e quem toca nele pode ter iPhone ou Android. O link olha o User-Agent e
manda cada celular para a sua loja (a lógica pura mora em ``api/site/baixar.py``):

- **iPhone/iPad/iPod → App Store; Android → Google Play**, com **302**, nunca
  301. O 301 é "mudou para sempre": navegadores e servidores no meio do caminho
  o guardam, e o destino ficaria congelado mesmo que um dia mudemos a loja, o
  endereço ou a marcação de campanha. O 302 é perguntado de novo a cada toque.
- **``Cache-Control: no-store`` e ``Vary: User-Agent, Accept-Language``** em
  toda resposta. A MESMA URL dá respostas diferentes conforme o aparelho; sem
  isso, um cache no caminho (o da operadora, um CDN) poderia guardar a resposta
  de um iPhone e entregá-la a um Android, mandando-o para a App Store.
- **Qualquer outro caso** (computador, robô de prévia de link, sem User-Agent)
  → uma página pequena com os dois selos, no idioma do ``Accept-Language``.
- **O iPad moderno se diz Mac** (desde o iPadOS 13, "Macintosh" no
  User-Agent) e o servidor não consegue separá-lo de um Mac. Ele cai na página
  de escolha, e um script curto nela (tela de toque + "Macintosh") leva o
  próprio navegador para a App Store.
- **``HEAD`` também é atendido**: alguns apps conferem o link antes de abri-lo,
  e o ``@router.get`` do FastAPI não responde ``HEAD`` sozinho.

A página de escolha é montada **uma vez por idioma, no import**, a partir do
modelo ``site/baixar.html``, como o resto do site: nada de disco a cada clique.

As fontes continuam **embutidas em base64** no HTML, de propósito: são o que a
página precisa no primeiro quadro, e buscá-las de fora deixaria o texto invisível
enquanto carregam. Há teste que falha se alguém trocar isso por um CDN.

O HTML é lido **uma vez, no import** (é imutável entre deploys) e servido da
memória: nada de tocar o disco a cada visita.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
)

from api.site import baixar

router = APIRouter()

# Pasta do site: <raiz-do-backend>/site.
# Este arquivo é api/site/rotas.py → parents[2] é a raiz do backend.
_DIR_SITE = Path(__file__).resolve().parents[2] / "site"


def _ler(nome: str) -> str:
    """Lê um arquivo do site. Devolve string vazia se ele não existir — assim um
    deploy sem a pasta `site/` **não derruba a API** (a landing some, a API vive).
    """
    caminho = _DIR_SITE / nome
    if not caminho.is_file():
        return ""
    return caminho.read_text(encoding="utf-8")


# Lidos no import: o conteúdo não muda enquanto o processo vive.
_INDEX_HTML = _ler("index.html")
_APP_ADS_TXT = _ler("app-ads.txt")


def _carregar_imagens() -> dict[str, tuple[bytes, str]]:
    """Lê `site/img/` para a memória: nome do arquivo → (bytes, content-type).

    Este dicionário **é** a lista de permissão da rota `/img/`: só se serve o que
    está aqui. Por isso a rota não precisa validar caminho — não existe caminho,
    existe uma chave. São ~1 MB no total desde o site dos quatro jogos (33 telas
    + 6 selos, novembro/2026); carregar uma vez custa menos que abrir o disco a
    cada visita, e a pasta não muda enquanto o processo vive.
    """
    tipos = {".webp": "image/webp", ".svg": "image/svg+xml", ".png": "image/png"}
    pasta = _DIR_SITE / "img"
    if not pasta.is_dir():
        return {}
    return {
        arquivo.name: (arquivo.read_bytes(), tipos[arquivo.suffix])
        for arquivo in sorted(pasta.iterdir())
        if arquivo.is_file() and arquivo.suffix in tipos
    }


_IMAGENS = _carregar_imagens()


def _listar_videos() -> dict[str, Path]:
    """Mapeia `site/video/`: nome do arquivo → caminho no disco.

    Como `_IMAGENS`, este dicionário é a **lista de permissão** da rota
    `/video/`: o nome que chega na URL é só uma chave de consulta, nunca vira
    caminho. A diferença é que aqui guardamos o `Path`, não os bytes: o vídeo é
    lido do disco a cada pedido (ver a docstring do módulo).
    """
    pasta = _DIR_SITE / "video"
    if not pasta.is_dir():
        return {}
    return {
        arquivo.name: arquivo
        for arquivo in sorted(pasta.iterdir())
        if arquivo.is_file() and arquivo.suffix == ".mp4"
    }


_VIDEOS = _listar_videos()


def _montar_paginas_baixar() -> dict[str, str]:
    """Monta a página de escolha do `/baixar` nos três idiomas, uma vez só.

    Sem o modelo `site/baixar.html` (um deploy sem a pasta), cai numa página
    mínima com os dois links: o `/baixar` está na bio do Instagram e nunca pode
    responder vazio.
    """
    modelo = _ler("baixar.html") or (
        '<!DOCTYPE html><meta charset="UTF-8"><title>{{titulo}}</title>'
        '<p><a href="{{loja_apple}}">App Store</a> · <a href="{{loja_play}}">Google Play</a></p>'
    )
    return {idioma: baixar.montar_pagina(modelo, idioma) for idioma in baixar.IDIOMAS}


_PAGINAS_BAIXAR = _montar_paginas_baixar()

# Cabeçalhos de TODA resposta do /baixar (o 302 e a página). Ver a docstring do
# módulo: `no-store` proíbe qualquer cache de guardar a resposta, e o `Vary` avisa
# que ela depende do aparelho e do idioma de quem pediu.
_CABECALHOS_BAIXAR = {
    "Cache-Control": "no-store",
    "Vary": "User-Agent, Accept-Language",
}


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing() -> HTMLResponse:
    """A landing page. `include_in_schema=False` mantém o OpenAPI só com a API."""
    if not _INDEX_HTML:
        # Sem o arquivo, é melhor um 404 honesto do que uma página em branco.
        return HTMLResponse("<h1>Arena Sagaz</h1>", status_code=404)
    return HTMLResponse(
        content=_INDEX_HTML,
        # Cache curto: queremos poder corrigir um texto sem esperar um dia.
        headers={"Cache-Control": "public, max-age=600"},
    )


@router.get("/img/{nome}", include_in_schema=False)
async def imagem(nome: str) -> Response:
    """Serve uma imagem da vitrine (capturas de tela e selos das lojas).

    Só entrega o que foi carregado de `site/img/` no import — qualquer outro nome
    é 404. Cache de **um dia**: as capturas só mudam quando o app muda de cara, e
    o nome do arquivo carrega o idioma, então trocar de idioma nunca serve a
    imagem errada do cache.
    """
    imagem = _IMAGENS.get(nome)
    if imagem is None:
        return PlainTextResponse("", status_code=404)
    conteudo, tipo = imagem
    return Response(
        content=conteudo,
        media_type=tipo,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/video/{nome}", include_in_schema=False)
async def video(nome: str) -> Response:
    """Serve a prévia em vídeo do app (uma por idioma).

    Só entrega o que `_listar_videos` achou no import; qualquer outro nome é 404.
    O `FileResponse` lê o arquivo em pedaços (não carrega os ~4,5 MB de uma vez)
    e atende o cabeçalho `Range` com `206 Partial Content`, que é o que o Safari
    do iPhone exige para tocar vídeo. Cache de um dia, como as imagens: o nome
    do arquivo carrega o idioma.
    """
    caminho = _VIDEOS.get(nome)
    if caminho is None:
        return PlainTextResponse("", status_code=404)
    return FileResponse(
        caminho,
        media_type="video/mp4",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# Um decorador por endereço: cada `api_route` registra a MESMA função num caminho,
# e devolve a função intacta para o decorador de cima. São três caminhos
# explícitos (nada de padrão "/{qualquer}"), então o 404 em JSON da API continua
# valendo para todo o resto.
@router.api_route("/baixar", methods=["GET", "HEAD"], include_in_schema=False)
@router.api_route("/download", methods=["GET", "HEAD"], include_in_schema=False)
@router.api_route("/descargar", methods=["GET", "HEAD"], include_in_schema=False)
async def baixar_app(request: Request) -> Response:
    """Leva o celular para a loja dele; o resto vê a página com os dois selos.

    Está isento do rate limit (`api/nucleo/rate_limit.py`): um story que viraliza
    traz muita gente de uma vez, e às vezes atrás do MESMO IP de operadora.
    """
    loja = baixar.loja_para(request.headers.get("user-agent"))
    if loja is not None:
        # 302 = "por enquanto está lá". Ver na docstring do módulo por que não 301.
        return RedirectResponse(loja, status_code=302, headers=_CABECALHOS_BAIXAR)
    idioma = baixar.escolher_idioma(request.headers.get("accept-language"))
    return HTMLResponse(_PAGINAS_BAIXAR[idioma], headers=_CABECALHOS_BAIXAR)


@router.get("/app-ads.txt", response_class=PlainTextResponse, include_in_schema=False)
async def app_ads() -> PlainTextResponse:
    """O ``app-ads.txt`` do AdMob, servido **na raiz do domínio** (é lá que o
    rastreador procura — não vale colocar em subpasta).

    ⚠️ Este caminho está na lista de ISENTOS do rate limit
    (``api/nucleo/rate_limit.py``). Sem isso, o rastreador do AdMob pode levar
    ``429`` e a validação dos vendedores falha **em silêncio** — quebrando
    justamente o arquivo que motiva a existência do site.
    """
    if not _APP_ADS_TXT:
        return PlainTextResponse("", status_code=404)
    return PlainTextResponse(
        content=_APP_ADS_TXT,
        headers={"Cache-Control": "public, max-age=3600"},
    )

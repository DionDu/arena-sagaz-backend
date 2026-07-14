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
mudando o contrato para os apps em campo. Como o site é **um único HTML
autocontido** (as fontes vêm embutidas em base64, sem CDN), duas rotas explícitas
resolvem — sem catch-all e sem risco para a API.

O HTML é lido **uma vez, no import** (é imutável entre deploys) e servido da
memória: nada de tocar o disco a cada visita.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

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

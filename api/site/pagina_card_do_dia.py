"""A página do card do dia, servida em `/card-do-dia/` (build Flutter web).

PRD dos cards de compartilhamento (raiz, `docs/PRD_Cards_de_Compartilhamento.md`),
§4 e §9: a página do dono que desenha os stories do dia. O código mora em
`card-do-dia/` (no repositório raiz, ao lado do `painel/`), e o BUILD vem para cá,
em `site/card-do-dia/`, pelo script `card-do-dia/publicar.ps1`.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE UM `StaticFiles` MONTADO, SE O SITE SÓ TEM ROTAS EXPLÍCITAS
═══════════════════════════════════════════════════════════════════════════

O site não tem *catch-all* (`api/site/rotas.py`): um `StaticFiles` montado em
"/" engoliria qualquer caminho, e o 404 em JSON da API, que os apps em campo
entendem, viraria o 404 do servidor de arquivos. Aqui o mount é sob um PREFIXO
próprio, `/card-do-dia`: só o que começa com ele chega aos arquivos, e o resto
continua com o 404 da API. Um build Flutter web tem dezenas de arquivos (o
JavaScript, o manifesto, as fontes de ícone), e escrever uma rota para cada um
seria frágil a cada versão do Flutter.

- ⚠️ É `/card-do-dia/`, e não `/v1/card-do-dia`: este é o endereço da PÁGINA; o
  da leitura dela é `/v1/card-do-dia` (`api/card_do_dia/rotas.py`).
- `X-Robots-Tag: noindex` em toda resposta: é ferramenta do dono, e não vitrine.
- `Cache-Control: no-cache`: o navegador confere a cada abertura se o arquivo
  mudou (e só baixa de novo se mudou). Sem isso, um build novo demoraria a
  chegar ao celular do dono.
- Sem a pasta (um deploy sem o build), a página simplesmente não existe (404 em
  JSON), e nada mais quebra.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

#: `<raiz-do-backend>/site/card-do-dia`. Este arquivo é `api/site/...`, então
#: `parents[2]` é a raiz do backend.
PASTA = Path(__file__).resolve().parents[2] / "site" / "card-do-dia"

#: O prefixo da página (e o `--base-href` do build Flutter).
PREFIXO = "/card-do-dia"


class _ArquivosDaPagina(StaticFiles):
    """O `StaticFiles` do Starlette com os dois cabeçalhos da página."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        resposta = await super().get_response(path, scope)
        resposta.headers["X-Robots-Tag"] = "noindex"
        resposta.headers["Cache-Control"] = "no-cache"
        return resposta


def montar(app: FastAPI) -> bool:
    """Monta a página em `/card-do-dia`, se o build estiver na pasta.

    `html=True` faz `/card-do-dia/` entregar o `index.html`. Devolve se montou.
    """
    if not (PASTA / "index.html").is_file():
        return False
    app.mount(PREFIXO, _ArquivosDaPagina(directory=PASTA, html=True), name="card-do-dia")
    return True

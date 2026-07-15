"""Hospedagem dos documentos legais — tarefa G3.

Serve **Termos de Uso**, **Política de Privacidade** e **Exclusão de Conta** como
páginas HTML públicas, a partir dos arquivos versionados em
`legal/<versao>/<idioma>/<documento>.md`.

Duas formas de acesso (decisão registrada no `tasks.md`/`guia`):
- **mais recente** — `GET /legal/<idioma>/<documento>` (a versão vigente; pode
  mudar quando publicarmos uma nova). Cache curto.
- **versão fixa e imutável** — `GET /legal/<versao>/<idioma>/<documento>` (ex.:
  `/legal/1.0/pt/privacidade`). Nunca muda → cache longo, `immutable`.

As URLs públicas exigidas pelas lojas (privacidade e exclusão de conta) saem daqui
(ex.: `https://api-dev.arenasagaz.santiagodata.com/legal/pt/privacidade`).

Tudo é leitura de arquivos estáticos com **whitelist** de idioma/documento — não há
entrada de usuário chegando ao caminho do arquivo (sem path traversal).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from api.legal.markdown_html import renderizar_markdown
from api.nucleo.excecoes import ErroNaoEncontrado

router = APIRouter()

# Versão vigente dos documentos (espelha `versaoLegal` no app).
VERSAO_LEGAL = "1.0"

# Whitelists — só estes valores são aceitos nas rotas (segurança + clareza).
IDIOMAS = ("pt", "en", "es")
DOCUMENTOS = ("termos", "privacidade", "exclusao-conta")

# Pasta raiz dos documentos: <raiz-do-backend>/legal.
# Este arquivo é api/legal/rotas.py → parents[2] é a raiz do backend.
_DIR_LEGAL = Path(__file__).resolve().parents[2] / "legal"

# Títulos amigáveis por documento e idioma (usados no <title> e cabeçalho).
_TITULOS = {
    "pt": {
        "termos": "Termos de Uso",
        "privacidade": "Política de Privacidade",
        "exclusao-conta": "Exclusão de Conta",
    },
    "en": {
        "termos": "Terms of Use",
        "privacidade": "Privacy Policy",
        "exclusao-conta": "Account Deletion",
    },
    "es": {
        "termos": "Términos de Uso",
        "privacidade": "Política de Privacidad",
        "exclusao-conta": "Eliminación de Cuenta",
    },
}

# CSS mínimo no tema "papel & madeira" do app, com suporte a tema escuro do SO.
_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1rem 4rem;
  font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  line-height: 1.6; color: #2B2218; background: #F2EDE4;
}
main { max-width: 720px; margin: 0 auto;
  background: #FBF8F1; border: 1px solid rgba(94,61,34,.22);
  border-radius: 16px; padding: 1.5rem 1.75rem; }
h1 { font-size: 1.7rem; color: #5E3D22; margin-top: 0; }
h2 { font-size: 1.25rem; color: #8A5A33; margin-top: 1.8rem; }
h3 { font-size: 1.05rem; color: #8A5A33; }
a { color: #A87A24; }
blockquote { margin: 1rem 0; padding: .25rem 1rem;
  border-left: 4px solid #D9A441; background: #E9E1D2; border-radius: 8px; }
code { background: #E9E1D2; padding: .1rem .3rem; border-radius: 4px; }
nav.idiomas { max-width: 720px; margin: 0 auto .75rem; text-align: right;
  font-size: .9rem; }
footer { max-width: 720px; margin: 1.5rem auto 0; text-align: center;
  font-size: .8rem; color: #6E6052; }
@media (prefers-color-scheme: dark) {
  body { color: #F4EFE3; background: #2E4034; }
  main { background: #3A5142; border-color: rgba(244,239,227,.18); }
  h1 { color: #F4EFE3; } h2, h3 { color: #B9C4B4; }
  blockquote { background: #4A6553; }
  code { background: #4A6553; }
}
"""


def _pagina(*, titulo: str, idioma: str, corpo_html: str, idiomas_base: str) -> str:
    """Monta a página HTML completa em torno do [corpo_html] renderizado.

    [idiomas_base] é o prefixo de URL para o seletor de idioma (ex.:
    "/legal" para a versão mais recente, "/legal/1.0" para a fixa).
    """
    # Links de troca de idioma (mantêm o mesmo documento).
    troca = " · ".join(
        f'<a href="{idiomas_base}/{lng}/{{doc}}">{lng.upper()}</a>'
        for lng in IDIOMAS
    )
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{idioma}">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{titulo} — Arena Sagaz</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        f'<nav class="idiomas">{troca}</nav>\n'
        f"<main>\n{corpo_html}\n</main>\n"
        "<footer>Arena Sagaz · Santiago Data</footer>\n"
        "</body>\n</html>\n"
    )


def _carregar(versao: str, idioma: str, documento: str) -> Optional[str]:
    """Lê o arquivo Markdown do documento; devolve `None` se não existir."""
    caminho = _DIR_LEGAL / versao / idioma / f"{documento}.md"
    # `resolve()` + verificação de prefixo evita qualquer escape do diretório.
    try:
        real = caminho.resolve()
        real.relative_to(_DIR_LEGAL.resolve())
    except (ValueError, OSError):
        return None
    if not real.is_file():
        return None
    return real.read_text(encoding="utf-8")


def _resposta_documento(
    *, versao: str, idioma: str, documento: str, imutavel: bool, idiomas_base: str
) -> HTMLResponse:
    """Renderiza e devolve a página de um documento (ou 404 amigável)."""
    if idioma not in IDIOMAS or documento not in DOCUMENTOS:
        return _resposta_404()

    texto = _carregar(versao, idioma, documento)
    if texto is None:
        return _resposta_404()

    titulo = _TITULOS[idioma][documento]
    # No seletor de idioma, o {doc} é preenchido com o documento atual.
    base = _pagina(
        titulo=titulo,
        idioma=idioma,
        corpo_html=renderizar_markdown(texto),
        idiomas_base=idiomas_base,
    ).replace("{doc}", documento)

    # Cache: versão fixa é imutável (1 ano); a "mais recente" tem cache curto.
    cache = (
        "public, max-age=31536000, immutable"
        if imutavel
        else "public, max-age=3600"
    )
    return HTMLResponse(content=base, headers={"Cache-Control": cache})


def _resposta_404() -> HTMLResponse:
    """Página 404 simples (em vez do JSON de erro da API) para conteúdo web."""
    corpo = _pagina(
        titulo="Não encontrado",
        idioma="pt",
        corpo_html="<h1>Documento não encontrado</h1>"
        '<p>Confira o endereço. Documentos disponíveis: '
        "<code>termos</code>, <code>privacidade</code>, "
        "<code>exclusao-conta</code>.</p>",
        idiomas_base="/legal",
    ).replace("{doc}", "privacidade")
    return HTMLResponse(content=corpo, status_code=404)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def indice() -> HTMLResponse:
    """Índice simples com links para os documentos (em português, com troca de
    idioma em cada página)."""
    itens = "".join(
        f'<li><a href="/legal/pt/{doc}">{_TITULOS["pt"][doc]}</a></li>'
        for doc in DOCUMENTOS
    )
    corpo = (
        "<h1>Documentos legais — Arena Sagaz</h1>"
        f"<p>Versão vigente: <strong>{VERSAO_LEGAL}</strong>.</p>"
        f"<ul>{itens}</ul>"
    )
    pagina = _pagina(
        titulo="Documentos legais",
        idioma="pt",
        corpo_html=corpo,
        idiomas_base="/legal",
    ).replace("{doc}", "privacidade")
    return HTMLResponse(content=pagina)


@router.get("/{idioma}/{documento}", response_class=HTMLResponse)
async def documento_recente(idioma: str, documento: str) -> HTMLResponse:
    """Versão **mais recente** (vigente) de um documento."""
    return _resposta_documento(
        versao=VERSAO_LEGAL,
        idioma=idioma,
        documento=documento,
        imutavel=False,
        idiomas_base="/legal",
    )


@router.get("/{versao}/{idioma}/{documento}", response_class=HTMLResponse)
async def documento_versionado(
    versao: str, idioma: str, documento: str
) -> HTMLResponse:
    """Versão **fixa e imutável** de um documento (ex.: `/legal/1.0/pt/termos`)."""
    return _resposta_documento(
        versao=versao,
        idioma=idioma,
        documento=documento,
        imutavel=True,
        idiomas_base=f"/legal/{versao}",
    )


# ── API JSON para o APP (montada em /v1/legal) ───────────────────────────────
#
# As rotas acima devolvem **HTML** — elas existem para o navegador (são as URLs
# que as lojas exigem). O app não quer HTML: ele quer o **markdown cru**, para
# renderizar com o próprio tema, e quer saber **qual versão** esse texto é.
#
# Por que o app precisa disto (o problema que resolve): o texto legal exibido no
# app era um **asset embutido**, que congela na build instalada. Publicar termos
# novos no servidor não mudava nada no aparelho de ninguém — e só uma nova versão
# na loja corrigiria. Com esta rota, o app baixa o texto vigente e o guarda em
# cache; o asset vira apenas o **fallback offline**.
router_api = APIRouter()


@router_api.get("/{idioma}/{documento}")
async def conteudo_documento(idioma: str, documento: str) -> dict[str, str]:
    """Markdown **cru** do documento vigente, com a versão a que ele corresponde.

    Pública e sem token: são os mesmos textos que qualquer um lê no navegador.

    Devolve os campos no padrão de nomes do projeto (`co_` = código, `tx_` =
    texto). O app compara `co_versao` com a versão que a pessoa aceitou para
    decidir se pede um novo aceite.
    """
    if idioma not in IDIOMAS or documento not in DOCUMENTOS:
        raise ErroNaoEncontrado("Documento não encontrado.", "documento_inexistente")

    texto = _carregar(VERSAO_LEGAL, idioma, documento)
    if texto is None:
        raise ErroNaoEncontrado("Documento não encontrado.", "documento_inexistente")

    return {
        "co_documento": documento,
        "co_idioma": idioma,
        "co_versao": VERSAO_LEGAL,
        "tx_conteudo": texto,
    }

"""Hospedagem dos documentos legais — tarefa G3.

Serve **Termos de Uso**, **Política de Privacidade** e **Exclusão de Conta** como
páginas HTML públicas, a partir dos arquivos versionados em
`legal/<versao>/<idioma>/<documento>.md`.

Duas formas de acesso (decisão registrada no `tasks.md`/`guia`):
- **mais recente** — `GET /legal/<idioma>/<documento>` (a versão vigente; pode
  mudar quando publicarmos uma nova). Sem cache (`no-cache`), para que ajustes
  entrem no ar na hora para usuários e robôs de revisão das lojas.
- **versão fixa e imutável** — `GET /legal/<versao>/<idioma>/<documento>` (ex.:
  `/legal/1.0/pt/privacidade`). Nunca muda → cache longo, `immutable`.

As URLs públicas exigidas pelas lojas (privacidade e exclusão de conta) saem daqui
(ex.: `https://api-dev.arenasagaz.santiagodata.com/legal/pt/privacidade`).

Tudo é leitura de arquivos estáticos com **whitelist** de idioma/documento — não há
entrada de usuário chegando ao caminho do arquivo (sem path traversal).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from api.legal.markdown_html import renderizar_markdown
from api.nucleo.excecoes import ErroNaoEncontrado

router = APIRouter()

# Whitelists — só estes valores são aceitos nas rotas (segurança + clareza).
IDIOMAS = ("pt", "en", "es")
DOCUMENTOS = ("termos", "privacidade", "exclusao-conta")

# Pasta raiz dos documentos: <raiz-do-backend>/legal.
# Este arquivo é api/legal/rotas.py → parents[2] é a raiz do backend.
_DIR_LEGAL = Path(__file__).resolve().parents[2] / "legal"

# Uma pasta de versão é só dígitos e pontos: "1.0", "1.1", "2.0", "1.10". Qualquer
# outra coisa em legal/ (um README, um "backup", um "1.1-rascunho") é ignorada.
_PADRAO_VERSAO = re.compile(r"^\d+(?:\.\d+)*$")


def _chave_ordem_versao(versao: str) -> tuple[int, ...]:
    """Transforma '1.10' em (1, 10) para ordenar por NÚMERO, não por texto — senão
    '1.10' viria antes de '1.9' na ordem alfabética, que é o erro clássico."""
    return tuple(int(parte) for parte in versao.split("."))


def versoes_publicadas(dir_legal: Path = _DIR_LEGAL) -> list[str]:
    """As versões que existem em legal/ (ex.: ['1.0', '1.1']), da mais antiga para
    a mais nova. É a lista de subpastas cujo nome é um número de versão."""
    if not dir_legal.is_dir():
        return []
    nomes = [
        p.name
        for p in dir_legal.iterdir()
        if p.is_dir() and _PADRAO_VERSAO.match(p.name)
    ]
    return sorted(nomes, key=_chave_ordem_versao)


def detectar_versao_vigente(dir_legal: Path = _DIR_LEGAL) -> str:
    """A MAIOR versão presente em legal/ — a "versão vigente" que o site e o app
    servem.

    É o coração da automação pedida em 14/07: publicar uma versão nova passou a ser
    só **criar a pasta** (copiar `legal/1.0/` para `legal/1.1/`, editar e subir).
    Ninguém precisa lembrar de mexer em código — o número vem da pasta.

    Fallback "1.0" se, por algum acidente, não houver nenhuma pasta: um valor
    seguro é melhor do que derrubar o boot da API por causa de uma pasta faltando.
    """
    versoes = versoes_publicadas(dir_legal)
    return versoes[-1] if versoes else "1.0"


# Versão vigente dos documentos. Calculada UMA VEZ, no import: as pastas de legal/
# estão dentro da imagem Docker e só mudam num novo deploy — que reinicia o
# processo e recalcula isto. Não há por que varrer o diretório a cada requisição.
VERSAO_LEGAL = detectar_versao_vigente()

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

# Quem é o app e quem o publica, como as LOJAS o mostram. Entra no `<title>`, no
# `<h1>` e no bloco de abertura de toda página legal, acima do texto do documento.
#
# ⚠️ POR QUE ISTO EXISTE (26/11/2026): a Google Play recusou a 1.6.0 duas vezes
# (decisão automática) porque o link de exclusão de conta do formulário de
# segurança de dados (`/legal/en/exclusao-conta`) "não faz referência à entidade
# mencionada na ficha" - o nome do app ou o do desenvolvedor.
#
# Por que a 1ª tentativa (só um `<p class="app">` com o título em inglês) não
# bastou:
# 1. O `<title>` ("Account Deletion - Sharp Arena") e o `<h1>` ("Account Deletion
#    - Arena Sagaz") continuavam citando apenas as marcas, que saíram dos títulos
#    das fichas da 1.6.0 nos três idiomas. Classificadores automáticos dão peso
#    principal ao `<title>` e ao `<h1>`.
# 2. O formulário de segurança de dados tem UM link global (`/legal/en/...`), mas
#    o próprio e-mail de recusa avaliou o app pelo título em português
#    ("Xadrez, Damas e Jogo da Velha"), e na loja pública ainda estavam no ar os
#    títulos da 1.4.0 ("Sharp Arena: Checkers & Dots" / "Arena Sagaz: Damas e
#    Velha") por causa da publicação gerenciada. A página em inglês não citava
#    nenhum desses.
# 3. A rota vigente respondia `Cache-Control: public, max-age=3600` (1 h de cache
#    público autorizado ao crawler do Google) e não atendia `HEAD` (respondia 405).
#
# Por isso cada página legal traz:
# - no `<title>` e no único `<h1>`: o nome do documento, o título da 1.6.0 no
#   idioma da página, as duas marcas (Sharp Arena e Arena Sagaz) e o
#   desenvolvedor (Fernando da Silva);
# - logo abaixo do `<h1>`, em `<p class="app">`: os títulos da 1.6.0 nos TRÊS
#   idiomas, os títulos anteriores da 1.4.0 ainda publicados na transição, as
#   duas marcas, o desenvolvedor Fernando da Silva (Santiago Data) e o pacote
#   `com.santiagodata.arenasagaz`.
#
# ⚠️ POR QUE AQUI, E NÃO NO `.md` do documento: o texto em `legal/<versao>/` é
# versionado e o app compara a versão (`co_versao`) para decidir se pede um novo
# aceite dos termos. Mudar o texto pediria uma `legal/1.1` e faria TODOS os
# jogadores aceitarem de novo, por uma linha que não muda nenhum direito. Tudo
# aqui é moldura HTML da página web: não entra no markdown que `/v1/legal`
# entrega ao app, e por isso não mexe na versão.
#
# ⚠️ Mudou o título do app numa loja (as fichas da versão, em
# `arena-sagaz-frontend/specs/<spec>/textos-fichas-lojas.md`) ou o nome do
# desenvolvedor? Atualize `_TITULO_LOJA` e `_IDENTIFICACAO` abaixo, junto com
# `tests/unitarios/test_legal.py`.
_TITULO_LOJA = {
    "pt": "Xadrez, Damas e Jogo da Velha",
    "en": "Chess, Checkers &amp; Tic Tac Toe",
    "es": "Ajedrez, Damas y Tres en Raya",
}

# Par de marcas na ordem natural de cada idioma (usado no `<title>` e no `<h1>`).
_MARCAS_DUPLAS = {
    "pt": "Arena Sagaz / Sharp Arena",
    "en": "Sharp Arena / Arena Sagaz",
    "es": "Arena Sagaz / Sharp Arena",
}

_IDENTIFICACAO = {
    "pt": (
        "Este documento vale para o aplicativo <strong>Xadrez, Damas e Jogo da Velha</strong> "
        "(em inglês: <strong>Chess, Checkers &amp; Tic Tac Toe</strong>; em espanhol: "
        "<strong>Ajedrez, Damas y Tres en Raya</strong>; títulos anteriores nas lojas: "
        "<strong>Arena Sagaz: Damas e Velha</strong>, <strong>Sharp Arena: Checkers &amp; Dots</strong> "
        "e <strong>Arena Sagaz: Damas y Raya</strong>), da marca <strong>Arena Sagaz</strong> / "
        "<strong>Sharp Arena</strong>, publicado pelo desenvolvedor <strong>Fernando da Silva</strong> "
        "(<strong>Santiago Data</strong>) na Google Play (<code>com.santiagodata.arenasagaz</code>) "
        "e na App Store."
    ),
    "en": (
        "This document applies to the app <strong>Chess, Checkers &amp; Tic Tac Toe</strong> "
        "(in Portuguese: <strong>Xadrez, Damas e Jogo da Velha</strong>; in Spanish: "
        "<strong>Ajedrez, Damas y Tres en Raya</strong>; previous store titles: "
        "<strong>Sharp Arena: Checkers &amp; Dots</strong>, <strong>Arena Sagaz: Damas e Velha</strong>, "
        "and <strong>Arena Sagaz: Damas y Raya</strong>), from the <strong>Sharp Arena</strong> / "
        "<strong>Arena Sagaz</strong> brand, published by developer <strong>Fernando da Silva</strong> "
        "(<strong>Santiago Data</strong>) on Google Play (<code>com.santiagodata.arenasagaz</code>) "
        "and the App Store."
    ),
    "es": (
        "Este documento se aplica a la aplicación <strong>Ajedrez, Damas y Tres en Raya</strong> "
        "(en portugués: <strong>Xadrez, Damas e Jogo da Velha</strong>; en inglés: "
        "<strong>Chess, Checkers &amp; Tic Tac Toe</strong>; títulos anteriores en las tiendas: "
        "<strong>Arena Sagaz: Damas y Raya</strong>, <strong>Arena Sagaz: Damas e Velha</strong> "
        "y <strong>Sharp Arena: Checkers &amp; Dots</strong>), de la marca <strong>Arena Sagaz</strong> / "
        "<strong>Sharp Arena</strong>, publicada por el desarrollador <strong>Fernando da Silva</strong> "
        "(<strong>Santiago Data</strong>) en Google Play (<code>com.santiagodata.arenasagaz</code>) "
        "y en App Store."
    ),
}

# A marca como cada idioma a conhece: em inglês o app se chama Sharp Arena.
_MARCA = {"pt": "Arena Sagaz", "en": "Sharp Arena", "es": "Arena Sagaz"}

# Casa o primeiro `<h1>...</h1>` gerado pelo `renderizar_markdown` a partir da 1ª
# linha `# ...` dos arquivos `.md` (que dizem só "Arena Sagaz" ou "Sharp Arena").
# `re.DOTALL` garante o casamento mesmo se um título tiver quebra de linha, e o
# `.*?` (não-guloso) para no primeiro `</h1>` sem engolir o resto do documento.
_PRIMEIRO_H1 = re.compile(r"^\s*<h1>.*?</h1>\s*", re.DOTALL)

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
/* O bloco "este documento vale para o app ..." (ver `_IDENTIFICACAO`). */
p.app { margin: 0 0 1.25rem; padding: .6rem .9rem; font-size: .92rem;
  background: #E9E1D2; border-radius: 10px; }
footer { max-width: 720px; margin: 1.5rem auto 0; text-align: center;
  font-size: .8rem; color: #6E6052; }
@media (prefers-color-scheme: dark) {
  body { color: #F4EFE3; background: #2E4034; }
  main { background: #3A5142; border-color: rgba(244,239,227,.18); }
  h1 { color: #F4EFE3; } h2, h3 { color: #B9C4B4; }
  blockquote { background: #4A6553; }
  code { background: #4A6553; }
  p.app { background: #4A6553; }
}
"""


def _pagina(
    *,
    titulo: str,
    idioma: str,
    corpo_html: str,
    idiomas_base: str,
    substituir_h1: bool = False,
) -> str:
    """Monta a página HTML completa em torno do [corpo_html] renderizado.

    [idiomas_base] é o prefixo de URL para o seletor de idioma (ex.:
    "/legal" para a versão mais recente, "/legal/1.0" para a fixa).

    Quando [substituir_h1] é `True` (nas páginas dos documentos legais), o
    primeiro `<h1>` vindo do Markdown (que traz só a marca antiga) é trocado
    por um único `<h1>` completo com o título da loja, as duas marcas e o
    desenvolvedor — evitando dois `<h1>` na mesma página e garantindo que os
    elementos de maior peso semântico (`<title>` e `<h1>`) citem a entidade da
    ficha.
    """
    # Links de troca de idioma (mantêm o mesmo documento).
    troca = " · ".join(
        f'<a href="{idiomas_base}/{lng}/{{doc}}">{lng.upper()}</a>'
        for lng in IDIOMAS
    )
    # `.get(..., pt)` porque a página de 404 e o índice caem em português por
    # padrão caso recebam código fora da lista.
    titulo_loja = _TITULO_LOJA.get(idioma, _TITULO_LOJA["pt"])
    marcas_duplas = _MARCAS_DUPLAS.get(idioma, _MARCAS_DUPLAS["pt"])
    identificacao = _IDENTIFICACAO.get(idioma, _IDENTIFICACAO["pt"])
    titulo_completo = (
        f"{titulo} - {titulo_loja} ({marcas_duplas}) - Fernando da Silva"
    )

    if substituir_h1:
        # Remove o `<h1>` original do Markdown e põe o `<h1>` completo no topo
        # de `<main>`, seguido imediatamente pelo bloco de identificação.
        corpo_sem_h1 = _PRIMEIRO_H1.sub("", corpo_html, count=1)
        miolo_main = (
            f"<h1>{titulo_completo}</h1>\n"
            f'<p class="app">{identificacao}</p>\n'
            f"{corpo_sem_h1}"
        )
    else:
        # Índice (`/legal`) e 404 já trazem seu próprio `<h1>` em `corpo_html`.
        miolo_main = f'<p class="app">{identificacao}</p>\n{corpo_html}'

    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{idioma}">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{titulo_completo}</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        f'<nav class="idiomas">{troca}</nav>\n'
        f"<main>\n{miolo_main}\n</main>\n"
        f"<footer>{titulo_loja} · {marcas_duplas} · Fernando da Silva · Santiago Data</footer>\n"
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
        substituir_h1=True,
    ).replace("{doc}", documento)

    # Cache: versão fixa (`/legal/1.0/...`) é imutável (1 ano). Já a rota
    # vigente (`/legal/<idioma>/<doc>`, usada nos formulários das lojas) manda
    # `no-cache`: em 26/11/2026 o `max-age=3600` autorizou o crawler da Google
    # Play a reutilizar a página antiga numa 2ª revisão minutos após o deploy.
    cache = "public, max-age=31536000, immutable" if imutavel else "no-cache"
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
    return HTMLResponse(
        content=corpo, status_code=404, headers={"Cache-Control": "no-cache"}
    )


# `@router.head(..., include_in_schema=False)` ao lado de cada `@router.get`:
# verificadores automáticos de link (como robôs das lojas) testam `HEAD` antes
# de `GET`, e o `@router.get` sozinho do FastAPI responderia `405`. Separar o
# `head` com `include_in_schema=False` evita o aviso de `Duplicate Operation ID`
# do OpenAPI que `api_route(methods=["GET", "HEAD"])` geraria.
@router.get("", response_class=HTMLResponse)
@router.head("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse)
@router.head("/", response_class=HTMLResponse, include_in_schema=False)
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
    return HTMLResponse(content=pagina, headers={"Cache-Control": "no-cache"})


@router.get("/{idioma}/{documento}", response_class=HTMLResponse)
@router.head(
    "/{idioma}/{documento}", response_class=HTMLResponse, include_in_schema=False
)
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
@router.head(
    "/{versao}/{idioma}/{documento}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
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

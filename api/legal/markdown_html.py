"""Conversor **mínimo** de Markdown para HTML — tarefa G3 (hospedagem legal).

Os documentos legais (`legal/<versao>/<idioma>/*.md`) usam um subconjunto pequeno
de Markdown: títulos (`#`/`##`/`###`), parágrafos, **negrito**, listas com `-` e
listas numeradas (`1.`), citações (`>`), links `[texto](url)` e comentários HTML
de rascunho (`<!-- ... -->`).

Em vez de trazer uma dependência de Markdown completa, fazemos um conversor
próprio e **testável** que cobre exatamente esse subconjunto. É proposital: o
texto é controlado por nós (não é entrada de usuário), então não precisamos de um
parser robusto contra Markdown arbitrário — só de algo correto para os nossos
documentos.

Segurança: todo texto é **escapado** para HTML antes de aplicarmos a formatação
inline, então um eventual `<` no texto não vira tag. Os links só permitem
esquemas seguros (`http`, `https`, `mailto`) e caminhos relativos.
"""
from __future__ import annotations

import html
import re

# Remove blocos de comentário HTML (inclusive multilinha), usados nos rascunhos.
_COMENTARIO = re.compile(r"<!--.*?-->", re.DOTALL)

# Formatação inline: **negrito** e [texto](url).
_NEGRITO = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Linha de lista não-ordenada ("- item" ou "* item") e numerada ("1. item").
_LISTA = re.compile(r"^\s*[-*]\s+(.*)$")
_LISTA_NUM = re.compile(r"^\s*\d+\.\s+(.*)$")
# Título: 1 a 3 "#".
_TITULO = re.compile(r"^(#{1,3})\s+(.*)$")
# Citação: "> ...".
_CITACAO = re.compile(r"^\s*>\s?(.*)$")


def _inline(texto: str) -> str:
    """Aplica a formatação inline (negrito e links) a um texto **já escapado**."""
    # Links primeiro: valida o destino e monta o <a>.
    def _link(m: "re.Match[str]") -> str:
        rotulo, destino = m.group(1), m.group(2).strip()
        # Links entre documentos vêm como "exclusao-conta.md" → vira relativo
        # "exclusao-conta" (a rota serve por nome de documento, sem extensão).
        if destino.endswith(".md"):
            destino = destino[:-3]
        if not _destino_seguro(destino):
            # Destino estranho: mostra só o rótulo (sem link), por segurança.
            return rotulo
        # O destino já está escapado (veio do texto escapado); seguro no href.
        return f'<a href="{destino}">{rotulo}</a>'

    texto = _LINK.sub(_link, texto)
    # Depois o negrito.
    texto = _NEGRITO.sub(r"<strong>\1</strong>", texto)
    return texto


def _destino_seguro(destino: str) -> bool:
    """Aceita apenas links http(s)/mailto ou caminhos relativos simples (sem
    esquema perigoso como `javascript:`)."""
    baixo = destino.lower()
    if baixo.startswith(("http://", "https://", "mailto:", "#", "/")):
        return True
    # Caminho relativo (ex.: "exclusao-conta"): sem ":" de esquema.
    return ":" not in destino


def renderizar_markdown(texto: str) -> str:
    """Converte o [texto] Markdown no **corpo HTML** (sem `<html>`/`<body>`).

    Processa por blocos: junta linhas consecutivas num parágrafo; agrupa itens de
    lista e linhas de citação; títulos viram `<h1..3>`. Linhas em branco separam
    blocos.
    """
    # Remove comentários e normaliza quebras de linha.
    limpo = _COMENTARIO.sub("", texto).replace("\r\n", "\n").replace("\r", "\n")
    linhas = limpo.split("\n")

    partes: list[str] = []  # blocos HTML acumulados
    paragrafo: list[str] = []  # linhas do parágrafo corrente
    itens: list[str] = []  # itens da lista corrente
    tipo_lista: str | None = None  # "ul" ou "ol" enquanto numa lista
    citacao: list[str] = []  # linhas da citação corrente

    def fechar_paragrafo() -> None:
        if paragrafo:
            conteudo = _inline(html.escape(" ".join(paragrafo)))
            partes.append(f"<p>{conteudo}</p>")
            paragrafo.clear()

    def fechar_lista() -> None:
        nonlocal tipo_lista
        if itens:
            lis = "".join(f"<li>{_inline(html.escape(i))}</li>" for i in itens)
            partes.append(f"<{tipo_lista}>{lis}</{tipo_lista}>")
            itens.clear()
        tipo_lista = None

    def fechar_citacao() -> None:
        if citacao:
            conteudo = _inline(html.escape(" ".join(citacao)))
            partes.append(f"<blockquote><p>{conteudo}</p></blockquote>")
            citacao.clear()

    def fechar_tudo() -> None:
        fechar_paragrafo()
        fechar_lista()
        fechar_citacao()

    for linha in linhas:
        if not linha.strip():
            # Linha em branco encerra qualquer bloco aberto.
            fechar_tudo()
            continue

        tit = _TITULO.match(linha)
        if tit:
            fechar_tudo()
            nivel = len(tit.group(1))  # 1..3
            conteudo = _inline(html.escape(tit.group(2).strip()))
            partes.append(f"<h{nivel}>{conteudo}</h{nivel}>")
            continue

        cit = _CITACAO.match(linha)
        if cit:
            # Citação: pode misturar com parágrafo/lista anteriores → fecha-os.
            fechar_paragrafo()
            fechar_lista()
            citacao.append(cit.group(1).strip())
            continue

        item = _LISTA.match(linha)
        item_num = _LISTA_NUM.match(linha)
        if item or item_num:
            fechar_paragrafo()
            fechar_citacao()
            novo_tipo = "ul" if item else "ol"
            # Se trocou o tipo de lista, fecha a anterior.
            if tipo_lista is not None and tipo_lista != novo_tipo:
                fechar_lista()
            tipo_lista = novo_tipo
            itens.append((item or item_num).group(1).strip())
            continue

        # Linha comum de texto.
        if itens:
            # Continuação (indentada) de um item de lista → anexa ao último item.
            itens[-1] = f"{itens[-1]} {linha.strip()}"
        elif citacao:
            citacao.append(linha.strip())
        else:
            paragrafo.append(linha.strip())

    fechar_tudo()
    return "\n".join(partes)

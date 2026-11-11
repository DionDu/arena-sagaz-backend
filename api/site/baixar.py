"""O ``/baixar``: um link só que leva cada celular para a loja certa.

Este módulo guarda a parte **pura** da rota (sem FastAPI, sem rede, sem disco):
decidir a loja pelo User-Agent, escolher o idioma pelo Accept-Language e montar
a página de escolha a partir do modelo ``site/baixar.html``. As rotas em si, e o
porquê de cada decisão (302, ``Vary``, iPad), estão em ``api/site/rotas.py``.

Separar assim deixa cada regra testável com uma chamada de função, sem subir
servidor nenhum.
"""
from __future__ import annotations

import html
import re

# ── As duas lojas ────────────────────────────────────────────────────────────
#
# Endereços https, e não `itms-apps://` nem `market://`: nos dois sistemas o https
# já abre o APP da loja quando ele está instalado, e continua funcionando (abre a
# loja no navegador) quando não está, ou quando o link é aberto num computador.
# Os esquemas próprios quebram com "endereço inválido" fora do celular certo.
#
# A App Store vai SEM o país na URL (nada de `/br/`): a Apple manda cada pessoa
# para a loja do país da conta dela. Com `/br/` fixo, um visitante de Portugal
# cairia na loja brasileira e veria "app indisponível no seu país".
#
# ⚠️ Os mesmos dois endereços estão também em `site/index.html` (STORE_APPLE e
# STORE_PLAY, no script da página). Se um app mudar de endereço, mudam os dois.
LOJA_APPLE = "https://apps.apple.com/app/id6790198320"
LOJA_PLAY = "https://play.google.com/store/apps/details?id=com.santiagodata.arenasagaz"

# ── Detecção pelo User-Agent ─────────────────────────────────────────────────
#
# Regex (expressão regular) é um padrão de texto; `re.compile` prepara o padrão
# uma vez só, e `re.IGNORECASE` ignora maiúsculas/minúsculas.
#
# Por que procurar só o NOME DO APARELHO, e não o do navegador: a maioria dos
# cliques vem do navegador interno do Instagram, do Facebook e do Threads. Os
# User-Agents deles acrescentam "Instagram 337.0...", "FBAN/FBIOS", "FB_IAB",
# "Barcelona" (o Threads) etc., mas MANTÊM o "iPhone"/"Android" do sistema. Uma
# regra que exigisse "Safari" ou "Chrome" erraria justamente esses cliques.
#
# Nenhum User-Agent de iPhone contém "Android", e o de Android não contém
# "iPhone"; a ordem das perguntas só importa para aparelhos exóticos (o antigo
# Windows Phone se dizia as duas coisas), e nesses o iOS vence.
#
# ⚠️ O iPad moderno NÃO aparece aqui: desde o iPadOS 13 o Safari dele se
# apresenta como "Macintosh", idêntico a um Mac. Só o próprio navegador sabe a
# diferença (tela de toque), e por isso a página de escolha traz um script que
# cuida desse caso (ver `site/baixar.html`).
_RE_IOS = re.compile(r"iPhone|iPad|iPod", re.IGNORECASE)
_RE_ANDROID = re.compile(r"Android", re.IGNORECASE)


def loja_para(user_agent: str | None) -> str | None:
    """Devolve o endereço da loja do aparelho, ou ``None`` se não deu para saber.

    ``None`` cobre o computador, o iPad que se diz Mac, robôs (inclusive o que
    gera a prévia do link no WhatsApp, cujo User-Agent é só "WhatsApp/2.x A") e
    pedidos sem User-Agent. Nesses casos a rota mostra a página com os dois selos.
    """
    ua = user_agent or ""
    if _RE_IOS.search(ua):
        return LOJA_APPLE
    if _RE_ANDROID.search(ua):
        return LOJA_PLAY
    return None


# ── Idioma da página de escolha ──────────────────────────────────────────────

IDIOMAS = ("pt", "en", "es")
IDIOMA_PADRAO = "pt"


def escolher_idioma(accept_language: str | None) -> str:
    """Escolhe pt, en ou es a partir do cabeçalho ``Accept-Language``.

    O cabeçalho é uma lista em ordem de preferência, cada item com um peso
    opcional ``q`` (de 0 a 1; sem ``q`` vale 1). Exemplo de um navegador em
    francês que também lê inglês: ``fr-FR,fr;q=0.9,en;q=0.5`` → aqui dá ``en``,
    o primeiro idioma da lista que nós temos.

    Só a parte antes do hífen conta (``pt-BR`` e ``pt-PT`` são ``pt``; ``es-419``
    é ``es``). Nada que sirva, ou cabeçalho ausente → português.
    """
    candidatos: list[tuple[float, int, str]] = []
    for posicao, item in enumerate((accept_language or "").split(",")):
        partes = item.strip().split(";")
        idioma = partes[0].strip().lower().split("-")[0]
        peso = 1.0
        for parametro in partes[1:]:
            parametro = parametro.strip()
            if parametro.startswith("q="):
                try:
                    peso = float(parametro[2:])
                except ValueError:
                    peso = 0.0  # peso ilegível: trata como "não quero"
        if idioma in IDIOMAS and peso > 0:
            # Ordena por peso (maior primeiro, daí o sinal de menos) e, no
            # empate, pela posição na lista, que é a ordem que o navegador deu.
            candidatos.append((-peso, posicao, idioma))
    return min(candidatos)[2] if candidatos else IDIOMA_PADRAO


# ── A página de escolha (computador, iPad-como-Mac, robôs) ───────────────────
#
# Os textos ficam aqui, e não no modelo, porque a página é montada no SERVIDOR
# (um HTML pronto por idioma), sem o dicionário em JavaScript do site principal.
# Regras herdadas do site: nome da marca "Sharp Arena" em inglês, nada de
# travessão longo, só o hífen comum.
TEXTOS = {
    "pt": {
        "titulo": "Baixe a Arena Sagaz",
        "descricao": "Damas, Jogo da Velha, Pontinhos e Quatro em Linha contra quatro rivais. Escolha a loja do seu celular:",
        "alt_apple": "Baixe na App Store",
        "alt_play": "Disponível no Google Play",
        "link_site": "Conhecer a Arena Sagaz",
    },
    "en": {
        "titulo": "Get Sharp Arena",
        "descricao": "Checkers, Tic Tac Toe, Dots and Boxes and Four in a Row against four rivals. Pick your phone's store:",
        "alt_apple": "Download on the App Store",
        "alt_play": "Get it on Google Play",
        "link_site": "Discover Sharp Arena",
    },
    "es": {
        "titulo": "Descarga Arena Sagaz",
        "descricao": "Damas, Tres en Raya, Puntos y Cajas y Cuatro en Raya contra cuatro rivales. Elige la tienda de tu móvil:",
        "alt_apple": "Descárgalo en la App Store",
        "alt_play": "Disponible en Google Play",
        "link_site": "Conocer Arena Sagaz",
    },
}


def montar_pagina(modelo: str, idioma: str) -> str:
    """Preenche o modelo ``site/baixar.html`` para um idioma.

    O modelo marca cada lacuna como ``{{chave}}`` (chaves duplas, para não se
    confundir com as chaves do CSS). Cada valor passa por ``html.escape``, que
    troca ``<``, ``>``, ``&`` e aspas pelas formas seguras do HTML: os textos são
    nossos, mas o hábito evita que um apóstrofo futuro quebre um atributo.
    """
    valores = {
        **TEXTOS[idioma],
        "idioma": idioma,
        "loja_apple": LOJA_APPLE,
        "loja_play": LOJA_PLAY,
    }
    pagina = modelo
    for chave, valor in valores.items():
        pagina = pagina.replace("{{" + chave + "}}", html.escape(valor, quote=True))
    return pagina

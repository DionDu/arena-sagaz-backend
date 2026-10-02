"""A POSICAO DESENHADA — o SVG que o painel mostra (RF-DES-012b, T039).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE, E NAO UM `<pre>` COM O JSON
═══════════════════════════════════════════════════════════════════════════

RF-DES-012b pede *"a posicao **desenhada**"*, e a palavra e deliberada: o dono
precisa decidir, olhando, se aquele desafio e bom. Uma FEN
(`W:W18,24,27:B12,16,K22`) e legivel por quem escreveu o motor e por mais
ninguem — e curadoria feita as cegas e curadoria que aprova tudo.

═══════════════════════════════════════════════════════════════════════════
⚠️ ISTO E DESENHO, NAO JULGAMENTO — E A DISTINCAO IMPORTA
═══════════════════════════════════════════════════════════════════════════

Este modulo le o JSON **cru** e nao importa motor nenhum. Duas razoes, e as duas
sao praticas:

  1. **A imagem da API nao tem o laboratorio instalado.** `Dockerfile` instala
     `requirements_api.txt`; e o `Dockerfile.job` que instala o runtime de
     inferencia. Um `from motores.pontinhos...` aqui derrubaria a API inteira no
     import — e a pagina que quebraria seria o `/health`, nao o painel.
  2. **Desenhar nao e conferir.** Quem confere que a posicao e alcancavel, que a
     vez bate e que o placar fecha e `job/posicao_inicial.conferir()`, na
     **geracao**, com o motor de verdade. Se aquilo passou, o JSON e confiavel; se
     nao passou, o candidato nem chegou ao banco.

⛔ **Nao acrescente regra de jogo aqui.** No dia em que este desenho precisar
decidir se um lance e legal, a peca certa e o arbitro — e o desenho passa a
receber o resultado pronto, nao a recalcula-lo.

═══════════════════════════════════════════════════════════════════════════
AS CORES SAO AS DO APLICATIVO, E ISSO NAO E ENFEITE
═══════════════════════════════════════════════════════════════════════════

`jogador 1 = AZUL` e `jogador 2 = VERMELHO`, sempre, em todos os jogos da Arena
(regra canonica do `CLAUDE.md` do aplicativo). O dono olha esta tela e as telas
do jogo no mesmo dia; se as cores se invertessem aqui, ele leria o desafio ao
contrario do que os jogadores vao ver.
"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Optional, Sequence

# ── A paleta, espelhada de `lib/core/tema/app_colors.dart` ───────────────────
AZUL_J1 = "#2A6F8E"
AZUL_J1_CLARO = "#BFD9E4"
VERMELHO_J2 = "#C84B31"
VERMELHO_J2_CLARO = "#F0CDC2"
PAPEL = "#F2EDE4"
PAPEL_2 = "#E9E1D2"
MADEIRA = "#8A5A33"
MADEIRA_ESC = "#5E3D22"
TINTA = "#2B2218"
TINTA_SUAVE = "#6E6052"
OURO = "#D9A441"
CREME = "#FBF8F1"

#: Lado do tabuleiro de damas, em casas. As quatro modalidades que o aplicativo
#: tem jogam em 8x8; a internacional (10x10) entraria aqui **com o numero vindo
#: do dado**, e nao com um `if` por modalidade.
LADO_DAMAS = 8

#: Quantas casas jogaveis ha por fileira — metade, porque so as escuras contam.
CASAS_POR_FILEIRA = LADO_DAMAS // 2


def _cor_do_jogador(jogador: int) -> str:
    """A cor canonica: `+1` azul, `-1` vermelho."""
    return AZUL_J1 if jogador == 1 else VERMELHO_J2


def _cor_clara_do_jogador(jogador: int) -> str:
    """O preenchimento de caixa fechada, na versao suave da cor do dono."""
    return AZUL_J1_CLARO if jogador == 1 else VERMELHO_J2_CLARO


# ═══════════════════════════════════════════════════════════════════════════
# Pontinhos
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ OS ROTULOS SAO COORDENADAS DA MATRIZ, E NAO INDICES DE CAIXA.
#
# O motor guarda o tabuleiro numa matriz `(2*H+1) x (2*W+1)`, e o rotulo carrega
# a posicao **nela**:
#
#     H_r_c  →  r PAR,   c IMPAR  →  traco horizontal, ligando (r, c-1) a (r, c+1)
#     V_r_c  →  r IMPAR, c PAR    →  traco vertical,   ligando (r-1, c) a (r+1, c)
#
# Confundir isso com "linha e coluna da caixa" e o erro natural de quem le o
# rotulo pela primeira vez, e ele produz um desenho plausivel e errado — que e o
# pior tipo.


def _coordenadas_do_traco(rotulo: str) -> tuple[int, int, int, int]:
    """As duas pontas de um traco, em coordenadas de **ponto** (x, y).

    Args:
        rotulo: `H_r_c` ou `V_r_c`, nas coordenadas da matriz do motor.

    Returns:
        `(x1, y1, x2, y2)` — cada valor e um indice de ponto, e nao um pixel.

    Raises:
        ValueError: rotulo que nao segue a forma.
    """
    tipo, r_txt, c_txt = rotulo.split("_")
    r, c = int(r_txt), int(c_txt)
    if tipo == "H":
        # Horizontal: mesma fileira de pontos, colunas vizinhas.
        return (c - 1) // 2, r // 2, (c + 1) // 2, r // 2
    if tipo == "V":
        # Vertical: mesma coluna de pontos, fileiras vizinhas.
        return c // 2, (r - 1) // 2, c // 2, (r + 1) // 2
    raise ValueError(f"rotulo de traco desconhecido: {rotulo!r}")


def _caixas_vizinhas(rotulo: str) -> list[tuple[int, int]]:
    """As caixas (coluna, linha) que aquele traco ajuda a fechar.

    Uma caixa da matriz mora em `(r impar, c impar)`; na tela ela e a celula cujo
    canto superior esquerdo e o ponto `((c-1)/2, (r-1)/2)`.
    """
    tipo, r_txt, c_txt = rotulo.split("_")
    r, c = int(r_txt), int(c_txt)
    if tipo == "H":
        # A caixa de cima e a de baixo compartilham este traco horizontal.
        return [((c - 1) // 2, (r - 2) // 2), ((c - 1) // 2, r // 2)]
    # A caixa da esquerda e a da direita compartilham este traco vertical.
    return [((c - 2) // 2, (r - 1) // 2), (c // 2, (r - 1) // 2)]


def _lados_da_caixa(cx: int, cy: int) -> list[str]:
    """Os quatro rotulos que fecham a caixa `(cx, cy)`.

    A volta pela matriz: a caixa esta em `(2*cy+1, 2*cx+1)`, e os lados sao os
    vizinhos ortogonais dela.
    """
    r, c = 2 * cy + 1, 2 * cx + 1
    return [
        f"H_{r - 1}_{c}",  # topo
        f"H_{r + 1}_{c}",  # base
        f"V_{r}_{c - 1}",  # esquerda
        f"V_{r}_{c + 1}",  # direita
    ]


def _donos_das_caixas(
    lances: list[Mapping[str, Any]],
) -> dict[tuple[int, int], int]:
    """Quem fechou cada caixa, reproduzindo a sequencia na ordem.

    ⚠️ **O dono e quem colocou o QUARTO lado**, e por isso a ordem importa: a
    mesma coleçao de tracos, marcada noutra ordem, daria outro dono para a mesma
    caixa. E a razao de o Pontinhos guardar sequencia, e nao matriz.
    """
    marcados: set[str] = set()
    donos: dict[tuple[int, int], int] = {}
    for lance in lances:
        rotulo = lance.get("lance")
        jogador = lance.get("jogador", 1)
        if not isinstance(rotulo, str):
            continue
        marcados.add(rotulo)
        for caixa in _caixas_vizinhas(rotulo):
            if caixa in donos:
                continue
            lados = _lados_da_caixa(*caixa)
            # Uma caixa fora do tabuleiro tem lados que nunca serao marcados —
            # ela simplesmente nao fecha, e nao precisa de checagem de borda.
            if all(lado in marcados for lado in lados):
                donos[caixa] = jogador
    return donos


def pontinhos(
    posicao: Mapping[str, Any],
    *,
    lado_px: int = 46,
    numerar: bool = False,
    destaque: str | None = None,
) -> str:
    """Desenha a posicao de Pontinhos: pontos, tracos e caixas ja fechadas.

    Args:
        posicao: o `js_posicao_inicial` do formato `sequencia_lances`.
        lado_px: quanto vale um passo entre dois pontos, em pixels.
        numerar: escreve o **rotulo de cada traco livre** (`V_3_4`, `H_0_1`)
            sobre a grade. ⚠️ **E o que torna a fita do gabarito legivel**: sem
            isso, `V_3_4` no JSON e uma linha de texto que nao aponta para lugar
            nenhum do desenho. Fica so nos tracos **livres**, porque o traco ja
            marcado esta desenhado — e um rotulo por cima dele viraria sujeira
            sobre a unica coisa que importa.
        destaque: o rotulo do traco que acabou de ser jogado, contornado em
            ouro.

    Returns:
        Um `<svg>` pronto para ir no HTML.

    ⚠️ O tamanho sai da **propria sequencia** (o maior indice usado), e nao de uma
    constante `4x3`: no dia em que um tabuleiro maior entrar no catalogo, o painel
    o desenha sem uma linha de mudanca — e um `LINHAS = 4` escrito aqui o
    desenharia cortado, sem erro nenhum.
    """
    lances = [l for l in (posicao.get("lances") or []) if isinstance(l, Mapping)]
    rotulos = [l.get("lance") for l in lances if isinstance(l.get("lance"), str)]
    if not rotulos:
        return _svg_vazio("posicao sem lances (tabuleiro limpo)")

    # O maior x e o maior y usados por qualquer ponta de traco dizem o tamanho.
    pontas = [_coordenadas_do_traco(r) for r in rotulos]
    max_x = max(max(p[0], p[2]) for p in pontas)
    max_y = max(max(p[1], p[3]) for p in pontas)

    margem = 14
    largura = max_x * lado_px + 2 * margem
    altura = max_y * lado_px + 2 * margem

    def px(indice: int) -> int:
        """Indice de ponto → pixel, ja com a margem."""
        return margem + indice * lado_px

    partes: list[str] = [
        f'<svg viewBox="0 0 {largura} {altura}" width="{largura}" '
        f'height="{altura}" role="img" '
        f'aria-label="Posicao inicial do desafio de Pontinhos">',
        f'<rect width="{largura}" height="{altura}" fill="{PAPEL}" rx="8"/>',
    ]

    # 1) As caixas fechadas, por baixo de tudo — elas sao fundo, nao contorno.
    for (cx, cy), dono in _donos_das_caixas(lances).items():
        partes.append(
            f'<rect x="{px(cx)}" y="{px(cy)}" width="{lado_px}" '
            f'height="{lado_px}" fill="{_cor_clara_do_jogador(dono)}"/>'
        )

    # 2) Os tracos marcados, na cor de quem os marcou.
    for lance in lances:
        rotulo = lance.get("lance")
        if not isinstance(rotulo, str):
            continue
        x1, y1, x2, y2 = _coordenadas_do_traco(rotulo)
        partes.append(
            f'<line x1="{px(x1)}" y1="{px(y1)}" x2="{px(x2)}" y2="{px(y2)}" '
            f'stroke="{_cor_do_jogador(lance.get("jogador", 1))}" '
            f'stroke-width="5" stroke-linecap="round"/>'
        )

    # 3) O traco que acabou de ser jogado, contornado em ouro.
    if destaque:
        try:
            hx1, hy1, hx2, hy2 = _coordenadas_do_traco(destaque)
        except (ValueError, IndexError):
            pass  # rotulo torto nao derruba o desenho inteiro
        else:
            partes.append(
                f'<line x1="{px(hx1)}" y1="{px(hy1)}" x2="{px(hx2)}" '
                f'y2="{px(hy2)}" stroke="{OURO}" stroke-width="9" '
                f'stroke-linecap="round" opacity="0.55"/>'
            )

    # 4) Os rotulos dos tracos LIVRES, quando pedidos.
    #
    # ⚠️ **So os livres.** O desenho ja mostra quem marcou os outros; escrever o
    # nome por cima competiria com a informacao que interessa.
    if numerar:
        marcados = set(rotulos)
        # ── ⛔ OS ROTULOS SAIEM DA ARESTA, E NAO DA GRADE DE PONTOS ──────────
        #
        # ⚠️ **`H_r_c` usa as coordenadas da MATRIZ do motor, e nao as do ponto.**
        # Numa horizontal, `r` e par e `c` e impar; numa vertical, o contrario.
        # A aresta horizontal que liga o ponto `(ix, iy)` ao `(ix+1, iy)` chama-se
        # `H_{2*iy}_{2*ix+1}`.
        #
        # ⛔ **Ate 11/09/2026 este laco varria a grade de PONTOS** e montava
        # `H_{iy}_{ix}` — nomes que em metade dos casos nao existem, e que o
        # conversor mapeia para a **mesma** aresta de um nome valido: `H_0_1` e
        # `H_0_2` dao os dois `(0,0)-(1,0)`. O resultado era o texto de dois
        # rotulos impresso um sobre o outro, e foi o que o dono viu: *"o
        # identificador das arestas no SVG esta se sobrepondo"*.
        for iy in range(max_y + 1):
            for ix in range(max_x + 1):
                arestas = []
                if ix < max_x:  # horizontal para a direita
                    arestas.append(f"H_{2 * iy}_{2 * ix + 1}")
                if iy < max_y:  # vertical para baixo
                    arestas.append(f"V_{2 * iy + 1}_{2 * ix}")
                for rotulo in arestas:
                    if rotulo in marcados:
                        continue
                    rx1, ry1, rx2, ry2 = _coordenadas_do_traco(rotulo)
                    # ⚠️ **O rotulo da vertical vai DE PE.** Deitado, ele
                    # tem a largura de uma casa inteira e encosta no rotulo da
                    # horizontal vizinha — o dono relatou exatamente isso:
                    # *"os nomes das arestas estao ficando sobrepostas e fica
                    # dificil pra mim identificar"*. Girado 90 graus, ele ocupa
                    # a direcao em que ha espaco sobrando, que e a mesma direcao
                    # do traco que ele nomeia.
                    cx = (px(rx1) + px(rx2)) / 2
                    cy = (px(ry1) + px(ry2)) / 2
                    if rotulo.startswith("V"):
                        giro = f' transform="rotate(-90 {cx:.0f} {cy:.0f})"'
                    else:
                        giro = ""
                    partes.append(
                        f'<text x="{cx:.0f}" y="{cy + 3:.0f}"{giro} '
                        f'text-anchor="middle" font-size="9" '
                        f'fill="{TINTA_SUAVE}" opacity="0.8">{rotulo}</text>'
                    )

    # 5) Os pontos, por cima — eles sao a grade, e precisam ficar visiveis.
    for iy in range(max_y + 1):
        for ix in range(max_x + 1):
            partes.append(
                f'<circle cx="{px(ix)}" cy="{px(iy)}" r="3.5" fill="{MADEIRA_ESC}"/>'
            )

    partes.append("</svg>")
    return "".join(partes)


# ═══════════════════════════════════════════════════════════════════════════
# Damas
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ A NUMERACAO DAS CASAS E A DO MOTOR, E ELA ESTA ESCRITA UMA VEZ SO LA.
#
# `espelho_laboratorio/.../tabuleiro_damas.py` diz: linha 0 e o topo (onde as
# PRETAS comecam), casa escura e a que tem `(linha + coluna) impar`, e o numero
# de 1 a 32 anda da esquerda para a direita, de cima para baixo.
#
# ⛔ Reescrever essa aritmetica em Dart ou em SQL seria criar uma segunda
# numeracao; **aqui** ela e reescrita porque o desenho nao pode importar o motor
# (ver o topo do modulo), e por isso ela vem com o teste que a prende: um
# tabuleiro inicial desenhado com as casas trocadas poe as pretas embaixo, e a
# unica coisa que denuncia isso e alguem olhar.


def _linha_coluna(casa: int) -> tuple[int, int]:
    """Numero da casa (1..32) → `(linha, coluna)` do tabuleiro 8x8.

    Raises:
        ValueError: casa fora do intervalo.
    """
    if not 1 <= casa <= LADO_DAMAS * CASAS_POR_FILEIRA:
        raise ValueError(f"casa fora do tabuleiro: {casa}")
    indice = casa - 1
    linha = indice // CASAS_POR_FILEIRA
    posicao_na_linha = indice % CASAS_POR_FILEIRA
    # Numa linha PAR a primeira casa escura esta na coluna 1; numa IMPAR, na 0.
    deslocamento = 1 if linha % 2 == 0 else 0
    return linha, posicao_na_linha * 2 + deslocamento


def _ler_fen(fen: str) -> tuple[str, dict[int, tuple[str, bool]]]:
    """Le a FEN de damas: a vez e o conteudo de cada casa ocupada.

    Args:
        fen: por exemplo `W:W18,24,K27:B12,16,K22`.

    Returns:
        `(vez, {casa: (cor, e_dama)})`, com `cor` em `'W'`/`'B'`.

    ⚠️ **As duas ordens sao aceitas** (`:W...:B...` e `:B...:W...`), como no
    motor: o prefixo de cada bloco diz de quem ele e, e confiar na posicao seria
    inventar uma regra que o motor nao tem.
    """
    partes = [p for p in fen.split(":") if p]
    if not partes:
        return "W", {}
    vez = partes[0].strip().upper()[:1] or "W"
    ocupadas: dict[int, tuple[str, bool]] = {}
    for bloco in partes[1:]:
        bloco = bloco.strip()
        if not bloco:
            continue
        cor, resto = bloco[0].upper(), bloco[1:]
        for item in resto.split(","):
            item = item.strip().upper()
            if not item:
                continue
            e_dama = item.startswith("K")
            numero = item[1:] if e_dama else item
            if numero.isdigit():
                ocupadas[int(numero)] = (cor, e_dama)
    return vez, ocupadas


def casas_do_lance(notacao: str) -> tuple[int, ...]:
    """As casas citadas por um lance de damas.

    `24-19` da `(24, 19)`; `21x30x23` da `(21, 30, 23)` — origem, casas
    intermediarias e destino.

    ⚠️ **Isto nao interpreta o lance**, so le os numeros que ele nomeia: serve
    para **acender** o caminho no desenho, e nao para saber o que aconteceu. Quem
    sabe o que aconteceu e o motor, e e por isso que a posicao resultante vem
    gravada em vez de ser recalculada aqui.
    """
    numeros: list[int] = []
    for pedaco in notacao.replace("x", "-").split("-"):
        pedaco = pedaco.strip().upper().lstrip("K")
        if pedaco.isdigit():
            numeros.append(int(pedaco))
    return tuple(numeros)


def _centro_da_casa(casa: int, *, margem: int, lado_px: int) -> tuple[float, float]:
    """O pixel do centro de uma casa jogavel (1..32)."""
    linha, coluna = _linha_coluna(casa)
    return (
        margem + coluna * lado_px + lado_px / 2,
        margem + linha * lado_px + lado_px / 2,
    )


def capturadas_no_lance(fen_antes: str, fen_depois: str) -> list[int]:
    """As casas das pecas que o lance comeu, pela DIFERENCA entre as duas FENs.

    Args:
        fen_antes: a posicao antes do lance (a vez e de quem joga).
        fen_depois: a posicao depois dele.

    Returns:
        As casas do adversario de quem jogou que estavam ocupadas antes e vazias
        depois, em ordem crescente.

    ⚠️ **Isto nao e regra de damas, e por isso pode morar aqui.** Quem decidiu o
    que foi comido foi o motor, quando gravou a FEN de depois; este codigo so
    compara duas fotografias. ⛔ Calcular a captura a partir do lance seria a
    segunda implementacao das regras que o topo deste modulo proibe.
    """
    vez, antes = _ler_fen(fen_antes)
    _, depois = _ler_fen(fen_depois)
    return sorted(
        casa for casa, (cor, _) in antes.items() if cor != vez and casa not in depois
    )


def ordem_das_capturas(
    trajeto: Sequence[int], condenadas: Sequence[int]
) -> dict[int, Optional[int]]:
    """Em que ordem cada peca condenada foi comida, seguindo o trajeto.

    Args:
        trajeto: as casas do lance, na ordem (`26x19x12x3` → `26, 19, 12, 3`).
        condenadas: as casas comidas (`capturadas_no_lance`).

    Returns:
        `{casa: ordem}`, com a ordem comecando em 1. ⚠️ **`None` quando a peca
        nao esta em nenhum trecho do trajeto** — o que acontece se a notacao so
        trouxer origem e destino de uma captura multipla. A peca continua
        marcada como condenada; so o numero fica de fora, em vez de inventado.

    ⚠️ E so geometria: a peca comida no trecho `a → b` esta na mesma diagonal,
    estritamente entre as duas casas. E o numero que o app desenha sobre a
    condenada (`TabuleiroDamasWidget.condenadas`), para quem le saber por onde
    a peca passou.
    """
    ordem: dict[int, Optional[int]] = {casa: None for casa in condenadas}
    proxima = 1
    for origem, destino in zip(trajeto, trajeto[1:]):
        try:
            l1, c1 = _linha_coluna(origem)
            l2, c2 = _linha_coluna(destino)
        except ValueError:
            continue
        dl, dc = l2 - l1, c2 - c1
        # So trecho em diagonal tem "casas entre": |dl| == |dc|.
        if dl == 0 or abs(dl) != abs(dc):
            continue
        passo_l, passo_c = dl // abs(dl), dc // abs(dc)
        for k in range(1, abs(dl)):
            l, c = l1 + k * passo_l, c1 + k * passo_c
            for casa in condenadas:
                if ordem[casa] is None and _linha_coluna(casa) == (l, c):
                    ordem[casa] = proxima
                    proxima += 1
    return ordem


def damas(
    posicao: Mapping[str, Any],
    *,
    lado_px: int = 30,
    numerar: bool = False,
    destaque: Sequence[int] = (),
    trajeto: Sequence[int] = (),
    condenadas: Mapping[int, Optional[int]] | None = None,
) -> str:
    """Desenha a posicao de damas a partir da FEN.

    Args:
        posicao: o `js_posicao_inicial` do formato `fen`.
        lado_px: o lado de uma casa, em pixels.
        numerar: escreve o numero de 1 a 32 nas casas jogaveis. ⚠️ **Sem isso a
            notacao do gabarito nao se liga ao desenho** — `21x30x23` so quer
            dizer alguma coisa para quem ja tem a numeracao na cabeca, e a
            curadoria e feita exatamente por quem ainda nao tem.
        destaque: casas a acender (as do lance recem-jogado).
        trajeto: as casas do lance que VAI ser jogado, na ordem. Desenha o
            caminho tracejado, um anel na peca que sai e um fantasma tracejado
            onde ela pousa — o mesmo vocabulario do replay e do "voltar
            jogada" no app (pedido do dono, 02/10/2026). ⚠️ A posicao
            desenhada e a de ANTES do lance: e nela que o trajeto faz sentido.
        condenadas: `{casa: ordem}` das pecas que o lance come
            (`capturadas_no_lance` + `ordem_das_capturas`). Ganham um × e o
            numero da ordem; `None` = sem numero.

    Returns:
        Um `<svg>` pronto para ir no HTML.

    ⚠️ **As BRANCAS sao o jogador 1 (azul) e as PRETAS o jogador 2 (vermelho)** —
    e a mesma traducao que `EstadoDamas.vez_de` faz para o log. Desenhar as pecas
    em branco e preto de verdade seria mais literal e menos util: o dono lê o
    quadro do dia e a tela do jogo nas cores dos jogadores, nao nas das pedras.
    """
    fen = posicao.get("fen")
    if not isinstance(fen, str) or not fen:
        return _svg_vazio("posicao sem FEN")

    vez, ocupadas = _ler_fen(fen)
    margem = 10
    tamanho = LADO_DAMAS * lado_px + 2 * margem

    partes: list[str] = [
        f'<svg viewBox="0 0 {tamanho} {tamanho}" width="{tamanho}" '
        f'height="{tamanho}" role="img" '
        f'aria-label="Posicao inicial do desafio de damas, vez das '
        f'{"brancas" if vez == "W" else "pretas"}">',
        f'<rect width="{tamanho}" height="{tamanho}" fill="{MADEIRA}" rx="6"/>',
    ]

    # 1) O xadrezado. Casa escura e `(linha + coluna) impar` — a mesma conta do
    #    motor, e e ela que poe a casa jogavel no canto inferior esquerdo.
    for linha in range(LADO_DAMAS):
        for coluna in range(LADO_DAMAS):
            escura = (linha + coluna) % 2 == 1
            partes.append(
                f'<rect x="{margem + coluna * lado_px}" '
                f'y="{margem + linha * lado_px}" '
                f'width="{lado_px}" height="{lado_px}" '
                f'fill="{PAPEL_2 if escura else PAPEL}"/>'
            )

    # 2) As casas do lance recem-jogado, acesas por baixo das pecas.
    for casa in destaque:
        try:
            linha, coluna = _linha_coluna(casa)
        except ValueError:
            continue
        partes.append(
            f'<rect x="{margem + coluna * lado_px}" '
            f'y="{margem + linha * lado_px}" width="{lado_px}" '
            f'height="{lado_px}" fill="{OURO}" opacity="0.38"/>'
        )

    # 3) O numero da casa, quando pedido — pequeno, no canto superior esquerdo,
    #    e so nas casas JOGAVEIS (as claras nao tem numero no jogo).
    if numerar:
        for casa in range(1, LADO_DAMAS * CASAS_POR_FILEIRA + 1):
            try:
                linha, coluna = _linha_coluna(casa)
            except ValueError:
                continue
            partes.append(
                f'<text x="{margem + coluna * lado_px + 3}" '
                f'y="{margem + linha * lado_px + 10}" font-size="8" '
                f'fill="{TINTA_SUAVE}" opacity="0.85">{casa}</text>'
            )

    # 4) As pecas.
    raio = lado_px * 0.36
    for casa, (cor, e_dama) in sorted(ocupadas.items()):
        try:
            linha, coluna = _linha_coluna(casa)
        except ValueError:
            # FEN com casa impossivel: nao desenha aquela peca, e nao derruba a
            # pagina inteira por causa de um dado torto — o painel existe
            # justamente para o dono ver o que esta torto.
            continue
        cx = margem + coluna * lado_px + lado_px / 2
        cy = margem + linha * lado_px + lado_px / 2
        preenchimento = AZUL_J1 if cor == "W" else VERMELHO_J2
        partes.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{raio:.1f}" '
            f'fill="{preenchimento}" stroke="{MADEIRA_ESC}" stroke-width="1"/>'
        )
        if e_dama:
            # A coroa: um anel dourado por dentro. E o mesmo sinal que o
            # aplicativo usa, e nao uma letra "K" — letra some no tamanho em que
            # este tabuleiro e desenhado.
            partes.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{raio * 0.5:.1f}" '
                f'fill="none" stroke="{OURO}" stroke-width="2.5"/>'
            )

    # 5) As CONDENADAS: um × sobre a peca e, quando se sabe, a ordem da captura.
    #    ⚠️ O × vai por cima das pecas e por baixo do trajeto, para o caminho
    #    continuar legivel quando passa ao lado. ⚠️ Os SELOS com a ordem vao por
    #    ULTIMO (lista `selos`, desenhada no passo 7): numa captura em linha
    #    reta o tracejado atravessa a diagonal de todas as condenadas, e
    #    desenhado depois ele cobria os numeros 1 e 2 — visto no painel em
    #    02/10/2026, no `26x19x12x3`.
    selos: list[str] = []
    for casa, ordem in sorted((condenadas or {}).items()):
        try:
            cx, cy = _centro_da_casa(casa, margem=margem, lado_px=lado_px)
        except ValueError:
            continue
        braco = raio * 0.62
        for sinal in (1, -1):
            # Duas linhas cruzadas: (−b,−b)→(b,b) e (−b,b)→(b,−b).
            partes.append(
                f'<line x1="{cx - braco:.1f}" y1="{cy - sinal * braco:.1f}" '
                f'x2="{cx + braco:.1f}" y2="{cy + sinal * braco:.1f}" '
                f'stroke="{CREME}" stroke-width="3" stroke-linecap="round"/>'
            )
        if ordem is not None:
            # O numero da ordem num circulo pequeno no canto da casa.
            bx, by = cx + lado_px * 0.3, cy - lado_px * 0.3
            selos.append(
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{lado_px * 0.2:.1f}" '
                f'fill="{TINTA}"/>'
                f'<text x="{bx:.1f}" y="{by + lado_px * 0.08:.1f}" '
                f'text-anchor="middle" font-size="{lado_px * 0.26:.0f}" '
                f'font-weight="700" fill="{CREME}">{ordem}</text>'
            )

    # 6) O TRAJETO do lance: anel na origem, caminho tracejado com seta e um
    #    fantasma tracejado onde a peca pousa.
    pontos: list[tuple[float, float]] = []
    for casa in trajeto:
        try:
            pontos.append(_centro_da_casa(casa, margem=margem, lado_px=lado_px))
        except ValueError:
            pontos = []
            break
    if len(pontos) >= 2:
        (ox, oy), (dx, dy) = pontos[0], pontos[-1]
        partes.append(
            f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="{raio + 3:.1f}" fill="none" '
            f'stroke="{OURO}" stroke-width="3"/>'
        )
        caminho = " ".join(f"{x:.1f},{y:.1f}" for x, y in pontos)
        # O contorno claro por baixo do tracejado e o que o mantem visivel
        # sobre as casas escuras e sobre as pecas vermelhas.
        partes.append(
            f'<polyline points="{caminho}" fill="none" stroke="{CREME}" '
            f'stroke-width="5" stroke-linejoin="round" stroke-linecap="round" '
            f'opacity="0.85"/>'
            f'<polyline points="{caminho}" fill="none" stroke="{MADEIRA_ESC}" '
            f'stroke-width="2.5" stroke-dasharray="6 4" stroke-linejoin="round" '
            f'stroke-linecap="round"/>'
        )
        # A ponta da seta: um triangulo apontando na direcao do ultimo trecho.
        (px1, py1) = pontos[-2]
        comprimento = max(((dx - px1) ** 2 + (dy - py1) ** 2) ** 0.5, 1.0)
        ux, uy = (dx - px1) / comprimento, (dy - py1) / comprimento
        ponta_x, ponta_y = dx - ux * raio * 0.9, dy - uy * raio * 0.9
        base = lado_px * 0.22
        # `(-uy, ux)` e a perpendicular do trecho: abre a base do triangulo.
        partes.append(
            f'<polygon points="{ponta_x:.1f},{ponta_y:.1f} '
            f'{ponta_x - ux * base - uy * base * 0.7:.1f},'
            f'{ponta_y - uy * base + ux * base * 0.7:.1f} '
            f'{ponta_x - ux * base + uy * base * 0.7:.1f},'
            f'{ponta_y - uy * base - ux * base * 0.7:.1f}" '
            f'fill="{MADEIRA_ESC}"/>'
        )
        partes.append(
            f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="{raio:.1f}" fill="none" '
            f'stroke="{MADEIRA_ESC}" stroke-width="2" stroke-dasharray="4 3"/>'
        )

    # 7) Os selos da ordem de captura, por cima de tudo (ver o passo 5).
    partes.extend(selos)

    partes.append("</svg>")
    return "".join(partes)


# ═══════════════════════════════════════════════════════════════════════════
# A porta de entrada
# ═══════════════════════════════════════════════════════════════════════════


def _svg_vazio(motivo: str) -> str:
    """Um retangulo com a explicacao, para quando nao ha o que desenhar.

    ⚠️ **Diz o motivo, e nao fica em branco.** Um espaco vazio na tela e
    indistinguivel de um erro de layout, e o dono ficaria sem saber se o desafio
    esta torto ou se o painel esta.
    """
    return (
        f'<svg viewBox="0 0 220 60" width="220" height="60" role="img" '
        f'aria-label="{escape(motivo)}">'
        f'<rect width="220" height="60" fill="{PAPEL_2}" rx="8"/>'
        f'<text x="110" y="34" text-anchor="middle" font-size="11" '
        f'fill="{TINTA_SUAVE}">{escape(motivo)}</text>'
        f"</svg>"
    )


def posicao(
    co_formato: str,
    js_posicao_inicial: Mapping[str, Any] | None,
    *,
    numerar: bool = False,
    destaque: Any = None,
    maior: bool = False,
) -> str:
    """Desenha a posicao inicial no formato que ela declarar.

    Args:
        co_formato: `sequencia_lances` ou `fen`.
        js_posicao_inicial: o JSON gravado na coluna.

    Returns:
        O `<svg>`, ou um aviso desenhado quando o formato e desconhecido.

    ⚠️ **Formato desconhecido nao levanta excecao**: o painel e a ferramenta que
    o dono abre justamente quando algo esta errado, e derruba-la com um 500 no
    dia em que uma linha torta chegar ao banco seria tirar dele a unica janela
    para ver a linha torta.
    """
    js_posicao_inicial = js_posicao_inicial or {}
    if co_formato == "sequencia_lances":
        return pontinhos(
            js_posicao_inicial,
            lado_px=58 if maior else 46,
            numerar=numerar,
            destaque=destaque if isinstance(destaque, str) else None,
        )
    if co_formato == "fen":
        return damas(
            js_posicao_inicial,
            numerar=numerar,
            destaque=destaque if isinstance(destaque, (list, tuple)) else (),
        )
    return _svg_vazio(f"formato {co_formato!r} sem desenho")


# ═══════════════════════════════════════════════════════════════════════════
# A FITA — a solucao de referencia, quadro a quadro
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Por que isto existe** (pedido do dono, 11/09/2026): *"o painel deveria ao
# menos exibir a solucao de gabarito, lance por lance. Olhando so o JSON dos
# lances fica muito dificil para mim visualizar isso."*
#
# ⛔ **E por que ele NAO reproduz os lances:** aplicar `21x30x23` a uma posicao e
# trabalho do motor, e a imagem da API nao o importa — ela nao instala numpy, e
# nao vai instalar por causa de uma pagina interna. Escrever as regras aqui seria
# a **segunda implementacao**, que e o defeito que este projeto mais persegue.
#
# Entao cada jogo entrega o quadro da maneira que lhe e natural:
#
#   · **damas** — o job grava a FEN depois de cada lance (`js_solucao.posicoes`),
#     porque e ele quem tem o motor;
#   · **Pontinhos** — a posicao **e** a lista de lances, entao o quadro k e a
#     concatenacao dos lances iniciais com os k primeiros do gabarito. ⚠️ Nenhuma
#     regra e aplicada: quem decide a posse das caixas ja e `_donos_das_caixas`,
#     que desenha a posicao inicial desde o primeiro dia.
#
# ⚠️ **E desde 02/10/2026 as damas mostram o LANCE, e nao so o resultado**
# (pedido do dono: *"Se no jogo da Dama voce conseguir exibir no tabuleiro o
# tracejado do lance e as pecas condenadas, como mostra nos replay e no poder
# voltar jogada, me ajudaria demais"*). Cada quadro de damas e a posicao de
# ANTES do lance, com o trajeto tracejado e as condenadas marcadas; o ultimo
# quadro e a posicao final. As condenadas saem da diferenca entre a FEN de
# antes e a de depois (`capturadas_no_lance`) — fotografias que o motor
# gravou, e nenhuma regra e recalculada aqui.
#
# ⚠️ **A mesma fita desenha a partida de quem jogou** (o raio-x do painel):
# o log das damas grava a FEN de antes de cada lance (`co_fen_antes`), e o do
# Pontinhos grava a sequencia de tracos. `fita_da_partida` so traduz o log
# para o vocabulario do gabarito.


#: Os rotulos de cada lado, no gabarito: quem resolve e "voce".
ROTULOS_DO_GABARITO = ("voce", "adversario")

#: E na partida de alguem: a pessoa e a CPU.
ROTULOS_DA_PARTIDA = ("jogador", "CPU")


def _quadros(
    co_formato: str,
    js_posicao_inicial: Mapping[str, Any],
    lances: list[Mapping[str, Any]],
    *,
    fens_depois: Optional[list[Optional[str]]],
    n_chave: Any,
    rotulos: tuple[str, str],
) -> list[dict[str, Any]]:
    """Os quadros de uma sequencia de lances — gabarito ou partida de alguem.

    Args:
        co_formato: `fen` ou `sequencia_lances`.
        js_posicao_inicial: a posicao publicada do desafio.
        lances: `[{"lance", "jogador" (+1/-1), "co_acao"?}]`, na ordem.
        fens_depois: so nas damas — a FEN depois de cada lance, alinhada com
            `lances`. `None` num item = nao se sabe (o ultimo lance de uma
            partida, que nao tem "proximo" de onde ler).
        n_chave: o numero do lance que cumpre o objetivo (1-based).
        rotulos: `(lado de quem resolve, o outro)`.

    Returns:
        Os quadros, cada um `{"n", "tipo", "titulo", "lance", "jogador",
        "de_quem", "chave", "errou_de_proposito", "svg"}` — `tipo` e
        `inicio`, `lance` ou `final`.
    """
    # ⚠️ QUEM RESOLVE O DESAFIO E QUEM JOGA PRIMEIRO — a mesma definicao que o
    # julgamento usa (`julgar(..., jogador=vez_de)`). Ver a nota historica de
    # 11/09/2026: o painel chamou de "adversario" o primeiro lance da propria
    # pessoa, porque o lado estava fixo em vez de vir de `vez_de`.
    solucionador = js_posicao_inicial.get("vez_de")

    def de_quem(jogador: Any) -> str:
        if solucionador is None or jogador is None:
            return "?"
        return rotulos[0] if jogador == solucionador else rotulos[1]

    def base(indice: int, lance: Mapping[str, Any]) -> dict[str, Any]:
        """Os campos que todo quadro de lance tem, nos dois jogos."""
        notacao = str(lance.get("lance", ""))
        return {
            "n": indice,
            "tipo": "lance",
            "titulo": notacao,
            "lance": notacao,
            "jogador": lance.get("jogador"),
            "de_quem": de_quem(lance.get("jogador")),
            "chave": indice == n_chave,
            # ⚠️ A CPU jogou fora do melhor lance de proposito (o epsilon do
            # nivel). Um desafio que so se resolve por causa disto e fragil.
            "errou_de_proposito": lance.get("co_acao") == "cnn_epsilon_aleatorio",
        }

    if co_formato == "fen":
        fen_inicial = js_posicao_inicial.get("fen")
        if not isinstance(fen_inicial, str) or fens_depois is None:
            return []
        quadros: list[dict[str, Any]] = []
        fen_antes: Optional[str] = fen_inicial
        for indice, (lance, fen_depois) in enumerate(zip(lances, fens_depois), 1):
            quadro = base(indice, lance)
            trajeto = casas_do_lance(quadro["lance"])
            condenadas: dict[int, Optional[int]] = {}
            if fen_antes and fen_depois:
                condenadas = ordem_das_capturas(
                    trajeto, capturadas_no_lance(fen_antes, fen_depois)
                )
            quadro["svg"] = damas(
                {"fen": fen_antes or ""},
                numerar=True,
                trajeto=trajeto,
                condenadas=condenadas,
            )
            quadros.append(quadro)
            fen_antes = fen_depois
        # O quadro FINAL: a posicao depois do ultimo lance, quando se sabe.
        if fen_antes:
            quadros.append(
                {
                    "n": len(lances) + 1,
                    "tipo": "final",
                    "titulo": "posicao final",
                    "lance": None,
                    "jogador": None,
                    "de_quem": None,
                    "chave": False,
                    "errou_de_proposito": False,
                    "svg": damas({"fen": fen_antes}, numerar=True),
                }
            )
        return quadros

    if co_formato == "sequencia_lances":
        quadros = [
            {
                "n": 0,
                "tipo": "inicio",
                "titulo": "posicao publicada",
                "lance": None,
                "jogador": None,
                "de_quem": None,
                "chave": False,
                "errou_de_proposito": False,
                "svg": posicao(
                    co_formato, js_posicao_inicial, numerar=True, maior=True
                ),
            }
        ]
        iniciais = [
            l
            for l in (js_posicao_inicial.get("lances") or [])
            if isinstance(l, Mapping)
        ]
        for indice, lance in enumerate(lances, start=1):
            quadro = base(indice, lance)
            # ⚠️ Nenhuma regra e aplicada: a posicao do Pontinhos E a lista de
            # tracos, e quem decide a posse das caixas e `_donos_das_caixas`.
            ate_aqui = iniciais + lances[:indice]
            quadro["svg"] = pontinhos(
                {**js_posicao_inicial, "lances": ate_aqui},
                # Maior que a miniatura da fila porque leva texto: com 46 px os
                # rotulos das arestas se encostam.
                lado_px=58,
                numerar=True,
                destaque=quadro["lance"],
            )
            quadros.append(quadro)
        return quadros

    return []


def fita_da_solucao(
    co_formato: str,
    js_posicao_inicial: Mapping[str, Any] | None,
    js_solucao: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Os quadros da solucao de referencia (o gabarito).

    Returns:
        Os quadros (ver `_quadros`). ⛔ **Lista vazia quando nao da para montar**
        — e quem chama explica o motivo ao dono, em vez de desenhar meia
        sequencia.

    ⚠️ **Desafio de damas gerado antes de 11/09/2026 nao tem `posicoes`**, e o
    correto e devolver vazio: uma sequencia com buraco desenharia um salto como
    se fosse um lance, e a curadoria aprovaria uma solucao que nao existe.
    """
    js_posicao_inicial = js_posicao_inicial or {}
    js_solucao = js_solucao or {}
    lances = [l for l in (js_solucao.get("lances") or []) if isinstance(l, Mapping)]
    if not lances:
        return []

    fens_depois: Optional[list[Optional[str]]] = None
    if co_formato == "fen":
        posicoes = {
            p.get("n"): p.get("fen")
            for p in (js_solucao.get("posicoes") or [])
            if isinstance(p, Mapping)
        }
        if len(posicoes) != len(lances):
            return []
        fens_depois = [posicoes.get(n) for n in range(1, len(lances) + 1)]
        if any(f is None for f in fens_depois):
            return []

    return _quadros(
        co_formato,
        js_posicao_inicial,
        lances,
        fens_depois=fens_depois,
        n_chave=js_solucao.get("lance_chave"),
        rotulos=ROTULOS_DO_GABARITO,
    )


def fita_da_partida(
    co_formato: str,
    js_posicao_inicial: Mapping[str, Any] | None,
    lances_do_log: Sequence[Mapping[str, Any]],
    *,
    nu_lance_cumpre_desafio: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Os quadros da partida de UMA pessoa — o raio-x do painel (02/10/2026).

    Args:
        co_formato: o formato da posicao publicada.
        js_posicao_inicial: a posicao publicada do desafio.
        lances_do_log: as linhas de `quadro.SQL_LANCES`, em ordem:
            `{"nu_ordem", "nu_jogador" (1 ou 2), "co_lance", "co_fen_antes"}`.
            ⚠️ **O log comeca DEPOIS da posicao publicada** (o lance 1 e o
            primeiro que a pessoa fez), e o jogador vem como 1/2 — o 2 e o
            `-1` do vocabulario do gabarito.
        nu_lance_cumpre_desafio: o lance em que o objetivo foi cumprido.

    ⚠️ **Nas damas a FEN de DEPOIS de um lance e a de ANTES do seguinte** —
    o log so guarda a de antes. O ultimo lance fica sem "depois", e por isso
    sem condenadas marcadas e sem quadro final: o que nao se sabe nao se desenha.
    """
    js_posicao_inicial = js_posicao_inicial or {}
    lances = [
        {
            "lance": linha.get("co_lance"),
            "jogador": 1 if linha.get("nu_jogador") == 1 else -1,
        }
        for linha in lances_do_log
        if linha.get("co_lance")
    ]
    if not lances:
        return []

    fens_depois: Optional[list[Optional[str]]] = None
    if co_formato == "fen":
        antes = [linha.get("co_fen_antes") for linha in lances_do_log if linha.get("co_lance")]
        # O "depois" do lance k e o "antes" do lance k+1; o ultimo nao tem.
        fens_depois = list(antes[1:]) + [None]
        # ⚠️ Se o log trouxer a FEN de antes do primeiro lance, ela e a fonte
        # mais fiel do inicio (a posicao publicada pode ter sido semeada
        # noutra ordem de blocos); senao vale a publicada.
        if antes and antes[0]:
            js_posicao_inicial = {**js_posicao_inicial, "fen": antes[0]}

    return _quadros(
        co_formato,
        js_posicao_inicial,
        lances,
        fens_depois=fens_depois,
        n_chave=nu_lance_cumpre_desafio,
        rotulos=ROTULOS_DA_PARTIDA,
    )

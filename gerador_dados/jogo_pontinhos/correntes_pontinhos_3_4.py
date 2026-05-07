"""Detecção de estruturas (correntes, ciclos, ramificações) no tabuleiro
do Jogo dos Pontinhos.

Módulo autossuficiente: opera apenas sobre `EstadoTabuleiro` e `Estrutura`.
Não depende de `ia_pontinhos_3_4`. Pode ser importado por:
- `ia_pontinhos_3_4` para o pipeline tático;
- `avaliador_partidas_pontinhos` (uso futuro) para classificar entrega de
  caixas pela CNN como erro vs. sacrifício;
- `visualizador_pontinhos` (uso futuro) para enriquecer visualizações.
"""
from __future__ import annotations

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import Estrutura


# =============================================================================
# Helpers de geometria
# =============================================================================


def _arestas_da_caixa(br: int, bc: int) -> list[tuple[int, int]]:
    return [(br - 1, bc), (br + 1, bc), (br, bc - 1), (br, bc + 1)]


def _grau_jogo(estado: EstadoTabuleiro, br: int, bc: int) -> int:
    """Quantas das 4 arestas da caixa estão preenchidas (não-zero)."""
    matriz = estado.matriz
    return sum(1 for r, c in _arestas_da_caixa(br, bc) if matriz[r, c] != 0)


def _arestas_livres_da_caixa(
    estado: EstadoTabuleiro, br: int, bc: int
) -> list[tuple[int, int]]:
    matriz = estado.matriz
    return [
        (r, c) for r, c in _arestas_da_caixa(br, bc) if matriz[r, c] == 0
    ]


def _caixa_oposta(
    aresta: tuple[int, int], origem: tuple[int, int], shape: tuple[int, int]
) -> tuple[int, int] | None:
    """Caixa do outro lado de `aresta` partindo de `origem`. None se borda."""
    altura, largura = shape
    ar_r, ar_c = aresta
    br, bc = origem
    if ar_r == br - 1:
        return (br - 2, bc) if br - 2 >= 1 else None
    if ar_r == br + 1:
        return (br + 2, bc) if br + 2 < altura else None
    if ar_c == bc - 1:
        return (br, bc - 2) if bc - 2 >= 1 else None
    if ar_c == bc + 1:
        return (br, bc + 2) if bc + 2 < largura else None
    return None


def _label_aresta(r: int, c: int) -> str:
    if r % 2 == 0 and c % 2 == 1:
        return f"H_{r}_{c}"
    if r % 2 == 1 and c % 2 == 0:
        return f"V_{r}_{c}"
    raise ValueError(f"({r},{c}) não corresponde a uma aresta válida.")


# =============================================================================
# Caixas grau-3 (Passo 1)
# =============================================================================


def caixas_grau_3(estado: EstadoTabuleiro) -> list[tuple[int, int]]:
    """Retorna as caixas com 3 lados preenchidos e 1 livre.

    Caixa fechada (interior != 0) é ignorada. Saída ordenada por (br, bc)
    para determinismo.
    """
    matriz = estado.matriz
    altura, largura = matriz.shape
    resultado: list[tuple[int, int]] = []
    for br in range(1, altura, 2):
        for bc in range(1, largura, 2):
            if matriz[br, bc] != 0:
                continue
            if _grau_jogo(estado, br, bc) == 3:
                resultado.append((br, bc))
    return resultado


def aresta_que_fecha(
    estado: EstadoTabuleiro, caixa: tuple[int, int]
) -> str:
    """Label da única aresta livre de uma caixa grau-3."""
    livres = _arestas_livres_da_caixa(estado, *caixa)
    if len(livres) != 1:
        raise ValueError(
            f"Caixa {caixa} não tem exatamente 1 aresta livre "
            f"(tem {len(livres)})."
        )
    return _label_aresta(*livres[0])


# =============================================================================
# Detecção de estruturas (Phase 4 — US2)
# =============================================================================


def _eh_grau_2_aberto(estado: EstadoTabuleiro, br: int, bc: int) -> bool:
    """True se a caixa não está fechada e tem exatamente 2 arestas preenchidas."""
    if estado.matriz[br, bc] != 0:
        return False
    return _grau_jogo(estado, br, bc) == 2


def _eh_juncao(
    estado: EstadoTabuleiro,
    br: int,
    bc: int,
    grau_2: set[tuple[int, int]],
) -> bool:
    """True se a caixa é não-fechada, NÃO grau-2, e tem 3+ arestas livres
    conectando a caixas grau-2 (junta múltiplas chains)."""
    if estado.matriz[br, bc] != 0:
        return False
    if (br, bc) in grau_2:
        return False
    shape = estado.matriz.shape
    n = 0
    for ar in _arestas_livres_da_caixa(estado, br, bc):
        oposta = _caixa_oposta(ar, (br, bc), shape)
        if oposta is not None and oposta in grau_2:
            n += 1
    return n >= 3


def _adjacencia_dual(
    estado: EstadoTabuleiro, nodes: set[tuple[int, int]]
) -> dict[tuple[int, int], list[tuple[int, int]]]:
    shape = estado.matriz.shape
    adj: dict[tuple[int, int], list[tuple[int, int]]] = {n: [] for n in nodes}
    for n in nodes:
        for ar in _arestas_livres_da_caixa(estado, *n):
            oposta = _caixa_oposta(ar, n, shape)
            if oposta is not None and oposta in nodes:
                adj[n].append(oposta)
    return adj


def _ordenar_caminho(
    adj: dict[tuple[int, int], list[tuple[int, int]]],
    inicio: tuple[int, int],
) -> list[tuple[int, int]]:
    ordem = [inicio]
    visitadas = {inicio}
    while True:
        ultimo = ordem[-1]
        proximo = None
        for v in sorted(adj[ultimo]):
            if v not in visitadas:
                proximo = v
                break
        if proximo is None:
            break
        ordem.append(proximo)
        visitadas.add(proximo)
    return ordem


def _ordenar_ciclo(
    adj: dict[tuple[int, int], list[tuple[int, int]]],
    componente: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    inicio = sorted(componente)[0]
    ordem = [inicio]
    visitadas = {inicio}
    while len(ordem) < len(componente):
        ultimo = ordem[-1]
        proximo = None
        for v in sorted(adj[ultimo]):
            if v not in visitadas:
                proximo = v
                break
        if proximo is None:
            break
        ordem.append(proximo)
        visitadas.add(proximo)
    return ordem


def detectar_estruturas(estado: EstadoTabuleiro) -> list[Estrutura]:
    """Detecta todas as estruturas (correntes, ciclos, ramificações) no
    tabuleiro.

    O grafo dual considera:
    - Nós: caixas grau-2 (interior livre, 2 arestas preenchidas) + "junções"
      (caixas livres não-grau-2 com 3+ arestas livres ligando a grau-2).
    - Arestas: pares de nós que compartilham aresta-jogo livre.

    Classificação por componente:
    - "ramificada": tem nó-junção OU algum grau-2 com grau dual > 2.
    - "ciclo": componente cíclico (todos grau dual 2; n_arestas == n_nodos).
    - "corrente": caminho simples; isolada (1 caixa, 0 arestas) também é corrente
      degenerada (tamanho=1, eh_corrente_longa=False).
    - "isolada": reservada para casos não usados pela detecção atual.
    """
    matriz = estado.matriz
    altura, largura = matriz.shape

    grau_2: set[tuple[int, int]] = set()
    grau_3_aberto: set[tuple[int, int]] = set()
    for br in range(1, altura, 2):
        for bc in range(1, largura, 2):
            if matriz[br, bc] != 0:
                continue
            grau = _grau_jogo(estado, br, bc)
            if grau == 2:
                grau_2.add((br, bc))
            elif grau == 3:
                grau_3_aberto.add((br, bc))

    juncoes: set[tuple[int, int]] = set()
    for br in range(1, altura, 2):
        for bc in range(1, largura, 2):
            if _eh_juncao(estado, br, bc, grau_2):
                juncoes.add((br, bc))

    nodes = grau_2 | grau_3_aberto | juncoes
    adj = _adjacencia_dual(estado, nodes)

    visitadas: set[tuple[int, int]] = set()
    estruturas: list[Estrutura] = []

    for inicio in sorted(nodes):
        if inicio in visitadas:
            continue
        componente: list[tuple[int, int]] = []
        fila = [inicio]
        while fila:
            atual = fila.pop()
            if atual in visitadas:
                continue
            visitadas.add(atual)
            componente.append(atual)
            for v in adj[atual]:
                if v not in visitadas:
                    fila.append(v)

        deg = {n: len(adj[n]) for n in componente}
        max_deg = max(deg.values()) if deg else 0
        n_nodes = len(componente)
        n_edges = sum(deg.values()) // 2
        tem_juncao = any(n in juncoes for n in componente)

        if tem_juncao or max_deg > 2:
            apenas_grau_2 = tuple(sorted(n for n in componente if n in grau_2))
            extremidades = tuple(
                sorted(n for n in componente if n in grau_2 and deg[n] == 1)
            )
            estruturas.append(
                Estrutura(
                    tipo="ramificada",
                    caixas=apenas_grau_2,
                    extremidades=extremidades,
                )
            )
            continue

        if n_nodes == 1 and max_deg == 0:
            unica = componente[0]
            estruturas.append(
                Estrutura(
                    tipo="corrente",
                    caixas=(unica,),
                    extremidades=(unica,),
                )
            )
            continue

        if n_edges == n_nodes:
            ordem = _ordenar_ciclo(adj, componente)
            estruturas.append(
                Estrutura(
                    tipo="ciclo",
                    caixas=tuple(ordem),
                    extremidades=(),
                )
            )
        elif n_edges == n_nodes - 1:
            extremidades_grau1 = sorted(n for n, d in deg.items() if d == 1)
            ordem = _ordenar_caminho(adj, extremidades_grau1[0])
            estruturas.append(
                Estrutura(
                    tipo="corrente",
                    caixas=tuple(ordem),
                    extremidades=(ordem[0], ordem[-1]),
                )
            )
        else:
            apenas_grau_2 = tuple(sorted(n for n in componente if n in grau_2))
            extremidades = tuple(
                sorted(n for n in componente if n in grau_2 and deg[n] == 1)
            )
            estruturas.append(
                Estrutura(
                    tipo="ramificada",
                    caixas=apenas_grau_2,
                    extremidades=extremidades,
                )
            )

    return estruturas


# =============================================================================
# Análise para Passo 2 (double-dealing)
# =============================================================================


def estrutura_ativa(
    estado: EstadoTabuleiro, caixas_grau_3_lista: list[tuple[int, int]]
) -> Estrutura | None:
    """Devolve a estrutura que CONTÉM todas as caixas grau-3 informadas,
    se houver exatamente uma. Caso contrário, None.

    Com caixas grau-3 incluídas em `detectar_estruturas`, basta verificar
    pertinência direta (subset) em vez de adjacência.
    """
    if not caixas_grau_3_lista:
        return None
    estruturas = detectar_estruturas(estado)
    if not estruturas:
        return None

    grau_3_set = set(caixas_grau_3_lista)
    candidatas: list[Estrutura] = []
    for est in estruturas:
        if grau_3_set <= set(est.caixas):
            candidatas.append(est)

    if len(candidatas) != 1:
        return None
    return candidatas[0]


def _eh_subsequencia_contigua_no_ciclo(
    subset: set[tuple[int, int]], ordem: tuple[tuple[int, int], ...]
) -> bool:
    n = len(ordem)
    k = len(subset)
    if k == 0 or k > n:
        return False
    for i in range(n):
        janela = {ordem[(i + j) % n] for j in range(k)}
        if janela == subset:
            return True
    return False


def trigger_double_dealing(
    estrutura: Estrutura | None, caixas_grau_3_lista: list[tuple[int, int]]
) -> bool:
    """True quando as caixas grau-3 estão numa extremidade de uma corrente
    longa (≥ 3) com exatamente 2 caixas não-grau-3 restantes na outra
    extremidade, OU formam ≥ 4 caixas contíguas de um ciclo.

    A condição 'exatamente 2 restantes' garante que o trigger dispara apenas
    quando o agente está no ponto correto da cascata — com 2 caixas grau-2
    para oferecer ao adversário via double-cross.
    """
    if estrutura is None or not caixas_grau_3_lista:
        return False
    grau_3_set = set(caixas_grau_3_lista)

    if estrutura.tipo == "corrente" and estrutura.eh_corrente_longa:
        caixas = estrutura.caixas
        n = len(caixas)
        n_g3 = len(grau_3_set & set(caixas))
        if n_g3 == 0:
            return False
        n_remaining = n - n_g3
        if n_remaining != 2:
            return False
        # Grau-3 deve ser contíguo numa extremidade
        from_start = 0
        for c in caixas:
            if c in grau_3_set:
                from_start += 1
            else:
                break
        if from_start == n_g3:
            return True
        from_end = 0
        for c in reversed(caixas):
            if c in grau_3_set:
                from_end += 1
            else:
                break
        if from_end == n_g3:
            return True
        return False

    if estrutura.tipo == "ciclo":
        if len(caixas_grau_3_lista) < 4:
            return False
        if estrutura.tamanho == 4:
            return grau_3_set == set(estrutura.caixas)
        return _eh_subsequencia_contigua_no_ciclo(grau_3_set, estrutura.caixas)

    return False


# =============================================================================
# Captura completa vs. double-cross — escolha de aresta e simulação
# =============================================================================


def primeira_aresta_de_captura(
    estrutura: Estrutura, estado: EstadoTabuleiro
) -> str:
    """Aresta para iniciar a captura completa de uma corrente/ciclo: fecha a
    PRIMEIRA caixa grau-3 da estrutura (menor índice canônico)."""
    grau_3_na_estrutura = [c for c in estrutura.caixas if _grau_jogo(estado, *c) == 3]
    if not grau_3_na_estrutura:
        raise ValueError("Estrutura não contém caixas grau-3 para capturar.")
    grau_3_na_estrutura.sort()
    return aresta_que_fecha(estado, grau_3_na_estrutura[0])


def _par_sacrificio_corrente(
    estrutura: Estrutura, estado: EstadoTabuleiro
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Retorna as 2 caixas grau-2 a sacrificar (extremidade oposta à abertura
    grau-3). Usada para correntes longas no cenário de double-dealing."""
    caixas = estrutura.caixas
    if _grau_jogo(estado, *caixas[0]) == 3:
        # Abertura no início → sacrificar as últimas 2
        return caixas[-2], caixas[-1]
    else:
        # Abertura no fim (ou sem grau-3 explícito) → sacrificar as primeiras 2
        return caixas[0], caixas[1]


def aresta_double_cross(
    estrutura: Estrutura, estado: EstadoTabuleiro
) -> str:
    """Aresta de double-cross: a aresta INTERNA entre as 2 caixas grau-2 a
    serem sacrificadas. Preenchê-la faz ambas saltarem para grau-3, oferecendo-as
    ao adversário sem pontuar."""
    if estrutura.tipo == "corrente":
        if estrutura.tamanho < 3:
            raise ValueError("Corrente curta demais para double-cross.")
        a, b = _par_sacrificio_corrente(estrutura, estado)
        return _aresta_entre_caixas(a, b)
    if estrutura.tipo == "ciclo":
        if estrutura.tamanho < 4:
            raise ValueError("Ciclo curto demais para double-cross.")
        a, b = estrutura.caixas[-2], estrutura.caixas[-1]
        return _aresta_entre_caixas(a, b)
    raise ValueError(f"Estrutura tipo {estrutura.tipo!r} não suporta double-cross.")


def _aresta_entre_caixas(c1: tuple[int, int], c2: tuple[int, int]) -> str:
    br1, bc1 = c1
    br2, bc2 = c2
    if br1 == br2 and abs(bc1 - bc2) == 2:
        return _label_aresta(br1, (bc1 + bc2) // 2)
    if bc1 == bc2 and abs(br1 - br2) == 2:
        return _label_aresta((br1 + br2) // 2, bc1)
    raise ValueError(f"Caixas {c1} e {c2} não compartilham aresta.")


def estado_apos_captura_completa(
    estado: EstadoTabuleiro, estrutura: Estrutura, jogador: int
) -> EstadoTabuleiro:
    """Simula o jogador capturando TODAS as caixas grau-3 da estrutura em
    sequência (cascata). Retorna estado clonado pós-cascata."""
    novo = estado.clonar()
    while True:
        grau_3 = [c for c in estrutura.caixas if _grau_jogo(novo, *c) == 3]
        if not grau_3:
            break
        grau_3.sort()
        aresta = aresta_que_fecha(novo, grau_3[0])
        novo.aplicar_traco(aresta, jogador)
    return novo


def estado_apos_double_cross(
    estado: EstadoTabuleiro, estrutura: Estrutura, jogador: int
) -> EstadoTabuleiro:
    """Simula o jogador executando o double-cross: preenche a aresta de
    sacrifício entre as 2 caixas grau-2 na extremidade oposta à abertura.

    Como `escolher_jogada` retorna UMA aresta por chamada, a ação do
    double-cross é um único movimento: preencher a aresta entre as 2 caixas
    a sacrificar (ambas grau-2 → ambas viram grau-3, sem pontuar).
    Retorna estado clonado pós-sacrifício.
    """
    novo = estado.clonar()
    aresta_dc = aresta_double_cross(estrutura, estado)
    r = int(aresta_dc.split("_")[1])
    c = int(aresta_dc.split("_")[2])
    if novo.matriz[r, c] == 0:
        novo.aplicar_traco(aresta_dc, jogador)
    return novo

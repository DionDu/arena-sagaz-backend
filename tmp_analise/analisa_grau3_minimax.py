"""Análise de estados com caixas de grau 3 no dataset Minimax(p=9).

Objetivo: validar se a rotulagem Minimax escolhe a jogada gulosa (fechar uma
caixa de grau 3) em todos os estados onde isso seria possível, e identificar
os estados onde a escolha NÃO gulosa é justificada pela exceção clássica do
sacrifício / double-dealing (Berlekamp) — e, mais importante, os estados onde
a escolha não gulosa NÃO se justifica (potenciais erros de rotulagem).

Contexto: tabuleiro pequeno 4 caixas × 3 caixas (matriz 9×7). Arestas horizontais
em (par, ímpar), verticais em (ímpar, par), interior de caixa em (ímpar, ímpar).
Valor 9 = aresta preenchida; 1 = caixa fechada; 8 = ponto fixo; 0 = vazio.

Saída: tabela com as 4 fases do jogo (conforme Treinamento_CNN_V5.ipynb).

Colunas:
1. Fase do jogo
2. Qtd. estados
3. Qtd. estados com ≥1 caixa de grau 3
4. Qtd. desses estados em que Minimax NÃO escolheu captura gulosa
5. Dos não-gulosos: quantos se explicam por sacrifício (corrente ≥3 ou ciclo ≥4)
6. ERRO = não-gulosos que NÃO se explicam por sacrifício
"""

from __future__ import annotations

import glob
import os
from collections import defaultdict
from typing import Iterable, List, Tuple

import numpy as np

SCORE_IND = -1e8  # qualquer score abaixo disso é "jogada inválida" (-1e9 original)

# --------------------------------------------------------------------------
# Geometria do tabuleiro pequeno (4 linhas × 3 colunas de caixas → matriz 9×7)
# --------------------------------------------------------------------------
LINHAS_CAIXAS = 4
COLUNAS_CAIXAS = 3
H_MATRIZ, W_MATRIZ = 9, 7

# Posições das caixas (ímpar, ímpar). 12 caixas.
POS_CAIXAS: List[Tuple[int, int]] = [
    (r, c) for r in range(1, H_MATRIZ, 2) for c in range(1, W_MATRIZ, 2)
]

# Labels canônicos — mesma ordem varredura linha-a-linha do contrato.
LABELS_CANONICOS: List[str] = []
for _r in range(H_MATRIZ):
    for _c in range(W_MATRIZ):
        if (_r % 2 == 0 and _c % 2 == 1):
            LABELS_CANONICOS.append(f'H_{_r}_{_c}')
        elif (_r % 2 == 1 and _c % 2 == 0):
            LABELS_CANONICOS.append(f'V_{_r}_{_c}')
assert len(LABELS_CANONICOS) == 31, len(LABELS_CANONICOS)
LABEL_TO_IDX = {l: i for i, l in enumerate(LABELS_CANONICOS)}


def arestas_da_caixa(r: int, c: int) -> List[Tuple[int, int]]:
    """Posições (linha, coluna) das 4 arestas em volta da caixa (r, c)."""
    return [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]


def grau(mat: np.ndarray, r: int, c: int) -> int:
    """Nº de arestas preenchidas (valor 9) em volta da caixa (r, c)."""
    return sum(1 for (rr, cc) in arestas_da_caixa(r, c) if mat[rr, cc] == 9)


def aresta_faltante(mat: np.ndarray, r: int, c: int) -> Tuple[int, int] | None:
    """Se caixa (r,c) tem grau 3, retorna a posição da única aresta aberta."""
    abertas = [(rr, cc) for (rr, cc) in arestas_da_caixa(r, c) if mat[rr, cc] != 9]
    return abertas[0] if len(abertas) == 1 else None


def label_da_aresta(r: int, c: int) -> str:
    if r % 2 == 0:
        return f'H_{r}_{c}'
    return f'V_{r}_{c}'


# --------------------------------------------------------------------------
# Fase do jogo — mesma regra do notebook V5 (1.3b)
# --------------------------------------------------------------------------
FASE_NOMES = {
    0: 'Abertura (0-9)',
    1: '1ª Metade (10-17)',
    2: '2ª Metade (18-25)',
    3: 'Final (26-31)',
}


def fase_do_estado(mat: np.ndarray) -> int:
    """Classifica a fase com base em nº de traços preenchidos (após normalização)."""
    # Aqui o estado ainda está no encoding cru {0,1,8,9}: contamos os 9s nas
    # posições de aresta (par×ímpar ou ímpar×par).
    n = 0
    for r in range(H_MATRIZ):
        for c in range(W_MATRIZ):
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                if mat[r, c] == 9:
                    n += 1
    if n < 10:
        return 0
    if n < 18:
        return 1
    if n < 26:
        return 2
    return 3


# --------------------------------------------------------------------------
# Análise da jogada do Minimax
# --------------------------------------------------------------------------
def jogadas_otimas(scores: np.ndarray) -> List[int]:
    """Índices canônicos das jogadas empatadas no score máximo válido."""
    validos = scores > SCORE_IND
    if not validos.any():
        return []
    max_s = scores[validos].max()
    return [int(i) for i, s in enumerate(scores) if s > SCORE_IND and s == max_s]


def arestas_que_fecham_grau3(mat: np.ndarray) -> set:
    """Conjunto de índices canônicos cujas arestas fecham alguma caixa de grau 3.

    Se existe mais de uma caixa grau-3 cuja aresta faltante é a mesma,
    ela é adicionada uma única vez.
    """
    out = set()
    for (r, c) in POS_CAIXAS:
        if mat[r, c] == 1:
            continue  # caixa já fechada
        if grau(mat, r, c) == 3:
            aa = aresta_faltante(mat, r, c)
            if aa is not None:
                out.add(LABEL_TO_IDX[label_da_aresta(*aa)])
    return out


# --------------------------------------------------------------------------
# Simulação da captura gulosa — quantas caixas encadeadas podemos fechar
# --------------------------------------------------------------------------
def simular_captura_gulosa(mat: np.ndarray) -> Tuple[int, bool]:
    """Aplica a política gulosa: enquanto houver caixa de grau 3, fecha-a.

    Retorna (qtd_caixas_capturadas, formou_ciclo).

    'formou_ciclo' é uma heurística: retornamos True se a última aresta jogada
    fechou DUAS caixas de grau 3 no mesmo passo (assinatura de ciclo) OU se a
    sequência começou com nenhuma 'ponta' inicial clara (todas as caixas que
    viraram grau-3 eram "interiores" de uma cadeia fechada).

    Para a pergunta deste estudo basta o tamanho da sequência e se é ciclo.
    """
    m = mat.copy()
    capturas = 0
    formou_ciclo = False

    while True:
        # Colete todas as caixas atualmente em grau 3.
        grau3 = [(r, c) for (r, c) in POS_CAIXAS if m[r, c] != 1 and grau(m, r, c) == 3]
        if not grau3:
            break

        # Captura UMA caixa grau-3 por iteração (fechando a aresta faltante).
        (r, c) = grau3[0]
        ar = aresta_faltante(m, r, c)
        if ar is None:
            break
        m[ar] = 9

        # Conta quantas caixas fecharam com essa única aresta (1 ou 2).
        fechou = 0
        for (rr, cc) in POS_CAIXAS:
            if m[rr, cc] != 1 and grau(m, rr, cc) == 4:
                m[rr, cc] = 1
                fechou += 1
        capturas += fechou
        if fechou == 2:
            # Dois fechamentos num mesmo passo → ciclo (aresta compartilhada).
            formou_ciclo = True

    return capturas, formou_ciclo


def sacrificio_aplicavel(mat: np.ndarray) -> bool:
    """A exceção de Berlekamp se aplica neste estado?

    Regra operacional: se a captura gulosa completa TOMA (a) uma corrente de
    ≥3 caixas OU (b) um ciclo de ≥4 caixas, então o jogador tem a opção de
    double-dealing (sacrificar as 2 últimas caixas da corrente, ou 4 últimas
    caixas do ciclo) — portanto escolher não capturar é racional.
    """
    capturas, ciclo = simular_captura_gulosa(mat)
    if ciclo:
        return capturas >= 4
    return capturas >= 3


# --------------------------------------------------------------------------
# Varredura de todos os NPZs
# --------------------------------------------------------------------------
def analisar(arquivos: Iterable[str]) -> None:
    # Contadores por fase
    total_estados = defaultdict(int)
    com_grau3 = defaultdict(int)
    nao_guloso = defaultdict(int)
    nao_guloso_sacrificio = defaultdict(int)
    nao_guloso_erro = defaultdict(int)

    # Distribuição da diferença de score (Minimax ótimo - gulosa) nos casos ERRO.
    # Se 0, Minimax trata empatadas; se grande, Minimax enxerga muito além.
    delta_erro = defaultdict(list)  # fase -> lista de deltas

    # Amostras de erro para inspeção posterior
    exemplos_erro = []

    total_arquivos = 0
    total_linhas = 0

    for arq in arquivos:
        total_arquivos += 1
        d = np.load(arq, allow_pickle=True)
        estados = d['estados']
        scores = d['scores']
        n = len(estados)
        total_linhas += n

        for i in range(n):
            mat = estados[i]
            f = fase_do_estado(mat)
            total_estados[f] += 1

            arestas_fecham = arestas_que_fecham_grau3(mat)
            if not arestas_fecham:
                continue  # nenhuma caixa grau-3 disponível

            com_grau3[f] += 1

            otimas = set(jogadas_otimas(scores[i]))
            # Gulosa = pelo menos uma jogada ótima do Minimax fecha grau-3.
            if otimas & arestas_fecham:
                continue  # Minimax foi guloso

            # Não gulosa: o Minimax escolheu (apenas) jogadas que NÃO fecham
            # caixa grau-3.
            nao_guloso[f] += 1

            if sacrificio_aplicavel(mat):
                nao_guloso_sacrificio[f] += 1
            else:
                nao_guloso_erro[f] += 1
                # Delta = score do Minimax - score da melhor jogada gulosa.
                sc_otimo = max(scores[i][j] for j in otimas) if otimas else 0.0
                sc_guloso = max(scores[i][j] for j in arestas_fecham)
                delta_erro[f].append(float(sc_otimo - sc_guloso))
                if len(exemplos_erro) < 5:
                    exemplos_erro.append((arq, i, mat.copy(), scores[i].copy(),
                                          arestas_fecham, otimas))

    # --------------------------------------------------------------
    # Relatório
    # --------------------------------------------------------------
    print()
    print(f'Arquivos processados: {total_arquivos}')
    print(f'Estados (linhas) lidos: {total_linhas:,}')
    print()
    hdr = (
        f'{"Fase":<22}'
        f'{"Estados":>10}'
        f'{"com grau3":>12}'
        f'{"nao guloso":>14}'
        f'{"sacrificio":>14}'
        f'{"ERRO":>10}'
    )
    print(hdr)
    print('-' * len(hdr))
    tot = [0] * 5
    for f in (0, 1, 2, 3):
        linha = (
            f'{FASE_NOMES[f]:<22}'
            f'{total_estados[f]:>10,}'
            f'{com_grau3[f]:>12,}'
            f'{nao_guloso[f]:>14,}'
            f'{nao_guloso_sacrificio[f]:>14,}'
            f'{nao_guloso_erro[f]:>10,}'
        )
        print(linha)
        tot[0] += total_estados[f]
        tot[1] += com_grau3[f]
        tot[2] += nao_guloso[f]
        tot[3] += nao_guloso_sacrificio[f]
        tot[4] += nao_guloso_erro[f]
    print('-' * len(hdr))
    print(
        f'{"TOTAL":<22}'
        f'{tot[0]:>10,}'
        f'{tot[1]:>12,}'
        f'{tot[2]:>14,}'
        f'{tot[3]:>14,}'
        f'{tot[4]:>10,}'
    )

    # Distribuição do delta de score nos casos ERRO
    print()
    print('Distribuição do delta de score (Minimax - gulosa) nos casos ERRO:')
    print(f'  {"Fase":<22}{"n":>6}{"min":>8}{"media":>8}{"mediana":>8}{"max":>8}'
          f'{"delta=0":>10}')
    for f in (0, 1, 2, 3):
        ds = delta_erro[f]
        if not ds:
            print(f'  {FASE_NOMES[f]:<22}{0:>6}')
            continue
        arr = np.array(ds)
        iguais = int((arr == 0).sum())
        print(f'  {FASE_NOMES[f]:<22}{len(arr):>6}{arr.min():>8.1f}'
              f'{arr.mean():>8.2f}{np.median(arr):>8.1f}{arr.max():>8.1f}'
              f'{iguais:>10}')
    print('  Legenda: delta=0 => gulosa era Minimax-equivalente (ERRO de')
    print('  heurística, não do Minimax). delta grande => Minimax enxergou')
    print('  além da cadeia local; gulosa é realmente pior.')

    if exemplos_erro:
        print()
        print('Exemplos de estados ERRO (até 5):')
        for (arq, idx, mat, sc, fecha, otimas) in exemplos_erro:
            print()
            print(f'  Arquivo: {os.path.basename(arq)}  linha={idx}')
            print(f'  Jogadas que fechariam grau-3: '
                  f'{sorted(LABELS_CANONICOS[i] for i in fecha)}')
            print(f'  Jogadas ótimas Minimax:        '
                  f'{sorted(LABELS_CANONICOS[i] for i in otimas)}')
            print('  Matriz:')
            for row in mat:
                print('   ', ' '.join(f'{int(v):2d}' for v in row))


def main():
    pasta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'dados', 'profundidade_minmax_9',
    )
    arquivos = sorted(glob.glob(os.path.join(pasta, '*.npz')))
    if not arquivos:
        raise SystemExit(f'Nenhum NPZ encontrado em {pasta}')
    print(f'Lendo de: {pasta}')
    print(f'Total de arquivos: {len(arquivos)}')
    analisar(arquivos)


if __name__ == '__main__':
    main()

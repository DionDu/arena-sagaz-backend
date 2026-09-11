"""T049h - extrai do AUTOPLAY as posicoes de partida do desafio de Pontinhos.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

Ate 11/09/2026 o gerador sorteava os tracos da posicao inicial **as cegas**, e o
comentario que justificava isso dizia que *"o acaso e o que da variedade a fila"*.

⛔ **E o mesmo argumento que o projeto ja testou e DESCARTOU**, no treino da CNN:
o dataset de tabuleiros aleatorios deu uma rede ruim, porque dois jogadores
quase nunca chegam aqueles estados. Foi por isso que se passou ao **autoplay de
minimax** — e a rede melhorou muito.

⚠️ E aqui a consequencia de reintroduzir o acaso e **concreta**, nao teorica: o
gabarito do desafio e produzido **pela propria CNN** (o backend roda o mesmo
`.tflite` do aplicativo, e o portao T001 existe para provar que os dois runtimes
concordam). Uma posicao fora da distribuicao de treino produz uma *solucao de
referencia* subotima, a regua mede a coisa errada — e ⛔ **nada no log denuncia**.

═══════════════════════════════════════════════════════════════════════════
⚠️ A PONTE NAO E DIRETA, E O MOTIVO IMPORTA
═══════════════════════════════════════════════════════════════════════════

O desafio guarda uma **sequencia de lances** (`co_formato_posicao =
'sequencia_lances'`), e nao uma matriz: a posse de uma caixa e **historico**, e
de quem e a vez depende de quem fechou caixa. Os NPZ tem so a matriz `9x7`, e os
valores `{0, 1, 8, 9}` dizem *que* uma caixa esta fechada, mas nao **de quem**
ela e.

✅ **A saida sao as posicoes SEM NENHUMA CAIXA FECHADA.** Nelas:

    - o placar e 0-0, entao nao ha dono de caixa a reconstruir;
    - a vez sai da paridade, porque ninguem ganhou turno extra;
    - ⚠️ **qualquer ordem dos mesmos tracos da o mesmo estado** — e essa e a
      propriedade que transforma um conjunto de tracos de volta numa sequencia
      legal. Ela vale porque "sem caixa fechada" e **monotono**: se o conjunto
      final nao fecha caixa nenhuma, nenhum prefixo dele fecha.

Por isso cada posicao cabe num **inteiro de 32 bits**: um bit por traco, na ordem
canonica dos 31 rotulos. E por isso o arquivo de saida tem 2,58 MB onde os NPZ
de origem tem 106 MB.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\extrair_posicoes_de_autoplay_pontinhos.py

Leva poucos segundos (419 arquivos, ~3,4 milhoes de estados). Ele imprime a
distribuicao por quantidade de tracos e reescreve o arquivo de saida.

⚠️ **A saida e ORDENADA de forma deterministica** (por quantidade de tracos e,
dentro dela, pelo valor da mascara). Rodar de novo sobre a mesma origem produz
um arquivo byte-identico — e e isso que permite reconstruir o artefato sem
deslocar a fila que a semente do dia ja escolheu.

⛔ **A origem e o laboratorio, e ela NAO viaja para o Railway.** Quem vai para o
repositorio e so o arquivo de saida; os NPZ ficam em `../ia/dados/`.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

import numpy as np

# `parents[1]` sobe de `scripts/este_arquivo.py` para a raiz do backend.
RAIZ = Path(__file__).resolve().parents[1]

#: A pasta do laboratorio com os estados de autoplay.
#:
#: ⚠️ **As tres pastas de `dados/jogo_pontinhos/` carregam os MESMOS estados** —
#: medido em 11/09/2026: 3.423.460 em cada uma, com as mesmas 897.125 posicoes
#: sem caixa fechada. O que muda entre elas sao os rotulos e os canais, e nao os
#: tabuleiros. Escolhemos esta porque o nome diz de onde os estados vieram:
#: autoplay de minimax com profundidade adaptativa.
ORIGEM = RAIZ.parent / "ia" / "dados" / "jogo_pontinhos" / "profundidade_minimax_11_adaptativo"

#: O arquivo que o job le em producao.
DESTINO = RAIZ / "dados" / "jogo_pontinhos" / "posicoes_de_autoplay_pequeno.npz"

#: Quantos tracos tem o tabuleiro 4x3. E o teto do bitmask.
TRACOS_DO_TABULEIRO = 31


def _coordenadas_dos_rotulos(rotulos: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Traduz `H_0_1` / `V_1_0` no par (linha, coluna) da matriz 9x7.

    O rotulo e `<orientacao>_<linha>_<coluna>`, e a posicao na matriz e
    literalmente a linha e a coluna que ele nomeia — o dataset e a matriz da
    partida usam a mesma grade. Devolve dois vetores para que a leitura de todos
    os 31 tracos de todos os estados vire **uma** indexacao de numpy
    (`estados[:, linhas, colunas]`), em vez de um laco de 31 x N.
    """
    linhas = np.array([int(r.split("_")[1]) for r in rotulos])
    colunas = np.array([int(r.split("_")[2]) for r in rotulos])
    return linhas, colunas


def _mascaras_sem_caixa(
    estados: np.ndarray, linhas: np.ndarray, colunas: np.ndarray, pesos: np.ndarray
) -> np.ndarray:
    """Converte um lote de matrizes nas mascaras das posicoes SEM caixa fechada.

    Args:
        estados: `(N, 9, 7)` em `{0, 1, 8, 9}`, como vem do NPZ.
        linhas, colunas: onde estao os 31 tracos, na ordem canonica.
        pesos: `2**0 .. 2**30`, para somar os bits ligados num uint32 so.

    ⚠️ **A caixa fechada mora nas posicoes impar/impar da matriz** — e o que o
    contrato de codificacao declara, e e por isso que o recorte e
    `[:, 1::2, 1::2]`. Valor diferente de zero ali significa caixa fechada, sem
    dizer de quem.
    """
    # `.all(axis=(1, 2))` reduz cada matriz de caixas a um unico booleano: ela
    # so sobrevive se TODAS as 12 caixas estiverem abertas.
    sem_caixa = (estados[:, 1::2, 1::2] == 0).all(axis=(1, 2))
    sobreviventes = estados[sem_caixa]

    # ⚠️ No dataset o traco marcado vale 9 e o vazio vale 0 — mas comparar com
    # `!= 0` em vez de `== 9` deixa a leitura correta mesmo que um dia a matriz
    # chegue na convencao da partida (`{-1, 0, 1, 8}`).
    bits = sobreviventes[:, linhas, colunas] != 0
    return (bits.astype(np.uint32) * pesos).sum(axis=1, dtype=np.uint32)


def principal() -> int:
    """Le os NPZ, filtra, deduplica, ordena e grava. Devolve o codigo de saida."""
    if not ORIGEM.is_dir():
        print(f"⛔ a pasta de origem nao existe: {ORIGEM}")
        print("   Ela e do laboratorio de IA, e nao viaja no repositorio do backend.")
        return 2

    arquivos = sorted(ORIGEM.glob("dataset_pequeno_*.npz"))
    if not arquivos:
        print(f"⛔ nenhum dataset_pequeno_*.npz em {ORIGEM}")
        return 2

    print(f"origem  : {ORIGEM}")
    print(f"arquivos: {len(arquivos)}")

    # A ordem canonica dos 31 rotulos vem do PROPRIO dataset, e nao de uma lista
    # escrita aqui. ⚠️ Ela e gravada junto com as mascaras no arquivo de saida,
    # para que decodificar um bit nunca dependa de uma convencao combinada de
    # boca — e `test_posicoes_de_autoplay_pontinhos.py` confere que ela bate com a ordem
    # que o motor do backend usa.
    rotulos = [str(x) for x in np.load(arquivos[0])["labels_canonicos"]]
    if len(rotulos) != TRACOS_DO_TABULEIRO:
        print(f"⛔ o dataset traz {len(rotulos)} rotulos, e o 4x3 tem {TRACOS_DO_TABULEIRO}")
        return 2

    linhas, colunas = _coordenadas_dos_rotulos(rotulos)
    pesos = np.uint32(1) << np.arange(TRACOS_DO_TABULEIRO, dtype=np.uint32)

    lidos = 0
    sem_caixa = 0
    lotes: list[np.ndarray] = []
    for arquivo in arquivos:
        estados = np.load(arquivo)["estados"]
        lidos += len(estados)
        mascaras = _mascaras_sem_caixa(estados, linhas, colunas, pesos)
        sem_caixa += len(mascaras)
        lotes.append(mascaras)

    # `np.unique` ja devolve ordenado e sem repeticao — as duas coisas de uma vez.
    distintas = np.unique(np.concatenate(lotes))
    tracos = np.bitwise_count(distintas)

    # ⚠️ **A ordenacao final e (quantidade de tracos, valor da mascara)**, e nao
    # so o valor. E ela que torna "as posicoes com N tracos" uma fatia contigua
    # do vetor, para o job nao precisar varrer 897 mil entradas a cada dia.
    # `kind="stable"` garante que, dentro de um mesmo N, a ordem crescente que o
    # `np.unique` produziu se mantem — e e isso que faz duas execucoes deste
    # script darem o mesmo arquivo.
    ordem = np.argsort(tracos, kind="stable")
    distintas = distintas[ordem]
    tracos = tracos[ordem]

    print()
    print(f"estados lidos            : {lidos}")
    print(f"sem nenhuma caixa fechada: {sem_caixa}")
    print(f"posicoes DISTINTAS       : {len(distintas)}")
    print()
    print("distribuicao por quantidade de tracos:")
    for n, quantas in sorted(collections.Counter(tracos.tolist()).items()):
        print(f"  {n:2d} tracos: {quantas:>7d}")

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    # `savez_compressed` e nao `savez`: as mascaras sao quase aleatorias e
    # comprimem pouco, mas os rotulos e o cabecalho comprimem bem, e o arquivo
    # vive no Git.
    np.savez_compressed(
        DESTINO,
        nu_mascara=distintas,
        co_rotulo=np.array(rotulos),
    )
    print()
    print(f"gravado: {DESTINO}")
    print(f"tamanho: {DESTINO.stat().st_size / 1_048_576:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(principal())

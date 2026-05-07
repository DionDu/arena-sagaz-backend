"""Executa o equivalente da célula 1 do notebook Avaliacao_CNN_vs_Minimax.

Saída: visualizacoes/avaliacao_partidas/<EXEC_ID>/minimax_p<prof>/*.png|*.md
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# Silencia logs do TF antes de importar.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

# Garante que conseguimos importar o pacote backend.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tqdm import tqdm  # noqa: E402

from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import (  # noqa: E402
    avaliar_paralelo,
    imprimir_relatorio,
    todos_labels_canonicos,
)


def main():
    CAMINHO_MODELO = str(ROOT / "modelos" / "pontinhos_pequeno_profundidade_9.tflite")
    TAMANHO = "pequeno"
    N_PARTIDAS = 400
    PROFUNDIDADES = [1, 3]
    TIMER_MS = 0
    MAX_WORKERS = 14

    SALVAR_CAIXAS_PERDIDAS = True
    BASE_VIS = ROOT / "visualizacoes" / "avaliacao_partidas"
    EXEC_ID = (
        f"{Path(CAMINHO_MODELO).stem}__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    EXEC_DIR = BASE_VIS / EXEC_ID

    labels = todos_labels_canonicos(4, 3)
    stats_list = []

    print(f"Modelo: {CAMINHO_MODELO}")
    print(f"Saída de visualizações: {EXEC_DIR}")
    print(f"Profundidades: {PROFUNDIDADES}  |  Partidas/prof: {N_PARTIDAS}")

    for prof in PROFUNDIDADES:
        nome = f"Minimax(p={prof})"
        with tqdm(
            total=N_PARTIDAS,
            desc=f"{nome:25s}",
            unit="partida",
            leave=True,
        ) as pbar:
            c = [0, 0, 0, 0, 0]

            def _cb(completed, total, result, _pbar=pbar, _c=c):
                if result["vencedor"] == 1:
                    _c[0] += 1
                elif result["vencedor"] == 0:
                    _c[1] += 1
                else:
                    _c[2] += 1
                _c[3] += result.get("opp_perdidas_a1", 0)
                _c[4] += result.get("opp_total_a1", 0)
                _pbar.update(completed - _pbar.n)
                postfix = {"V": _c[0], "E": _c[1], "D": _c[2]}
                if _c[4] > 0:
                    postfix["?caixa"] = f"{_c[3]}/{_c[4]}"
                _pbar.set_postfix(postfix)

            saida_misses = (
                EXEC_DIR / f"minimax_p{prof}" if SALVAR_CAIXAS_PERDIDAS else None
            )
            s = avaliar_paralelo(
                CAMINHO_MODELO,
                labels,
                prof,
                nome,
                TAMANHO,
                N_PARTIDAS,
                TIMER_MS,
                MAX_WORKERS,
                progress_callback=_cb,
                salvar_caixas_perdidas_em=saida_misses,
            )
        stats_list.append(s)

    imprimir_relatorio(stats_list)
    print(f"\nEXEC_DIR: {EXEC_DIR}")
    return EXEC_DIR


if __name__ == "__main__":
    main()

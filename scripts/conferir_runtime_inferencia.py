"""T001 - CONFERE O RUNTIME DE INFERENCIA DA IMAGEM DO JOB (RF-DES-018b).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

O job em batch do Desafio do Dia precisa jogar Pontinhos no servidor, e o
adversario do Pontinhos e uma CNN que vive num arquivo `.tflite` de 19,8 MB -
o MESMO arquivo embarcado no aplicativo (RF-DES-018b). O `research.md` §R-03
decidiu que a imagem do job roda **Python 3.11** com **`ai-edge-litert`**, e
deixou uma pergunta em aberto, que e a razao desta tarefa existir:

    "a versao exata de `ai-edge-litert` que instala em linux/amd64 + Python
     3.11 e abre o `.tflite` de 19,8 MB. Se nao instalar, o plano B e
     `tensorflow-cpu` (imagem muito maior, mesmo resultado) - nunca
     reimplementar a inferencia."

⚠️ **O risco nao e "nao instalar".** Esse falha alto e cedo. O risco de
verdade e instalar, abrir o modelo e devolver numeros **um pouco** diferentes
dos que o aplicativo devolve: a calibracao do desafio sairia de um adversario
que nao e o adversario que a pessoa enfrenta, e nada no sistema denunciaria.
Por isso este script nao pergunta "abriu?" - ele pergunta **"deu o mesmo
numero?"**, comparando contra um arquivo de referencia versionado.

═══════════════════════════════════════════════════════════════════════════
COMO ELE PROVA ISSO
═══════════════════════════════════════════════════════════════════════════

1. Monta N tensores de entrada **deterministicos** - gerados por semente fixa,
   no dominio {0.0, 1.0} e na forma (1, 4, 3, 12) que o modelo de 12 canais
   espera (ver `encoding_cnn.dart` do app e `analisador_estrutural_pontinhos.py`
   do laboratorio). Semente fixa significa que qualquer maquina, em qualquer
   sistema operacional, monta **exatamente** os mesmos tensores.
2. Roda a inferencia com o runtime escolhido em `--runtime`.
3. Compara a saida, arredondada, com `scripts/referencia_runtime_inferencia.json`.

O arquivo de referencia e o **contrato**: quem o gerou foi o runtime que o app
usa (`tensorflow`, a mesma biblioteca C que o `tflite_flutter` embrulha). Se o
`ai-edge-litert` bater com ele, trocar de runtime e seguro.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    # 1) Gerar a referencia com o runtime DO APP (venv do laboratorio, 3.12):
    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    ..\\ia\\.venv_tf\\Scripts\\python scripts\\conferir_runtime_inferencia.py --runtime tensorflow --gravar-referencia

    # 2) Conferir com o runtime DO JOB. ⚠️ Isto NAO se roda a mao: e o
    #    `Dockerfile.job` que o roda, no build da imagem que vai para o Railway.

Codigo de saida 0 = confere. Diferente de 0 = **nao troque o runtime**.

═══════════════════════════════════════════════════════════════════════════
POR QUE A CONFERENCIA IN-IMAGE E UM PORTAO DE BUILD, E NAO UM COMANDO
═══════════════════════════════════════════════════════════════════════════

A maquina do dono nao tem Docker, nem WSL, nem Python 3.11 - conferido em
09/09/2026. Rodar isto em `linux/amd64` a mao exigiria instalar um dos tres so
para esta conferencia.

Entao a chamada mora dentro do `Dockerfile.job`, depois do `pip install`: se o
runtime da imagem divergir da referencia versionada, **o build falha**.

⚠️ **E melhor assim, e nao e um contorno.** Um comando manual se roda uma vez e
envelhece; o portao re-confere a cada imagem construida - inclusive no dia em que
alguem subir a versao do `ai-edge-litert` sem pensar. E ele e a UNICA execucao em
`linux/amd64` que o projeto tem.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np

# ── Onde as coisas moram ────────────────────────────────────────────────────
# `Path(__file__).parents[1]` sobe um nivel a partir deste arquivo: de
# `scripts/conferir_runtime_inferencia.py` para a raiz do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]

# O modelo tem duas casas possiveis, e a ordem importa: dentro da imagem do job
# so existe a copia do espelho (RF-DES-148); na maquina do dono, o app e quem o
# tem. Procuramos nessa ordem e usamos a primeira que existir.
NOME_DO_MODELO = (
    "pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento2_8p3M.tflite"
)
CAMINHOS_DO_MODELO = (
    RAIZ_BACKEND / "espelho_laboratorio" / "modelos" / NOME_DO_MODELO,
    RAIZ_BACKEND.parent
    / "arena-sagaz-frontend"
    / "assets"
    / "jogos"
    / "pontinhos"
    / "modelos"
    / NOME_DO_MODELO,
)

ARQUIVO_REFERENCIA = RAIZ_BACKEND / "scripts" / "referencia_runtime_inferencia.json"

# ── O que se espera do modelo pequeno ───────────────────────────────────────
# 4x3 caixas, 12 canais na entrada; 31 tracos possiveis na saida. Os numeros vem
# de `contrato_codificacao_pontinhos.json` (`dimensoes_por_tamanho.pequeno`) e de
# `encoding_cnn.dart` (kLinhas / kColunas / kCanais).
FORMA_ENTRADA = (1, 4, 3, 12)
NEURONIOS_SAIDA = 31

# Quantos tensores de teste, e com quantas casas decimais comparar. Seis casas e
# folgado para float32 (que carrega ~7 digitos significativos) e apertado o
# bastante para pegar uma implementacao diferente do mesmo grafo.
QUANTOS_VETORES = 12
CASAS_DECIMAIS = 6
SEMENTE = 20260909  # a data da decisao do dono; qualquer valor fixo serviria


def montar_vetores() -> np.ndarray:
    """Monta os tensores de entrada, iguais em qualquer maquina.

    Usa `np.random.default_rng(SEMENTE)`, o gerador moderno do numpy, cuja
    sequencia e **estavel entre versoes** - ao contrario do antigo
    `np.random.seed`, que a documentacao do numpy so garante dentro da mesma
    versao.

    O primeiro vetor e proposital: **tudo zero**, o tabuleiro vazio. E o caso
    que mais provavelmente expoe uma diferenca de inicializacao do interpretador.
    """
    gerador = np.random.default_rng(SEMENTE)
    # `integers(0, 2, ...)` sorteia em {0, 1} - o dominio que o contrato de
    # codificacao exige do tensor final ("invariante_final_do_tensor_da_cnn").
    vetores = gerador.integers(
        0, 2, size=(QUANTOS_VETORES, *FORMA_ENTRADA[1:]), dtype=np.int8
    ).astype(np.float32)
    vetores[0] = 0.0  # o tabuleiro vazio
    return vetores


def abrir_interpretador(runtime: str, caminho_modelo: Path):
    """Devolve um interpretador TFLite do runtime pedido.

    Os dois expoem a MESMA interface (`allocate_tensors`, `get_input_details`,
    `set_tensor`, `invoke`, `get_tensor`) porque sao a mesma biblioteca C com
    embalagens diferentes - e e justamente por isso que a troca e possivel.
    """
    if runtime == "litert":
        # O runtime autonomo do LiteRT, sucessor do `tflite-runtime`. E o que a
        # imagem do job instala, e nada mais: sem TensorFlow, sem treino.
        from ai_edge_litert.interpreter import Interpreter  # type: ignore
    else:
        # O runtime que o app usa: o `tflite_flutter` embrulha a mesma libtflite
        # que o TensorFlow distribui. So existe no venv do laboratorio.
        #
        # ⚠️ O caminho de import mudou de versao para versao: no TF 2.21 o
        # `tensorflow.lite` e um modulo de carga preguicosa, e
        # `from tensorflow.lite import Interpreter` falha embora
        # `tf.lite.Interpreter` exista. Por isso vamos pelo modulo interno, que
        # e estavel, e so caimos no atributo publico se ele nao existir.
        try:
            from tensorflow.lite.python.interpreter import (  # type: ignore
                Interpreter,
            )
        except ImportError:  # pragma: sem cobertura - versoes antigas do TF
            import tensorflow as tf  # type: ignore

            Interpreter = tf.lite.Interpreter

    return Interpreter(model_path=str(caminho_modelo))


def conferir_formas(interp) -> None:
    """Falha alto se o modelo aberto nao for o que o job espera.

    Sem esta conferencia, um modelo trocado por engano (o medio, o grande)
    rodaria e devolveria numeros plausiveis - e a comparacao com a referencia
    acusaria "divergiu" sem dizer o porque.
    """
    entrada = interp.get_input_details()[0]
    saida = interp.get_output_details()[0]

    forma_entrada = tuple(int(x) for x in entrada["shape"])
    if forma_entrada != FORMA_ENTRADA:
        raise SystemExit(
            f"ENTRADA INESPERADA: o modelo pede {forma_entrada}, "
            f"e o job monta {FORMA_ENTRADA}."
        )
    if entrada["dtype"] != np.float32:
        raise SystemExit(
            f"DTYPE INESPERADO: o modelo pede {entrada['dtype']}, "
            "e o contrato de codificacao exige float32."
        )
    if int(saida["shape"][-1]) != NEURONIOS_SAIDA:
        raise SystemExit(
            f"SAIDA INESPERADA: {int(saida['shape'][-1])} neuronios, "
            f"esperados {NEURONIOS_SAIDA} (tabuleiro pequeno)."
        )


def inferir(interp, vetores: np.ndarray) -> list[list[float]]:
    """Roda a inferencia vetor a vetor e devolve a saida arredondada.

    Arredondar ANTES de comparar e proposital: dois interpretadores corretos
    podem divergir no ultimo bit de um float32 por ordem de soma, e um portao
    que reprovasse por isso seria ignorado no primeiro uso.
    """
    interp.allocate_tensors()
    indice_entrada = interp.get_input_details()[0]["index"]
    indice_saida = interp.get_output_details()[0]["index"]

    resultados: list[list[float]] = []
    for vetor in vetores:
        # `[None]` acrescenta a dimensao de lote: (4,3,12) -> (1,4,3,12).
        interp.set_tensor(indice_entrada, vetor[None].astype(np.float32))
        interp.invoke()
        saida = interp.get_tensor(indice_saida)[0]
        resultados.append([round(float(x), CASAS_DECIMAIS) for x in saida])
    return resultados


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Confere que o runtime de inferencia do job reproduz o do app."
    )
    analisador.add_argument(
        "--runtime",
        choices=("litert", "tensorflow"),
        default="litert",
        help="litert = o runtime da imagem do job; tensorflow = o runtime do app",
    )
    analisador.add_argument(
        "--gravar-referencia",
        action="store_true",
        help="grava a saida como referencia em vez de comparar "
        "(use com --runtime tensorflow)",
    )
    analisador.add_argument(
        "--modelo",
        type=Path,
        default=None,
        help="caminho do .tflite (por padrao, procura no espelho e depois no app)",
    )
    args = analisador.parse_args()

    caminho = args.modelo
    if caminho is None:
        for candidato in CAMINHOS_DO_MODELO:
            if candidato.exists():
                caminho = candidato
                break
    if caminho is None or not caminho.exists():
        raise SystemExit(
            "MODELO NAO ENCONTRADO. Procurei em:\n  "
            + "\n  ".join(str(c) for c in CAMINHOS_DO_MODELO)
        )

    print("=" * 72)
    print("CONFERENCIA DO RUNTIME DE INFERENCIA (T001 / RF-DES-018b)")
    print("=" * 72)
    print(f"  python  : {platform.python_version()} ({platform.machine()})")
    print(f"  sistema : {platform.system()} {platform.release()}")
    print(f"  runtime : {args.runtime}")
    print(f"  modelo  : {caminho}")
    print(f"  tamanho : {caminho.stat().st_size} bytes")

    interp = abrir_interpretador(args.runtime, caminho)
    conferir_formas(interp)
    print("  formas  : OK - entrada (1,4,3,12) float32, saida 31 neuronios")

    saidas = inferir(interp, montar_vetores())

    if args.gravar_referencia:
        ARQUIVO_REFERENCIA.write_text(
            json.dumps(
                {
                    "gerado_por": args.runtime,
                    "python": platform.python_version(),
                    "semente": SEMENTE,
                    "casas_decimais": CASAS_DECIMAIS,
                    "modelo_bytes": caminho.stat().st_size,
                    "saidas": saidas,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nREFERENCIA GRAVADA em {ARQUIVO_REFERENCIA}")
        print("Agora rode sem --gravar-referencia dentro da imagem do job.")
        return 0

    if not ARQUIVO_REFERENCIA.exists():
        raise SystemExit(
            f"SEM REFERENCIA: {ARQUIVO_REFERENCIA} nao existe.\n"
            "Gere-a primeiro com o runtime do app:\n"
            "  ..\\ia\\.venv_tf\\Scripts\\python scripts\\conferir_runtime_inferencia.py "
            "--runtime tensorflow --gravar-referencia"
        )

    referencia = json.loads(ARQUIVO_REFERENCIA.read_text(encoding="utf-8"))
    esperadas = referencia["saidas"]

    if referencia["modelo_bytes"] != caminho.stat().st_size:
        raise SystemExit(
            "MODELO DIFERENTE do que gerou a referencia "
            f"({referencia['modelo_bytes']} bytes la, "
            f"{caminho.stat().st_size} aqui). Compare-os antes de seguir."
        )

    divergentes = []
    for i, (obtida, esperada) in enumerate(zip(saidas, esperadas)):
        # `np.abs(...).max()` da o maior desvio entre os 31 neuronios do vetor.
        desvio = float(np.abs(np.array(obtida) - np.array(esperada)).max())
        if desvio > 0:
            divergentes.append((i, desvio))

    print(f"\n  vetores conferidos   : {len(saidas)}")
    print(
        f"  referencia gerada por: {referencia['gerado_por']} "
        f"(python {referencia['python']})"
    )

    if divergentes:
        print("\n[X] DIVERGIU. O runtime do job NAO reproduz o do app:")
        for i, desvio in divergentes:
            print(f"    vetor {i:2}: desvio maximo {desvio:.9f}")
        print("\nPlano B (research.md R-03): tensorflow-cpu na imagem do job.")
        print("NUNCA reimplementar a inferencia (RF-DES-018b).")
        return 1

    print("\n[OK] CONFERE. Os dois runtimes produzem, numero por numero, a mesma saida.")
    print("     Plano A vale: ai-edge-litert na imagem do job.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

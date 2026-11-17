"""Compila o executável do xadrez com o CARIMBO dos fontes (spec 012, T061).

═══════════════════════════════════════════════════════════════════════════
POR QUE UM SCRIPT, E NÃO SÓ O `cargo build`
═══════════════════════════════════════════════════════════════════════════

O `servidor_de_lances_xadrez` se apresenta com o `resumo_do_motor`: o SHA-256
dos fontes com que foi compilado. O Rust não calcula esse número (o crate não
leva um `sha2`, R-20): ele o recebe **na compilação**, pela variável
`CARIMBO_MOTOR_XADREZ`, e o grava dentro do binário (`option_env!`). Sem a
variável, o carimbo é `"sem_carimbo"`, e o backend recusa a conversa.

Este script calcula o carimbo pela MESMA função que confere a abertura
(`resumo_dos_fontes` com `PADROES_RUST`, `motores/nucleo/processo_dart.py`) e
chama o `cargo` com ele. ⛔ Não há uma segunda fórmula: é por isso que o
carimbo bate com a conferência por construção, e não por cuidado.

═══════════════════════════════════════════════════════════════════════════
⚠️ DE ONDE ELE COMPILA, E PARA ONDE
═══════════════════════════════════════════════════════════════════════════

- **De:** o crate do ESPELHO (`espelho_laboratorio/jogos/jogo_xadrez/motor_rust/`),
  que é o motor que o backend conhece. Compilar o do laboratório daria um
  executável que o backend recusaria assim que os dois divergissem.
- **Para:** `build/motor_xadrez/` (fora do Git, `build/` no `.gitignore`), pelo
  `--target-dir`. ⛔ Nunca dentro do espelho: a pasta `target/` do `cargo`
  apareceria lá, e o espelho deixaria de ser só o que o carimbo lê
  (`test_espelho_laboratorio.py` acusaria).

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\compilar_motor_xadrez.py            (~1 a 3 min: LTO "fat")
    .venv\\Scripts\\python scripts\\compilar_motor_xadrez.py --so-o-carimbo

A segunda forma só imprime o carimbo: é como a imagem do job (`Dockerfile.job`)
o calcula num estágio Python e o entrega ao estágio Rust, que não tem Python.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# ⚠️ A raiz do backend entra no caminho de busca: `python scripts/este.py` põe
# `scripts/` no `sys.path`, e não a raiz. Sem isto, `import motores` falha.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motores.nucleo.processo_dart import PADROES_RUST, resumo_dos_fontes  # noqa: E402

# O crate do espelho, a pasta da compilação e o nome do executável vêm do
# JOGADOR, que é quem depois procura o executável e confere o carimbo: com uma
# cópia dos caminhos aqui, o script poderia compilar num lugar e o jogador
# procurar em outro.
from motores.xadrez.jogador_xadrez import (  # noqa: E402
    FONTES_DO_MOTOR as CRATE_NO_ESPELHO,
    NOME_DO_BINARIO,
    PASTA_DA_COMPILACAO,
)

#: A variável que o `servidor_de_lances_xadrez.rs` lê com `option_env!`.
VARIAVEL_DO_CARIMBO = "CARIMBO_MOTOR_XADREZ"


def carimbo(crate: Path = CRATE_NO_ESPELHO) -> str:
    """O resumo dos fontes do crate: o mesmo que o backend confere na abertura."""
    return resumo_dos_fontes(crate, PADROES_RUST)


def executavel_compilado(pasta: Path = PASTA_DA_COMPILACAO) -> Path:
    """Onde o `cargo build --release` deixa o executável, com `.exe` no Windows."""
    nome = f"{NOME_DO_BINARIO}.exe" if os.name == "nt" else NOME_DO_BINARIO
    return pasta / "release" / nome


def compilar(crate: Path = CRATE_NO_ESPELHO, pasta: Path = PASTA_DA_COMPILACAO) -> Path:
    """Compila o executável com o carimbo e devolve o caminho dele.

    Raises:
        SystemExit: o `cargo` falhou (a saída dele já foi para a tela).
    """
    resumo = carimbo(crate)
    # `{**os.environ, ...}`: o ambiente de quem chamou, mais o carimbo. O resto
    # (PATH, RUSTUP_HOME...) tem de passar, ou o `cargo` nem é achado.
    ambiente = {**os.environ, VARIAVEL_DO_CARIMBO: resumo}
    comando = [
        "cargo", "build", "--release", "--bin", NOME_DO_BINARIO,
        "--target-dir", str(pasta),
    ]
    print(f"carimbo {resumo}\ncompilando em {pasta} ...", flush=True)
    # `cwd=crate`: o `cargo` acha o `Cargo.toml` e o `rust-toolchain.toml` dali.
    resultado = subprocess.run(comando, cwd=crate, env=ambiente)
    if resultado.returncode != 0:
        raise SystemExit(f"o cargo falhou (codigo {resultado.returncode})")
    caminho = executavel_compilado(pasta)
    print(f"executavel em {caminho}")
    return caminho


def main(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    analisador.add_argument(
        "--so-o-carimbo", action="store_true",
        help="so imprime o carimbo dos fontes do espelho (o estagio Python da imagem)",
    )
    analisador.add_argument("--crate", type=Path, default=CRATE_NO_ESPELHO)
    analisador.add_argument("--pasta", type=Path, default=PASTA_DA_COMPILACAO)
    args = analisador.parse_args(argumentos)
    if not (args.crate / "Cargo.toml").is_file():
        print(
            f"nao achei o crate do xadrez em {args.crate}.\n"
            "Rode antes: .venv\\Scripts\\python scripts\\espelhar_laboratorio.py",
            file=sys.stderr,
        )
        return 2
    if args.so_o_carimbo:
        # Só o número, sem mais nada na linha: a imagem o lê com `$(cat ...)`.
        print(carimbo(args.crate))
        return 0
    compilar(args.crate, args.pasta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

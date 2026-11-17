"""T059 da spec 012 - os fontes que entram no resumo de um motor compilado.

`hashes_dos_fontes` ganhou um parâmetro **aditivo** (os padrões de arquivo, com
`**` para descer em subpastas), para o executável Rust do xadrez ser conferido
pela mesma trava dos três motores Dart (fricção F-3, `research.md` R-20). O que
estes testes travam:

1. **os três motores em produção não mudaram de resumo.** A fórmula de antes está
   copiada aqui, CONGELADA, e o resumo de hoje das damas, do Pontinhos e do Quatro
   tem de sair igual ao dela. ⚠️ A comparação é com a cópia congelada, e não com
   os três números de hoje escritos à mão: o espelho muda quando um motor Dart
   muda de propósito, e um número escrito à mão ficaria vermelho por um motivo que
   não é este. O número escrito à mão existe, mas numa pasta montada pelo teste
   (o caso 2), onde ele não envelhece;
2. a fórmula em si, contra um número calculado **fora** dela (com o `hashlib`);
3. o padrão do Rust: o `.rs` de qualquer subpasta de `src/`, com o caminho
   relativo e `/`, e os três arquivos da compilação; `tests/`, `target/` e o resto
   ficam de fora;
4. o resumo muda quando um arquivo muda, some ou troca de nome.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from motores.damas import jogador_dart as damas
from motores.nucleo.processo_dart import (
    PADROES_DART,
    PADROES_RUST,
    hashes_dos_fontes,
    resumo_dos_fontes,
)
from motores.pontinhos import jogador_dart_pontinhos as pontinhos
from motores.quatro import jogador_dart_quatro as quatro

#: O laboratório, quando os três repositórios moram lado a lado (a máquina do
#: dono). `parents[3]` sobe de `tests/unitarios/<este arquivo>` até a pasta que
#: tem `arena-sagaz-backend/` e `ia/`.
CRATE_DO_XADREZ = (
    Path(__file__).resolve().parents[3] / "ia" / "jogos" / "jogo_xadrez" / "motor_rust"
)


def resumo_de_antes(pasta: Path) -> str:
    """A fórmula de ANTES da T059, copiada e congelada.

    ⛔ Não "atualize" esta função: ela é o "antes" da comparação. Se um dia a
    fórmula do resumo dos motores Dart mudar de propósito, este teste deixa de
    fazer sentido e sai junto com a mudança, que também muda o lado Dart
    (`bin/compilar_servidor_de_lances*.dart`).
    """
    arquivos = sorted(pasta.glob("*.dart"), key=lambda a: a.name)
    material = "\n".join(
        f"{a.name}:{hashlib.sha256(a.read_bytes()).hexdigest()}" for a in arquivos
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@pytest.mark.parametrize(
    "modulo", [damas, pontinhos, quatro], ids=["damas", "pontinhos", "quatro"]
)
def test_os_tres_motores_dart_tem_o_mesmo_resumo_de_antes(modulo):
    pasta = modulo.FONTES_DO_MOTOR_DART
    # Sem esta guarda, um espelho vazio daria o resumo da lista vazia nos dois
    # lados, e o teste passaria sem comparar nada.
    assert len(list(pasta.glob("*.dart"))) >= 5, f"espelho vazio em {pasta}"
    assert resumo_dos_fontes(pasta) == resumo_de_antes(pasta)
    # Pelo padrão escrito por extenso também (é o que `ProcessoDart` passa).
    assert resumo_dos_fontes(pasta, PADROES_DART) == resumo_de_antes(pasta)
    # E pelo próprio módulo do jogo, que é quem o servidor chama.
    assert modulo.resumo_dos_fontes() == resumo_de_antes(pasta)


def test_a_formula_contra_um_numero_calculado_fora_dela(tmp_path):
    # `a.dart` = "x" e `b.dart` = "y\n"; o `.txt` não é fonte. O número abaixo
    # saiu do `hashlib`, à mão:
    #   sha256("a.dart:" + sha256(b"x") + "\n" + "b.dart:" + sha256(b"y\n"))
    (tmp_path / "b.dart").write_bytes(b"y\n")
    (tmp_path / "a.dart").write_bytes(b"x")
    (tmp_path / "c.txt").write_bytes(b"z")
    assert (
        resumo_dos_fontes(tmp_path)
        == "d9d2f73f1207ed8793bd322d7b1d8b52c1905aee96efe6746e7129cd60f0deca"
    )


def montar_crate(raiz: Path) -> None:
    """Um crate Rust de mentira, com um arquivo de cada tipo que importa."""
    arquivos = {
        "Cargo.toml": "[package]\n",
        "Cargo.lock": "# travado\n",
        "rust-toolchain.toml": "[toolchain]\n",
        "README.md": "fora\n",
        "src/lib.rs": "pub mod busca;\n",
        "src/busca.rs": "fn buscar() {}\n",
        "src/bin/servidor.rs": "fn main() {}\n",
        "tests/perft.rs": "fora\n",
        "target/release/build/gerado.rs": "fora\n",
        "src/notas.txt": "fora\n",
    }
    for relativo, texto in arquivos.items():
        caminho = raiz / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(texto.encode("utf-8"))


def test_o_padrao_do_rust_pega_src_inteiro_e_os_tres_da_compilacao(tmp_path):
    montar_crate(tmp_path)
    hashes = hashes_dos_fontes(tmp_path, PADROES_RUST)
    # A ordem do dicionário é a ordem do resumo: a dos caminhos, com `/`.
    assert list(hashes) == [
        "Cargo.lock",
        "Cargo.toml",
        "rust-toolchain.toml",
        "src/bin/servidor.rs",
        "src/busca.rs",
        "src/lib.rs",
    ]
    assert hashes["src/bin/servidor.rs"] == hashlib.sha256(b"fn main() {}\n").hexdigest()
    # O padrão Dart, na mesma pasta, não acha nada: os dois não se misturam.
    assert hashes_dos_fontes(tmp_path) == {}


def test_o_resumo_do_rust_muda_quando_um_fonte_muda_some_ou_troca_de_nome(tmp_path):
    montar_crate(tmp_path)
    original = resumo_dos_fontes(tmp_path, PADROES_RUST)
    assert resumo_dos_fontes(tmp_path, PADROES_RUST) == original  # estável

    # O conteúdo do executável muda: o resumo muda (o servidor é feito de lá).
    servidor = tmp_path / "src" / "bin" / "servidor.rs"
    servidor.write_bytes(b"fn main() { println!(); }\n")
    mudou_o_conteudo = resumo_dos_fontes(tmp_path, PADROES_RUST)
    assert mudou_o_conteudo != original

    # O mesmo conteúdo com outro nome: outro motor.
    servidor.rename(servidor.with_name("servidor2.rs"))
    assert resumo_dos_fontes(tmp_path, PADROES_RUST) not in (original, mudou_o_conteudo)

    # Um arquivo que some: outro motor.
    (tmp_path / "src" / "bin" / "servidor2.rs").unlink()
    sem_o_servidor = resumo_dos_fontes(tmp_path, PADROES_RUST)
    assert sem_o_servidor not in (original, mudou_o_conteudo)

    # O que está fora do padrão não mexe em nada.
    (tmp_path / "tests" / "perft.rs").write_bytes(b"outro teste\n")
    (tmp_path / "target" / "release" / "build" / "gerado.rs").write_bytes(b"outro\n")
    assert resumo_dos_fontes(tmp_path, PADROES_RUST) == sem_o_servidor


@pytest.mark.skipif(
    not CRATE_DO_XADREZ.is_dir(),
    reason="o laboratorio nao esta ao lado (fora da maquina do dono); "
    "o espelho e conferido em test_espelho_laboratorio.py",
)
def test_no_crate_do_xadrez_o_padrao_le_src_e_deixa_testes_e_target_de_fora():
    hashes = hashes_dos_fontes(CRATE_DO_XADREZ, PADROES_RUST)
    # O que tem de estar: os três da compilação, a biblioteca e o executável.
    for obrigatorio in (
        "Cargo.toml",
        "Cargo.lock",
        "rust-toolchain.toml",
        "src/lib.rs",
        "src/bin/servidor_de_lances_xadrez.rs",
    ):
        assert obrigatorio in hashes, obrigatorio
    # Todo `.rs` de `src/` entrou, e nada de fora de `src/` além dos três.
    em_src = {
        a.relative_to(CRATE_DO_XADREZ).as_posix()
        for a in (CRATE_DO_XADREZ / "src").rglob("*.rs")
    }
    assert set(hashes) == em_src | {"Cargo.toml", "Cargo.lock", "rust-toolchain.toml"}
    assert not any(c.startswith(("tests/", "target/")) for c in hashes)


@pytest.mark.skipif(
    not CRATE_DO_XADREZ.is_dir(),
    reason="o laboratorio nao esta ao lado (fora da maquina do dono); "
    "o espelho e conferido em test_espelho_laboratorio.py",
)
def test_a_lista_do_espelho_tem_cada_fonte_do_crate_do_xadrez():
    """Um `.rs` novo no laboratório que a lista escrita à mão esqueceu.

    `test_espelho_laboratorio.py` confere o espelho sem o laboratório (e por isso
    só vê o que já foi espelhado). Aqui, onde o laboratório está ao lado, a
    lista de `scripts/espelhar_laboratorio.py` tem de ser exatamente o que o
    `PADROES_RUST` acha no crate de verdade.
    """
    from scripts.espelhar_laboratorio import ARQUIVOS_ESPELHADOS

    prefixo = "jogos/jogo_xadrez/motor_rust/"
    na_lista = {r[len(prefixo):] for r in ARQUIVOS_ESPELHADOS if r.startswith(prefixo)}
    assert na_lista == set(hashes_dos_fontes(CRATE_DO_XADREZ, PADROES_RUST))

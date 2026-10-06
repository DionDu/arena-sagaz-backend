"""O `gpg` DE VERDADE fecha e abre o backup - quando ele existe na máquina.

Os outros casos usam um `gpg` falso, que só anota o comando. Este roda o programa
real, porque três coisas só ele prova:

1. a senha que entra pela **entrada padrão** é a mesma que abre o arquivo -
   inclusive com espaços nas pontas (a `Configuracao` não os tira, de propósito);
2. o comando de abrir que o plano ensina ao dono (`gpg --output ... --decrypt`)
   funciona sobre o que o serviço gera;
3. a senha errada **não** abre.

No Windows o `gpg` vem com o Git (na pasta `usr/bin` da instalação); sem ele, o
caso é pulado - e o pulo aparece no resumo do pytest.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from backup import backup_do_banco as bk


def _achar_gpg() -> str | None:
    """O `gpg` do PATH, ou o que o Git para Windows instala."""
    no_path = shutil.which("gpg")
    if no_path:
        return no_path
    do_git = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "usr" / "bin" / "gpg.exe"
    return str(do_git) if do_git.exists() else None


GPG = _achar_gpg()
pytestmark = pytest.mark.skipif(GPG is None, reason="gpg não instalado nesta máquina")

SENHA = "  uma frase longa com espaços  "


def _caminho_para_o_gpg(argumento: str) -> str:
    """Converte `C:/pasta/arq` (com barra invertida) em `/c/pasta/arq` para o gpg do Git.

    ⚠️ O `gpg` do Git para Windows é um programa MSYS: ele não entende caminho com
    letra de unidade e barra invertida, e procura a pasta como se fosse relativa
    (medido em 06/10/2026: `keyblock resource '.../C:/Users/...'`, com a pasta
    temporária do pytest grudada depois da pasta atual). No servidor (Linux) o
    caminho já é `/tmp/...` e nada disto acontece - é só desta bancada.
    """
    if os.name == "nt" and len(argumento) > 2 and argumento[1] == ":" and argumento[2] in "\\/":
        return "/" + argumento[0].lower() + argumento[2:].replace("\\", "/")
    return argumento


def _rodar_com_este_gpg(comando, **kwargs):
    """O `subprocess.run`, trocando "gpg" pelo caminho achado e os caminhos de arquivo."""
    if comando[0] == "gpg":
        comando = [GPG, *(_caminho_para_o_gpg(a) for a in comando[1:])]
    return subprocess.run(comando, **kwargs)


def _abrir(fechado: Path, aberto: Path, senha: str, pasta: Path) -> subprocess.CompletedProcess:
    """O comando do plano (B7), com a senha pela entrada em vez de digitada."""
    return _rodar_com_este_gpg(
        ["gpg", "--batch", "--yes", "--pinentry-mode", "loopback", "--passphrase-fd", "0",
         "--homedir", str(pasta), "--output", str(aberto), "--decrypt", str(fechado)],
        input=senha, capture_output=True, text=True,
    )


@pytest.fixture
def pasta_curta():
    """Fabrica pastas de estado do `gpg` com caminho CURTO, e as limpa no fim.

    ⚠️ Não serve a `tmp_path` do pytest: o caminho dela é longo demais para o socket
    do `gpg-agent` (~108 caracteres, ver `criptografar`). `mkdtemp` cria direto
    na pasta temporária do sistema, com um nome de poucas letras.
    """
    criadas: list[str] = []

    def criar() -> Path:
        pasta = tempfile.mkdtemp(prefix="g")
        criadas.append(pasta)
        return Path(pasta)

    yield criar
    for pasta in criadas:
        # O agente fica de pé depois do `gpg`; `gpgconf --kill` o derruba para a
        # pasta poder ser apagada (no Windows, arquivo aberto não se apaga).
        subprocess.run([str(Path(GPG).with_name("gpgconf" + Path(GPG).suffix)),
                        "--homedir", _caminho_para_o_gpg(pasta), "--kill", "gpg-agent"],
                       capture_output=True)
        shutil.rmtree(pasta, ignore_errors=True)


def _fechar(tmp_path: Path, pasta_curta, tamanho: int) -> tuple[Path, Path]:
    """Gera um arquivo e o fecha pelo `criptografar` do serviço."""
    original = tmp_path / "banco.dump"
    original.write_bytes(b"PGDMP" + os.urandom(tamanho))
    fechado = tmp_path / "arena-sagaz-prd_2026-10-12_diario.dump.gpg"
    bk.criptografar(_rodar_com_este_gpg, original, fechado, SENHA, pasta_curta())
    return original, fechado


def test_fecha_e_abre_com_a_mesma_senha(tmp_path: Path, pasta_curta):
    original, fechado = _fechar(tmp_path, pasta_curta, 4096)
    assert fechado.exists()
    assert original.read_bytes()[5:200] not in fechado.read_bytes()  # está fechado

    # ⚠️ Abre com OUTRA pasta de estado: na mesma, o agente poderia lembrar a senha
    # do fechamento e o caso passaria sem provar nada. E é assim no PC do dono.
    aberto = tmp_path / "aberto.dump"
    resultado = _abrir(fechado, aberto, SENHA, pasta_curta())
    assert resultado.returncode == 0, resultado.stderr
    assert aberto.read_bytes() == original.read_bytes()


def test_senha_sem_os_espacos_nao_abre(tmp_path: Path, pasta_curta):
    """Prova que o espaço faz parte da senha - e que tirá-lo seria perder o backup."""
    _, fechado = _fechar(tmp_path, pasta_curta, 512)
    resultado = _abrir(fechado, tmp_path / "x.dump", SENHA.strip(), pasta_curta())
    assert resultado.returncode != 0

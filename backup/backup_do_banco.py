"""Uma execução do backup diário do banco do `prd` (T101 da spec 009).

Roda como `python3 -m backup.backup_do_banco`, dentro da imagem do
`Dockerfile.backup`, acordada pelo cron do Railway às 04:00 UTC.

═══════════════════════════════════════════════════════════════════════════
O FLUXO, NA ORDEM - e por que a ordem é esta
═══════════════════════════════════════════════════════════════════════════

    1. pg_dump --format=custom   copia o banco (só lê; nada é escrito nele)
    2. pg_restore --list         confere que o arquivo está inteiro e legível
    3. gpg --symmetric           criptografa com a senha do dono (AES-256)
    4. envio ao Drive            e confere o tamanho que CHEGOU
    5. faxina                    manda para a lixeira o que passou do prazo
    6. código 0                  (qualquer falha acima: código 1)

⛔ **A faxina é o último passo, e só roda se o envio de hoje foi conferido.** Uma
execução que falhou no meio não apaga nada: o pior caso de um defeito é um backup a
menos, nunca os backups antigos a menos.

⚠️ **Terminar é o sucesso.** O serviço do Railway tem `Restart Policy = NEVER`;
código 1 marca a execução como falha no painel, e é por esse estado que se sabe
que o backup não chegou.

═══════════════════════════════════════════════════════════════════════════
⛔ NENHUM SEGREDO SAI NO LOG
═══════════════════════════════════════════════════════════════════════════

A URL do banco (com a senha do Postgres dentro), a senha do backup e as
credenciais do Google vêm por variável de ambiente e **nunca** são impressas:

- a senha do backup chega ao `gpg` pela **entrada padrão**, e não como argumento
  - argumento de programa aparece na lista de processos da máquina;
- quando um programa externo falha, a mensagem leva o **nome** dele, o código de
  saída e o fim do que ele escreveu no erro - e nunca a linha de comando, que tem
  a URL do banco;
- a variável que falta é citada pelo **nome**.

═══════════════════════════════════════════════════════════════════════════
AS VARIÁVEIS DO SERVIÇO NO RAILWAY
═══════════════════════════════════════════════════════════════════════════

| variável | o que é |
|---|---|
| `DATABASE_URL` | por referência ao Postgres do `prd` (`${{Postgres.DATABASE_URL}}`), pela rede privada |
| `BACKUP_SENHA` | a senha do dono - a mesma que está no e-mail pessoal dele |
| `GOOGLE_OAUTH_CLIENT_ID` · `GOOGLE_OAUTH_CLIENT_SECRET` | a credencial OAuth do projeto no Google Cloud |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | a autorização que o `autorizar_drive.py` devolveu |
| `BACKUP_ID_PASTA_DRIVE` | o id da pasta que o `autorizar_drive.py` criou |
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from backup import drive as drive_mod
from backup import retencao

#: As variáveis de ambiente que o serviço exige, na ordem da tabela acima.
VARIAVEIS_EXIGIDAS = (
    "DATABASE_URL",
    "BACKUP_SENHA",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_REFRESH_TOKEN",
    "BACKUP_ID_PASTA_DRIVE",
)

#: A tabela que todo banco migrado pelo Alembic tem. Se ela não aparece no índice
#: do arquivo, o `pg_dump` copiou o banco errado (ou nenhum) - e enviar isso ao
#: Drive seria guardar uma cópia que não serve para nada.
TABELA_QUE_PROVA_O_BANCO = "alembic_version"

# Uma função com a forma do `subprocess.run`. O teste passa uma falsa, que anota
# o comando e devolve o resultado combinado, sem rodar programa nenhum.
Rodar = Callable[..., subprocess.CompletedProcess]


class ErroDoBackup(RuntimeError):
    """Uma etapa do backup falhou. A mensagem nunca leva segredo."""


@dataclass(frozen=True)
class Configuracao:
    """O que o serviço lê do ambiente, já conferido."""

    url_do_banco: str
    senha: str
    id_cliente: str
    segredo_cliente: str
    refresh_token: str
    id_pasta: str


def ler_configuracao(ambiente: Mapping[str, str]) -> Configuracao:
    """Lê as variáveis exigidas, e recusa se faltar alguma.

    A recusa cita **todas** as que faltam de uma vez, pelo nome - quem configura o
    serviço corrige tudo numa ida ao painel, em vez de descobrir uma por execução.
    Variável presente e vazia conta como faltando.
    """
    faltam = [nome for nome in VARIAVEIS_EXIGIDAS if not ambiente.get(nome, "").strip()]
    if faltam:
        raise ErroDoBackup("faltam variáveis de ambiente: " + ", ".join(faltam))
    return Configuracao(
        url_do_banco=ambiente["DATABASE_URL"].strip(),
        # ⚠️ A senha NÃO passa por `.strip()`: um espaço no começo ou no fim faz
        # parte dela, e tirá-lo fecharia o arquivo com uma senha diferente da que
        # o dono guardou no e-mail.
        senha=ambiente["BACKUP_SENHA"],
        id_cliente=ambiente["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        segredo_cliente=ambiente["GOOGLE_OAUTH_CLIENT_SECRET"].strip(),
        refresh_token=ambiente["GOOGLE_OAUTH_REFRESH_TOKEN"].strip(),
        id_pasta=ambiente["BACKUP_ID_PASTA_DRIVE"].strip(),
    )


def _rodar_programa(
    rodar: Rodar,
    nome: str,
    comando: list[str],
    entrada: str | None = None,
) -> str:
    """Roda um programa externo e devolve o que ele escreveu na saída padrão.

    `capture_output=True` guarda a saída e o erro em vez de jogá-los no log;
    `text=True` faz isso em texto, e não em bytes. Na falha, a mensagem leva o
    `nome` do programa e as últimas linhas do erro - nunca o `comando`, que pode
    ter a URL do banco.
    """
    resultado = rodar(comando, input=entrada, capture_output=True, text=True)
    if resultado.returncode != 0:
        fim_do_erro = "\n".join((resultado.stderr or "").strip().splitlines()[-5:])
        raise ErroDoBackup(
            f"{nome} saiu com código {resultado.returncode}: {fim_do_erro}"
        )
    return resultado.stdout or ""


def gerar_dump(rodar: Rodar, url_do_banco: str, destino: Path) -> None:
    """Passo 1: copia o banco inteiro para `destino`, no formato `custom`.

    O formato `custom` (`-Fc`) já sai comprimido e é o que o `pg_restore` lê -
    inclusive para restaurar **uma tabela só**, que é o uso principal destes
    backups (consertos pontuais, DECISOES §8zv).

    ⚠️ O `pg_dump` tem de ser da **mesma versão maior** do servidor, ou mais nova:
    um `pg_dump` 17 recusa um Postgres 18. É por isso que a imagem parte da
    oficial `postgres:18` (`Dockerfile.backup`).
    """
    _rodar_programa(
        rodar,
        "pg_dump",
        ["pg_dump", "--format=custom", f"--dbname={url_do_banco}", f"--file={destino}"],
    )


def conferir_dump(rodar: Rodar, arquivo: Path) -> None:
    """Passo 2: o arquivo se lê, e é do banco certo.

    `pg_restore --list` lê o índice do arquivo sem restaurar nada. Um arquivo
    truncado ou corrompido falha aqui; um arquivo inteiro sem a tabela do Alembic
    é de outro banco.

    ⚠️ Isto **não** substitui a prova de restauração do plano (B7): abrir o
    arquivo de verdade, num Postgres, é o que prova que o backup serve.
    """
    indice = _rodar_programa(rodar, "pg_restore", ["pg_restore", "--list", str(arquivo)])
    if TABELA_QUE_PROVA_O_BANCO not in indice:
        raise ErroDoBackup(
            f"o índice do arquivo não tem a tabela {TABELA_QUE_PROVA_O_BANCO}: "
            "a cópia não é do banco da API"
        )


def criptografar(rodar: Rodar, origem: Path, destino: Path, senha: str, pasta_gpg: Path) -> None:
    """Passo 3: fecha o arquivo com a senha do dono (AES-256).

    Decisão do dono (06/10/2026): **uma senha só**, a mesma que ele guarda no
    e-mail pessoal. Para abrir no Windows, o Git Bash já traz o `gpg`:

        gpg --output banco.dump --decrypt arena-sagaz-prd_....dump.gpg

    Os argumentos, um a um:
    - `--batch` e `--pinentry-mode loopback`: sem janela de senha (não há tela);
    - `--passphrase-fd 0`: a senha vem da **entrada padrão** (o descritor 0), e não
      de um argumento, que apareceria na lista de processos;
    - `--homedir`: uma pasta temporária para o `gpg` guardar o estado dele, que
      morre com a execução (a casa do usuário no container pode não ser gravável).
      ⚠️ **O caminho dela tem de ser CURTO**: o `gpg` sobe um ajudante
      (`gpg-agent`) que abre um *socket* dentro dessa pasta, e caminho de socket
      tem limite de ~108 caracteres. Passou disso, o agente não sobe e o `gpg`
      sai com código 2 (medido em 06/10/2026, numa pasta temporária do pytest).
      No container a pasta é `/tmp/backup-xxxxxxxx/gpg`, com folga;
    - `--symmetric --cipher-algo AES256`: criptografia por senha, com AES-256.
    """
    _rodar_programa(
        rodar,
        "gpg",
        [
            "gpg",
            "--batch",
            "--yes",
            "--pinentry-mode",
            "loopback",
            "--passphrase-fd",
            "0",
            "--homedir",
            str(pasta_gpg),
            "--symmetric",
            "--cipher-algo",
            "AES256",
            "--output",
            str(destino),
            str(origem),
        ],
        entrada=senha,
    )


def faxina(
    cliente: drive_mod.ClienteDrive,
    id_pasta: str,
    enviado: drive_mod.ArquivoNoDrive,
    hoje: date,
) -> list[str]:
    """Passo 5: manda para a lixeira o que passou do prazo. Devolve o que ficou.

    Além da regra de prazo (`retencao.py`), apaga **cópias repetidas do backup de
    hoje**: se o dono disparar o serviço à mão duas vezes no mesmo dia, o Drive
    aceita dois arquivos de mesmo nome, e só o mais novo (o que acabou de chegar)
    fica. ⛔ O arquivo recém-enviado nunca é apagado, qualquer que seja a regra.
    """
    arquivos = cliente.listar(id_pasta)
    vencidos = set(retencao.nomes_a_apagar([a.nome for a in arquivos], hoje))
    ficaram: list[str] = []
    for arquivo in arquivos:
        if arquivo.id == enviado.id:
            ficaram.append(arquivo.nome)
            continue
        repetido = arquivo.nome == enviado.nome
        if arquivo.nome in vencidos or repetido:
            cliente.mandar_para_lixeira(arquivo.id)
            motivo = "repetido de hoje" if repetido else "passou do prazo"
            print(f"[backup] para a lixeira ({motivo}): {arquivo.nome}")
        else:
            ficaram.append(arquivo.nome)
    return sorted(ficaram)


def executar(
    config: Configuracao,
    hoje: date,
    rodar: Rodar,
    criar_cliente: Callable[[Configuracao], drive_mod.ClienteDrive],
    pasta_de_trabalho: Path,
) -> list[str]:
    """Os passos 1 a 5, em ordem. Devolve os nomes que ficaram na pasta.

    Tudo o que pode variar entra por parâmetro (o dia, quem roda programas, quem
    fala com o Drive, a pasta temporária) - é o que deixa o teste conferir a ordem
    e as recusas sem banco, sem `gpg` e sem internet.
    """
    nome = retencao.nome_do_arquivo(hoje)
    dump = pasta_de_trabalho / "banco.dump"
    fechado = pasta_de_trabalho / nome
    pasta_gpg = pasta_de_trabalho / "gpg"
    pasta_gpg.mkdir(mode=0o700, exist_ok=True)

    gerar_dump(rodar, config.url_do_banco, dump)
    conferir_dump(rodar, dump)
    print(f"[backup] cópia do banco conferida: {dump.stat().st_size} bytes")

    criptografar(rodar, dump, fechado, config.senha, pasta_gpg)
    tamanho_local = fechado.stat().st_size

    cliente = criar_cliente(config)
    enviado = cliente.enviar(fechado, nome, config.id_pasta)
    # ⚠️ A conferência pelo ESTADO: o tamanho que o Drive diz ter recebido. Um envio
    # que "deu certo" e chegou pela metade não pode autorizar a faxina.
    if enviado.tamanho != tamanho_local:
        raise ErroDoBackup(
            f"o Drive recebeu {enviado.tamanho} bytes de {tamanho_local}: "
            "envio incompleto, nada foi apagado"
        )
    print(f"[backup] enviado ao Drive: {nome} ({tamanho_local} bytes)")

    ficaram = faxina(cliente, config.id_pasta, enviado, hoje)
    print(f"[backup] {len(ficaram)} backups na pasta:")
    for nome_que_ficou in ficaram:
        print(f"[backup]   {nome_que_ficou}")
    return ficaram


def _cliente_de_verdade(config: Configuracao) -> drive_mod.ClienteDrive:
    """O cliente do Drive com a autorização do dono trocada por um token novo."""
    token = drive_mod.obter_token_de_acesso(
        config.id_cliente, config.segredo_cliente, config.refresh_token
    )
    return drive_mod.ClienteDrive(token)


def main() -> int:
    """O ponto de entrada do serviço: 0 se o backup chegou, 1 se não."""
    # O dia do backup é o dia UTC - o mesmo calendário do cron do Railway.
    hoje = datetime.now(timezone.utc).date()
    try:
        config = ler_configuracao(os.environ)
        # `TemporaryDirectory` cria uma pasta que é apagada ao sair do `with`,
        # com o dump aberto dentro: a cópia sem criptografia não sobrevive à
        # execução.
        with tempfile.TemporaryDirectory(prefix="backup-") as pasta:
            executar(config, hoje, subprocess.run, _cliente_de_verdade, Path(pasta))
    except (ErroDoBackup, drive_mod.ErroDoDrive) as erro:
        print(f"[backup] FALHOU em {hoje.isoformat()}: {erro}", file=sys.stderr)
        return 1
    print(f"[backup] OK em {hoje.isoformat()}")
    return 0


if __name__ == "__main__":
    # `sys.exit` devolve o código ao sistema: é ele que o Railway lê.
    sys.exit(main())

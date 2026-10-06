"""O fluxo de uma execução do backup (`backup/backup_do_banco.py`).

Sem banco, sem `gpg` e sem internet: os programas externos são substituídos por
`RodarFalso`, que anota cada comando e escreve no disco o arquivo que o programa
de verdade escreveria; o Drive é substituído por `DriveFalso`, que guarda os
arquivos numa lista.

O que estes casos travam, em ordem de gravidade:

1. ⛔ **nada é apagado quando o backup de hoje não chegou inteiro**;
2. ⛔ **nenhum segredo aparece em mensagem nem em argumento de programa**;
3. a ordem dos passos e as recusas de cada um.
"""

from __future__ import annotations

import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from backup import backup_do_banco as bk
from backup import retencao
from backup.drive import ArquivoNoDrive

HOJE = date(2026, 10, 12)  # uma segunda: o backup de hoje é "diario"
URL = "postgresql://postgres:SENHA_DO_POSTGRES@postgres.railway.internal:5432/railway"
SENHA = "  frase longa do dono  "  # com espaços nas pontas, de propósito

AMBIENTE_COMPLETO = {
    "DATABASE_URL": URL,
    "BACKUP_SENHA": SENHA,
    "GOOGLE_OAUTH_CLIENT_ID": "id-do-cliente",
    "GOOGLE_OAUTH_CLIENT_SECRET": "SEGREDO_DO_CLIENTE",
    "GOOGLE_OAUTH_REFRESH_TOKEN": "REFRESH_TOKEN_DO_DONO",
    "BACKUP_ID_PASTA_DRIVE": "pasta-1",
}

#: Todo valor que não pode sair em mensagem de erro nem no log.
SEGREDOS = ("SENHA_DO_POSTGRES", "frase longa do dono", "SEGREDO_DO_CLIENTE", "REFRESH_TOKEN_DO_DONO")


class RodarFalso:
    """Faz o papel do `subprocess.run` para `pg_dump`, `pg_restore` e `gpg`."""

    def __init__(self, falhar: str | None = None, indice: str = "TABLE DATA public alembic_version postgres"):
        self.comandos: list[list[str]] = []
        self.entradas: list[str | None] = []
        self.falhar = falhar
        self.indice = indice

    def __call__(self, comando, input=None, capture_output=False, text=False):
        self.comandos.append(list(comando))
        self.entradas.append(input)
        programa = comando[0]
        if programa == self.falhar:
            # O erro de um programa de verdade pode citar o host; nunca a senha.
            return subprocess.CompletedProcess(comando, 1, "", "linha 1\nconnection failed\n")
        if programa == "pg_dump":
            destino = next(a for a in comando if a.startswith("--file=")).split("=", 1)[1]
            Path(destino).write_bytes(b"PGDMP" + b"x" * 100)
            return subprocess.CompletedProcess(comando, 0, "", "")
        if programa == "pg_restore":
            return subprocess.CompletedProcess(comando, 0, self.indice, "")
        if programa == "gpg":
            destino = comando[comando.index("--output") + 1]
            Path(destino).write_bytes(b"\x8c" + b"y" * 120)
            return subprocess.CompletedProcess(comando, 0, "", "")
        raise AssertionError(f"programa inesperado: {programa}")


class DriveFalso:
    """Faz o papel do `ClienteDrive`: uma pasta numa lista, e o que foi pedido."""

    def __init__(self, ja_na_pasta: list[str] = (), encolher_envio: int = 0):
        self.arquivos = [ArquivoNoDrive(f"antigo-{i}", nome, 10) for i, nome in enumerate(ja_na_pasta)]
        self.lixeira: list[str] = []
        self.envios: list[tuple[str, str]] = []
        self.encolher_envio = encolher_envio

    def enviar(self, caminho: Path, nome: str, id_pasta: str) -> ArquivoNoDrive:
        self.envios.append((nome, id_pasta))
        novo = ArquivoNoDrive("novo", nome, caminho.stat().st_size - self.encolher_envio)
        self.arquivos.append(novo)
        return novo

    def listar(self, id_pasta: str) -> list[ArquivoNoDrive]:
        return list(self.arquivos)

    def mandar_para_lixeira(self, id_arquivo: str) -> None:
        self.lixeira.append(id_arquivo)
        self.arquivos = [a for a in self.arquivos if a.id != id_arquivo]


def _executar(tmp_path, rodar=None, drive=None, hoje=HOJE):
    config = bk.ler_configuracao(AMBIENTE_COMPLETO)
    rodar = rodar or RodarFalso()
    drive = drive or DriveFalso()
    ficaram = bk.executar(config, hoje, rodar, lambda _c: drive, tmp_path)
    return ficaram, rodar, drive


def _nome(dias_atras: int) -> str:
    return retencao.nome_do_arquivo(HOJE - timedelta(days=dias_atras))


class TestConfiguracao:
    def test_cita_todas_as_que_faltam_pelo_nome(self):
        ambiente = dict(AMBIENTE_COMPLETO, BACKUP_SENHA="", GOOGLE_OAUTH_REFRESH_TOKEN="   ")
        del ambiente["DATABASE_URL"]
        with pytest.raises(bk.ErroDoBackup) as erro:
            bk.ler_configuracao(ambiente)
        texto = str(erro.value)
        for nome in ("DATABASE_URL", "BACKUP_SENHA", "GOOGLE_OAUTH_REFRESH_TOKEN"):
            assert nome in texto
        assert "GOOGLE_OAUTH_CLIENT_ID" not in texto
        assert not any(s in texto for s in SEGREDOS)

    def test_a_senha_nao_perde_os_espacos(self):
        """Tirar o espaço fecharia o arquivo com outra senha que não a do e-mail."""
        assert bk.ler_configuracao(AMBIENTE_COMPLETO).senha == SENHA


class TestCaminhoFeliz:
    def test_os_passos_vem_na_ordem(self, tmp_path):
        _, rodar, drive = _executar(tmp_path)
        assert [c[0] for c in rodar.comandos] == ["pg_dump", "pg_restore", "gpg"]
        assert drive.envios == [(_nome(0), "pasta-1")]

    def test_o_dump_e_custom_e_vai_para_o_banco_da_variavel(self, tmp_path):
        _, rodar, _ = _executar(tmp_path)
        dump = rodar.comandos[0]
        assert "--format=custom" in dump
        assert f"--dbname={URL}" in dump

    def test_o_gpg_recebe_a_senha_pela_entrada_e_nao_por_argumento(self, tmp_path):
        _, rodar, _ = _executar(tmp_path)
        gpg = rodar.comandos[2]
        assert rodar.entradas[2] == SENHA
        assert not any("frase longa" in arg for arg in gpg)
        assert ["--passphrase-fd", "0"] == gpg[gpg.index("--passphrase-fd"):gpg.index("--passphrase-fd") + 2]
        assert ["--cipher-algo", "AES256"] == gpg[gpg.index("--cipher-algo"):gpg.index("--cipher-algo") + 2]
        assert "--symmetric" in gpg

    def test_o_arquivo_enviado_e_o_criptografado(self, tmp_path):
        """O gpg escreve no arquivo com o nome do dia, e é esse que sobe."""
        _, rodar, _ = _executar(tmp_path)
        gpg = rodar.comandos[2]
        assert Path(gpg[gpg.index("--output") + 1]).name == _nome(0)
        assert gpg[-1].endswith("banco.dump")


class TestFaxina:
    def test_apaga_so_o_que_passou_do_prazo(self, tmp_path):
        # ⚠️ 8 dias antes de 12/10 é 04/10, um DOMINGO (semanal, fica 35 dias): o
        # diário vencido tem de ser de um dia de semana - 03/10, um sábado.
        vencido = _nome(9)  # diário de 9 dias: sai
        no_prazo = _nome(7)  # diário de 7 dias (05/10, segunda): fica
        semanal = "arena-sagaz-prd_2026-09-13_semanal.dump.gpg"  # 29 dias: fica
        ficaram, _, drive = _executar(tmp_path, drive=DriveFalso([vencido, no_prazo, semanal]))
        assert drive.lixeira == ["antigo-0"]
        assert ficaram == sorted([no_prazo, semanal, _nome(0)])

    def test_arquivo_que_nao_e_nosso_fica(self, tmp_path):
        _, _, drive = _executar(tmp_path, drive=DriveFalso(["planilha do dono.xlsx"]))
        assert drive.lixeira == []

    def test_repetido_de_hoje_sai_e_o_novo_fica(self, tmp_path):
        """O dono disparou o serviço à mão duas vezes no mesmo dia."""
        ficaram, _, drive = _executar(tmp_path, drive=DriveFalso([_nome(0)]))
        assert drive.lixeira == ["antigo-0"]
        assert [a.id for a in drive.arquivos] == ["novo"]
        assert ficaram == [_nome(0)]


class TestNadaEApagadoQuandoAlgoFalha:
    """⛔ O pior caso de um defeito é um backup a menos - nunca os antigos a menos."""

    @pytest.mark.parametrize("programa", ["pg_dump", "pg_restore", "gpg"])
    def test_falha_de_programa_para_antes_do_drive(self, tmp_path, programa):
        drive = DriveFalso([_nome(30)])
        with pytest.raises(bk.ErroDoBackup) as erro:
            _executar(tmp_path, rodar=RodarFalso(falhar=programa), drive=drive)
        assert programa in str(erro.value)
        assert drive.envios == [] and drive.lixeira == []

    def test_indice_sem_a_tabela_do_alembic_e_recusado(self, tmp_path):
        drive = DriveFalso([_nome(30)])
        with pytest.raises(bk.ErroDoBackup, match="alembic_version"):
            _executar(tmp_path, rodar=RodarFalso(indice="TABLE DATA public outra"), drive=drive)
        assert drive.envios == [] and drive.lixeira == []

    def test_envio_que_chegou_pela_metade_nao_autoriza_a_faxina(self, tmp_path):
        drive = DriveFalso([_nome(30)], encolher_envio=1)
        with pytest.raises(bk.ErroDoBackup, match="incompleto"):
            _executar(tmp_path, drive=drive)
        assert drive.lixeira == []


class TestNenhumSegredoSaiNaMensagem:
    @pytest.mark.parametrize("programa", ["pg_dump", "pg_restore", "gpg"])
    def test_a_mensagem_de_falha_nao_tem_a_linha_de_comando(self, tmp_path, programa):
        with pytest.raises(bk.ErroDoBackup) as erro:
            _executar(tmp_path, rodar=RodarFalso(falhar=programa))
        texto = str(erro.value)
        assert not any(s in texto for s in SEGREDOS)
        assert "connection failed" in texto  # o fim do erro do programa, sim

    def test_main_devolve_1_e_imprime_so_o_nome_da_variavel(self, monkeypatch, capsys):
        for nome in bk.VARIAVEIS_EXIGIDAS:
            monkeypatch.delenv(nome, raising=False)
        monkeypatch.setenv("DATABASE_URL", URL)
        assert bk.main() == 1
        saida = capsys.readouterr()
        assert "BACKUP_SENHA" in saida.err
        assert "SENHA_DO_POSTGRES" not in saida.err + saida.out

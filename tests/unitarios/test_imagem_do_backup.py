"""A imagem e a configuração do serviço de backup batem com o código.

`railway.backup.json` é **documentação** do que tem de estar na UI do Railway (o
Config-as-code foi descontinuado - a lição da T049d, 16/09/2026). Ninguém o lê em
produção, então quem o mantém honesto é este teste: ele confere o arquivo contra
o `Dockerfile.backup` e contra o pacote `backup/`.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCKERFILE = (RAIZ / "Dockerfile.backup").read_text(encoding="utf-8")
CONFIG = json.loads((RAIZ / "railway.backup.json").read_text(encoding="utf-8"))

#: A versão maior do Postgres do `prd` (18.6, lida em 06/10/2026). Se o Railway
#: subir o banco para o 19, sobe aqui e no `FROM` do Dockerfile - um `pg_dump` mais
#: velho que o servidor recusa a cópia, e o backup falharia toda madrugada.
VERSAO_DO_POSTGRES_DO_PRD = 18


def _instrucoes() -> list[str]:
    """As linhas do Dockerfile que não são comentário nem vazias."""
    return [l.strip() for l in DOCKERFILE.splitlines() if l.strip() and not l.strip().startswith("#")]


def test_a_imagem_parte_do_postgres_da_versao_do_prd():
    assert f"FROM postgres:{VERSAO_DO_POSTGRES_DO_PRD}" in _instrucoes()


def test_a_imagem_instala_python_e_gpg():
    instalacao = " ".join(_instrucoes())
    assert re.search(r"apt-get install .*\bpython3\b", instalacao)
    assert re.search(r"apt-get install .*\bgnupg\b", instalacao)


def test_o_comando_roda_o_modulo_do_backup():
    assert 'CMD ["python3", "-m", "backup.backup_do_banco"]' in _instrucoes()
    assert (RAIZ / "backup" / "backup_do_banco.py").exists()


def test_o_entrypoint_do_postgres_e_zerado():
    """Sem isso o container tentaria preparar um servidor de banco."""
    assert "ENTRYPOINT []" in _instrucoes()


def test_nao_roda_como_root():
    assert "USER postgres" in _instrucoes()


def test_o_pacote_so_usa_a_biblioteca_padrao():
    """A imagem não tem `pip install`: um import de fora quebraria na madrugada."""
    import sys

    externos = set()
    for arquivo in (RAIZ / "backup").glob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
                nomes = [no.module]
            else:
                continue
            for nome in nomes:
                raiz = nome.split(".")[0]
                if raiz not in sys.stdlib_module_names and raiz not in ("backup", "__future__"):
                    externos.add(f"{arquivo.name}: {nome}")
    assert not externos, externos


def test_a_configuracao_do_railway_aponta_para_esta_imagem():
    assert CONFIG["build"]["dockerfilePath"] == "Dockerfile.backup"
    assert set(CONFIG["build"]["watchPatterns"]) == {"backup/**", "Dockerfile.backup"}


def test_o_cron_e_as_04_utc_e_nao_reinicia():
    """04:00 UTC: duas horas antes do job do desafio (06:00 UTC), decisão do dono."""
    assert CONFIG["deploy"]["cronSchedule"] == "0 4 * * *"
    assert CONFIG["deploy"]["restartPolicyType"] == "NEVER"
    assert "healthcheckPath" not in CONFIG["deploy"]

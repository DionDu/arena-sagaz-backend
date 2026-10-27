"""🔒 O `--forcar-jogo` do `rodar_job_local.py` (T121 da spec 010).

O script grava no banco, então o teste troca as três portas que falam com o
mundo (a URL do catálogo, a conferência do motor e o `principal` do job) por
espiões, e confere o que chegaria a elas.

O que se trava:

  1. **o `prd` recusa o jogo forçado**, mesmo com a confirmação - e recusa ANTES
     de ler a URL ou chamar o job;
  2. no `des`, o jogo forçado chega ao job como a faixa "1 dia em 1";
  3. só jogo em adoção se força;
  4. sem o argumento, o job é chamado como antes (sem faixa nenhuma), no `des`
     e no `prd`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from job import __main__ as principal_mod  # noqa: E402
from job.adocao import Frequencia, dia_do_jogo_novo  # noqa: E402
from scripts import rodar_job_local as script  # noqa: E402


@pytest.fixture
def portas(monkeypatch):
    """As três portas do script, trocadas por espiões que anotam as chamadas."""
    anotado: dict = {"url": [], "motor": 0, "principal": [], "sequencia": []}

    def url_espia(co_ambiente: str) -> str:
        anotado["url"].append(co_ambiente)
        return "postgresql+asyncpg://falso/falso"

    def motor_espiao() -> None:
        anotado["motor"] += 1

    def principal_espiao(dt_hoje=None, *, frequencias_forcadas=None, sequencia=None) -> int:
        anotado["principal"].append(frequencias_forcadas)
        anotado["sequencia"].append(sequencia)
        return 0

    monkeypatch.setattr(script, "url_do_ambiente", url_espia)
    monkeypatch.setattr(script, "conferir_o_motor", motor_espiao)
    monkeypatch.setattr(principal_mod, "principal", principal_espiao)
    # O script escreve estas duas variáveis; o `monkeypatch` as devolve no fim.
    monkeypatch.setenv("DATABASE_URL", "")
    # ⚠️ `setenv` ANTES do `delenv` (27/10/2026): `delenv` de uma variável
    # ausente não registra nada para desfazer, e o `--dias 10` que o script
    # escreve vazava para os testes seguintes da suíte (o plano do job crescia).
    monkeypatch.setenv("DESAFIO_DIAS_A_COBRIR", "")
    monkeypatch.delenv("DESAFIO_DIAS_A_COBRIR")
    return anotado


def _rodar(monkeypatch, argumentos: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["rodar_job_local.py", *argumentos])
    return script.main()


@pytest.mark.parametrize(
    "argumentos",
    [
        ["--ambiente", "prd", "--forcar-jogo", "quatro"],
        ["--ambiente", "prd", "--forcar-jogo", "quatro", "--confirmo-escrita-em-producao"],
    ],
)
def test_o_prd_recusa_o_jogo_forcado_mesmo_confirmado(monkeypatch, portas, argumentos):
    with pytest.raises(SystemExit) as erro:
        _rodar(monkeypatch, argumentos)
    assert "so do `des`" in str(erro.value)
    # Recusou ANTES de tudo: nem a URL do `prd` foi lida.
    assert portas == {"url": [], "motor": 0, "principal": [], "sequencia": []}


def test_no_des_o_jogo_forcado_chega_ao_job_como_todo_dia(monkeypatch, portas):
    assert _rodar(monkeypatch, ["--forcar-jogo", "quatro", "--dias", "10"]) == 0
    assert portas["url"] == ["des"]
    assert portas["principal"] == [{"quatro": Frequencia(um_dia_em=1)}]
    # "1 dia em 1" é a janela inteira da regra dos dias: todo dia é do jogo, e
    # quem alterna é a vizinhança.
    (faixa,) = portas["principal"][0].values()
    assert all(dia_do_jogo_novo(d, faixa) for d in range(400))


@pytest.mark.parametrize("jogo", ["pontinhos", "damas", "velha"])
def test_so_se_forca_jogo_em_adocao(monkeypatch, portas, jogo):
    with pytest.raises(SystemExit) as erro:
        _rodar(monkeypatch, ["--forcar-jogo", jogo])
    assert "so se forca jogo em adocao" in str(erro.value)
    assert portas["principal"] == []


def test_sem_o_argumento_o_job_e_chamado_como_antes(monkeypatch, portas):
    assert _rodar(monkeypatch, []) == 0
    assert portas["principal"] == [None]
    assert portas["sequencia"] == [None]
    assert portas["url"] == ["des"]


def test_o_prd_confirmado_sem_jogo_forcado_continua_rodando(monkeypatch, portas):
    assert _rodar(monkeypatch, ["--ambiente", "prd", "--confirmo-escrita-em-producao"]) == 0
    assert portas["principal"] == [None]
    assert portas["url"] == ["prd"]


def test_o_prd_sem_confirmacao_continua_recusado(monkeypatch, portas):
    with pytest.raises(SystemExit) as erro:
        _rodar(monkeypatch, ["--ambiente", "prd"])
    assert "--confirmo-escrita-em-producao" in str(erro.value)
    assert portas["principal"] == []


# ═══════════════════════════════════════════════════════════════════════════
# A sequência (`--sequencia`, `--jogo`, 27/10/2026)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "argumentos",
    [
        ["--ambiente", "prd", "--confirmo-escrita-em-producao", "--jogo", "quatro"],
        ["--ambiente", "prd", "--confirmo-escrita-em-producao", "--sequencia", "quatro_virada"],
    ],
)
def test_o_prd_recusa_a_sequencia_mesmo_confirmado(monkeypatch, portas, argumentos):
    with pytest.raises(SystemExit) as erro:
        _rodar(monkeypatch, argumentos)
    assert "so do `des`" in str(erro.value)
    assert portas["url"] == [] and portas["principal"] == []


def test_sequencia_e_jogo_forcado_nao_se_combinam(monkeypatch, portas):
    with pytest.raises(SystemExit):
        _rodar(monkeypatch, ["--forcar-jogo", "quatro", "--jogo", "quatro"])
    assert portas["principal"] == []


def test_a_sequencia_chega_ao_job_na_ordem_e_estica_o_plano(monkeypatch, portas):
    import os

    texto = "quatro_figura[figura=z], quatro_segurar_magno"
    assert _rodar(monkeypatch, ["--sequencia", texto]) == 0
    (sequencia,) = portas["sequencia"]
    assert [p.descrever() for p in sequencia] == [
        "quatro_figura[figura=z]",
        "quatro_segurar_magno",
    ]
    # Sem `--dias`, o teto: a lista precisa de dias livres para caber.
    assert os.environ["DESAFIO_DIAS_A_COBRIR"] == "30"


def test_o_jogo_sozinho_vira_um_pedido_por_tipo(monkeypatch, portas):
    assert _rodar(monkeypatch, ["--jogo", "quatro", "--dias", "14"]) == 0
    (sequencia,) = portas["sequencia"]
    assert len(sequencia) == len({p.co_tipo for p in sequencia}) > 1


def test_sequencia_invalida_para_ANTES_do_motor(monkeypatch, portas):
    """🔒 Um erro de digitação não pode custar a conferência do motor nem a geração."""
    with pytest.raises(SystemExit) as erro:
        _rodar(monkeypatch, ["--sequencia", "quatro_figura[w], quatro_bloquear"])
    assert "quatro_figura[w]" in str(erro.value)
    assert "quatro_bloquear" in str(erro.value)
    assert portas["motor"] == 0 and portas["principal"] == []

"""Os solucionadores proprios e o contexto deles (`job/solucionadores.py`, T124c da spec 010)."""

from __future__ import annotations

import pytest

from job import gerador
from job import solucionadores as sol
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR
from motores.nucleo.papeis import NivelDeMotor
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro

MOTOR = MotorQuatro("tradicional")
BASE = ("s3", "s3", "s4", "s4")


class _JogadorFalso:
    """So o que o perseguidor le do jogador: o executavel (aqui, nenhum)."""

    motor_dart = None


def _contexto(**trocas) -> sol.ContextoDoSolucionador:
    campos = dict(
        arbitro=MOTOR,
        jogador=_JogadorFalso(),
        estado_inicial=EstadoQuatro("tradicional", BASE),
        estado=EstadoQuatro("tradicional", BASE + ("s5", "s2")),
        nivel=NivelDeMotor.SAGAZ,
        semente=7,
        lance_do_nivel=lambda: "s1",
    )
    campos.update(trocas)
    return sol.ContextoDoSolucionador(**campos)


def test_com_chegada_poe_a_chegada_no_contexto() -> None:
    vistos = []
    ligado = sol.com_chegada(lambda c: vistos.append(c.js_chegada) or "s1", {"x": 1})
    assert ligado(_contexto()) == "s1"
    assert vistos == [{"x": 1}]


def test_tipo_sem_solucionador_continua_sem() -> None:
    assert sol.com_chegada(None, {"x": 1}) is None


def test_o_perseguidor_sem_chegada_falha_ALTO() -> None:
    """⛔ Jogar o lance do nivel aqui esconderia um caminho que esqueceu `com_chegada`."""
    perseguidor = sol.perseguidor_do_quatro("quatro_vencer_diagonal")
    with pytest.raises(RuntimeError, match="sem a linha de chegada"):
        perseguidor(_contexto())


def test_o_perseguidor_le_a_fita_a_partir_da_posicao_publicada() -> None:
    """Depois de s5 s2 o X vence pela horizontal em s6: num desafio de diagonal
    esse lance e o jeito ERRADO, e nao pode sair - se a fita fosse contada do
    tabuleiro vazio, a pessoa e os lances sairiam trocados."""
    chegada = {**RECEITAS, **RECEITAS_FORA_DO_AR}["quatro_vencer_diagonal"].montar({})
    perseguidor = sol.com_chegada(
        sol.perseguidor_do_quatro("quatro_vencer_diagonal"), chegada
    )
    # Sem executavel: a prova consultaria o `motor_dart`. A Cacau na mistura
    # (sorteio da semente 7) nao chega a prova se o lance do nivel sobreviver.
    lance = perseguidor(
        _contexto(nivel=NivelDeMotor.CACAU, lance_do_nivel=lambda: "s1")
    )
    assert lance != "s6"


def test_o_registro_liga_SO_os_tipos_que_a_medicao_aprovou() -> None:
    """⛔ A lista sai das medicoes pareadas, e cada entrada tem a sua:

    * diagonal e encostadas: a medicao de 21/10 (historico "2026-10-21 (9)");
    * golpe duplo e linha de cinco: a fase 2 de `medir_objetivo_forcavel_quatro.py`
      nas posicoes forcaveis (o perseguidor 1,00 contra os quatro adversarios;
      o Magno que so vence 0,50 a 0,83; o controle batendo) - historico
      "2026-10-21 (10)" e "(12)";
    * sem o meio: o mesmo banco, e o perseguidor e quem nao joga na coluna
      central (o Magno que so vence a ocuparia, e o gabarito descumpriria o
      proprio tipo) - historico "2026-10-21 (12)";
    * o "Encoste N em ate M": o script pareado com o controle PROPRIO dele (o
      alvo de jogar colado), 30 de 30, e o perseguidor-Magno 30 de 30 contra 10
      do Magno que so vence - historico "2026-10-22 (4)".
    """
    do_quatro = {t for t in gerador.SOLUCIONADOR_POR_TIPO if t.startswith("quatro_")}
    assert do_quatro == {
        "quatro_vencer_diagonal",
        "quatro_encostadas",
        "quatro_golpe_duplo",
        "quatro_linha_de_cinco",
        "quatro_sem_o_meio",
        "quatro_encoste",
    }


def test_o_teto_da_prova_e_o_da_medicao() -> None:
    """Mudar um sem o outro mediria um perseguidor que nao passou no controle."""
    import importlib.util
    import sys
    from pathlib import Path

    caminho = Path(__file__).parents[2] / "scripts" / "medir_perseguir_vs_vencer_quatro.py"
    spec = importlib.util.spec_from_file_location("medir_perseguir_q", caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["medir_perseguir_q"] = modulo
    spec.loader.exec_module(modulo)
    assert modulo.TETO_DA_PROVA_DO_MAGNO == sol.TETO_DA_PROVA_DO_PERSEGUIDOR

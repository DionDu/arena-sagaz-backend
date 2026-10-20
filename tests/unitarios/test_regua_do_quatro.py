"""A régua dos mascotes com o Quatro em Linha (T117 da spec 010).

O que a régua precisou aprender para medir o Quatro, e os cadeados de cada
coisa:

  1. **a vez vem do árbitro** quando o estado não a carrega (`regua.vez_de`):
     o `EstadoQuatro` é só a lista de lances;
  2. **cada lado joga no seu nível**: o mascote medido do lado de quem
     resolve, o adversário do dia do outro - a mesma regra das damas e do
     Pontinhos, conferida agora com o jogador do Quatro;
  3. **o Quatro mede em paralelo**, e isso só é seguro porque o
     `JogadorQuatro` NÃO guarda o processo da primeira thread: cada thread
     fala com o seu (`jogador_compartilhado`).
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from job import regua
from motores.nucleo.papeis import NivelDeMotor
from motores.quatro import jogador_quatro as jq_mod
from motores.quatro.jogador_quatro import DecisaoQuatro, JogadorQuatro
from motores.quatro.motor_quatro import EstadoQuatro, ler_sequencia

MODALIDADE = "tradicional"


def _estado(sequencia: str) -> EstadoQuatro:
    return EstadoQuatro(MODALIDADE, ler_sequencia(sequencia))


class _MotorDeMentira:
    """Faz o papel do executável: joga o 1º lance legal e anota quem pediu.

    Responde como o `decidir` do Dart (`lance` + `acao`), e a ação diz o nível,
    para o teste ver o nível sem abrir a resposta.
    """

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, NivelDeMotor]] = []
        self.arbitro = JogadorQuatro(MODALIDADE, motor_dart=self).arbitro

    def decidir(self, *, lances: str, co_modalidade: str, nivel, semente: int) -> dict:
        self.pedidos.append((lances, nivel))
        estado = EstadoQuatro(co_modalidade, ler_sequencia(lances))
        legais = self.arbitro.lances_legais(estado)
        if not legais:
            raise ValueError("partida terminada")
        return {"lance": legais[0], "acao": f"nivel_{nivel.value}"}


# ═══════════════════════════════════════════════════════════════════════════
# 1. A vez
# ═══════════════════════════════════════════════════════════════════════════


def test_a_vez_do_quatro_vem_do_arbitro() -> None:
    jogador = JogadorQuatro(MODALIDADE, motor_dart=_MotorDeMentira())
    assert regua.vez_de(jogador, _estado("")) == 1
    assert regua.vez_de(jogador, _estado("s4")) == -1
    assert regua.vez_de(jogador, _estado("s4s4s3")) == -1


def test_sem_arbitro_a_vez_vem_do_estado() -> None:
    """As damas e o Pontinhos: o estado carrega `vez_de`, e nada muda para eles."""
    jogador = SimpleNamespace()  # o MotorDamas não tem `arbitro`
    assert regua.vez_de(jogador, SimpleNamespace(vez_de=-1)) == -1


def test_o_arbitro_vence_um_estado_que_tambem_responda() -> None:
    """Pelo árbitro primeiro: é ele quem conhece a modalidade."""
    jogador = SimpleNamespace(arbitro=SimpleNamespace(vez_de=lambda estado: -1))
    assert regua.vez_de(jogador, SimpleNamespace(vez_de=1)) == -1


def test_o_arbitro_do_pontinhos_nao_responde_a_vez() -> None:
    """O `JogadorPontinhos.arbitro` é o `MotorPontinhos`, que NÃO tem `vez_de`:
    se um dia tiver, este caso avisa que a leitura do Pontinhos mudou de dono."""
    from motores.pontinhos.motor_pontinhos import MotorPontinhos

    assert not callable(getattr(MotorPontinhos(), "vez_de", None))


# ═══════════════════════════════════════════════════════════════════════════
# 2. Cada lado no seu nível
# ═══════════════════════════════════════════════════════════════════════════


def test_o_mascote_joga_do_lado_de_quem_resolve_e_o_adversario_do_outro() -> None:
    motor = _MotorDeMentira()
    jogador = JogadorQuatro(MODALIDADE, motor_dart=motor)
    fitas: list[list[dict]] = []

    def julgar(fita):
        fitas.append(list(fita))
        return SimpleNamespace(cumpriu=len(fita) == 4)

    # Posição com 3 lances: quem resolve é o jogador 2 (-1).
    tentar = regua.tentativa_com_motor(
        jogador=jogador,
        estado_inicial=_estado("s4s4s3"),
        julgar=julgar,
        nu_semente=11,
        maximo_de_meios_lances=10,
        co_personagem_do_dia="magno",
    )
    assert tentar("cacau", 1) is True
    fita = fitas[-1]
    assert [p["jogador"] for p in fita] == [-1, 1, -1, 1]
    niveis = [nivel for _, nivel in motor.pedidos]
    assert niveis == [
        NivelDeMotor.CACAU,
        NivelDeMotor.SAGAZ,
        NivelDeMotor.CACAU,
        NivelDeMotor.SAGAZ,
    ]


def test_partida_terminada_antes_do_objetivo_nao_resolve() -> None:
    """O motor recusa jogar depois do fim (ValueError), e a tentativa é perdida."""
    motor = _MotorDeMentira()
    jogador = JogadorQuatro(MODALIDADE, motor_dart=motor)
    tentar = regua.tentativa_com_motor(
        jogador=jogador,
        # O J1 vence no próximo lance (coluna 1), e o 1º legal é exatamente ela.
        estado_inicial=_estado("s1s2s1s2s1s2"),
        julgar=lambda fita: SimpleNamespace(cumpriu=False),
        nu_semente=11,
        maximo_de_meios_lances=10,
        co_personagem_do_dia="tex",
    )
    assert tentar("pita", 1) is False


def test_a_decisao_do_quatro_traz_o_motivo() -> None:
    jogador = JogadorQuatro(MODALIDADE, motor_dart=_MotorDeMentira())
    decisao = jogador.decidir(_estado("s4"), NivelDeMotor.TEX, 3)
    assert decisao == DecisaoQuatro("s1", "nivel_tex", decisao.resposta)
    assert jogador.escolher_lance(_estado("s4"), NivelDeMotor.TEX, semente=3) == "s1"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Em paralelo, um processo por thread
# ═══════════════════════════════════════════════════════════════════════════


def test_o_quatro_mede_em_paralelo(monkeypatch) -> None:
    monkeypatch.delenv(regua.ENV_PARALELA, raising=False)
    monkeypatch.setattr(regua.os, "cpu_count", lambda: 4)
    assert regua.PARALELISMO_POR_JOGO["quatro"] == "maquina"
    assert regua.trabalhadores_para("quatro") == 3


def test_cada_thread_fala_com_o_seu_processo(monkeypatch) -> None:
    """⛔ O cadeado do paralelo: o jogador NÃO guarda o processo de quem perguntou
    primeiro. Com a guarda, a 2ª thread escreveria no `stdin` da 1ª."""
    local = threading.local()
    abertos: list[object] = []

    def compartilhado():
        if not hasattr(local, "motor"):
            local.motor = object()
            abertos.append(local.motor)
        return local.motor

    monkeypatch.setattr(jq_mod, "jogador_compartilhado", compartilhado)
    jogador = JogadorQuatro(MODALIDADE)
    vistos: dict[str, object] = {}

    def pergunta(nome: str) -> None:
        vistos[nome] = jogador.motor_dart

    pergunta("principal")
    outra = threading.Thread(target=pergunta, args=("outra",))
    outra.start()
    outra.join()
    assert vistos["principal"] is not vistos["outra"]
    assert len(abertos) == 2
    # E na mesma thread, o mesmo processo de novo (sem abrir um terceiro).
    assert jogador.motor_dart is vistos["principal"]
    assert len(abertos) == 2


def test_o_motor_injetado_continua_valendo_em_toda_thread() -> None:
    """Quem injeta (os testes, a bancada) escolheu um processo só, de propósito."""
    motor = _MotorDeMentira()
    jogador = JogadorQuatro(MODALIDADE, motor_dart=motor)
    visto: list[object] = []
    outra = threading.Thread(target=lambda: visto.append(jogador.motor_dart))
    outra.start()
    outra.join()
    assert visto == [motor]


@pytest.mark.parametrize("co_jogo", ["damas", "quatro"])
def test_o_paralelo_nao_muda_a_contagem(co_jogo, monkeypatch) -> None:
    """A taxa é a mesma em série e em paralelo: cada execução tem a sua semente."""

    def tentar(co_personagem: str, execucao: int) -> bool:
        return (execucao * len(co_personagem)) % 3 == 0

    def medir(paralela: str):
        monkeypatch.setenv(regua.ENV_PARALELA, paralela)
        return regua.medir_candidato(
            co_personagem_do_dia="tex",
            tentar=tentar,
            co_versao_perfil="p",
            co_versao_motor="m",
            nu_execucoes=12,
            co_jogo=co_jogo,
        )

    assert medir("1") == medir("4")

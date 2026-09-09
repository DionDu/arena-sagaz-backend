"""T006 — o orçamento de busca dos motores (RF-DES-163).

⚠️ **Nenhum teste daqui dorme.** O relógio entra por parâmetro justamente para
isso: um teste que espera meio segundo para provar "estourou o tempo" é um teste
que alguém marca para pular no primeiro dia apertado.
"""

import pytest

from motores.nucleo.orcamento import BuscaCancelada, Orcamento
from motores.nucleo.papeis import LimiteDeBusca


class RelogioFalso:
    """Um relógio que só anda quando mandam — em segundos.

    Substitui `time.monotonic` nos testes. `avancar(0.3)` é a passagem de 300 ms
    sem que ninguém espere de verdade.
    """

    def __init__(self) -> None:
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


def orcamento_de_teste(nos: int = 100, segundos: float = 1.0) -> tuple[Orcamento, RelogioFalso]:
    """Monta um orçamento com relógio falso, já iniciado."""
    relogio = RelogioFalso()
    return Orcamento(nos_maximos=nos, segundos_maximos=segundos, relogio=relogio).iniciar(), relogio


# ── A fronteira ─────────────────────────────────────────────────────────────


def test_orcamento_satisfaz_o_protocolo_limite_de_busca():
    """É assim que `escolher_lance` o aceita, sem herança nenhuma."""
    orcamento, _ = orcamento_de_teste()
    assert isinstance(orcamento, LimiteDeBusca)


# ── Tetos que não fazem sentido são recusados na construção ────────────────


@pytest.mark.parametrize("nos", [0, -1])
def test_teto_de_nos_nao_positivo_e_recusado(nos):
    """Teto zero não é 'sem limite' — é quase sempre parâmetro esquecido."""
    with pytest.raises(ValueError, match="nos_maximos"):
        Orcamento(nos_maximos=nos, segundos_maximos=1.0)


@pytest.mark.parametrize("segundos", [0.0, -0.5])
def test_teto_de_tempo_nao_positivo_e_recusado(segundos):
    with pytest.raises(ValueError, match="segundos_maximos"):
        Orcamento(nos_maximos=10, segundos_maximos=segundos)


# ── O teto de nós ───────────────────────────────────────────────────────────


def test_nao_cancela_enquanto_ha_orcamento():
    orcamento, _ = orcamento_de_teste(nos=10)
    orcamento.contar_no(9)
    assert orcamento.cancelado() is False


def test_cancela_ao_atingir_o_teto_de_nos():
    orcamento, _ = orcamento_de_teste(nos=10)
    orcamento.contar_no(10)
    assert orcamento.cancelado() is True


def test_contar_em_lote_e_equivalente_a_contar_um_a_um():
    """O motor que conta a cada N nós custa menos e não perde o teto."""
    um_a_um, _ = orcamento_de_teste(nos=5)
    for _ in range(5):
        um_a_um.contar_no()
    em_lote, _ = orcamento_de_teste(nos=5)
    em_lote.contar_no(5)
    assert um_a_um.cancelado() == em_lote.cancelado() is True


# ── O teto de tempo ─────────────────────────────────────────────────────────


def test_cancela_ao_estourar_o_tempo_mesmo_com_nos_de_sobra():
    orcamento, relogio = orcamento_de_teste(nos=1_000_000, segundos=0.5)
    orcamento.contar_no(3)
    assert orcamento.cancelado() is False
    relogio.avancar(0.5)
    assert orcamento.cancelado() is True


def test_tempo_gasto_e_zero_antes_de_iniciar():
    orcamento = Orcamento(nos_maximos=10, segundos_maximos=1.0, relogio=RelogioFalso())
    assert orcamento.segundos_gastos == 0.0


def test_iniciar_duas_vezes_e_recusado():
    """Reiniciar o relógio no meio daria à posição patológica o fôlego extra
    que o teto existe para negar."""
    orcamento, _ = orcamento_de_teste()
    with pytest.raises(RuntimeError, match="já foi iniciado"):
        orcamento.iniciar()


# ── Cancelamento por fora, sem estado sujo ─────────────────────────────────


def test_cancelar_por_fora_para_a_busca_na_proxima_consulta():
    orcamento, _ = orcamento_de_teste()
    assert orcamento.cancelado() is False
    orcamento.cancelar()
    assert orcamento.cancelado() is True


def test_cancelar_nao_apaga_o_que_ja_foi_gasto():
    """'Sem estado sujo' não é 'sem memória': a contagem sobrevive, e é ela que
    distingue 'jogou mal' de 'não teve tempo de pensar' no banco."""
    orcamento, _ = orcamento_de_teste()
    orcamento.contar_no(7)
    orcamento.cancelar()
    assert orcamento.nos_gastos == 7


def test_verificar_levanta_quando_o_orcamento_acaba():
    """A porta para o motor recursivo, que não tem um laço único onde consultar."""
    orcamento, _ = orcamento_de_teste(nos=2)
    orcamento.verificar()  # ainda há orçamento: não levanta
    orcamento.contar_no(2)
    with pytest.raises(BuscaCancelada):
        orcamento.verificar()


# ── Uso único ───────────────────────────────────────────────────────────────


def test_orcamento_estourado_continua_estourado():
    orcamento, _ = orcamento_de_teste(nos=1)
    orcamento.contar_no(1)
    assert orcamento.cancelado() is True
    orcamento.contar_no(0)
    assert orcamento.cancelado() is True


def test_proximo_lance_nasce_zerado_com_os_mesmos_tetos():
    gasto, relogio = orcamento_de_teste(nos=10, segundos=0.5)
    gasto.contar_no(10)
    relogio.avancar(0.5)

    novo = gasto.para_o_proximo_lance().iniciar()
    assert novo.nos_maximos == 10
    assert novo.segundos_maximos == 0.5
    assert novo.nos_gastos == 0
    assert novo.cancelado() is False
    # E o antigo segue estourado — nada foi zerado por baixo.
    assert gasto.cancelado() is True


# ── O resumo que vai para o carimbo ─────────────────────────────────────────


def test_resumo_diz_se_estourou_e_quanto_gastou():
    orcamento, relogio = orcamento_de_teste(nos=50, segundos=2.0)
    orcamento.contar_no(50)
    relogio.avancar(0.25)

    resumo = orcamento.resumo()
    assert resumo["nos_gastos"] == 50
    assert resumo["nos_maximos"] == 50
    assert resumo["segundos_gastos"] == 0.25
    assert resumo["estourou"] is True


def test_resumo_e_serializavel_em_json():
    """Ele vai para o banco junto com a medição — precisa passar por JSON."""
    import json

    orcamento, _ = orcamento_de_teste()
    orcamento.contar_no(3)
    json.dumps(orcamento.resumo())  # não levanta

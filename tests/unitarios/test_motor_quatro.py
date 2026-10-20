"""O árbitro do Quatro em Linha (spec 010, T105).

O que se confere:
  - ele é `Arbitro` e NÃO é `JogadorDeMotor` (validar não é jogar);
  - as quatro direções de linha, encostadas na borda; cinco em linha são UMA
    linha; um lance que fecha duas devolve as duas; a última casa que fecha
    linha é vitória, e não empate;
  - o tabuleiro cheio sem linha é empate;
  - as recusas: coluna cheia, coluna fora do tabuleiro, lance depois do fim,
    notação errada, modalidade desconhecida, tipo de lance sem regra;
  - o dado do banco vai e volta, e o de outro formato é recusado;
  - nenhum tamanho de tabuleiro escrito no código (o cadeado de fonte).

A modalidade real é a 1ª que o contrato declara: o teste não a cita pelo nome.
Os casos de geometria pequena injetam regras de gravidade com outras dimensões,
pela mesma porta que a modalidade-sonda usa (T108).
"""

import ast
import json
from pathlib import Path

import pytest

from motores.nucleo.papeis import Arbitro, JogadorDeMotor, NivelDeMotor
from motores.quatro import contrato_quatro as cq
from motores.quatro.motor_quatro import (
    MOTIVO_ALINHOU,
    MOTIVO_TABULEIRO_CHEIO,
    EstadoQuatro,
    MotorQuatro,
    RegrasDeGravidadeQuatro,
    estado_inicial,
    ler_sequencia,
)

MODALIDADE = cq.modalidades_declaradas()[0]
DIM = cq.dimensoes(MODALIDADE)


@pytest.fixture
def motor() -> MotorQuatro:
    return MotorQuatro(MODALIDADE)


def _jogar(motor: MotorQuatro, sequencia: str) -> EstadoQuatro:
    """O estado depois da [sequencia], lance a lance pelo `aplicar`."""
    estado = estado_inicial(motor.co_modalidade)
    for lance in ler_sequencia(sequencia):
        estado = motor.aplicar(estado, lance)
    return estado


def _pequeno(largura: int, altura: int, alinhar: int) -> MotorQuatro:
    """Um árbitro de gravidade com outro tamanho, para os casos de geometria."""
    regras = RegrasDeGravidadeQuatro(
        cq.DimensoesQuatro(largura=largura, altura=altura, alinhar=alinhar),
        {"s": "soltar"},
    )
    return MotorQuatro(MODALIDADE, regras=regras)


class TestOPapel:
    def test_e_arbitro_e_nao_joga(self, motor):
        assert isinstance(motor, Arbitro)
        # ⛔ Sem `escolher_lance`: o avaliador do desafio, que recebe o árbitro,
        # não tem como jogar.
        assert not isinstance(motor, JogadorDeMotor)
        assert not hasattr(motor, "escolher_lance")

    def test_o_tabuleiro_vazio_tem_todas_as_colunas(self, motor):
        estado = estado_inicial(MODALIDADE)
        assert motor.lances_legais(estado) == [f"s{c}" for c in range(1, DIM.largura + 1)]
        assert motor.vez_de(estado) == 1
        assert motor.veredito(estado).acabou is False

    def test_a_vez_alterna_e_o_estado_antigo_nao_muda(self, motor):
        inicio = estado_inicial(MODALIDADE)
        depois = motor.aplicar(inicio, "s4")
        assert inicio.lances == ()
        assert motor.vez_de(depois) == -1
        assert motor.tabuleiro(depois).peca((4, 1)) == 1


class TestAsLinhas:
    def test_vertical_na_borda_esquerda(self, motor):
        estado = _jogar(motor, "s1s2s1s2s1s2s1")
        v = motor.veredito(estado)
        assert (v.acabou, v.co_motivo, v.vencedor) == (True, MOTIVO_ALINHOU, 1)
        assert motor.desfecho(estado).linhas == (((1, 1), (1, 2), (1, 3), (1, 4)),)

    def test_horizontal_na_borda_direita_vence_o_jogador_2(self, motor):
        d = DIM.largura
        # O J1 joga longe; o J2 enche a linha de baixo da direita.
        seq = f"s1s{d}s1s{d-1}s2s{d-2}s2s{d-3}"
        estado = _jogar(motor, seq)
        assert motor.veredito(estado).vencedor == -1
        assert motor.desfecho(estado).linhas == (
            ((d - 3, 1), (d - 2, 1), (d - 1, 1), (d, 1)),
        )

    def test_diagonal_que_sobe(self, motor):
        # Escada: J1 em (1,1) (2,2) (3,3) (4,4). O 10º lance (J2) vai para a
        # última coluna: na 5ª ele fecharia a linha de baixo (2,1)..(5,1).
        estado = _jogar(motor, f"s1s2s2s3s3s4s3s4s4s{DIM.largura}s4")
        assert motor.veredito(estado).vencedor == 1
        assert motor.desfecho(estado).linhas == (((1, 1), (2, 2), (3, 3), (4, 4)),)

    def test_diagonal_que_desce(self, motor):
        # O espelho da anterior: J1 em (4,1) (3,2) (2,3) (1,4).
        estado = _jogar(motor, "s4s3s3s2s2s1s2s1s1s5s1")
        assert motor.veredito(estado).vencedor == 1
        assert motor.desfecho(estado).linhas == (((1, 4), (2, 3), (3, 2), (4, 1)),)

    def test_cinco_em_linha_sao_uma_linha(self):
        m = _pequeno(5, 2, 4)
        # J1: 1,2,4,5 na linha de baixo; J2 em cima; o J1 fecha no meio (3).
        estado = _jogar(m, "s1s1s2s2s4s4s5s5s3")
        assert m.desfecho(estado).linhas == (tuple((c, 1) for c in range(1, 6)),)

    def test_a_ultima_casa_fecha_duas_linhas_e_e_vitoria(self):
        m = _pequeno(3, 3, 3)
        # O 9º lance (J1 em (3,3)) é a última casa do tabuleiro e fecha DUAS
        # linhas: a coluna 3 inteira e a diagonal (1,1)-(3,3). Antes dele
        # ninguém tem três: J1 (1,1)(2,2)(3,1)(3,2); J2 (2,1)(1,2)(1,3)(2,3).
        antes = _jogar(m, "s1s2s2s1s3s1s3s2")
        assert m.veredito(antes).acabou is False
        estado = m.aplicar(antes, "s3")
        v = m.veredito(estado)
        # Vitória, e não empate, mesmo com o tabuleiro cheio.
        assert (v.co_motivo, v.vencedor) == (MOTIVO_ALINHOU, 1)
        # A vertical vem antes da diagonal: a ordem de direções do motor Dart.
        assert m.desfecho(estado).linhas == (
            ((3, 1), (3, 2), (3, 3)),
            ((1, 1), (2, 2), (3, 3)),
        )

    def test_o_tabuleiro_cheio_sem_linha_e_empate(self):
        m = _pequeno(2, 2, 3)  # alinhar 3 num 2×2: ninguém vence
        estado = _jogar(m, "s1s1s2s2")
        v = m.veredito(estado)
        assert (v.acabou, v.co_motivo, v.vencedor) == (True, MOTIVO_TABULEIRO_CHEIO, 0)
        assert m.desfecho(estado).linhas == ()
        assert m.lances_legais(estado) == []


class TestAsRecusas:
    def test_a_coluna_cheia(self, motor):
        cheia = "".join("s1" for _ in range(DIM.altura))
        # Alternando J1/J2 na mesma coluna ninguém alinha na vertical.
        estado = _jogar(motor, cheia)
        assert "s1" not in motor.lances_legais(estado)
        with pytest.raises(ValueError, match="ilegal"):
            motor.aplicar(estado, "s1")

    def test_a_coluna_fora_do_tabuleiro(self, motor):
        with pytest.raises(ValueError, match="ilegal"):
            motor.aplicar(estado_inicial(MODALIDADE), f"s{DIM.largura + 1}")

    def test_lance_depois_do_fim(self, motor):
        estado = _jogar(motor, "s1s2s1s2s1s2s1")
        assert motor.lances_legais(estado) == []
        with pytest.raises(ValueError, match="depois do fim"):
            motor.aplicar(estado, "s3")

    @pytest.mark.parametrize("ruim", ["s0", "x4", "S4", "s04", "4", "s"])
    def test_notacao_errada(self, motor, ruim):
        with pytest.raises(ValueError):
            motor.aplicar(estado_inicial(MODALIDADE), ruim)

    @pytest.mark.parametrize("ruim", ["s4 s3", "s4s", "4s4", "s4-s3"])
    def test_sequencia_com_sobra(self, ruim):
        with pytest.raises(ValueError):
            ler_sequencia(ruim)

    def test_a_sequencia_vazia_e_o_tabuleiro_vazio(self, motor):
        assert ler_sequencia("") == ()
        assert motor.estado_de_sequencia("").lances == ()

    def test_a_modalidade_desconhecida(self):
        with pytest.raises(cq.ModalidadeDesconhecida):
            MotorQuatro("pop_out_que_nao_existe")
        with pytest.raises(cq.ModalidadeDesconhecida):
            estado_inicial("pop_out_que_nao_existe")

    def test_o_estado_de_outra_modalidade(self, motor):
        with pytest.raises(ValueError, match="entregue ao árbitro"):
            motor.lances_legais(EstadoQuatro(co_modalidade="outra"))

    def test_tipo_de_lance_sem_regra(self, tmp_path, monkeypatch):
        dados = json.loads(cq.CAMINHO_DO_CONTRATO.read_text(encoding="utf-8"))
        [entrada] = dados["por_modalidade"].values()
        entrada["tipos_de_lance"] = {"s": "soltar", "t": "tirar"}
        dados["por_modalidade"] = {"pop_x": entrada}
        caminho = tmp_path / "contrato.json"
        caminho.write_text(json.dumps(dados), encoding="utf-8")
        monkeypatch.setattr(cq, "CAMINHO_DO_CONTRATO", caminho)
        cq._bytes_do_contrato.cache_clear()
        try:
            with pytest.raises(cq.ContratoQuatroInvalido, match="não tem regra"):
                MotorQuatro("pop_x")
        finally:
            cq._bytes_do_contrato.cache_clear()


class TestODado:
    def test_vai_e_volta(self, motor):
        estado = _jogar(motor, "s4s4s3")
        dado = motor.para_dado(estado)
        assert dado["co_formato_posicao"] == "sequencia_lances"
        assert dado["co_lances"] == "s4s4s3"
        assert dado["vez_de"] == -1
        assert motor.de_dado(dado) == estado

    def test_recusa_o_fen_e_outro_jogo(self, motor):
        dado = motor.para_dado(_jogar(motor, "s4"))
        with pytest.raises(ValueError, match="sequencia_lances"):
            motor.de_dado({**dado, "co_formato_posicao": "fen"})
        with pytest.raises(ValueError, match="não do Quatro"):
            motor.de_dado({**dado, "co_jogo": "pontinhos"})

    def test_recusa_o_dado_com_lance_ilegal(self, motor):
        dado = motor.para_dado(_jogar(motor, "s4"))
        with pytest.raises(ValueError):
            motor.de_dado({**dado, "sequencia_lances": ["s4", "s9999"]})

    def test_o_carimbo(self, motor):
        carimbo = motor.carimbo(NivelDeMotor.SAGAZ, "regua-1")
        assert carimbo.co_jogo == "quatro"
        assert carimbo.co_modalidade == MODALIDADE
        assert carimbo.co_versao_motor == cq.versao_do_motor()


def test_nenhum_tamanho_de_tabuleiro_escrito_no_codigo():
    """O cadeado de fonte da T105: as dimensões vêm do contrato.

    Procura, pela árvore do Python (e não por texto, que acharia os números dos
    comentários), constantes inteiras do tamanho de um tabuleiro conhecido.
    """
    pasta = Path(__file__).resolve().parents[2] / "motores" / "quatro"
    proibidos = {
        DIM.largura, DIM.altura,
    } - {0, 1, 2}  # 0, 1 e 2 são aritmética (índices, passos), não tamanho
    for arquivo in sorted(pasta.glob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Constant) and type(no.value) is int:
                assert no.value not in proibidos, (
                    f"{arquivo.name}:{no.lineno} escreve o número {no.value}: "
                    "a dimensão do tabuleiro vem do contrato."
                )

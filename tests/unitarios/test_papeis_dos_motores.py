"""T004 — os dois papéis da camada de motores (RF-DES-160 a 162, 164, 166).

O que estes testes travam, e por quê:

1. **Que os papéis sejam mesmo DOIS.** Um objeto que só sabe arbitrar tem de
   satisfazer `Arbitro` e **não** satisfazer `JogadorDeMotor` — é isso que torna
   "validar não é jogar" (RF-DES-035) uma propriedade da peça, e não uma promessa.
2. **Que nenhuma assinatura mencione transporte** (RF-DES-166). A spec chama isso
   de "critério de aceitação verificável por leitura"; aqui a leitura é feita por
   máquina, porque leitura humana envelhece.
3. **Que o estado seja por valor** (RF-DES-162): `aplicar` devolve estado novo e
   não altera o que recebeu.
"""

import inspect

import pytest

from motores.nucleo.papeis import (
    Arbitro,
    JogadorDeMotor,
    LimiteDeBusca,
    NivelDeMotor,
    TradutorDeEstado,
    Veredito,
)


# ── Dublês de teste ─────────────────────────────────────────────────────────
#
# Um jogo de brinquedo: o estado é um `int` (quantos passos foram dados) e o
# lance é um `str`. Serve para exercitar os papéis sem arrastar damas nem CNN
# para dentro de um teste de unidade.


class ArbitroDeBrinquedo:
    """Sabe arbitrar e mais nada — é justamente esse o ponto do teste."""

    def lances_legais(self, estado: int) -> list[str]:
        return [] if estado >= 3 else ["andar", "parar"]

    def aplicar(self, estado: int, lance: str) -> int:
        if lance not in self.lances_legais(estado):
            raise ValueError(f"lance ilegal: {lance}")
        # Devolve um valor NOVO; `estado` é imutável (int), então não há como
        # sujá-lo por engano — que é exatamente o espírito de RF-DES-162.
        return estado + 1

    def veredito(self, estado: int) -> Veredito:
        if estado < 3:
            return Veredito(acabou=False)
        return Veredito(acabou=True, co_motivo="passos_esgotados", vencedor=0)


class MotorCompletoDeBrinquedo(ArbitroDeBrinquedo):
    """Veste os DOIS papéis, como um motor de verdade faz."""

    def escolher_lance(
        self, estado: int, nivel: NivelDeMotor, limite: LimiteDeBusca
    ) -> str:
        # Um motor de verdade consultaria `limite.cancelado()` no laço; aqui só
        # provamos que a assinatura fecha.
        return "parar" if nivel is NivelDeMotor.SAGAZ else "andar"


class LimiteFixo:
    """Um orçamento que nunca cancela — o mínimo que `LimiteDeBusca` pede."""

    nos_maximos = 1_000
    segundos_maximos = 0.5

    def cancelado(self) -> bool:
        return False


# ── 1. Os papéis são dois, e a separação é estrutural ───────────────────────


def test_arbitro_puro_satisfaz_arbitro():
    assert isinstance(ArbitroDeBrinquedo(), Arbitro)


def test_arbitro_puro_NAO_satisfaz_o_papel_de_jogador():
    """O coração de RF-DES-035: quem só arbitra não tem como jogar.

    Se este teste um dia passar a falhar, alguém acrescentou um método de escolha
    ao árbitro — e o avaliador de resoluções voltou a poder rodar busca.
    """
    assert not isinstance(ArbitroDeBrinquedo(), JogadorDeMotor)


def test_motor_completo_satisfaz_os_dois_papeis():
    motor = MotorCompletoDeBrinquedo()
    assert isinstance(motor, Arbitro)
    assert isinstance(motor, JogadorDeMotor)


def test_limite_de_busca_e_satisfeito_por_quem_tem_os_tres_membros():
    assert isinstance(LimiteFixo(), LimiteDeBusca)


# ── 2. Nenhuma assinatura menciona transporte (RF-DES-166) ──────────────────

# Palavras que denunciariam a camada tendo virado uma API. Ficam em minúsculas
# porque a comparação é feita sobre o texto da assinatura em minúsculas.
PALAVRAS_DE_TRANSPORTE = (
    "request",
    "response",
    "requisicao",
    "requisição",
    "resposta",
    "token",
    "sessao",
    "sessão",
    "session",
    "header",
    "cabecalho",
    "cabeçalho",
    "endpoint",
    "rota",
    "http",
)


@pytest.mark.parametrize("papel", [Arbitro, JogadorDeMotor, TradutorDeEstado])
def test_nenhuma_assinatura_dos_papeis_menciona_transporte(papel):
    """RF-DES-166 — expor depois deve ser acrescentar camada, não mexer no motor.

    ⚠️ Olhamos a **assinatura**, não a docstring: a prosa pode (e deve) explicar
    por que a rota não existe; o que não pode é um parâmetro ou um tipo de
    retorno carregar vocabulário de HTTP.
    """
    for nome, membro in vars(papel).items():
        if nome.startswith("_") or not callable(membro):
            continue
        # `inspect.signature` devolve "(self, estado: TipoEstado) -> ...".
        assinatura = str(inspect.signature(membro)).lower()
        for palavra in PALAVRAS_DE_TRANSPORTE:
            assert palavra not in assinatura, (
                f"{papel.__name__}.{nome} menciona '{palavra}' na assinatura — "
                "a camada de motores não pode conhecer transporte (RF-DES-166)."
            )


# ── 3. Estado por valor, e veredito imutável ────────────────────────────────


def test_aplicar_devolve_estado_novo_e_nao_altera_o_recebido():
    arbitro = ArbitroDeBrinquedo()
    antes = 0
    depois = arbitro.aplicar(antes, "andar")
    assert depois == 1
    assert antes == 0  # o estado recebido segue intacto


def test_aplicar_recusa_lance_ilegal_alto():
    """Recusar alto é o comportamento certo: quem chama é o auditor."""
    arbitro = ArbitroDeBrinquedo()
    with pytest.raises(ValueError):
        arbitro.aplicar(3, "andar")  # em 3 não há lance legal nenhum


def test_veredito_e_imutavel():
    v = Veredito(acabou=True, co_motivo="passos_esgotados", vencedor=0)
    # `frozen=True` faz a atribuição levantar — ninguém "corrige" um veredito
    # depois de recebê-lo.
    with pytest.raises(Exception):
        v.co_motivo = "outra_coisa"  # type: ignore[misc]


def test_veredito_de_partida_em_andamento_nao_tem_motivo_nem_vencedor():
    v = ArbitroDeBrinquedo().veredito(0)
    assert v.acabou is False
    assert v.co_motivo is None
    assert v.vencedor is None


# ── 4. A escada de níveis ───────────────────────────────────────────────────


def test_os_quatro_niveis_na_ordem_da_escada():
    assert [n.value for n in NivelDeMotor] == ["cacau", "pita", "tex", "sagaz"]


def test_indice_de_forca_cresce_do_cacau_ao_sagaz():
    assert NivelDeMotor.CACAU.indice_forca == 0
    assert NivelDeMotor.SAGAZ.indice_forca == 3


def test_o_nivel_nao_carrega_numero_de_jogo_nenhum():
    """RF-DES-140/141 — os parâmetros vêm do contrato do jogo, não do degrau.

    É a mesma regra que o app aplica a `NivelDificuldade`: pôr ε, teto de nós ou
    timer aqui faria a camada comum saber de um jogo específico.
    """
    proibidos = {"epsilon", "nos", "timer", "profundidade", "segundos"}
    for nome in dir(NivelDeMotor.CACAU):
        assert nome.lower() not in proibidos, (
            f"NivelDeMotor ganhou '{nome}' — número de jogo não mora no degrau."
        )

"""Cadeados da garantia de TÉRMINO, que estava sem teste (11/09/2026).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

No mesmo dia, um defeito de meses foi achado em `regua.tentativa_com_motor` — a
função aplicava o nível do mascote medido aos **dois lados** do tabuleiro, e a
régua media *"Cacau contra Cacau"* em vez de *"Cacau contra o adversário do
dia"*. ⛔ **O comentário no topo do módulo descrevia o comportamento certo**; só
o código é que nunca o cumpriu.

⚠️ **O que permitiu isso durar foi a ausência de teste**: `tentativa_com_motor`
não era mencionada em lugar nenhum da suíte. Uma varredura no dia seguinte achou
**nove** funções públicas na mesma situação; este arquivo cobre as duas que
guardam garantias declaradas em documento:

  · `estado_terminal.provar_termino` — *"toda partida de desafio chega a estado
    terminal, provado **na geração**"* (`CLAUDE.md`, Bloco 1c).

⚠️ **A varredura achou uma segunda coisa, e ela nem chegou a virar teste:**
`gabarito.lance_chave_padrao` era **código morto**, e a docstring dela declarava
um parâmetro que o corpo não usava — uma única execução teria levantado
`TypeError`. Foi removida; a nota ficou no lugar dela.

⚠️ **Nada aqui roda motor de verdade.** Os dublês respondem o que o teste quer
perguntar, e é isso que torna estes casos baratos o bastante para ficarem na
suíte — a mesma razão pela qual `moldes_de_damas` pergunta por lances legais em
vez de rodar busca.
"""

from __future__ import annotations

from dataclasses import dataclass

from job.estado_terminal import provar_termino


# ═══════════════════════════════════════════════════════════════════════════
# Os dublês
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class _Veredito:
    """O que o árbitro responde sobre uma posição."""

    acabou: bool
    co_motivo: str | None = None


class _EstadoContado:
    """Um estado que só sabe quantos lances já se jogou a partir do início."""

    def __init__(self, lances: int = 0) -> None:
        self.lances = lances

    def com_lance(self, _lance: str) -> "_EstadoContado":
        return _EstadoContado(self.lances + 1)


class _JogadorSempreJoga:
    """Escolhe um lance qualquer, sempre — a partida nunca trava por falta dele."""

    def escolher_lance(self, _estado, _nivel, *, limite=None, semente=None) -> str:
        return "x"


class _JogadorSemLance:
    """Recusa escolher lance — é o que o motor faz numa posição sem saída.

    ⚠️ **`ValueError` é o contrato**, e não um acidente: o motor não devolve
    `None` nem string vazia. Um dublê que devolvesse outra coisa testaria um
    caminho que não existe.
    """

    def escolher_lance(self, _estado, _nivel, *, limite=None, semente=None) -> str:
        raise ValueError("sem lance legal")


# ═══════════════════════════════════════════════════════════════════════════
# 1. provar_termino — a garantia de que a partida ACABA
# ═══════════════════════════════════════════════════════════════════════════


def test_partida_que_ja_NASCE_terminada_tem_zero_lances() -> None:
    """O árbitro diz que acabou antes do primeiro lance."""
    prova = provar_termino(
        jogador=_JogadorSempreJoga(),
        estado_inicial=_EstadoContado(),
        veredito_de=lambda _e: _Veredito(acabou=True, co_motivo="afogamento"),
        nu_semente=1,
    )
    assert prova.tem_fim is True
    assert prova.nu_lances == 0
    assert prova.co_motivo == "afogamento"


def test_a_contagem_e_de_lances_JOGADOS_e_nao_de_perguntas() -> None:
    """🔒 ⚠️ O laço pergunta ao árbitro **antes** de cada lance.

    Numa partida que acaba depois de três lances, a quarta pergunta é a que
    responde "acabou" — e o número a guardar é **3**, não 4. ⛔ Um erro de um aqui
    não quebraria nada visivelmente: apareceria como partidas sempre um lance
    mais longas no diagnóstico, e ninguém compara esse número com nada.
    """
    prova = provar_termino(
        jogador=_JogadorSempreJoga(),
        estado_inicial=_EstadoContado(),
        veredito_de=lambda e: _Veredito(acabou=e.lances >= 3, co_motivo="vitoria"),
        nu_semente=1,
    )
    assert prova.tem_fim is True
    assert prova.nu_lances == 3


def test_partida_que_NAO_acaba_no_teto_reprova() -> None:
    """🔒 ⛔ O caso que esta função existe para pegar.

    ⚠️ **É a garantia do Bloco 1c**: *"toda partida de desafio chega a estado
    terminal, provado na geração"*. Se isto devolvesse `tem_fim=True` por
    engano, o job publicaria um desafio cuja partida não fecha — e o sintoma
    apareceria no aparelho de alguém, meses depois, como uma partida que nunca
    vai para `concluida`.
    """
    prova = provar_termino(
        jogador=_JogadorSempreJoga(),
        estado_inicial=_EstadoContado(),
        veredito_de=lambda _e: _Veredito(acabou=False),
        nu_semente=1,
        teto_de_lances=5,
    )
    assert prova.tem_fim is False
    assert prova.nu_lances == 5


def test_motor_sem_lance_legal_PERGUNTA_ao_arbitro_em_vez_de_supor() -> None:
    """🔒 ⚠️ Ficar sem lance **costuma** ser fim de partida, e não é o mesmo que ser.

    Quem decide é o árbitro. O caso de baixo prova o contrário do intuitivo: com
    o motor recusando lance e o árbitro dizendo que a partida **não** acabou, a
    prova tem de **falhar** — porque aí há uma inconsistência entre as duas
    metades do motor, e ⛔ publicar sobre uma inconsistência é o que este passo
    impede.
    """
    de_acordo = provar_termino(
        jogador=_JogadorSemLance(),
        estado_inicial=_EstadoContado(),
        veredito_de=lambda _e: _Veredito(acabou=True, co_motivo="sem_lances"),
        nu_semente=1,
    )
    assert de_acordo.tem_fim is True
    assert de_acordo.co_motivo == "sem_lances"

    discordando = provar_termino(
        jogador=_JogadorSemLance(),
        estado_inicial=_EstadoContado(),
        veredito_de=lambda _e: _Veredito(acabou=False),
        nu_semente=1,
    )
    assert discordando.tem_fim is False, (
        "o motor não tem lance e o árbitro diz que a partida segue — isso é "
        "contradição, e a prova não pode passar por cima dela"
    )

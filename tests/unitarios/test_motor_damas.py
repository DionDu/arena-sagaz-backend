"""T014 — o motor de damas do backend (RF-DES-018/019/141/161/162).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTES TESTES PROVAM
═══════════════════════════════════════════════════════════════════════════

1. **Que o adaptador não distorce nada.** Na mesma posição, no mesmo nível e com
   a mesma semente, `MotorDamas.escolher_lance` devolve **o mesmo lance** que uma
   chamada direta ao `Buscador` do laboratório com os parâmetros do contrato.

   ⚠️ Comparar contra o motor **do espelho** é comparar contra o laboratório: o
   cadeado 6 (`test_espelho_laboratorio.py`) prova, arquivo por arquivo e por
   SHA-256, que os dois são os mesmos bytes. Depender de `../ia` aqui faria este
   teste pular no CI — e um teste que pula no CI fica verde e cego.

2. **Que os números vêm do contrato** (RF-DES-141), e não de literais repetidos
   no backend. Uma terceira cópia dos parâmetros divergiria em silêncio, e o job
   calibraria contra um adversário que ninguém enfrenta.

3. **Que o estado é um valor** (RF-DES-162): aplicar um lance devolve estado
   novo, o de origem fica intacto, e a partida atravessa um `dict` de ida e volta.

4. **Que o árbitro não joga** (RF-DES-035/161) — a separação que torna
   "validar não é jogar" uma propriedade da peça.
"""

import pytest

from motores.damas.contrato_damas import (
    carregar_contrato,
    parametros_do_nivel,
    versao_do_motor,
)
from motores.damas.motor_damas import EstadoDamas, MotorDamas, estado_inicial
from motores.nucleo.carimbo import Carimbo
from motores.nucleo.orcamento import Orcamento
from motores.nucleo.papeis import (
    Arbitro,
    JogadorDeMotor,
    NivelDeMotor,
    TradutorDeEstado,
    Veredito,
)

# O import do motor do laboratório só funciona **depois** que `motor_damas` põe o
# espelho no caminho de busca — por isso ele vem aqui embaixo, e não no topo.
from jogos.jogo_damas.motor.busca_damas import NIVEIS, Buscador  # noqa: E402
from jogos.jogo_damas.motor.regras_damas import REGULAMENTOS  # noqa: E402
from jogos.jogo_damas.motor.tabuleiro_damas import Tabuleiro  # noqa: E402


@pytest.fixture
def motor() -> MotorDamas:
    return MotorDamas("brasileira")


# ── Os dois papéis ──────────────────────────────────────────────────────────


def test_o_motor_veste_os_tres_papeis(motor):
    assert isinstance(motor, Arbitro)
    assert isinstance(motor, JogadorDeMotor)
    assert isinstance(motor, TradutorDeEstado)


def test_modalidade_desconhecida_e_recusada_na_construcao():
    """Falhar aqui é muito mais barato que falhar no meio de uma calibração."""
    with pytest.raises(ValueError, match="modalidade desconhecida"):
        MotorDamas("xadrez")


# ── Os números vêm do contrato (RF-DES-141) ────────────────────────────────


@pytest.mark.parametrize("nivel", list(NivelDeMotor))
def test_os_parametros_lidos_sao_os_do_motor_do_laboratorio(nivel):
    """O contrato é GERADO do código do motor, então os dois têm de bater.

    Se este teste falhar, o contrato do espelho está velho: alguém mexeu no
    `busca_damas.NIVEIS` e não regerou. O conserto é regerar no laboratório e
    reespelhar — ⛔ nunca editar o JSON à mão.
    """
    do_contrato = parametros_do_nivel(nivel)
    do_motor = NIVEIS[nivel.value]

    assert do_contrato.profundidade == do_motor.profundidade
    assert do_contrato.ruido == do_motor.ruido
    assert do_contrato.teto_de_nos == do_motor.teto_de_nos
    assert do_contrato.extensao_de_captura == do_motor.extensao_de_captura
    assert do_contrato.chance_de_errar == do_motor.chance_de_errar
    assert do_contrato.margem_do_erro == do_motor.margem_do_erro


def test_os_quatro_numeros_que_o_dono_declarou():
    """A escada, escrita à mão aqui de propósito.

    ⚠️ É a única repetição deliberada dos números neste repositório, e ela existe
    para ser um **segundo par de olhos**: se um dia o contrato e o motor mudarem
    juntos por engano — um reespelhamento de um ramo errado, por exemplo —, o
    teste acima continuaria verde. Este não.

    Os valores são os da tarefa T014: Cacau 1/90/35%/24k · Pita 2/40/25%/24k ·
    Tex 3/0/8%/48k · Sagaz 64/0/0%/288k.
    """
    esperado = {
        NivelDeMotor.CACAU: (1, 90, 0.35, 24_000),
        NivelDeMotor.PITA: (2, 40, 0.25, 24_000),
        NivelDeMotor.TEX: (3, 0, 0.08, 48_000),
        NivelDeMotor.SAGAZ: (64, 0, 0.00, 288_000),
    }
    for nivel, (profundidade, ruido, erro, nos) in esperado.items():
        p = parametros_do_nivel(nivel)
        assert (p.profundidade, p.ruido, p.chance_de_errar, p.teto_de_nos) == (
            profundidade,
            ruido,
            erro,
            nos,
        ), f"o nível {nivel.value} saiu do que o dono declarou"


def test_nivel_ausente_do_contrato_falha_alto():
    """Cair num padrão faria o job calibrar o Sagaz com o orçamento do Cacau e
    gravar "sagaz" no banco — o pior desfecho possível."""
    contrato = carregar_contrato()
    assert set(contrato["dificuldade"]["niveis"]) == {
        n.value for n in NivelDeMotor
    }, "o contrato e a escada da camada divergiram"


# ── O coração: o mesmo lance que o laboratório ─────────────────────────────


# Três posições: a inicial, um meio-jogo com captura disponível e um final de
# damas. São diferentes de propósito — a inicial tem simetria (onde um empate mal
# desempatado apareceria), a segunda tem captura obrigatória (onde a Lei da
# Maioria manda), e a terceira tem quiescência a exercer.
POSICOES = {
    "inicial": "W:W21,22,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,11,12",
    "meio_jogo": "W:W18,21,23,24,25,26,27,28,30,31,32:B1,2,3,5,6,7,8,9,10,11,14",
    "final_de_damas": "W:WK14,K23:BK5,10",
}


@pytest.mark.parametrize("nivel", list(NivelDeMotor))
@pytest.mark.parametrize("nome_da_posicao", sorted(POSICOES))
def test_mesmo_lance_que_o_laboratorio_na_mesma_posicao_e_semente(
    motor, nivel, nome_da_posicao
):
    """A prova de que o adaptador é só um adaptador.

    Ele monta o `Buscador` com os parâmetros do contrato; este teste monta o
    mesmo `Buscador` à mão, com os mesmos parâmetros e a mesma semente, e exige
    o mesmo lance.

    ⚠️ A semente é fixa porque três dos quatro níveis têm acaso declarado (ruído
    e chance de errar). Sem ela, este teste falharia às vezes — e um teste que
    falha às vezes é desligado.
    """
    fen = POSICOES[nome_da_posicao]
    semente = 20260909
    estado = EstadoDamas(co_modalidade="brasileira", fen_inicial=fen)
    parametros = parametros_do_nivel(nivel)

    # A referência: o motor do laboratório, chamado diretamente.
    tabuleiro, historico = estado._partida
    referencia = Buscador(
        regulamento=REGULAMENTOS["brasileira"], semente=semente
    ).buscar(
        Tabuleiro.de_fen(fen),
        profundidade=parametros.profundidade,
        teto_de_nos=parametros.teto_de_nos,
        tempo_maximo=parametros.tempo_maximo,
        ruido=parametros.ruido,
        historico=historico,
        extensao_de_captura=parametros.extensao_de_captura,
        chance_de_errar=parametros.chance_de_errar,
        margem_do_erro=parametros.margem_do_erro,
    )

    obtido = motor.escolher_lance(estado, nivel, semente=semente)
    assert obtido == str(referencia.lance), (
        f"o adaptador divergiu do motor em {nome_da_posicao}/{nivel.value}: "
        f"ele jogou {obtido}, o laboratório jogou {referencia.lance}."
    )
    assert tabuleiro.para_fen() == fen  # o estado não foi alterado no caminho


def test_a_mesma_semente_devolve_sempre_o_mesmo_lance(motor):
    """Reprodutibilidade: é o que permite recalibrar e comparar com o histórico."""
    estado = estado_inicial()
    primeiro = motor.escolher_lance(estado, NivelDeMotor.CACAU, semente=7)
    segundo = motor.escolher_lance(estado, NivelDeMotor.CACAU, semente=7)
    assert primeiro == segundo


def test_o_sagaz_e_reprodutivel_ATE_SEM_semente(motor):
    """RF-DES-019a — é por isso que o gabarito de referência sai dele.

    Ele é o único com `ruido=0` e `chance_de_errar=0`: não há o que sortear.
    """
    estado = estado_inicial()
    assert motor.escolher_lance(estado, NivelDeMotor.SAGAZ) == motor.escolher_lance(
        estado, NivelDeMotor.SAGAZ
    )


def test_o_orcamento_da_camada_aperta_o_do_contrato(motor):
    """O menor dos dois é o que vale.

    O teto do contrato define o **nível**; o da camada protege o **job**. Deixar
    o maior mandar anularia um dos dois — e seria sempre o mesmo, em silêncio.
    """
    estado = estado_inicial()
    apertado = Orcamento(nos_maximos=500, segundos_maximos=5.0).iniciar()

    lance = motor.escolher_lance(estado, NivelDeMotor.SAGAZ, limite=apertado)

    assert lance in motor.lances_legais(estado)
    # O orçamento voltou com o gasto anotado — é o que distingue, no banco,
    # "jogou mal" de "não teve tempo de pensar".
    assert apertado.nos_gastos > 0


# ── O papel árbitro ─────────────────────────────────────────────────────────


def test_lances_legais_sao_os_do_motor(motor):
    estado = estado_inicial()
    assert motor.lances_legais(estado) == [
        "21-17",
        "22-17",
        "22-18",
        "23-18",
        "23-19",
        "24-19",
        "24-20",
    ]


def test_aplicar_devolve_estado_novo_e_nao_altera_o_recebido(motor):
    """RF-DES-162 — estado por valor, sem sessão em memória."""
    antes = estado_inicial()
    fen_antes = antes.fen

    depois = motor.aplicar(antes, "22-18")

    assert depois is not antes
    assert antes.fen == fen_antes
    assert depois.lances == ("22-18",)
    assert depois.vez_de == -1  # passou a vez para o jogador 2


def test_aplicar_lance_ilegal_recusa_alto_dizendo_qual(motor):
    """Quem chama é o auditor, re-executando o que chegou do app — e um lance
    ilegal é exatamente o que ele foi olhar."""
    with pytest.raises(ValueError, match="ilegal"):
        motor.aplicar(estado_inicial(), "1-2")


def test_veredito_de_partida_em_andamento(motor):
    veredito = motor.veredito(estado_inicial())
    assert veredito.acabou is False
    assert veredito.co_motivo is None
    assert veredito.vencedor is None


def test_quem_nao_tem_lance_perdeu(motor):
    """'Imobilizar ou capturar': quem tem a vez e não tem lance legal, perdeu.

    A posição é extrema de propósito — brancas sem peça nenhuma —, porque o que
    se testa é a regra, não a raridade da posição.
    """
    estado = EstadoDamas(co_modalidade="brasileira", fen_inicial="W:W:B1,2,3")
    veredito = motor.veredito(estado)

    assert veredito.acabou is True
    assert veredito.co_motivo == "sem_lances"
    assert veredito.vencedor == -1  # venceu o jogador 2 (as pretas)


def test_o_motivo_e_identificador_e_nunca_texto_de_tela(motor):
    """RF-DES-019b — quem traduz é o app, pelo `l10n`.

    Um motivo em português dentro do servidor obrigaria a mexer no backend para
    acrescentar um idioma, e deixaria o app sem como traduzir o que já existe.
    """
    estado = EstadoDamas(co_modalidade="brasileira", fen_inicial="W:W:B1,2,3")
    motivo = motor.veredito(estado).co_motivo
    assert motivo == motivo.lower()
    assert " " not in motivo


# Duas damas soltas, uma em cada canto, indo e voltando. Quatro lances devolvem
# a posição ao que era — foi assim que se achou o ciclo, procurando por força
# bruta o primeiro par de casas em que ele existe sem captura pelo meio.
POSICAO_DO_CICLO = "W:WK1:BK2"
CICLO_QUE_REPETE = ("1-5", "2-6", "5-1", "6-2")


def test_o_veredito_consulta_o_HISTORICO_e_nao_so_a_posicao(motor):
    """A mesma posição, duas histórias, dois vereditos.

    É a prova de que `EstadoDamas` precisa carregar a partida inteira. Um árbitro
    que olhasse só o FEN diria "a partida continua" numa posição já empatada pelo
    art. 98 — e um desafio publicado a partir dela prometeria uma vitória
    impossível.
    """
    fresco = EstadoDamas(co_modalidade="brasileira", fen_inicial=POSICAO_DO_CICLO)
    # Duas voltas no ciclo: a posição inicial ocorre pela terceira vez.
    repetido = EstadoDamas(
        co_modalidade="brasileira",
        fen_inicial=POSICAO_DO_CICLO,
        lances=CICLO_QUE_REPETE * 2,
    )

    assert fresco.fen == repetido.fen, "as duas histórias têm de terminar igual"

    assert motor.veredito(fresco).acabou is False
    assert motor.veredito(repetido) == Veredito(
        acabou=True, co_motivo="empate_posicao_repetida", vencedor=0
    )


def test_o_motivo_do_empate_sai_como_identificador_e_nao_como_prosa(motor):
    """RF-DES-019b — o servidor não manda texto de tela.

    ⚠️ O motor do laboratório devolve prosa (`"posicao repetida 3 vezes
    (art. 98)"`), porque o motivo dele vai para o PDN. Traduzir é trabalho do
    adaptador: ⛔ consertar no espelho derrubaria o cadeado 6, que prova que a
    cópia é byte-idêntica.
    """
    repetido = EstadoDamas(
        co_modalidade="brasileira",
        fen_inicial=POSICAO_DO_CICLO,
        lances=CICLO_QUE_REPETE * 2,
    )
    motivo = motor.veredito(repetido).co_motivo

    assert motivo == "empate_posicao_repetida"
    assert " " not in motivo, "voltou prosa em vez de identificador"
    assert "(" not in motivo, "o artigo vazou para dentro do identificador"


def test_motivo_de_empate_desconhecido_falha_alto():
    """Uma regra de empate nova no laboratório tem de ser mapeada de propósito.

    Deixar a prosa passar adiante mandaria português para dentro de `co_motivo`,
    e o app cairia na tela de "motivo desconhecido" sem que ninguém soubesse por
    quê — a falha silenciosa que este projeto já pagou várias vezes.
    """
    from motores.damas.motor_damas import _identificador_do_empate

    assert _identificador_do_empate("posicao repetida 3 vezes (art. 98)") == (
        "empate_posicao_repetida"
    )
    with pytest.raises(ValueError, match="desconhecido"):
        _identificador_do_empate("regra nova que ninguem mapeou")


# ── O tradutor de estado ────────────────────────────────────────────────────


def test_ida_e_volta_pelo_dicionario(motor):
    """O estado atravessa o banco: o job morre, o avaliador roda horas depois."""
    original = motor.aplicar(estado_inicial(), "22-18")
    dado = motor.para_dado(original)
    reconstruido = motor.de_dado(dado)

    assert reconstruido == original
    assert reconstruido.fen == original.fen


def test_as_damas_gravam_a_posicao_em_fen(motor):
    """`co_formato_posicao` distingue os dois jogos no `data-model.md`."""
    dado = motor.para_dado(estado_inicial())
    assert dado["co_formato_posicao"] == "fen"
    assert dado["co_jogo"] == "damas"
    assert dado["co_modalidade"] == "brasileira"


def test_de_dado_recusa_o_formato_do_pontinhos(motor):
    """Uma sequência de lances do Pontinhos chegando aqui produziria uma partida
    de damas plausível e errada, em vez de um erro."""
    with pytest.raises(ValueError, match="fen"):
        motor.de_dado(
            {
                "co_modalidade": "brasileira",
                "co_formato_posicao": "sequencia_lances",
                "co_posicao_inicial": "H_0_1",
            }
        )


# ── O carimbo ───────────────────────────────────────────────────────────────


def test_o_carimbo_identifica_o_motor_que_jogou(motor):
    """RF-DES-164 — sem carimbo, recalibrar apaga a evidência."""
    carimbo = motor.carimbo(NivelDeMotor.SAGAZ, co_versao_perfil="perfil-2026-09")

    assert isinstance(carimbo, Carimbo)
    assert carimbo.co_jogo == "damas"
    assert carimbo.co_modalidade == "brasileira"
    assert carimbo.para_colunas()["co_nivel"] == "sagaz"


def test_a_versao_do_motor_sai_dos_hashes_do_espelho():
    """⚠️ E não de um número escrito à mão, que envelhece calado.

    A forma `damas-py-<8 hex>` cabe nos 40 caracteres da coluna e respeita a
    forma que o carimbo exige — minúsculas, dígitos, ponto, hífen, sublinhado.
    """
    versao = versao_do_motor()
    assert versao.startswith("damas-py-")
    assert len(versao) == len("damas-py-") + 8
    assert versao == versao.lower()
    # Se ela não coubesse na coluna, ou tivesse forma estranha, o carimbo recusa.
    Carimbo(
        co_jogo="damas",
        co_nivel=NivelDeMotor.SAGAZ,
        co_versao_motor=versao,
        co_versao_perfil="perfil-2026-09",
    )


def test_a_versao_do_motor_e_estavel_entre_chamadas():
    """Uma versão que oscilasse não identificaria coisa nenhuma."""
    assert versao_do_motor() == versao_do_motor()

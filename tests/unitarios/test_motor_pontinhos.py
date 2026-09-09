"""T015 — o motor do Pontinhos no backend (RF-DES-018a/018b/018d/161/162).

═══════════════════════════════════════════════════════════════════════════
A CADEIA QUE FAZ "O MESMO ADVERSÁRIO" SER VERDADE
═══════════════════════════════════════════════════════════════════════════

RF-DES-018b promete que o job enfrenta a **mesma** CNN que a pessoa enfrenta.
Isso não se prova num teste só; prova-se numa cadeia, e cada elo já tem dono:

1. o `.tflite` e o mapeamento do espelho são **byte-idênticos** aos do
   aplicativo — o cadeado 6 confere isso por SHA-256, sem pular;
2. a extração dos 12 canais é o **código do laboratório**, também no espelho e
   também conferido por hash;
3. o runtime devolve **os mesmos números** que o do aplicativo — medido na T001,
   com o arquivo de referência versionado;
4. a única peça escrita aqui, `partida_para_dataset`, é comparada com a do
   laboratório neste arquivo.

O que estes testes acrescentam é o elo 4 e as regras do jogo em volta.
"""

import json

import numpy as np
import pytest

from motores.nucleo.carimbo import Carimbo
from motores.nucleo.orcamento import Orcamento
from motores.nucleo.papeis import (
    Arbitro,
    JogadorDeMotor,
    NivelDeMotor,
    TradutorDeEstado,
)
from motores.pontinhos.motor_pontinhos import (
    CAMINHO_DO_MAPEAMENTO,
    EstadoPontinhos,
    MotorPontinhos,
    contrato_de_codificacao,
    estado_inicial,
    partida_para_dataset,
    versao_do_motor,
)

# Só funciona depois que `motor_pontinhos` põe o espelho no caminho de busca.
from jogos.jogo_pontinhos.motor.analisador_estrutural_pontinhos import (  # noqa: E402
    extrair_canais,
)
from jogos.jogo_pontinhos.motor.tabuleiro_pontinhos import (  # noqa: E402
    EstadoTabuleiro,
)


@pytest.fixture
def motor() -> MotorPontinhos:
    return MotorPontinhos()


def partida_de_exemplo() -> EstadoPontinhos:
    """Quatro traços que fecham a caixa de cima à esquerda.

    Escolhida à mão porque exercita o **turno extra**: o quarto traço fecha a
    caixa, e quem o marcou joga de novo.
    """
    return EstadoPontinhos(lances=("H_0_1", "V_1_0", "V_1_2", "H_2_1"))


# ── Os papéis ───────────────────────────────────────────────────────────────


def test_o_motor_veste_os_tres_papeis(motor):
    assert isinstance(motor, Arbitro)
    assert isinstance(motor, JogadorDeMotor)
    assert isinstance(motor, TradutorDeEstado)


# ── O tabuleiro pequeno, e só ele ──────────────────────────────────────────


def test_nasce_no_tabuleiro_pequeno_o_unico_tflite_que_existe(motor):
    """RF-DES-018d — não é limitação desta entrega, é o estado do ativo."""
    assert len(motor.lances_legais(estado_inicial())) == 31


def test_as_dimensoes_batem_com_o_contrato_de_codificacao():
    """4×3 caixas, matriz 9×7, 31 traços — os números vêm do contrato."""
    pequeno = contrato_de_codificacao()["dimensoes_por_tamanho"]["pequeno"]
    assert pequeno["linhas_caixas_conceituais"] == 4
    assert pequeno["colunas_caixas_conceituais"] == 3
    assert pequeno["forma_matriz"] == [9, 7]
    assert pequeno["num_tracos_possiveis_e_neuronios_saida_cnn"] == 31


def test_o_mapeamento_e_os_lances_legais_falam_do_mesmo_tabuleiro(motor):
    """O erro histórico que este teste guarda: a ordem ALFABÉTICA.

    Ela agrupa todos os `H_` antes dos `V_`, e não é a ordem dos neurônios do
    modelo treinado — usá-la inutiliza 28 das 31 predições. Está registrado no
    contrato como erro evitado, e aqui fica travado: os rótulos do mapeamento são
    exatamente os traços do tabuleiro vazio, **na mesma ordem**.
    """
    do_mapeamento = json.loads(CAMINHO_DO_MAPEAMENTO.read_text(encoding="utf-8"))
    ordem_do_mapeamento = [do_mapeamento[str(i)] for i in range(31)]

    assert motor.lances_legais(estado_inicial()) == ordem_do_mapeamento


# ── O elo 4: `partida_para_dataset` ────────────────────────────────────────


def _matrizes_de_teste() -> list[np.ndarray]:
    """Algumas matrizes de partida, montadas jogando de verdade.

    Montar jogando, em vez de sortear números, garante que elas são estados
    **alcançáveis** — uma matriz sorteada poderia ter caixa fechada sem os quatro
    traços em volta, e aí as duas implementações concordariam sobre algo que não
    acontece.
    """
    matrizes = []
    estado = estado_inicial()
    motor = MotorPontinhos()
    for _ in range(6):
        matrizes.append(estado.tabuleiro.matriz.copy())
        legais = motor.lances_legais(estado)
        if not legais:
            break
        estado = motor.aplicar(estado, legais[0])
    return matrizes


def _funcao_do_laboratorio():
    """Extrai `_partida_para_dataset` do simulador do laboratório, sem importá-lo.

    ⚠️ **Por que extrair em vez de importar.** O simulador importa
    `jogos.jogo_pontinhos.motor.minimax_pontinhos`, e `jogos` já está resolvido
    para o **espelho** — que só espelha o que o job usa, e não o minimax. Um
    `import` aqui resolveria metade dos nomes numa árvore e metade na outra, e o
    erro seria confuso.

    Então lemos o arquivo, achamos a função pela árvore sintática (`ast`) e
    compilamos **só ela**. É a mesma peça, byte a byte, sem arrastar a árvore de
    dependências de um script de avaliação para dentro de um teste de unidade.

    Devolve `None` quando o laboratório não está no disco.
    """
    import ast
    from pathlib import Path

    origem = (
        Path(__file__).resolve().parents[3]
        / "ia"
        / "jogos"
        / "jogo_pontinhos"
        / "avaliacao"
        / "simulador_tatico_pontinhos.py"
    )
    if not origem.exists():
        return None

    arvore = ast.parse(origem.read_text(encoding="utf-8"), filename=str(origem))
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef) and no.name == "_partida_para_dataset":
            # `ast.Module` com esta única função, compilado e executado num
            # espaço de nomes que só tem o numpy — que é tudo o que ela usa.
            modulo = ast.Module(body=[no], type_ignores=[])
            espaco: dict = {"np": np}
            exec(compile(modulo, str(origem), "exec"), espaco)  # noqa: S102
            return espaco["_partida_para_dataset"]
    return None


def test_partida_para_dataset_bate_com_a_do_laboratorio():
    """A única peça reescrita aqui, comparada com a do laboratório.

    ⚠️ **Pula com motivo quando o `ia/` não está no disco**, e isso é legítimo:
    é o nível **local** da conferência. O nível de CI destas mesmas regras é
    outro — o cadeado 6 provando que `extrair_canais` e o `.tflite` são cópia
    fiel, e os testes de invariante logo abaixo, que não pulam.

    A função do laboratório mora dentro de um script de avaliação, com `argparse`
    e minimax junto: espelhá-lo inteiro traria para a imagem do Railway um punhado
    de código que o job nunca chama. É por isso que a função é reescrita, e é por
    isso que ela é comparada.
    """
    do_laboratorio = _funcao_do_laboratorio()
    if do_laboratorio is None:
        pytest.skip(
            "o laboratório não está neste disco — esperado em quem clonou apenas "
            "o backend."
        )

    for matriz in _matrizes_de_teste():
        assert np.array_equal(
            partida_para_dataset(matriz), do_laboratorio(matriz)
        ), f"a conversão do backend divergiu do laboratório: {matriz}"


def test_partida_para_dataset_nao_altera_a_matriz_recebida():
    """O aviso em caixa alta do contrato, e ele veio de um defeito real.

    Normalizar por cima da matriz da partida corromperia o estado do jogo: o
    marcador do jogador 2 viraria do jogador 1, e a próxima jogada sairia
    inválida.
    """
    original = partida_de_exemplo().tabuleiro.matriz
    copia = original.copy()

    partida_para_dataset(original)

    assert np.array_equal(original, copia)


@pytest.mark.parametrize("indice", range(6))
def test_o_dominio_da_matriz_convertida_e_o_que_o_contrato_declara(indice):
    """`{0, 1, 8, 9}` — o formato do dataset, como o contexto 1 declara."""
    matrizes = _matrizes_de_teste()
    if indice >= len(matrizes):
        pytest.skip("a partida de exemplo acabou antes deste índice")
    convertida = partida_para_dataset(matrizes[indice])
    assert set(np.unique(convertida)).issubset({0, 1, 8, 9})


def test_o_tensor_final_fica_so_em_zero_e_um():
    """`invariante_final_do_tensor_da_cnn`, palavra por palavra do contrato.

    "Qualquer valor fora desse conjunto indica bug de normalização." Um `-1`
    chegando ao modelo o põe fora da distribuição do treino: em 2026-04-23 isso
    derrubou a CNN de 96% para 57% de vitória contra o minimax — 39 pontos, sem
    erro nenhum aparecer.
    """
    for matriz in _matrizes_de_teste():
        canais = np.asarray(extrair_canais(partida_para_dataset(matriz)))
        assert set(np.unique(canais)).issubset({0, 1}), (
            f"o tensor saiu com {sorted(set(np.unique(canais)))}"
        )


# ── As regras do jogo ───────────────────────────────────────────────────────


def test_aplicar_devolve_estado_novo_e_nao_altera_o_recebido(motor):
    """RF-DES-162 — estado por valor."""
    antes = estado_inicial()
    depois = motor.aplicar(antes, "H_0_1")

    assert depois is not antes
    assert antes.lances == ()
    assert depois.lances == ("H_0_1",)


def test_aplicar_traco_ja_ocupado_recusa_alto(motor):
    estado = motor.aplicar(estado_inicial(), "H_0_1")
    with pytest.raises(ValueError, match="não está disponível"):
        motor.aplicar(estado, "H_0_1")


def test_aplicar_traco_inexistente_recusa_alto(motor):
    with pytest.raises(ValueError, match="não está disponível"):
        motor.aplicar(estado_inicial(), "H_99_99")


def test_quem_nao_fecha_caixa_passa_a_vez(motor):
    estado = estado_inicial()
    assert estado.vez_de == 1
    assert motor.aplicar(estado, "H_0_1").vez_de == -1


def test_quem_FECHA_caixa_joga_de_novo(motor):
    """O turno extra — a regra que faz a vez depender da história, e não da
    posição. É por isso que o estado é a sequência de lances."""
    quatro_tracos = partida_de_exemplo()

    # Foram quatro traços: J1, J2, J1, J2 — e o quarto fecha a caixa.
    assert quatro_tracos.placar == {1: 0, -1: 1}
    assert quatro_tracos.vez_de == -1, "quem fechou a caixa tinha de jogar de novo"


def test_veredito_de_partida_em_andamento(motor):
    veredito = motor.veredito(estado_inicial())
    assert veredito.acabou is False
    assert veredito.co_motivo is None
    assert veredito.vencedor is None


def test_toda_partida_chega_a_estado_terminal(motor):
    """⚠️ Não é uma promessa: é aritmética.

    Cada lance ocupa um traço, os traços são 31, e nenhum lance os devolve. O
    Desafio do Dia depende disso — "toda partida de desafio chega a estado
    terminal, provado na geração" (determinação do dono, 04/09/2026).
    """
    estado = estado_inicial()
    for _ in range(40):
        if motor.veredito(estado).acabou:
            break
        estado = motor.aplicar(estado, motor.lances_legais(estado)[0])
    else:  # pragma: sem cobertura — só se a regra mudar
        pytest.fail("a partida não terminou em 40 lances")

    veredito = motor.veredito(estado)
    assert veredito.acabou is True
    assert veredito.co_motivo == "tabuleiro_cheio"
    assert len(estado.lances) == 31
    # Doze caixas, todas de alguém: 4 × 3.
    assert sum(estado.placar.values()) == 12


def test_o_vencedor_e_quem_fechou_mais_caixas(motor):
    estado = estado_inicial()
    while not motor.veredito(estado).acabou:
        estado = motor.aplicar(estado, motor.lances_legais(estado)[0])

    placar = estado.placar
    esperado = 1 if placar[1] > placar[-1] else (-1 if placar[-1] > placar[1] else 0)
    assert motor.veredito(estado).vencedor == esperado


def test_o_motivo_e_identificador_e_nunca_texto_de_tela(motor):
    """RF-DES-019b — quem traduz é o app, pelo `l10n`."""
    estado = estado_inicial()
    while not motor.veredito(estado).acabou:
        estado = motor.aplicar(estado, motor.lances_legais(estado)[0])
    motivo = motor.veredito(estado).co_motivo
    assert motivo == motivo.lower() and " " not in motivo


# ── A rede ──────────────────────────────────────────────────────────────────


def test_ranquear_devolve_so_os_disponiveis_e_soma_um(motor):
    """As probabilidades são renormalizadas sobre os traços livres.

    É o que o aplicativo faz, e é sobre essa distribuição que a política de cada
    nível vai decidir.
    """
    estado = partida_de_exemplo()
    ranqueados = motor.ranquear(estado)
    disponiveis = set(motor.lances_legais(estado))

    assert {r for r, _ in ranqueados} == disponiveis
    assert sum(p for _, p in ranqueados) == pytest.approx(1.0)


def test_ranquear_sai_ordenado_do_maior_para_o_menor(motor):
    probabilidades = [p for _, p in motor.ranquear(estado_inicial())]
    assert probabilidades == sorted(probabilidades, reverse=True)


def test_o_ranqueamento_e_reprodutivel(motor):
    """A CNN é determinística; o acaso do nível entra depois, na política.

    Sem ordem estável no desempate, dois traços com a mesma nota trocariam de
    lugar entre execuções e a calibração deixaria de ser reprodutível.
    """
    assert motor.ranquear(estado_inicial()) == motor.ranquear(estado_inicial())


def test_ranquear_recusa_partida_terminada(motor):
    estado = estado_inicial()
    while motor.lances_legais(estado):
        estado = motor.aplicar(estado, motor.lances_legais(estado)[0])
    with pytest.raises(ValueError, match="já acabou"):
        motor.ranquear(estado)


def test_escolher_lance_devolve_o_topo_do_ranqueamento(motor):
    estado = estado_inicial()
    assert motor.escolher_lance(estado) == motor.ranquear(estado)[0][0]


def test_escolher_lance_anota_o_no_no_orcamento(motor):
    """A CNN é uma inferência de custo fixo, sem árvore a podar — mas o gasto é
    anotado assim mesmo, para que o resumo gravado distinga "jogou mal" de "não
    teve tempo de pensar"."""
    orcamento = Orcamento(nos_maximos=10, segundos_maximos=1.0).iniciar()
    motor.escolher_lance(estado_inicial(), NivelDeMotor.SAGAZ, limite=orcamento)
    assert orcamento.nos_gastos == 1


def test_a_matriz_da_partida_esta_no_dominio_do_contexto_3():
    """`{-1, 0, 1, 8}` — a matriz da partida distingue de quem é cada traço.

    É essa distinção que o contrato manda apagar antes de ir ao modelo, e é ela
    que o servidor precisa para contar as caixas de cada lado.
    """
    matriz = partida_de_exemplo().tabuleiro.matriz
    assert set(np.unique(matriz)).issubset({-1, 0, 1, 8})


# ── O tradutor de estado ────────────────────────────────────────────────────


def test_ida_e_volta_pelo_dicionario(motor):
    original = partida_de_exemplo()
    reconstruido = motor.de_dado(motor.para_dado(original))
    assert reconstruido == original


def test_o_pontinhos_grava_a_posicao_como_SEQUENCIA_DE_LANCES(motor):
    """`co_formato_posicao` distingue os dois jogos no `data-model.md`."""
    dado = motor.para_dado(partida_de_exemplo())
    assert dado["co_formato_posicao"] == "sequencia_lances"
    assert dado["co_jogo"] == "pontinhos"
    assert dado["co_modalidade"] is None
    assert dado["co_tamanho_tabuleiro"] == "pequeno"


def test_de_dado_recusa_o_formato_das_damas(motor):
    with pytest.raises(ValueError, match="sequencia_lances"):
        motor.de_dado({"co_formato_posicao": "fen", "co_posicao_inicial": "W:W1:B2"})


def test_o_dado_leva_o_placar_e_a_vez_reconstruidos(motor):
    """São eles que o portão T050 exige ver conferidos no ambiente `des`."""
    dado = motor.para_dado(partida_de_exemplo())
    assert dado["vez_de"] == -1
    assert dado["placar"] == {"1": 0, "-1": 1}


# ── O carimbo ───────────────────────────────────────────────────────────────


def test_o_carimbo_do_pontinhos_nao_tem_modalidade(motor):
    """Nulo é diferente de string vazia: "não se aplica" não é "não informado"."""
    carimbo = motor.carimbo(NivelDeMotor.SAGAZ, co_versao_perfil="perfil-2026-09")
    assert isinstance(carimbo, Carimbo)
    assert carimbo.para_colunas()["co_modalidade"] is None


def test_a_versao_do_motor_identifica_a_rede_e_a_codificacao():
    """O que define este jogador é a `.tflite` mais o código que monta o tensor.

    Os dois estão no manifesto do espelho, e é de lá que a versão sai — não de um
    número escrito à mão, que envelhece calado.
    """
    versao = versao_do_motor()
    assert versao.startswith("pontinhos-py-")
    assert versao == versao.lower()
    Carimbo(  # cabe na coluna e respeita a forma exigida
        co_jogo="pontinhos",
        co_nivel=NivelDeMotor.SAGAZ,
        co_versao_motor=versao,
        co_versao_perfil="perfil-2026-09",
    )


def test_a_versao_do_motor_e_estavel_entre_chamadas():
    assert versao_do_motor() == versao_do_motor()


# ── O modelo é o certo ──────────────────────────────────────────────────────


def test_o_modelo_do_espelho_e_o_de_19_8_MB_do_aplicativo():
    """Um modelo trocado por engano rodaria e devolveria números plausíveis.

    O tamanho é a conferência mais barata; o SHA-256 contra o do aplicativo é
    trabalho do cadeado 6, que já o faz.
    """
    from motores.pontinhos.motor_pontinhos import CAMINHO_DO_MODELO

    assert CAMINHO_DO_MODELO.stat().st_size == 19_801_152


def test_o_tabuleiro_do_laboratorio_e_quem_sabe_as_regras():
    """⛔ Nenhuma regra de Pontinhos é escrita no backend.

    Se este teste falhar porque a classe sumiu, alguém reescreveu as regras aqui
    — e o servidor passou a calibrar um jogo que ninguém joga.
    """
    tabuleiro = EstadoTabuleiro(4, 3)
    assert tabuleiro.matriz.shape == (9, 7)
    assert len(tabuleiro.tracos_disponiveis()) == 31

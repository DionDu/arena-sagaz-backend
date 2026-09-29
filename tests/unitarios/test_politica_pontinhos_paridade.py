"""🔒 T017 — CADEADO NUMÉRICO da política do Pontinhos (RF-DES-018c/142).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE CADEADO GUARDA
═══════════════════════════════════════════════════════════════════════════

⚠️ **A CNN sozinha não é o nível.** Sem a política, o job mediria quatro vezes o
mesmo adversário, a régua sairia plana, e o Desafio do Dia teria uma escada de
dificuldade que não existe — sem que nada desse erro.

Então o que precisa ficar travado não é só *um número*, são três coisas:

1. **Os valores** que a política aplica são, campo a campo, os do contrato.
   A mensagem de falha **nomeia o campo e o nível**: um cadeado que só diz "a
   política divergiu" obriga a comparar dezesseis números à mão, e é assim que se
   aprende a ignorá-lo.
2. **A ponte entre os dois vocabulários** — `cacau/pita/tex/sagaz` do hub e
   `facil/normal/dificil/sagaz` do aplicativo — é pela **posição na escada**, e
   não por coincidência de nomes.
3. **O comportamento portado**: as três fases, na ordem certa, e o
   arredondamento que decide o que é "o topo".

⚠️ **Este cadeado não pula.** Tudo o que ele precisa — o contrato e o código —
está neste repositório.
"""

import ast
import re
from pathlib import Path

import pytest

from motores.nucleo.papeis import NivelDeMotor
from motores.pontinhos.motor_pontinhos import (
    EstadoPontinhos,
    MotorPontinhos,
    estado_inicial,
)
from motores.pontinhos.jogador_dart_pontinhos import FONTES_DO_MOTOR_DART
from motores.pontinhos.politica import (
    CASAS_DO_DESEMPATE,
    AcaoCpu,
    _CHAVE_DO_CONTRATO_POR_NIVEL,
    JogadorPontinhos,
    capturas_disponiveis,
    carregar_contrato,
    escolher_lance,
    parametros_do_nivel,
)


@pytest.fixture
def motor() -> MotorPontinhos:
    return MotorPontinhos()


def _do_contrato(chave: str) -> dict:
    for nivel in carregar_contrato()["niveis"]:
        if nivel["chave"] == chave:
            return nivel
    raise AssertionError(f"o contrato não declara o nível {chave!r}")


# ── 1. Os valores, campo a campo, nomeando quem divergiu ───────────────────


@pytest.mark.parametrize("nivel", list(NivelDeMotor), ids=lambda n: n.value)
def test_os_valores_aplicados_sao_os_do_contrato(nivel):
    """Campo a campo. A falha diz **qual** campo e **qual** nível."""
    chave = _CHAVE_DO_CONTRATO_POR_NIVEL[nivel]
    aplicado = parametros_do_nivel(nivel)
    declarado = _do_contrato(chave)

    comparacoes = (
        ("epsilon", aplicado.epsilon, declarado["epsilon"]),
        (
            "usa_captura_gulosa",
            aplicado.usa_captura_gulosa,
            declarado["usa_captura_gulosa"],
        ),
        ("timer_segundos", aplicado.timer_segundos, declarado["timer_segundos"]),
    )
    for campo, na_politica, no_contrato in comparacoes:
        assert na_politica == no_contrato, (
            f"DIVERGIU: `{campo}` do nível `{chave}` ({nivel.value}).\n"
            f"  na política do backend: {na_politica}\n"
            f"  no contrato           : {no_contrato}\n"
            "O contrato é a declaração do enum `Dificuldade` do aplicativo, que "
            "é a fonte da verdade (research.md R-20). Traga o número de lá."
        )


def test_a_escada_e_a_mesma_dos_dois_lados():
    """Quatro degraus, nem três nem cinco, e nenhum sem par.

    O teste acima percorre a **camada**: um quinto nível inventado no contrato
    passaria por ele sem ser notado, e o job passaria a calibrar um degrau que o
    aplicativo não sabe mostrar.
    """
    do_contrato = [n["chave"] for n in carregar_contrato()["niveis"]]
    da_camada = [_CHAVE_DO_CONTRATO_POR_NIVEL[n] for n in NivelDeMotor]
    assert do_contrato == da_camada, (
        f"a escada do contrato {do_contrato} não é a da camada {da_camada}."
    )


def test_a_ponte_entre_os_vocabularios_e_por_POSICAO_e_nao_por_nome():
    """⚠️ `cacau` e `facil` são o mesmo degrau, e não a mesma palavra.

    Se a ponte fosse por coincidência de nome, ela quebraria calada no dia em que
    um personagem for renomeado — e o job passaria a medir o Magno com o desleixo
    da Cacau. O que a liga é o `indice_forca`, que os dois lados declaram.
    """
    for nivel in NivelDeMotor:
        chave = _CHAVE_DO_CONTRATO_POR_NIVEL[nivel]
        assert _do_contrato(chave)["indice_forca"] == nivel.indice_forca, (
            f"o degrau `{chave}` está na posição "
            f"{_do_contrato(chave)['indice_forca']} do contrato e na "
            f"{nivel.indice_forca} da camada."
        )


def test_nenhum_campo_de_nivel_do_contrato_fica_sem_uso():
    """Um campo declarado que ninguém lê é uma promessa que ninguém cumpre.

    ⚠️ `estrelas` é da tela e não viaja para o servidor; os outros quatro têm de
    aparecer em `ParametrosDeNivel` ou na ponte da escada.
    """
    consumidos = {"chave", "epsilon", "usa_captura_gulosa", "timer_segundos",
                  "indice_forca"}
    so_da_tela = {"estrelas", "personagem"}
    declarados = set(_do_contrato("sagaz"))

    sobrando = declarados - consumidos - so_da_tela
    assert not sobrando, (
        f"o contrato ganhou {sorted(sobrando)}, e a política não lê. "
        "Ou passa a ler, ou o campo é da tela e entra na lista de exceções — "
        "com o motivo escrito."
    )


# ── 2. O arredondamento que decide o que é "o topo" ────────────────────────


def test_o_desempate_arredonda_a_tres_casas():
    """É ele que define o que conta como erro, e vale para todos os níveis.

    Calibrado por análise da CNN no aplicativo: três casas reproduzem ~92% dos
    empates de uma tolerância relativa de 0,5%. Sem o arredondamento, um lance
    que a rede considera praticamente idêntico ao melhor (0,4001 contra 0,4004)
    contaria como "pior", e a CPU "erraria" escolhendo um lance tão bom quanto o
    argmax — o que não é erro nenhum.

    ⚠️ **Quem APLICA o número é o motor Dart desde a T093**, e por isso este caso
    o confere no fonte espelhado, e não numa função daqui. Um número declarado de
    um lado e aplicado do outro, sem ninguém comparar, é a definição de
    comentário que envelhece calado.
    """
    assert CASAS_DO_DESEMPATE == 3

    fonte = (FONTES_DO_MOTOR_DART / "politica_dificuldade_pontinhos.dart").read_text(
        encoding="utf-8"
    )
    achado = re.search(r"const int casasDoDesempate = (\d+);", fonte)
    assert achado, (
        "não achei `casasDoDesempate` em politica_dificuldade_pontinhos.dart. "
        "Ele foi renomeado? Este cadeado precisa acompanhar."
    )
    assert int(achado.group(1)) == CASAS_DO_DESEMPATE, (
        f"o motor arredonda a {achado.group(1)} casas e este backend declara "
        f"{CASAS_DO_DESEMPATE}. Os dois falam do MESMO número - o que separa o "
        f"topo do resto, e portanto o que conta como erro de propósito."
    )


# ⚠️ **A separação do topo em si é conferida do lado Dart**, em
# `test/jogos/pontinhos/oraculo_test.dart`, com rankings sintéticos: é lá que dá
# para construir "todos empatados no topo" e "um lance só", que a CNN real nunca
# entrega de encomenda. Os casos que moravam aqui testavam uma função Python que
# ⛔ decide mais nada.


# ── 3. As três fases, portadas na ordem certa ──────────────────────────────


def test_o_magno_NUNCA_fecha_caixa_pela_fase_gulosa(motor):
    """É o que o libera para o sacrifício da dupla-cruz.

    Abrir mão das duas últimas caixas de uma cadeia para manter o turno é a
    jogada mestre que os outros três nunca fazem — e ela é impossível para quem
    fecha caixa por instinto.
    """
    # Uma posição com caixa de graça disponível: três lados da caixa marcados.
    estado = EstadoPontinhos(lances=("H_0_1", "V_1_0", "V_1_2"))
    assert capturas_disponiveis(motor, estado) == ["H_2_1"]

    # ⚠️ Uma semente NOVA a cada volta, e não um sorteador de vida longa: quem
    # sorteia agora é o motor Dart, e a semente é o que atravessa a fronteira.
    for i in range(20):
        decisao = escolher_lance(motor, estado, NivelDeMotor.SAGAZ, semente=1 + i)
        assert decisao.co_acao != AcaoCpu.CAPTURA_GULOSA


@pytest.mark.parametrize(
    "nivel", [NivelDeMotor.CACAU, NivelDeMotor.PITA, NivelDeMotor.TEX],
    ids=lambda n: n.value,
)
def test_os_outros_tres_SEMPRE_fecham_caixa_de_graca(motor, nivel):
    """Instinto, não habilidade: todo iniciante fecha caixa aberta.

    ⚠️ E é **antes** do epsilon, de propósito. Sabotar isso com o sorteio faria a
    CPU ignorar caixa de graça na cara dela, o que parece DEFEITO e não
    dificuldade — e ainda quebraria o turno extra que encadeia a cadeia inteira.
    """
    estado = EstadoPontinhos(lances=("H_0_1", "V_1_0", "V_1_2"))
    for i in range(20):
        decisao = escolher_lance(motor, estado, nivel, semente=7 + i)
        assert decisao.co_acao == AcaoCpu.CAPTURA_GULOSA
        assert decisao.lance == "H_2_1"


def test_so_o_magno_sorteia_a_abertura(motor):
    """FASE 0 — e só quando é ELE quem abre.

    Com epsilon 0 e a rede determinística, ele abriria toda partida com o mesmo
    traço. No desafio, isso seria um dia igual ao outro.
    """
    vazio = estado_inicial()

    assert (
        escolher_lance(motor, vazio, NivelDeMotor.SAGAZ, semente=3).co_acao
        == AcaoCpu.CNN_ABERTURA_ALEATORIA
    )
    # Os outros três não passam por lá: o epsilon deles já dá variedade.
    for nivel in (NivelDeMotor.CACAU, NivelDeMotor.PITA, NivelDeMotor.TEX):
        acao = escolher_lance(motor, vazio, nivel, semente=3).co_acao
        assert acao != AcaoCpu.CNN_ABERTURA_ALEATORIA


def test_o_magno_nao_sorteia_quando_NAO_foi_ele_quem_abriu(motor):
    """Se o oponente abriu, o Magno segue rede e argmax, como sempre."""
    depois_da_abertura = EstadoPontinhos(lances=("H_0_1",))
    acao = escolher_lance(
        motor, depois_da_abertura, NivelDeMotor.SAGAZ, semente=3
    ).co_acao
    assert acao in (AcaoCpu.CNN_ARGMAX_ABSOLUTO, AcaoCpu.CNN_ARGMAX_DESEMPATADO)


def test_o_magno_nunca_erra_de_proposito(motor):
    """Epsilon 0. É a reputação do Magno, e ela é ativo do produto."""
    estado = EstadoPontinhos(lances=("H_0_1", "H_0_3"))
    for i in range(30):
        decisao = escolher_lance(motor, estado, NivelDeMotor.SAGAZ, semente=11 + i)
        assert decisao.co_acao != AcaoCpu.CNN_EPSILON_ALEATORIO


def test_a_cacau_erra_perto_dos_oitenta_por_cento_das_jogadas_taticas(motor):
    """A escada é feita de frequência de erro, não de força de busca.

    ⚠️ A tolerância é larga (±0,12) de propósito: o que se trava aqui é que o
    `epsilon` **está sendo aplicado**, não a estatística do sorteio. Um teste
    apertado falharia às vezes, e um teste que falha às vezes é desligado.
    """
    # Uma posição sem captura de graça, para que a fase A não roube a decisão.
    estado = EstadoPontinhos(lances=("H_0_1", "H_0_3"))
    erros = sum(
        escolher_lance(motor, estado, NivelDeMotor.CACAU, semente=2026 + i).co_acao
        == AcaoCpu.CNN_EPSILON_ALEATORIO
        for i in range(400)
    )
    proporcao = erros / 400
    esperado = parametros_do_nivel(NivelDeMotor.CACAU).epsilon
    assert abs(proporcao - esperado) < 0.12, (
        f"a Cacau errou {proporcao:.0%} das jogadas táticas, e o contrato "
        f"declara {esperado:.0%}. O epsilon está sendo aplicado?"
    )


def test_a_escada_de_erro_cai_do_cacau_ao_magno(motor):
    """Monotonicidade — a inversão que os dados de campo acharam no "difícil".

    Ninguém percebeu por meses, porque a sensação de quem joga aponta para o lado
    oposto: "está tudo difícil".
    """
    estado = EstadoPontinhos(lances=("H_0_1", "H_0_3"))
    proporcoes = []
    for nivel in NivelDeMotor:
        erros = sum(
            escolher_lance(motor, estado, nivel, semente=99 + i).co_acao
            == AcaoCpu.CNN_EPSILON_ALEATORIO
            for i in range(200)
        )
        proporcoes.append(erros / 200)

    assert proporcoes == sorted(proporcoes, reverse=True), proporcoes
    assert proporcoes[-1] == 0.0, "o Magno errou de propósito"


# ── 4. O vocabulário de `co_acao` ──────────────────────────────────────────


def test_os_codigos_de_acao_sao_os_do_aplicativo():
    """Eles vão para a coluna `co_acao` do log, que já tem dados em produção.

    ⛔ **Não reciclar nome aposentado.** `cnn_nucleo_top_p` existe na dimensão do
    banco por causa das partidas gravadas com a política anterior à ε-greedy;
    reaproveitar a string faria as duas épocas virarem uma só no relatório.
    """
    declarados = {
        valor
        for nome, valor in vars(AcaoCpu).items()
        if not nome.startswith("_") and isinstance(valor, str)
    }
    assert declarados == {
        "captura_gulosa",
        "cnn_epsilon_aleatorio",
        "cnn_argmax_absoluto",
        "cnn_argmax_desempatado",
        "cnn_abertura_aleatoria",
    }
    assert "cnn_nucleo_top_p" not in declarados


def test_toda_decisao_sai_com_um_codigo_de_acao_conhecido(motor):
    """Sem isso, calibrar dificuldade seria adivinhação: uma derrota da CPU por
    erro de propósito e uma por a rede não bastar ficariam iguais no banco."""
    conhecidos = {
        valor
        for nome, valor in vars(AcaoCpu).items()
        if not nome.startswith("_") and isinstance(valor, str)
    }
    estado = estado_inicial()
    semente = 5
    while motor.lances_legais(estado):
        decisao = escolher_lance(motor, estado, NivelDeMotor.PITA, semente=semente)
        assert decisao.co_acao in conhecidos
        estado = motor.aplicar(estado, decisao.lance)
        semente += 1  # semente por lance, como o job deriva


# ── 5. Reprodutibilidade ───────────────────────────────────────────────────


def test_a_mesma_semente_devolve_a_mesma_partida(motor):
    """Uma régua que não se reproduz não mede nada."""
    def partida(semente: int) -> list[str]:
        jogador = JogadorPontinhos(motor)
        estado = estado_inicial()
        lances = []
        while motor.lances_legais(estado):
            lance = jogador.escolher_lance(
                estado, NivelDeMotor.CACAU, semente=semente
            )
            lances.append(lance)
            estado = motor.aplicar(estado, lance)
            semente += 1  # semente por lance, como o job vai derivar
        return lances

    assert partida(42) == partida(42)


# ── 6. O cadeado confere a si mesmo ────────────────────────────────────────


def test_este_cadeado_nao_tem_saida_de_emergencia():
    """Um pulo aqui deixaria a escada de dificuldade sem guarda nenhuma.

    A conferência é por `ast`, e não por busca de texto: procurar a string do
    decorador encontraria a própria linha que procura.
    """
    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)
    marcas_de_pulo = {"skip", "skipif", "xfail"}

    def nome_final(no: ast.AST) -> str | None:
        if isinstance(no, ast.Call):
            return nome_final(no.func)
        if isinstance(no, ast.Attribute):
            return no.attr
        if isinstance(no, ast.Name):
            return no.id
        return None

    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorador in no.decorator_list:
                assert nome_final(decorador) not in marcas_de_pulo, (
                    f"{no.name} ganhou um decorador de pulo."
                )
        if isinstance(no, ast.Call):
            alvo = no.func
            if isinstance(alvo, ast.Attribute) and alvo.attr == "skip":
                raise AssertionError(
                    f"linha {no.lineno}: chamada a .skip(). Este cadeado falha "
                    "ou passa, nunca pula."
                )

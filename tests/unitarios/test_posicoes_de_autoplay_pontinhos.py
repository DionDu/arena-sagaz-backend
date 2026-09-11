"""T049h - o acervo de posicoes de autoplay do Pontinhos.

⚠️ **O que estes testes guardam e uma classe de defeito que NAO faz barulho.** O
acervo e um vetor de inteiros de 32 bits, e *toda* mascara de 32 bits e um
tabuleiro valido: ler o bit 3 como se fosse o traco errado, ou embaralhar de um
jeito que fecha caixa, produziria uma posicao perfeitamente bem-formada e
simplesmente **outra**. Nada erraria, nada logaria, e o desafio publicado seria
diferente do que a regua mediu.

Por isso os cadeados aqui sao sobre **identidade** (a ordem canonica bate com a
do motor?) e sobre **invariantes** (a posicao reproduz com placar 0-0?), e nao
sobre "o codigo roda".
"""

from __future__ import annotations

import random

import pytest

from job import posicao_inicial as posicao_mod
from job import posicoes_de_autoplay_pontinhos as autoplay
from job.editorial import EDITORIAL
from job.gerador import _preparar_pontinhos
from motores.pontinhos.motor_pontinhos import EstadoPontinhos


@pytest.fixture(scope="module")
def acervo() -> autoplay.Acervo:
    """O acervo carregado uma vez para o arquivo inteiro.

    `scope="module"` porque sao 897 mil posicoes: recarregar por teste trocaria
    segundos de suite por nenhuma garantia — o objeto e imutavel e ninguem o
    altera.
    """
    return autoplay.carregar()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os cadeados de identidade
# ═══════════════════════════════════════════════════════════════════════════


def test_a_ordem_canonica_do_acervo_BATE_com_a_do_motor(acervo) -> None:
    """🔒 O bit `i` da mascara e o traco `i` do tabuleiro do motor.

    ⛔ **Este e o cadeado mais importante do arquivo.** A mascara foi montada no
    laboratorio, a partir da ordem de `labels_canonicos` dos NPZ; ela e decodificada
    aqui, contra os rotulos que viajaram dentro do proprio arquivo. Se um dia o
    motor do backend reordenar os tracos, a decodificacao continuaria funcionando
    e passaria a devolver **outro tabuleiro** — sem erro nenhum, porque toda
    combinacao de tracos e um tabuleiro legal.

    A unica forma de enxergar isso e comparar as duas listas, na ordem.
    """
    do_motor = list(EstadoPontinhos().tabuleiro.tracos_disponiveis())
    assert list(acervo.co_rotulo) == do_motor


def test_o_acervo_cobre_as_fases_QUE_O_EDITORIAL_PEDE() -> None:
    """🔒 Todo tipo de Pontinhos publicavel tem posicao para a sua fase.

    ⚠️ O caminho natural para quebrar isto e editorial: alguem sobe o
    `nu_lances_de_preparo` de um tipo para uma fase que nenhuma partida real
    alcanca sem fechar caixa. O job falharia **na madrugada**, e este teste faz a
    mesma pergunta em dois segundos.
    """
    for co_tipo, publicacao in EDITORIAL.items():
        if not co_tipo.startswith("pontinhos"):
            continue
        quantas = len(autoplay.carregar().com_tracos(publicacao.nu_lances_de_preparo))
        assert quantas > 0, (
            f"o tipo {co_tipo!r} prepara com {publicacao.nu_lances_de_preparo} "
            "tracos, e o acervo de autoplay nao tem nenhuma posicao dessa fase"
        )


def test_as_fatias_por_fase_sao_CONTIGUAS_e_completas(acervo) -> None:
    """A soma das fases e o acervo inteiro, e cada fatia so tem o seu tamanho.

    E o que prova que `nu_inicio` descreve mesmo o vetor: se a ordenacao por
    quantidade de tracos se perdesse, alguma posicao ficaria fora de toda fatia —
    e o job sortearia de um bloco menor sem nunca saber.
    """
    total = 0
    for n in range(autoplay.TRACOS_DO_TABULEIRO + 1):
        fatia = acervo.com_tracos(n)
        total += len(fatia)
        for mascara in fatia[:50]:  # uma amostra basta: sao 897 mil
            assert bin(int(mascara)).count("1") == n
    assert total == len(acervo.nu_mascara)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Os invariantes da posicao sorteada
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("nu_tracos", [1, 5, 8, 14, 20])
def test_a_posicao_sorteada_TEM_a_quantidade_pedida(nu_tracos) -> None:
    """Sem traco repetido e com a contagem exata do que se pediu."""
    lances = autoplay.sortear(random.Random(2026), nu_tracos)
    assert len(lances) == nu_tracos
    assert len(set(lances)) == nu_tracos


@pytest.mark.parametrize("nu_tracos", [5, 8, 14, 20])
def test_a_posicao_reproduz_com_placar_ZERO_A_ZERO(nu_tracos) -> None:
    """✅ Nenhum prefixo da sequencia fecha caixa — e por isso a ordem e livre.

    ⚠️ **E este o invariante que sustenta a ponte NPZ -> desafio.** Os NPZ guardam
    a matriz, que nao diz **de quem** e cada caixa fechada; so nas posicoes sem
    caixa nenhuma o placar e reconstruivel (0-0) e a vez sai da paridade. Se uma
    posicao do acervo fechasse caixa, o desafio nasceria com placar que a frase
    nao explica — e a vez viria do turno extra, nao da paridade.
    """
    lances = autoplay.sortear(random.Random(7), nu_tracos)
    estado = EstadoPontinhos(lances=lances)
    assert estado.placar == {1: 0, -1: 0}
    # Sem caixa fechada os jogadores se alternam estritamente: com N par, a vez
    # volta para quem abriu.
    assert estado.vez_de == (1 if nu_tracos % 2 == 0 else -1)


@pytest.mark.parametrize("nu_tracos", [8, 14])
def test_QUALQUER_ordem_dos_mesmos_tracos_da_o_mesmo_estado(nu_tracos) -> None:
    """A propriedade que permite embaralhar: o estado nao depende da ordem.

    ⚠️ Ela vale porque "sem caixa fechada" e **monotono** — se o conjunto final
    nao fecha caixa nenhuma, nenhum prefixo dele fecha. Com uma caixa fechada no
    meio, o turno extra faria a vez depender da ordem, e duas permutacoes dariam
    desafios diferentes com a mesma aparencia.
    """
    lances = list(autoplay.sortear(random.Random(11), nu_tracos))
    embaralhado = list(lances)
    random.Random(99).shuffle(embaralhado)

    um = EstadoPontinhos(lances=tuple(lances))
    outro = EstadoPontinhos(lances=tuple(embaralhado))

    assert um.vez_de == outro.vez_de
    assert um.placar == outro.placar
    assert set(um.tabuleiro.tracos_disponiveis()) == set(
        outro.tabuleiro.tracos_disponiveis()
    )


def test_a_sequencia_e_ACEITA_por_posicao_inicial() -> None:
    """O JSON publicado se monta sem `PosicaoInvalida`.

    ⛔ Quem valida a sequencia e `do_pontinhos()`, reproduzindo-a pelo motor — e
    nao o acervo. Este teste liga os dois: uma posicao sorteada aqui tem de
    atravessar a validacao de la sem remendo.
    """
    lances = autoplay.sortear(random.Random(3), 14)
    js = posicao_mod.do_pontinhos(list(lances))
    assert js["vez_de"] == 1  # 14 tracos, nenhuma caixa: volta para quem abriu
    assert js["placar"] == {"j1": 0, "j2": 0}
    assert len(js["lances"]) == 14


# ═══════════════════════════════════════════════════════════════════════════
# 3. Determinismo e variedade — as duas metades da mesma exigencia
# ═══════════════════════════════════════════════════════════════════════════


def test_a_MESMA_semente_da_a_MESMA_posicao() -> None:
    """🔒 A idempotencia de T038 nao pode ter sido paga pela troca da fonte.

    ⚠️ Duas execucoes do job para o mesmo dia precisam gerar a mesma fila. O
    acervo nao cria gerador proprio: a unica fonte de acaso e o `random.Random`
    que chega semeado pelo dia.
    """
    assert autoplay.sortear(random.Random(4242), 14) == autoplay.sortear(
        random.Random(4242), 14
    )


def test_sementes_DIFERENTES_dao_posicoes_diferentes() -> None:
    """A outra metade: variedade de verdade, e nao uma posicao fixa.

    ⚠️ Com 36 mil posicoes de 14 tracos, vinte sementes darem vinte resultados
    distintos e o esperado; duas iguais aqui denunciariam um sorteio que ignora a
    semente — que passaria calado no teste de determinismo acima.
    """
    vistas = {autoplay.sortear(random.Random(s), 14) for s in range(20)}
    assert len(vistas) == 20


def test_a_ordem_NAO_e_a_canonica() -> None:
    """A sequencia sai embaralhada, e isso decide a cor de cada traco na tela.

    Sem caixa fechada os jogadores se alternam estritamente, entao a ordem diz de
    quem e cada traco. A ordem canonica e uma varredura geometrica do tabuleiro, e
    daria sempre o mesmo padrao de cores — o desafio pareceria montado a regua.
    """
    canonicos = list(autoplay.carregar().co_rotulo)
    # Vinte sorteios: a chance de os vinte sairem em ordem canonica por acaso e
    # desprezivel, e um so nao provaria nada.
    saiu_fora_de_ordem = False
    for semente in range(20):
        lances = autoplay.sortear(random.Random(semente), 14)
        posicoes = [canonicos.index(lance) for lance in lances]
        if posicoes != sorted(posicoes):
            saiu_fora_de_ordem = True
            break
    assert saiu_fora_de_ordem


# ═══════════════════════════════════════════════════════════════════════════
# 4. O que acontece quando se pede o impossivel
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("nu_tracos", [0, 21, 31, 40])
def test_fase_SEM_ACERVO_falha_alto_e_diz_o_limite(nu_tracos) -> None:
    """⛔ Nao ha volta ao sorteio as cegas — nem como plano B.

    ⚠️ Cair de volta no acaso resolveria o sintoma e reintroduziria, calado,
    exatamente o defeito que T049h veio corrigir. A mensagem precisa dizer **qual
    e o limite** e **onde se ajusta**, senao quem a ler vai procurar defeito no
    gerador.
    """
    with pytest.raises(autoplay.SemPosicaoDeAutoplay) as erro:
        autoplay.sortear(random.Random(1), nu_tracos)
    texto = str(erro.value)
    assert "20" in texto  # o teto real do 4x3
    assert "nu_lances_de_preparo" in texto


# ═══════════════════════════════════════════════════════════════════════════
# 5. A ponte com o gerador
# ═══════════════════════════════════════════════════════════════════════════


def test_o_gerador_PREPARA_pelo_acervo_e_nao_por_sorteio() -> None:
    """🔒 `_preparar_pontinhos` devolve exatamente a posicao do acervo.

    ⚠️ **O cadeado e sobre a fonte, nao sobre o formato.** Um sorteio as cegas
    tambem devolveria 14 tracos sem caixa fechada — a diferenca esta em a posicao
    existir no acervo de autoplay, e e so isso que este teste pergunta.
    """
    acervo = autoplay.carregar()
    estado = _preparar_pontinhos(random.Random(555), 14)

    indice = {rotulo: i for i, rotulo in enumerate(acervo.co_rotulo)}
    mascara = 0
    for lance in estado.lances:
        mascara |= 1 << indice[lance]

    assert mascara in set(int(m) for m in acervo.com_tracos(14).tolist())

"""O motor do servidor é o motor do aparelho — a trava e o vetor de paridade.

⚠️ **Este arquivo guarda duas coisas diferentes, e as duas nasceram do mesmo
defeito** (25/09/2026, `docs/investigacao_paridade_motores.md`):

  1. **A trava de identidade** — o executável que joga precisa ter saído dos
     fontes que este backend tem espelhados. Pedido do dono: *"Importante também
     termos algum mecanismo que garanta que o motor Dart compilado que vai jogar
     no servidor seja o mesmo embarcado no App."*
  2. **O vetor de paridade** — posições reais, com o lance que o **aparelho**
     jogou, conferido contra o que o servidor escolhe.

⛔ **A trava sozinha não bastaria.** Ela prova que o binário saiu do código certo;
não prova que o código certo, chamado do jeito que o servidor chama, escolhe o
mesmo lance. Foi exatamente aí que o defeito morava: o port estava fiel, e o
servidor o chamava com um relógio que o aparelho nunca via.
"""

from __future__ import annotations

import pytest

from motores.damas.contrato_damas import parametros_do_nivel
from motores.damas.jogador_dart import (
    MotorDartIndisponivel,
    JogadorDart,
    caminho_do_executavel,
    pasta_da_base_de_finais,
    resumo_dos_fontes,
)
from motores.nucleo.papeis import NivelDeMotor

# ═══════════════════════════════════════════════════════════════════════════
# O VETOR DE PARIDADE — a partida do dono, inteira
# ═══════════════════════════════════════════════════════════════════════════
#
# A partida `a267bba1-88f1-4f49-9121-bda8def57955`, jogada pelo dono no `des` em
# 25/09/2026 contra o desafio `d6a7317e` (`damas_coroar`, anglo, Magno, semente
# publicada 282565477). Ela veio do banco (`jogo_damas.vw002_jogada`) com o FEN
# antes de cada lance, a semente daquele lance e a telemetria do motor — por isso
# serve de vetor sem custo nenhum.
#
# ⚠️ **O aparelho jogou com o motor RUST**, e é o alvo certo: `conferir_equivalencia
# _com_rust.dart` trava Rust e Dart no mesmo lance, então bater com o Rust é bater
# com os dois.
#
# ⛔ **Os treze lances da CPU entram, inclusive os finais.** Até 25/09 só os três
# primeiros estavam aqui, porque o servidor jogava **sem** a base de finais e um
# cadeado que falha por um defeito conhecido ensina a ser ignorado. A base entrou
# no mesmo dia (`pasta_da_base_de_finais`), e com ela o vetor passou a cobrir a
# partida inteira — 13 de 13.
#
# ⚠️ **Olhe `consultas_base` antes de olhar o lance.** No 16º lance o aparelho
# registrou **795 consultas e 636 acertos**; o servidor precisa registrar os
# mesmos números. Dois motores só chegam ao mesmo par se estiverem lendo a mesma
# base, com as mesmas fatias — é o que separa *"usa uma base"* de *"usa A base"*,
# e a base crua do laboratório (41 fatias contra 23) daria outro par.

FEN_INICIAL = "W:W18,22,23,28,29,30,31,32:B4,6,8,10,12,13,15,16,21"

#: A partida inteira, na ordem. O índice `n-1` é o lance de ordem `n`.
PARTIDA_DO_DONO = (
    "18x11", "8x15", "23-18", "15-19", "18-15", "4-8", "32-27", "16-20",
    "15-11", "8x15", "22-18", "15x22", "27-23", "19x26", "30x23", "21-25",
    "31-26", "22x31", "29x22", "13-17", "22x13", "31-26", "28-24", "26x19x28",
    "13-9", "6x13",
)

#: `(ordem do lance, semente gravada, nós, profundidade, consultas à base)`.
#:
#: ⚠️ `None` na telemetria é o **atalho de lance único** do aplicativo: sem
#: escolha a fazer, ele joga sem buscar e sem gravar números
#: (`TelemetriaDaBuscaDamas.lanceUnico`). O servidor busca nessas posições e
#: chega ao mesmo lance — porque é o único legal. ⛔ Reproduzir o atalho aqui
#: seria copiar para o motor uma decisão que é de **tela**, e ela não muda lance
#: nenhum.
#:
#: As sementes são as do banco, e cada uma confere com a derivação do app —
#: `(282565477 + ordem * 2654435761) & 0x7FFFFFFF`.
LANCES_DA_CPU = (
    (2, 1296469703, None, None, None),
    (4, 162890281, 288001, 12, 0),
    (6, 1176794507, 288001, 12, 0),
    (8, 43215085, 288001, 12, 0),
    (10, 1057119311, None, None, None),
    (12, 2071023537, None, None, None),
    (14, 937444115, None, None, None),
    (16, 1951348341, 288001, 14, 795),
    (18, 817768919, None, None, None),
    (20, 1831673145, 23404, 10, 73),
    (22, 698093723, 3989, 8, 34),
    (24, 1711997949, 12, 2, 0),
    (26, 578418527, None, None, None),
)


@pytest.fixture(scope="module")
def jogador():
    """Um processo do motor Dart para o arquivo inteiro.

    ⚠️ `scope="module"`: subir um processo por caso pagaria a partida do
    executável três vezes sem necessidade.

    Pula (em vez de falhar) quando não há executável compilado — quem clona o
    backend sozinho não tem o laboratório ao lado, e um vermelho que só diz
    "faltou compilar" treina a ignorar o vermelho. ⚠️ A conferência de que o
    binário **existe** é do portão de operação, não deste arquivo.
    """
    try:
        caminho_do_executavel()
    except MotorDartIndisponivel as erro:
        pytest.skip(str(erro))
    with JogadorDart() as processo:
        yield processo


# ═══════════════════════════════════════════════════════════════════════════
# A TRAVA
# ═══════════════════════════════════════════════════════════════════════════


def test_o_resumo_dos_fontes_e_deterministico() -> None:
    """Duas leituras da mesma pasta dão o mesmo resumo.

    Parece óbvio, e não é: a fórmula ordena os arquivos por nome justamente
    porque a ordem do sistema de arquivos **não** é estável entre máquinas. Sem
    o `sorted`, este caso passaria aqui e o resumo divergiria na máquina de
    outra pessoa — com a trava acusando um motor errado que está certo.
    """
    assert resumo_dos_fontes() == resumo_dos_fontes()


def test_o_resumo_cobre_os_dezesseis_arquivos_do_motor() -> None:
    """A pasta espelhada tem os mesmos dezesseis arquivos que o app embarca.

    ⚠️ É o elo do meio da corrente: `paridade_motor_test.dart` prova que o app é
    byte-idêntico ao laboratório, e `espelhar_laboratorio.py` traz o laboratório
    para cá. Se o espelho vier com quatorze, a trava continuaria "passando" sobre
    um conjunto incompleto.
    """
    from motores.damas.jogador_dart import FONTES_DO_MOTOR_DART

    nomes = sorted(a.name for a in FONTES_DO_MOTOR_DART.glob("*.dart"))
    assert len(nomes) == 16, (
        f"o espelho tem {len(nomes)} arquivo(s) do motor Dart, e o app embarca "
        f"16. Se um arquivo novo nasceu no laboratório, acrescente-o a "
        f"ARQUIVOS_ESPELHADOS em scripts/espelhar_laboratorio.py — e à lista de "
        f"paridade_motor_test.dart no app, na MESMA resposta. Achei: {nomes}"
    )
    assert "busca_damas.dart" in nomes
    assert "regras_damas.dart" in nomes
    assert "consulta_base_finais_damas.dart" in nomes


def test_o_executavel_saiu_dos_fontes_deste_backend(jogador: JogadorDart) -> None:
    """A trava: o carimbo do binário bate com o resumo dos fontes espelhados.

    ⛔ **É o caso que impede o servidor de gerar uma fila inteira de desafios com
    um motor velho**, depois de alguém corrigir uma regra e esquecer de
    recompilar. A conferência roda na abertura do processo, então chegar até aqui
    já significa que ela passou — este caso trava a afirmação por escrito.
    """
    assert jogador.resumo_do_motor == resumo_dos_fontes()


# ═══════════════════════════════════════════════════════════════════════════
# A PARIDADE DE COMPORTAMENTO
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "ordem, semente, nos, profundidade, consultas", LANCES_DA_CPU
)
def test_o_servidor_joga_o_mesmo_lance_que_o_aparelho(
    jogador: JogadorDart,
    ordem: int,
    semente: int,
    nos: int | None,
    profundidade: int | None,
    consultas: int | None,
) -> None:
    """O lance do servidor é o que o aparelho jogou, na mesma posição.

    ⚠️ **O lance 8 é o que abriu a investigação.** Ali o servidor respondia
    `19-23` e o aparelho `16-20`, e o desafio do dia ficava, nas palavras do
    dono, *"praticamente impossível"*.

    ⚠️ **E o lance 16 é o que prova a base de finais.** O aparelho registrou 795
    consultas e 636 acertos; sem a base — ou com a base errada — o servidor
    chegaria a outros números muito antes de chegar a outro lance.
    """
    resposta = jogador.escolher_lance(
        co_modalidade="anglo",
        fen_inicial=FEN_INICIAL,
        lances=PARTIDA_DO_DONO[: ordem - 1],
        parametros=parametros_do_nivel(NivelDeMotor.SAGAZ),
        semente=semente,
        pasta_da_base=pasta_da_base_de_finais("anglo"),
    )
    esperado = PARTIDA_DO_DONO[ordem - 1]

    assert resposta["lance"] == esperado, (
        f"no lance {ordem} o servidor jogou {resposta['lance']} onde o aparelho "
        f"jogou {esperado}.\n"
        f"Olhe NÓS, PROFUNDIDADE e CONSULTAS À BASE antes de olhar o lance:\n"
        f"  servidor: nos={resposta['nos']} prof={resposta['profundidade']} "
        f"consultas={resposta.get('consultas_base')}\n"
        f"  aparelho: nos={nos} prof={profundidade} consultas={consultas}\n"
        f"Se pararam em pontos diferentes, o orçamento divergiu; se consultaram "
        f"a base um número diferente de vezes, não é a mesma base."
    )

    # ⚠️ **A telemetria é conferida só onde o aparelho a gravou.** Onde ela veio
    # nula, o aplicativo usou o atalho de lance único e não buscou — ver
    # `LANCES_DA_CPU`.
    if nos is None:
        return
    assert (resposta["nos"], resposta["profundidade"]) == (nos, profundidade), (
        f"no lance {ordem} o servidor parou em {resposta['nos']} nós e "
        f"profundidade {resposta['profundidade']}; o aparelho parou em {nos} e "
        f"{profundidade}. Dois motores que param em pontos diferentes só "
        f"escolhem o mesmo lance por sorte."
    )
    assert resposta.get("consultas_base") == consultas, (
        f"no lance {ordem} o servidor perguntou {resposta.get('consultas_base')} "
        f"vezes à base de finais e o aparelho perguntou {consultas}. Não é a "
        f"mesma base: a do laboratório tem 41 fatias por modalidade, e a que o "
        f"aparelho embarca tem 23 (o resto sai por simetria de cor)."
    )


def test_a_busca_gasta_o_orcamento_INTEIRO_do_sagaz(jogador: JogadorDart) -> None:
    """O servidor varre os 288 mil nós, e não para antes.

    ⛔ **É este o caso que teria pegado o defeito original.** O port Python estava
    fiel; o que o traía era a rede de segurança de 10 s, que mordia todo lance no
    servidor e nenhum no aparelho — parando com 124.928 nós e um ply mais raso.
    Um caso que só olhasse o lance escolhido continuaria verde em muitas posições,
    porque na maioria delas o segundo melhor lance não empata com o melhor.

    ⚠️ O número do aparelho, gravado no banco, é `288001`: a busca para **ao
    ultrapassar** o teto, e não ao atingi-lo.
    """
    parametros = parametros_do_nivel(NivelDeMotor.SAGAZ)
    resposta = jogador.escolher_lance(
        co_modalidade="anglo",
        fen_inicial=FEN_INICIAL,
        lances=PARTIDA_DO_DONO[:7],
        parametros=parametros,
        semente=43215085,
    )
    assert resposta["nos"] > parametros.teto_de_nos, (
        f"a busca parou em {resposta['nos']} nós, antes do teto de "
        f"{parametros.teto_de_nos}. Algum limite mordeu antes do orçamento — "
        f"provavelmente um relógio."
    )
    assert resposta["profundidade"] == 12, (
        f"o aparelho chegou à profundidade 12 nesta posição e o servidor chegou "
        f"à {resposta['profundidade']}."
    )

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
    resumo_dos_fontes,
)
from motores.nucleo.papeis import NivelDeMotor

# ═══════════════════════════════════════════════════════════════════════════
# O VETOR DE PARIDADE
# ═══════════════════════════════════════════════════════════════════════════
#
# A partida `a267bba1-88f1-4f49-9121-bda8def57955`, jogada pelo dono no `des` em
# 25/09/2026 contra o desafio `d6a7317e` (`damas_coroar`, anglo, Magno, semente
# publicada 282565477). Ela veio do banco com FEN antes de cada lance, a semente
# de cada lance e o motor de busca identificado — por isso serve de vetor sem
# custo nenhum.
#
# ⚠️ **Só entram os lances em que o aparelho NÃO consultou a base de finais.**
# `qt_consultas_base` é zero nos lances 4, 6 e 8, e passa a 795 no lance 16. O
# servidor ainda joga **sem** base (`motores/damas/motor_damas.py` nunca a passa),
# então um vetor que incluísse os finais estaria cobrando uma paridade que
# sabidamente ainda não existe — e um cadeado que falha por um defeito conhecido
# ensina a ser ignorado.
#
# ⛔ **Quando a base entrar no servidor, os finais entram aqui.** É a segunda
# divergência registrada na investigação, e este comentário é o lembrete dela.

FEN_INICIAL = "W:W18,22,23,28,29,30,31,32:B4,6,8,10,12,13,15,16,21"

#: `(lances jogados até ali, semente daquele lance, o que o APARELHO jogou)`.
#:
#: As sementes são as gravadas no banco, e cada uma confere com a derivação do
#: app — `(282565477 + ordem * 2654435761) & 0x7FFFFFFF`.
VETOR_DA_PARTIDA_DO_DONO = (
    (("18x11", "8x15", "23-18"), 162890281, "15-19"),
    (("18x11", "8x15", "23-18", "15-19", "18-15"), 1176794507, "4-8"),
    (
        ("18x11", "8x15", "23-18", "15-19", "18-15", "4-8", "32-27"),
        43215085,
        "16-20",
    ),
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


def test_o_resumo_cobre_os_quinze_arquivos_do_motor() -> None:
    """A pasta espelhada tem os mesmos quinze arquivos que o app embarca.

    ⚠️ É o elo do meio da corrente: `paridade_motor_test.dart` prova que o app é
    byte-idêntico ao laboratório, e `espelhar_laboratorio.py` traz o laboratório
    para cá. Se o espelho vier com quatorze, a trava continuaria "passando" sobre
    um conjunto incompleto.
    """
    from motores.damas.jogador_dart import FONTES_DO_MOTOR_DART

    nomes = sorted(a.name for a in FONTES_DO_MOTOR_DART.glob("*.dart"))
    assert len(nomes) == 15, (
        f"o espelho tem {len(nomes)} arquivo(s) do motor Dart, e o app embarca "
        f"15. Se um arquivo novo nasceu no laboratório, acrescente-o a "
        f"ARQUIVOS_ESPELHADOS em scripts/espelhar_laboratorio.py — e à lista de "
        f"paridade_motor_test.dart no app, na MESMA resposta. Achei: {nomes}"
    )
    assert "busca_damas.dart" in nomes
    assert "regras_damas.dart" in nomes


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
    "lances, semente, esperado", VETOR_DA_PARTIDA_DO_DONO
)
def test_o_servidor_joga_o_mesmo_lance_que_o_aparelho(
    jogador: JogadorDart, lances: tuple[str, ...], semente: int, esperado: str
) -> None:
    """O lance do servidor é o que o aparelho jogou, na mesma posição.

    ⚠️ **O terceiro caso é o que abriu a investigação.** Ali o servidor respondia
    `19-23` e o aparelho `16-20`, e o desafio do dia ficava, nas palavras do
    dono, *"praticamente impossível"*.
    """
    resposta = jogador.escolher_lance(
        co_modalidade="anglo",
        fen_inicial=FEN_INICIAL,
        lances=lances,
        parametros=parametros_do_nivel(NivelDeMotor.SAGAZ),
        semente=semente,
    )
    assert resposta["lance"] == esperado, (
        f"o servidor jogou {resposta['lance']} onde o aparelho jogou {esperado}. "
        f"Olhe NÓS e PROFUNDIDADE antes de olhar o lance: "
        f"nos={resposta['nos']} prof={resposta['profundidade']}. "
        f"Se pararam em pontos diferentes, o orçamento divergiu — foi assim que "
        f"o defeito de 25/09/2026 se revelou."
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
        lances=("18x11", "8x15", "23-18", "15-19", "18-15", "4-8", "32-27"),
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

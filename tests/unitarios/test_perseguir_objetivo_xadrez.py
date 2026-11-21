"""O perseguidor do objetivo do xadrez (spec 012, T076; `DECISOES-do-dono.md` §8zzzz57).

Cada caso monta uma posicao A MAO, pequena, em que a resposta certa e conhecida
sem rodar busca nenhuma, e confere um passo do perseguidor:

  1. o passo (a): o lance que cumpre agora e jogado (a troca na ordem 2);
  2. o passo (b): sai o lance que encerra a partida sem o objetivo (o
     afogamento), o que deixa um xeque-mate ao adversario, a espia comivel, a
     peca do `nao_perder` comivel, o xeque ao alcance no `sem_levar_xeque`;
  3. o passo (c): a nota de cada tipo (comer com a espia, atravessar, o xeque
     descoberto, atacar o alvo, comer com a classe, oferecer a troca);
  4. o desempate (o lance do nivel entre os empatados) e a mistura do nivel.

⚠️ Quem diz o que acontece e o motor (o executavel): sem ele compilado, o
arquivo inteiro pula, com a receita. Nenhuma posicao aqui e "conferida" por
regra escrita no teste: o teste so sabe o que a posicao foi montada para ter.
"""

from __future__ import annotations

import random

import pytest

from job.tipos_de_desafio import RECEITAS_FORA_DO_AR
from motores.nucleo.papeis import NivelDeMotor
from motores.xadrez import perseguir_objetivo_xadrez as ps
from motores.xadrez.fen_xadrez import fen_com_a_vez_trocada
from motores.xadrez.jogador_xadrez import JogadorXadrez, MotorDartIndisponivel, MotorXadrezRecusou


@pytest.fixture(scope="module")
def motor():
    """O executavel, ou o pulo com a receita."""
    try:
        with JogadorXadrez() as jogador:
            yield jogador
    except MotorDartIndisponivel as erro:
        pytest.skip(f"sem o executavel do xadrez compilado: {erro}")


def _desafio(co_tipo: str, fen: str, parametros: dict, **extra) -> ps.DesafioXadrez:
    """Um desafio com a posicao [fen] (vez das brancas = a pessoa) e a chegada
    montada pela RECEITA do tipo, com os [parametros]."""
    posicao = {
        "jogo": "xadrez",
        "modalidade": "tradicional",
        "fen": fen,
        "cor_da_pessoa": "branca",
        **extra,
        "origem": "base_equilibrada",
    }
    chegada = RECEITAS_FORA_DO_AR[co_tipo].montar(parametros)
    return ps.desafio_de(co_tipo, posicao, chegada)


def _restantes(motor, desafio) -> set[str]:
    """Os lances que sobram do passo (b), na posicao publicada."""
    _, examinados = ps.examinar_todos(motor, desafio, [])
    return {e.lance for e in ps.filtrar(motor, desafio, [], examinados)}


def _notas(motor, desafio) -> dict[str, float]:
    """A nota de cada lance legal, na posicao publicada."""
    _, examinados = ps.examinar_todos(motor, desafio, [])
    return {e.lance: ps.nota_do_objetivo(motor, desafio, [], e) for e in examinados}


def _persegue(motor, desafio, *, do_nivel: str = "g1h1", nivel=NivelDeMotor.SAGAZ) -> str:
    """O lance do perseguidor, com um "lance do nivel" fixo (o teste o escolhe)."""
    return ps.lance_de_quem_persegue(
        motor, desafio, [], nivel=nivel, sorteio=random.Random(7), lance_do_nivel=lambda: do_nivel
    )


# ═══════════════════════════════════════════════════════════════════════════
# O desafio e as pecas pequenas
# ═══════════════════════════════════════════════════════════════════════════


def test_o_mate_nao_tem_perseguidor():
    """O `xadrez_dar_mate` fica com o motor que vence (§8zzzz57)."""
    chegada = RECEITAS_FORA_DO_AR["xadrez_dar_mate"].montar({"lances": 5})
    with pytest.raises(ValueError, match="nao persegue"):
        ps.desafio_de("xadrez_dar_mate", {"fen": "x"}, chegada)


def test_os_tipos_do_perseguidor_sao_os_que_nao_pedem_vitoria_mais_o_controle():
    tipos_do_xadrez = {t for t, r in RECEITAS_FORA_DO_AR.items() if r.co_jogo == "xadrez"}
    assert ps.TIPOS_DO_PERSEGUIDOR == (tipos_do_xadrez - {"xadrez_dar_mate"}) | {ps.TIPO_DE_CONTROLE}


def test_as_probabilidades_crescem_e_o_magno_persegue_sempre():
    ordem = [NivelDeMotor.CACAU, NivelDeMotor.PITA, NivelDeMotor.TEX, NivelDeMotor.SAGAZ]
    valores = [ps.PROBABILIDADE_DE_PERSEGUIR[n] for n in ordem]
    assert valores == sorted(valores) and valores[-1] == 1.0


def test_a_peca_protegida_sai_da_clausula_da_chegada():
    desafio = _desafio("xadrez_nao_perder", "7k/8/8/8/8/8/8/6K1 w - - 0 1", {"lances": 8, "peca": "torre"})
    assert desafio.peca_protegida == "torre"


def test_a_vez_trocada_muda_so_a_vez_e_a_passagem():
    fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2"
    assert fen_com_a_vez_trocada(fen) == "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2"


def test_o_motor_recusa_a_vez_trocada_com_o_outro_lado_em_xeque(motor):
    """A torre preta da xeque no rei branco: trocar a vez deixaria o lado que
    NAO joga em xeque, e o motor recusa (e e por isso que a nota cai a 0)."""
    with pytest.raises(MotorXadrezRecusou) as erro:
        motor.estado(
            modalidade="tradicional",
            fen_inicial=fen_com_a_vez_trocada("4k3/8/8/8/8/8/8/r3K3 w - - 0 1"),
            lances=[],
        )
    assert erro.value.codigo == "fen_invalido"


def test_a_promocao_dos_candidatos_e_a_dama(motor):
    estado = motor.estado(modalidade="tradicional", fen_inicial="7k/P7/8/8/8/8/8/K7 w - - 0 1", lances=[])
    lances = ps.lances_do_estado(estado, (ps.PROMOCAO_DOS_CANDIDATOS,))
    assert "a7a8q" in lances and "a7a8" not in lances
    assert {"a7a8q", "a7a8r", "a7a8b", "a7a8n"} <= set(ps.lances_do_estado(estado, ps.TODAS_AS_PROMOCOES))


# ═══════════════════════════════════════════════════════════════════════════
# O passo (a): o que cumpre agora
# ═══════════════════════════════════════════════════════════════════════════


def test_a_troca_na_ordem_2_cumpre_e_e_jogada(motor):
    """O bispo come o cavalo: a troca conta no lance da captura (RF-XDR-201)."""
    desafio = _desafio(
        "xadrez_troca", "7k/8/8/8/4n3/8/8/1B4K1 w - - 0 1", {"lances": 8},
        troca={"minha": "bispo", "dele": "cavalo"},
    )
    assert _persegue(motor, desafio) == "b1e4"


def test_o_controle_da_o_mate_que_esta_na_mesa(motor):
    """No controle (so vencer) o mate cumpre, e vem antes de qualquer filtro."""
    chegada = RECEITAS_FORA_DO_AR["xadrez_dar_mate"].montar({"lances": 5})
    posicao = {
        "jogo": "xadrez", "modalidade": "tradicional",
        "fen": "k7/8/1K6/2Q5/8/8/8/8 w - - 0 1", "cor_da_pessoa": "branca", "origem": "base_equilibrada",
    }
    desafio = ps.desafio_de(ps.TIPO_DE_CONTROLE, posicao, chegada)
    lance = _persegue(motor, desafio)
    resposta = motor.aplicar(modalidade="tradicional", fen_inicial=posicao["fen"], lances=[], lance=lance)
    assert resposta["fatos"]["fim"] == {"motivo": "xeque_mate", "vencedor": "branca"}


# ═══════════════════════════════════════════════════════════════════════════
# O passo (b): os filtros
# ═══════════════════════════════════════════════════════════════════════════


def test_sai_o_afogamento_e_o_mate_que_nao_e_o_objetivo(motor):
    """Dama em c7 afoga o rei de a8; dama em c8 da mate. Num desafio de xeques,
    os dois encerram a partida sem o objetivo, e saem."""
    desafio = _desafio("xadrez_xeques_seguidos", "k7/8/1K6/2Q5/8/8/8/8 w - - 0 1", {"xeques": 3, "lances": 8})
    restantes = _restantes(motor, desafio)
    assert "c5c7" not in restantes  # o afogamento
    assert "c5c8" not in restantes  # o mate, que aqui nao e o objetivo
    assert "c5c6" in restantes


def test_sai_o_lance_que_deixa_o_mate_ao_adversario(motor):
    """A torre de e2 tapa a coluna da dama de e5: tira-la para a2 deixa a dama
    dar mate em e1 (os peoes g2 e h2 fecham a saida, e a torre nao volta)."""
    fen = "1k6/8/8/4q3/8/8/4R1PP/7K w - - 0 1"
    # A posicao faz o que diz: depois de Ta2, a dama em e1 e mate (o motor confere).
    resposta = motor.aplicar(modalidade="tradicional", fen_inicial=fen, lances=["e2a2"], lance="e5e1")
    assert resposta["fatos"]["fim"] == {"motivo": "xeque_mate", "vencedor": "preta"}
    desafio = _desafio("xadrez_xeques_seguidos", fen, {"xeques": 3, "lances": 8})
    restantes = _restantes(motor, desafio)
    assert "e2a2" not in restantes
    assert "e2e3" in restantes


def test_sem_levar_xeque_tira_o_lance_que_deixa_um_xeque(motor):
    """Tirar o cavalo de b1 para c3 ou d2 deixa um xeque (Ta1+), mas nao mate (o
    cavalo volta para tapar): o tipo de xeques o mantem, e o `sem_levar_xeque`
    o tira. Em a3 ele tapa a coluna, e nao ha xeque."""
    fen = "r6k/8/8/8/8/8/6P1/1N5K w - - 0 1"
    xeques = _restantes(motor, _desafio("xadrez_xeques_seguidos", fen, {"xeques": 3, "lances": 8}))
    assert "b1c3" in xeques
    sem_xeque = _restantes(motor, _desafio("xadrez_sem_levar_xeque", fen, {"lances": 10}))
    assert not {"b1c3", "b1d2"} & sem_xeque
    assert {"b1a3", "g2g3"} <= sem_xeque


def test_os_cinco_da_espia_tiram_o_lance_que_a_deixa_comivel(motor):
    """O cavalo espiao come o peao de d5, defendido por e6: comido de volta, o
    desafio acaba. Em e4 o peao de d5 tambem o come."""
    fen = "7k/8/4p3/3p4/8/2N5/8/6K1 w - - 0 1"
    for tipo, parametros in (
        ("xadrez_espia_comer", {"capturas": 2, "lances": 8}),
        ("xadrez_espia_proteger", {"lances": 10}),
        ("xadrez_espia_xeque", {"xeques": 2, "lances": 8}),
    ):
        restantes = _restantes(motor, _desafio(tipo, fen, parametros, marcas={"espia": "c3"}))
        assert "c3d5" not in restantes and "c3e4" not in restantes, tipo
        assert "c3b5" in restantes, tipo


def test_as_duas_espias_ficam_a_salvo_as_duas(motor):
    """21/11/2026 (§8zzzz64): com duas espias, nenhuma pode ficar comivel. O
    bispo espiao (a 2a marca) iria a e4, onde o peao de d5 o come: sai, como o
    cavalo em d5 e em e4. O controle: com UMA espia (so o cavalo), o bispo em e4
    nao e protegido, e o lance fica."""
    fen = "7k/8/4p3/3p4/8/2N5/8/1B4K1 w - - 0 1"
    duas = _desafio(
        "xadrez_duas_espias", fen, {"capturas": 3, "lances": 12},
        marcas={"espia": "c3", "espia2": "b1"},
    )
    restantes = _restantes(motor, duas)
    assert not {"b1e4", "c3d5", "c3e4"} & restantes
    assert {"b1d3", "c3b5"} <= restantes
    uma = _desafio("xadrez_espia_comer", fen, {"capturas": 2, "lances": 8}, marcas={"espia": "c3"})
    assert "b1e4" in _restantes(motor, uma)


def test_duas_espias_da_nota_a_captura_de_qualquer_uma(motor):
    """O cavalo (c3) e o bispo (f3), as duas espias, alcancam o peao de d5:
    comer com qualquer uma vale o peso do agora ("vale o total"). O controle:
    com so o cavalo espiao, o bispo comendo nao e captura da espia."""
    fen = "7k/8/8/3p4/8/2N2B2/8/6K1 w - - 0 1"
    duas = _desafio(
        "xadrez_duas_espias", fen, {"capturas": 3, "lances": 12},
        marcas={"espia": "c3", "espia2": "f3"},
    )
    notas = _notas(motor, duas)
    assert notas["c3d5"] >= ps.PESO_DO_AGORA and notas["f3d5"] >= ps.PESO_DO_AGORA
    assert notas["g1h1"] < ps.PESO_DO_AGORA
    uma = _desafio("xadrez_espia_comer", fen, {"capturas": 2, "lances": 8}, marcas={"espia": "c3"})
    assert _notas(motor, uma)["f3d5"] < ps.PESO_DO_AGORA


def test_comer_com_nao_entrega_a_peca_que_come(motor):
    """O bispo comeria o peao de h6, mas o peao de g7 o comeria de volta, e sem
    o bispo o desafio acaba: o lance sai, e ficam os que o deixam a salvo."""
    desafio = _desafio(
        "xadrez_comer_com", "k7/6p1/7p/8/8/8/P7/2B3K1 w - - 0 1",
        {"capturas": 2, "lances": 20, "come": "bispo", "comida": "peao"},
        classes={"come": "bispo", "comida": "peao"},
    )
    restantes = _restantes(motor, desafio)
    assert "c1h6" not in restantes
    assert {"a2a3", "g1h1"} <= restantes


def test_espia_alvo_nunca_come_o_alvo_com_outra_peca(motor):
    """O peao de e3 poderia comer o alvo (o peao de d4), e o lance ainda tiraria
    a ameaca sobre a espia: mas o desafio ficaria impossivel. Sai."""
    desafio = _desafio(
        "xadrez_espia_alvo", "7k/p7/8/8/3p4/2N1P3/P7/6K1 w - - 0 1", {"lances": 12},
        marcas={"espia": "c3", "alvo": "d4"},
    )
    restantes = _restantes(motor, desafio)
    assert "e3d4" not in restantes
    assert "c3e4" in restantes


def test_nao_perder_protege_a_peca_do_desafio(motor):
    """O cavalo de f6 ataca o peao de e4: so o avanco a e5 o salva."""
    desafio = _desafio("xadrez_nao_perder", "k7/8/5n2/8/4P3/8/8/6K1 w - - 0 1", {"lances": 8, "peca": "peao"})
    assert _restantes(motor, desafio) == {"e4e5"}


def test_nao_perder_sem_saida_fica_com_o_que_deixa_menos(motor):
    """Dois peoes atacados pelo cavalo de d5 (c3 e e3), e so um pode fugir:
    sobram os lances que deixam UM comivel, e nenhum que deixe os dois."""
    desafio = _desafio("xadrez_nao_perder", "k7/8/8/3n4/8/2P1P3/8/6K1 w - - 0 1", {"lances": 8, "peca": "peao"})
    restantes = _restantes(motor, desafio)
    assert restantes == {"c3c4", "e3e4"}


def test_nao_perder_de_outra_peca_nao_liga_para_o_peao(motor):
    """Protegendo a TORRE, o peao atacado nao filtra nada (decisao 2 da T076)."""
    desafio = _desafio("xadrez_nao_perder", "k7/8/5n2/8/4P3/8/8/2R3K1 w - - 0 1", {"lances": 8, "peca": "torre"})
    assert "g1h1" in _restantes(motor, desafio)


# ═══════════════════════════════════════════════════════════════════════════
# O passo (c): a nota de cada tipo
# ═══════════════════════════════════════════════════════════════════════════


def test_espia_comer_da_nota_a_captura_e_ao_que_ela_alcancaria(motor):
    """Comer o peao de d5 vale o peso do agora; ir a b5 vale 1 (de la o cavalo
    alcancaria o peao de a7); ir a e2 nao alcanca nada."""
    desafio = _desafio(
        "xadrez_espia_comer", "7k/p7/8/3p4/8/2N5/P7/6K1 w - - 0 1", {"capturas": 2, "lances": 8},
        marcas={"espia": "c3"},
    )
    notas = _notas(motor, desafio)
    assert notas["c3d5"] == ps.PESO_DO_AGORA
    assert notas["c3b5"] == 1.0 and notas["c3e2"] == 0.0
    assert _persegue(motor, desafio) == "c3d5"


def test_espia_comer_sem_captura_leva_a_espia_para_perto(motor):
    """Sem nada a comer agora, o cavalo vai para onde alcanca o peao de d6 (e4
    ou b5), e nao fica parado: e o lance adiante da T077."""
    desafio = _desafio(
        "xadrez_espia_comer", "7k/p7/3p4/8/8/2N5/P7/6K1 w - - 0 1", {"capturas": 2, "lances": 8},
        marcas={"espia": "c3"},
    )
    notas = _notas(motor, desafio)
    assert notas["c3e4"] >= 1.0 and notas["c3b5"] >= 1.0
    assert notas["c3b1"] == 0.0 and notas["g1h1"] == 0.0
    assert _persegue(motor, desafio, do_nivel="g1h1") in {"c3e4", "c3b5"}


def test_espia_atravessar_vai_para_mais_perto_da_ultima_fileira(motor):
    """A torre espia de a1 so sobe ate a6 (o peao preto a tapa)."""
    desafio = _desafio("xadrez_espia_atravessar", "7k/8/p7/8/8/8/8/R5K1 w - - 0 1", {"lances": 8}, marcas={"espia": "a1"})
    assert _persegue(motor, desafio) == "a1a6"


def test_espia_xeque_conta_o_xeque_descoberto_e_desempata_pelo_nivel(motor):
    """A torre espia de e1 esta tapada pelo bispo de e4: TODO lance do bispo
    descobre o xeque dela no rei de e8. Entre os empatados, o do nivel."""
    desafio = _desafio(
        "xadrez_espia_xeque", "4k3/8/8/8/4B3/8/8/4R1K1 w - - 0 1", {"xeques": 2, "lances": 8},
        marcas={"espia": "e1"},
    )
    notas = _notas(motor, desafio)
    # O xeque agora vale o peso; e depois dele "jogar de novo" nao existe (o
    # rei preto esta em xeque), entao nao soma o lance adiante.
    assert notas["e4d5"] == notas["e4h7"] == ps.PESO_DO_AGORA
    # A torre em d1 nao da xeque, mas daria um (em d8) se jogasse de novo.
    assert notas["e1d1"] == 1.0
    # O rei em h1: a torre continua tapada pelo bispo.
    assert notas["g1h1"] == 0.0
    # O lance do nivel esta entre os empatados: e ele, seja qual for (cada um
    # dos lances do bispo, um por vez; um sorteio acertaria no maximo um).
    do_bispo = sorted(l for l, n in notas.items() if n == ps.PESO_DO_AGORA)
    assert len(do_bispo) > 1
    for do_nivel in do_bispo:
        assert _persegue(motor, desafio, do_nivel=do_nivel) == do_nivel
    # O do nivel NAO esta: sai um lance do bispo (o desempate e o sorteio).
    assert _persegue(motor, desafio, do_nivel="g1h1").startswith("e4")


def test_espia_alvo_da_nota_a_espia_que_passa_a_atacar_o_alvo(motor):
    """O cavalo espiao de c3 passa a atacar o bispo-alvo de f6 de e4 ou de d5."""
    desafio = _desafio(
        "xadrez_espia_alvo", "7k/8/5b2/8/8/2N5/8/6K1 w - - 0 1", {"lances": 8},
        marcas={"espia": "c3", "alvo": "f6"},
    )
    notas = _notas(motor, desafio)
    assert notas["c3e4"] == notas["c3d5"] == 1.0
    assert notas["c3b1"] == notas["g1h1"] == 0.0


def test_comer_com_da_nota_so_a_classe_e_a_comida_marcadas(motor):
    """O bispo come o peao de h6 (nota); o cavalo come o de e5 (sem nota)."""
    desafio = _desafio(
        "xadrez_comer_com", "k7/8/7p/4p3/8/5N2/8/2B3K1 w - - 0 1",
        {"capturas": 2, "lances": 8, "come": "bispo", "comida": "peao"},
        classes={"come": "bispo", "comida": "peao"},
    )
    notas = _notas(motor, desafio)
    assert notas["c1h6"] == ps.PESO_DO_AGORA
    # O cavalo come o de e5, que nao conta (a classe e o bispo); o bispo de c1
    # continua alcancando o peao de h6: 1.
    assert notas["f3e5"] == 1.0


def test_xeques_seguidos_da_nota_ao_xeque(motor):
    desafio = _desafio("xadrez_xeques_seguidos", "k7/8/1K6/2Q5/8/8/8/8 w - - 0 1", {"xeques": 3, "lances": 8})
    notas = _notas(motor, desafio)
    # Qa5+ so deixa ao rei b8, e de la ha xeque de novo (Qe5+): o xeque vale
    # o agora mais a sequencia inteira.
    assert notas["c5a5"] == ps.PESO_DO_AGORA + ps.PESO_DA_SEQUENCIA
    # Sem xeque agora, a dama em c4 daria varios xeques se jogasse de novo.
    assert 0.0 < notas["c5c4"] < ps.PESO_DO_AGORA


def test_xeques_seguidos_prefere_o_xeque_que_continua(motor):
    """21/11/2026, depois da 5a regua: o "um lance adiante" troca a vez no FEN,
    e depois de um xeque o motor recusa a posicao trocada (o adversario esta em
    xeque). Ate aqui todo xeque empatava; agora conta-se, em cada resposta do
    adversario, se ainda ha xeque para dar."""
    desafio = _desafio("xadrez_xeques_seguidos", "4k3/pp6/8/8/8/8/PP6/4K2Q w - - 0 1", {"xeques": 3, "lances": 8})
    _, examinados = ps.examinar_todos(motor, desafio, [])
    por_lance = {e.lance: e for e in examinados}
    # O defeito: com o adversario em xeque, nao ha "jogar de novo".
    assert ps._estado_com_a_vez_trocada(motor, desafio, por_lance["h1e4"]) is None
    # Qe4+ deixa xeque depois de qualquer resposta; Qc6+ deixa o rei escapar
    # de algum xeque (uma das respostas acaba com a sequencia).
    assert ps._xeque_que_continua(motor, desafio, por_lance["h1e4"]) == 1.0
    assert 0.0 < ps._xeque_que_continua(motor, desafio, por_lance["h1c6"]) < 1.0
    notas = {lance: ps.nota_do_objetivo(motor, desafio, [], e) for lance, e in por_lance.items()}
    assert notas["h1e4"] > notas["h1c6"] >= ps.PESO_DO_AGORA
    # Um lance sem xeque nunca vale mais que um xeque (quebraria a sequencia).
    sem_xeque = [n for lance, n in notas.items() if not por_lance[lance].fatos.get("xeque_por")]
    assert max(sem_xeque) < ps.PESO_DO_AGORA


def test_troca_na_ordem_1_oferece_o_bispo_onde_o_cavalo_come_e_o_peao_retoma(motor):
    """O bispo de b1 em e4: o cavalo de f6 o come, e o peao de f3 retoma."""
    desafio = _desafio(
        "xadrez_troca", "7k/8/5n2/8/8/5P2/8/1B4K1 w - - 0 1", {"lances": 8},
        troca={"minha": "bispo", "dele": "cavalo"},
    )
    notas = _notas(motor, desafio)
    assert notas["b1e4"] == 1.0
    assert notas["b1d3"] == notas["b1f5"] == 0.0
    # Sem o peao de f3, o cavalo come o bispo em e4 e ninguem retoma: nao e
    # troca, e perder o bispo.
    sem_retomada = _desafio(
        "xadrez_troca", "7k/p7/5n2/8/8/8/P7/1B4K1 w - - 0 1", {"lances": 8},
        troca={"minha": "bispo", "dele": "cavalo"},
    )
    assert _notas(motor, sem_retomada)["b1e4"] == 0.0


def test_os_tipos_sem_nota_dao_zero_a_tudo(motor):
    fen = "7k/p7/8/8/8/2N5/P7/6K1 w - - 0 1"
    for tipo, parametros, extra in (
        ("xadrez_espia_proteger", {"lances": 10}, {"marcas": {"espia": "c3"}}),
        ("xadrez_sem_levar_xeque", {"lances": 10}, {}),
        ("xadrez_nao_perder", {"lances": 8, "peca": "cavalo"}, {}),
    ):
        assert set(_notas(motor, _desafio(tipo, fen, parametros, **extra)).values()) == {0.0}, tipo


# ═══════════════════════════════════════════════════════════════════════════
# A mistura do nivel
# ═══════════════════════════════════════════════════════════════════════════


class _SorteioFixo(random.Random):
    """Um sorteio cujo `random()` devolve sempre o mesmo numero."""

    def __init__(self, valor: float) -> None:
        super().__init__(0)
        self._valor = valor

    def random(self) -> float:  # noqa: D102 (o de `random.Random`)
        return self._valor


def test_fora_da_probabilidade_o_lance_e_o_do_nivel_cru(motor):
    """A Cacau persegue com 0,25: com o sorteio em 0,9, joga o lance do nivel,
    MESMO havendo a captura da espia na mesa (a v3 do Quatro)."""
    desafio = _desafio(
        "xadrez_espia_comer", "7k/p7/8/3p4/8/2N5/P7/6K1 w - - 0 1", {"capturas": 2, "lances": 8},
        marcas={"espia": "c3"},
    )
    lance = ps.lance_de_quem_persegue(
        motor, desafio, [], nivel=NivelDeMotor.CACAU, sorteio=_SorteioFixo(0.9),
        lance_do_nivel=lambda: "g1h1",
    )
    assert lance == "g1h1"
    lance = ps.lance_de_quem_persegue(
        motor, desafio, [], nivel=NivelDeMotor.CACAU, sorteio=_SorteioFixo(0.1),
        lance_do_nivel=lambda: "g1h1",
    )
    assert lance == "c3d5"


def test_partida_acabada_nao_tem_lance(motor):
    desafio = _desafio("xadrez_xeques_seguidos", "k7/1Q6/1K6/8/8/8/8/8 b - - 0 1", {"xeques": 3, "lances": 8})
    with pytest.raises(ValueError):
        ps.examinar_todos(motor, desafio, [])

"""T034 - o gerador de candidatos: as tres escolhas e as duas portas.

⚠️ **A maioria destes testes nao gera desafio nenhum**, e isso e de proposito: a
geracao de verdade roda motor, e um teste que a exercite a cada `pytest` cobraria
segundos de todo mundo por uma garantia que dois casos ja dao.

O que os casos rapidos guardam e o que costuma quebrar sem fazer barulho: o
rodizio deixar de ser deterministico, um tipo sem receita ou sem vetor escapar
para a fila, e o mascote virar o degrau errado da escada.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from job.gerador import (
    EPOCA_DO_RODIZIO,
    JOGOS_DO_RODIZIO,
    PERSONAGENS,
    SemCandidato,
    escolher_jogo,
    escolher_personagem,
    escolher_tipo,
    exigir_vetor,
    gerar_candidatos,
    nivel_do_personagem,
    tipos_com_vetor,
)
from job.tipos_de_desafio import RECEITAS, TipoSemReceita, receita_de, tipos_do_jogo
from motores.nucleo.papeis import NivelDeMotor


# ═══════════════════════════════════════════════════════════════════════════
# 1. As tres escolhas do dia
# ═══════════════════════════════════════════════════════════════════════════


def test_as_escolhas_sao_DETERMINISTICAS() -> None:
    """🔒 Duas execucoes do job para o mesmo dia escolhem a mesma coisa.

    ⚠️ E disso que a idempotencia de T038 depende. Se a escolha fosse sorteada, a
    segunda execucao geraria um desafio diferente, e "rodar duas vezes nao troca o
    publicado" viraria "nao troca porque o `UNIQUE` barrou" — o que e verdade,
    mas deixaria a fila com candidatos orfaos de todo dia.
    """
    dia = date(2026, 9, 15)
    assert escolher_jogo(dia) == escolher_jogo(dia)
    assert escolher_personagem(dia) == escolher_personagem(dia)
    assert escolher_tipo("pontinhos", dia) == escolher_tipo("pontinhos", dia)


def test_o_rodizio_de_jogo_passa_por_todos() -> None:
    """Em dias consecutivos, cada jogo aparece."""
    vistos = {escolher_jogo(EPOCA_DO_RODIZIO + timedelta(days=n)) for n in range(8)}
    assert vistos == set(JOGOS_DO_RODIZIO)


def test_o_rodizio_de_personagem_passa_pelos_quatro() -> None:
    """⚠️ O personagem e o NIVEL: a fila precisa variar de dificuldade."""
    vistos = {
        escolher_personagem(EPOCA_DO_RODIZIO + timedelta(days=n)) for n in range(8)
    }
    assert vistos == set(PERSONAGENS)


def test_o_tipo_NAO_repete_o_recente() -> None:
    """Dois dias seguidos de "feche N caixas" fazem o dia parecer o de ontem."""
    dia = date(2026, 9, 15)
    primeiro = escolher_tipo("pontinhos", dia)
    segundo = escolher_tipo("pontinhos", dia, tipos_recentes=[primeiro])
    assert segundo != primeiro


def test_com_TODOS_recentes_o_rodizio_nao_falha() -> None:
    """⚠️ Um jogo com poucos tipos nao pode ficar sem desafio por variedade.

    A regra de nao repetir e sobre a experiencia; ficar sem desafio do dia e sobre
    o produto nao funcionar. A segunda perde.
    """
    dia = date(2026, 9, 15)
    todos = tipos_do_jogo("pontinhos")
    assert escolher_tipo("pontinhos", dia, tipos_recentes=todos) in todos


def test_jogo_sem_tipo_publicavel_falha_ALTO() -> None:
    with pytest.raises(SemCandidato):
        escolher_tipo("velha", date(2026, 9, 15))


@pytest.mark.parametrize(
    "personagem, nivel",
    [
        ("cacau", NivelDeMotor.CACAU),
        ("pita", NivelDeMotor.PITA),
        ("tex", NivelDeMotor.TEX),
        ("magno", NivelDeMotor.SAGAZ),
    ],
)
def test_o_mascote_vira_o_degrau_certo(personagem: str, nivel: NivelDeMotor) -> None:
    """⚠️ **Sagaz e o nome do DEGRAU; Magno e o nome do PERSONAGEM.**

    Os dois vocabularios convivem no projeto desde as damas, e trocar um pelo
    outro e o engano mais comum de quem chega — e ele nao daria erro: so mediria
    a regua com o adversario errado.
    """
    assert nivel_do_personagem(personagem) is nivel


def test_personagem_inventado_falha() -> None:
    with pytest.raises(ValueError):
        nivel_do_personagem("magno_jr")


# ═══════════════════════════════════════════════════════════════════════════
# 2. As duas portas
# ═══════════════════════════════════════════════════════════════════════════


def test_todo_tipo_com_receita_TEM_vetor() -> None:
    """🔒 As duas portas fecham juntas, ou a fila publica o que ninguem confere.

    ⚠️ E este o teste que impede a tentacao de escrever a receita e "acrescentar o
    vetor depois": no intervalo entre as duas, o tipo seria publicavel e a
    divergencia entre Dart e Python nasceria calada.
    """
    com_vetor = tipos_com_vetor()
    sem = sorted(set(RECEITAS) - com_vetor)
    assert not sem, (
        f"tipos com receita e sem vetor de verificacao: {sem}. ⛔ Escreva o vetor "
        "antes de deixar o tipo publicavel."
    )


def test_tipo_sem_vetor_e_RECUSADO() -> None:
    with pytest.raises(SemCandidato, match="vetor"):
        exigir_vetor("damas_final_da_base")


def test_tipo_sem_receita_e_RECUSADO() -> None:
    """⚠️ A alternativa (chegada vazia) daria um desafio impossivel, sem erro."""
    with pytest.raises(TipoSemReceita):
        receita_de("pontinhos_lance_unico")


def test_a_receita_monta_uma_chegada_VALIDA() -> None:
    """O que a receita emite tem de passar pelo avaliador — senao ela e decoracao."""
    from motores.nucleo.chegada import LinhaDeChegada

    parametros = {"caixas": 4, "turnos": 2, "damas": 1, "lances": 3, "pecas": 2}
    for codigo, receita in RECEITAS.items():
        chegada = LinhaDeChegada.de_dado(receita.montar(parametros))
        assert chegada.clausulas, codigo
        # A frase precisa dos valores, e o personagem entra nela.
        valores = receita.valores_da_frase(parametros, "pita")
        assert valores["personagem"] == "pita", codigo


def test_a_chave_do_objetivo_nunca_e_a_frase() -> None:
    """⛔ O aplicativo recebe a CHAVE de i18n, nunca o texto pronto.

    Uma frase gravada no banco viajaria num idioma so — e o app e trilingue desde
    o nascimento.
    """
    for codigo, receita in RECEITAS.items():
        chave = receita.co_chave_objetivo
        assert " " not in chave, f"{codigo}: {chave!r} parece uma frase"
        assert chave.startswith("desafioObjetivo"), codigo


# ═══════════════════════════════════════════════════════════════════════════
# 3. A geracao de verdade — dois casos, e sao caros
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def candidato_de_damas():
    """Gera UM candidato de damas, uma vez para o arquivo inteiro.

    ⚠️ **`scope="module"` nao e detalhe de estilo: e o preco da suite.** Esta
    geracao roda o motor e leva cerca de 30 segundos. Dois testes que a
    repetissem cobrariam um minuto de todo `pytest` do projeto por uma garantia
    que uma geracao ja da — e uma suite lenta e uma suite que se roda menos.
    """
    dia = next(
        EPOCA_DO_RODIZIO + timedelta(days=n)
        for n in range(10)
        if escolher_jogo(EPOCA_DO_RODIZIO + timedelta(days=n)) == "damas"
    )
    candidatos = gerar_candidatos(
        dia,
        parametros={"damas": 1, "lances": 6, "pecas": 2},
        quantos=1,
        tentativas_por_candidato=4,
        lances_de_preparo=8,
        maximo_de_lances=8,
    )
    assert candidatos, (
        "nenhum candidato de damas. ⚠️ Isto guarda a descoberta de 09/09/2026: o "
        "gerador ingenuo (lances aleatorios a partir da abertura) da ZERO "
        "candidatos de damas, e a regressao para ele so apareceria como fila "
        "vazia, dias depois."
    )
    return candidatos[0]


def test_gera_um_candidato_de_damas_a_partir_de_um_MOLDE(candidato_de_damas) -> None:
    """O candidato sai completo: posicao, formato e gabarito.

    ⚠️ **Todo candidato sai com gabarito**, e e essa a prova de que o desafio TEM
    solucao (RF-DES-196). Um desafio sem solucao conhecida nao e publicado.
    """
    candidato = candidato_de_damas
    assert candidato.co_jogo == "damas"
    assert candidato.co_formato_posicao == "fen"
    assert candidato.nu_lances_solucao >= 1
    assert candidato.js_solucao["lances"]
    assert 1 <= candidato.js_solucao["lance_chave"] <= candidato.nu_lances_solucao


def test_o_candidato_gerado_e_JULGADO_como_cumprido_pela_sua_propria_solucao(
    candidato_de_damas,
) -> None:
    """🔒 O fecho do circulo: a solucao publicada resolve o desafio publicado.

    ⚠️ Parece obvio, e nao e: a solucao e achada com uma linha de chegada, e
    gravada ao lado dela. Se as duas se separarem — um parametro lido de um lugar
    e escrito de outro —, o gabarito de D+1 mostraria uma sequencia que nao
    cumpre o objetivo do dia, e ninguem descobriria antes de alguem reclamar.
    """
    from motores.juiz import julgar_desafio

    candidato = candidato_de_damas
    julgamento = julgar_desafio(
        co_jogo=candidato.co_jogo,
        js_posicao_inicial=candidato.js_posicao_inicial,
        js_chegada=candidato.js_chegada,
        fita=candidato.js_solucao["lances"],
        jogador=candidato.js_posicao_inicial["vez_de"],
        co_modalidade=candidato.co_modalidade or "brasileira",
    )
    assert julgamento.cumpriu, (
        f"o gabarito do candidato NAO cumpre a propria linha de chegada: "
        f"{julgamento.veredito} ({julgamento.de_motivo})"
    )

"""A REPRISE COMO COPIA — T041 (RF-DES-029, RF-DES-012d, RF-DES-152).

O que estes casos protegem:

  · ⛔ **nunca um candidato nao revisado** — um dia repetido e um aborrecimento;
    um desafio impossivel no ar e uma sessao perdida;
  · **a preferencia por menor participacao**, que e o unico criterio que reduz o
    incomodo real da reprise;
  · **a copia, e nao o mesmo desafio**: identificador proprio, ponteiro para a
    origem, marca de reprise — e **sem cadeia** de copia de copia;
  · **os feitos de saida vao junto**, senao a reprise pagaria so o piso de 18 XP
    sem nada dar erro.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from job.reprise import (
    DIAS_MINIMOS_DESDE_A_ORIGEM,
    SQL_CANDIDATAS,
    SQL_COPIAR,
    SQL_COPIAR_FEITOS,
    TAXA_MINIMA_PARA_REPRISAR,
    TENTATIVAS_MINIMAS_PARA_JULGAR,
    CandidataAReprise,
    RepriseImpossivel,
    elegivel,
    escolher,
    publicar_reprise,
)
from tests.unitarios.fakes_desafio import FakeSessaoSQL

HOJE = date(2026, 9, 10)
BEM_ANTIGA = HOJE - timedelta(days=200)


def _candidata(
    *,
    tentativas: int = 100,
    resolucoes: int = 80,
    dt_dia: date = BEM_ANTIGA,
    id_desafio=None,
    id_origem=None,
) -> CandidataAReprise:
    """Uma candidata boa por padrao — cada caso estraga só o que quer testar."""
    ident = id_desafio or uuid4()
    return CandidataAReprise(
        id_desafio=ident,
        id_origem=id_origem or ident,
        dt_dia_original=dt_dia,
        qt_tentativas=tentativas,
        qt_resolucoes=resolucoes,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quem pode voltar ao ar
# ═══════════════════════════════════════════════════════════════════════════


def test_desafio_bem_avaliado_e_elegivel():
    """80 de 100 resolveram: acima do alvo de 70% de RF-DES-014."""
    assert elegivel(_candidata()) is True


def test_desafio_com_taxa_baixa_nao_volta():
    """⚠️ Um desafio que deu errado quando estreou nao melhorou sozinho.

    Reprisa-lo seria repetir de proposito o dia ruim — e com um rotulo dizendo
    que foi escolhido.
    """
    assert elegivel(_candidata(tentativas=100, resolucoes=30)) is False
    # A fronteira exata: exatamente no alvo passa.
    assert elegivel(_candidata(tentativas=100, resolucoes=70)) is True
    assert TAXA_MINIMA_PARA_REPRISAR == 0.70


def test_desafio_pouco_jogado_nao_volta():
    """⚠️ "2 de 3 resolveram" nao e uma medida — e o mesmo piso de RF-DES-063.

    Um desafio julgado por tres pessoas seria escolhido pelo acaso, e a reprise
    e justamente a hora de nao apostar.
    """
    assert elegivel(_candidata(tentativas=3, resolucoes=3)) is False
    assert (
        elegivel(
            _candidata(
                tentativas=TENTATIVAS_MINIMAS_PARA_JULGAR,
                resolucoes=TENTATIVAS_MINIMAS_PARA_JULGAR,
            )
        )
        is True
    )


def test_desafio_que_ninguem_tentou_tem_taxa_zero():
    """Sem tentativa nao ha prova; estrear um desconhecido com rotulo de reprise
    e o pior dos dois mundos."""
    sem_ninguem = _candidata(tentativas=0, resolucoes=0)
    assert sem_ninguem.taxa_de_resolucao == 0.0
    assert elegivel(sem_ninguem) is False


# ═══════════════════════════════════════════════════════════════════════════
# 2. A escolha (RF-DES-029)
# ═══════════════════════════════════════════════════════════════════════════


def test_escolhe_a_de_MENOR_participacao():
    """⚠️ RF-DES-029, textual: *"para que caia sobre o menor numero possivel de
    gente que ja a jogou"*.

    Repetir o desafio mais popular do mes seria repetir para todo mundo.
    """
    pouca = _candidata(tentativas=25, resolucoes=20)
    muita = _candidata(tentativas=900, resolucoes=800)
    # A ordem vem do banco (ASC por tentativas); `escolher` filtra e pega a 1a.
    assert escolher([pouca, muita], dt_hoje=HOJE) is pouca


def test_recente_demais_nao_volta():
    """⚠️ Repetir o desafio da semana passada parece o job travado.

    O intervalo nao e conforto: e o que faz a reprise parecer o que ela e — um
    fallback raro — em vez de um defeito.
    """
    recente = _candidata(dt_dia=HOJE - timedelta(days=5))
    with pytest.raises(RepriseImpossivel):
        escolher([recente], dt_hoje=HOJE)

    # Exatamente no limite, passa.
    no_limite = _candidata(
        dt_dia=HOJE - timedelta(days=DIAS_MINIMOS_DESDE_A_ORIGEM)
    )
    assert escolher([no_limite], dt_hoje=HOJE) is no_limite


def test_sem_candidata_elegivel_faz_barulho():
    """⛔ O pior caso operacional da spec: a fila acabou E nao ha reprise.

    ⚠️ Devolver `None` calado deixaria o job "terminar bem" no dia em que o
    aplicativo abre sem desafio — indistinguivel, no painel do Railway, de um dia
    normal.
    """
    with pytest.raises(RepriseImpossivel) as erro:
        escolher([_candidata(tentativas=2, resolucoes=2)], dt_hoje=HOJE)

    # A mensagem tem de dizer o que foi avaliado e por que reprovou — quem a le
    # esta no meio de um incidente.
    texto = str(erro.value)
    assert "1 candidata" in texto
    assert "70%" in texto


def test_sem_candidata_nenhuma_tambem_faz_barulho():
    """Lista vazia e o mesmo incidente, e nao um caminho silencioso."""
    with pytest.raises(RepriseImpossivel):
        escolher([], dt_hoje=HOJE)


# ═══════════════════════════════════════════════════════════════════════════
# 3. A copia (RF-DES-152)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_consulta_so_traz_APROVADO():
    """⛔ RF-DES-012d: **nunca** um candidato nao revisado.

    ⚠️ E o filtro nao e redundante com "ja foi publicado": um desafio pode ter
    sido descartado **depois** de ir ao ar, e e exatamente esse que nao pode
    voltar.
    """
    assert "d.co_curadoria = 'aprovado'" in SQL_CANDIDATAS


def test_a_consulta_evita_a_cadeia_de_copias():
    """⚠️ A origem apontada e sempre a linha ORIGINAL.

    Sem o `COALESCE`, uma reprise de reprise apontaria para a copia, e
    *"quantas vezes este desafio ja foi ao ar"* viraria travessia recursiva.
    """
    assert "COALESCE(d.id_desafio_origem, d.id_desafio)" in SQL_CANDIDATAS


def test_a_copia_nasce_aprovada_e_marcada():
    """Identificador proprio, ponteiro para a origem e marca de reprise."""
    assert "'aprovado', NULL" in SQL_COPIAR
    assert ":id_origem, TRUE" in SQL_COPIAR


def test_a_copia_nao_repete_a_lista_de_colunas_em_python():
    """⚠️ `INSERT ... SELECT`, e nao ler e reescrever campo a campo.

    Uma coluna nova em `tb001_desafio` entraria na tabela e **ficaria de fora da
    copia** sem que nada acusasse — a reprise sairia com um campo `NULL` que
    ninguem procuraria.
    """
    assert "INSERT INTO desafio.tb001_desafio" in SQL_COPIAR
    assert "SELECT co_jogo" in SQL_COPIAR
    # ⛔ O identificador e o `dh_geracao` NAO viajam: sao o que distingue a copia.
    cabecalho = SQL_COPIAR.split("SELECT", 1)[0]
    assert "id_desafio," not in cabecalho
    assert "dh_geracao" not in SQL_COPIAR


def test_os_feitos_de_saida_vao_junto():
    """⚠️ Sem eles a reprise iria ao ar pagando so o piso de 18 XP.

    E **nada daria erro**: o `INSERT` do desafio passaria, o aplicativo baixaria
    a linha, e a diferenca so apareceria no extrato de quem jogou.
    """
    assert "INSERT INTO desafio.tb003_feito_desafio" in SQL_COPIAR_FEITOS
    assert ":id_copia" in SQL_COPIAR_FEITOS


# ═══════════════════════════════════════════════════════════════════════════
# 4. A publicacao inteira
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_publicar_copia_os_feitos_ANTES_de_publicar_o_dia():
    """⚠️ A ordem das tres escritas nao e negociavel.

    Publicar o dia antes de copiar os feitos abriria uma janela em que o
    aplicativo poderia baixar um desafio que paga so o piso — curta,
    intermitente e impossivel de reproduzir depois.
    """
    origem = uuid4()
    copia = uuid4()
    sessao = FakeSessaoSQL(
        respostas={
            "COALESCE(d.id_desafio_origem": [
                {
                    "id_desafio": origem,
                    "id_origem": origem,
                    "dt_dia_original": BEM_ANTIGA,
                    "qt_tentativas": 30,
                    "qt_resolucoes": 27,
                }
            ],
            "INSERT INTO desafio.tb001_desafio": [{"id_desafio": copia}],
            "INSERT INTO desafio_dia.tb001_desafio_dia": [
                {"id_desafio_dia": uuid4()}
            ],
        }
    )

    devolvido = await publicar_reprise(sessao, dt_dia=HOJE)

    assert devolvido == copia
    ordem = [
        i
        for i, (sql, _) in enumerate(sessao.executadas)
        if "tb003_feito_desafio" in sql or "tb001_desafio_dia" in sql
    ]
    feitos = next(
        i for i, (sql, _) in enumerate(sessao.executadas)
        if "tb003_feito_desafio" in sql
    )
    dia = next(
        i for i, (sql, _) in enumerate(sessao.executadas)
        if "INSERT INTO desafio_dia.tb001_desafio_dia" in sql
    )
    assert feitos < dia, "os feitos precisam existir antes de o dia ir ao ar"
    assert len(ordem) == 2
    assert sessao.commits == 1


@pytest.mark.asyncio
async def test_publicar_sem_candidata_nao_toca_no_banco():
    """⛔ Nenhuma escrita quando nao ha o que reprisar."""
    sessao = FakeSessaoSQL(respostas={"COALESCE(d.id_desafio_origem": []})

    with pytest.raises(RepriseImpossivel):
        await publicar_reprise(sessao, dt_dia=HOJE)

    assert not sessao.sql_executado("INSERT")
    assert sessao.commits == 0


@pytest.mark.asyncio
async def test_a_copia_que_nao_grava_e_incidente_e_nao_dia_vazio():
    """Se o `INSERT ... SELECT` nao devolver linha, ninguem publica um dia torto."""
    origem = uuid4()
    sessao = FakeSessaoSQL(
        respostas={
            "COALESCE(d.id_desafio_origem": [
                {
                    "id_desafio": origem,
                    "id_origem": origem,
                    "dt_dia_original": BEM_ANTIGA,
                    "qt_tentativas": 30,
                    "qt_resolucoes": 27,
                }
            ],
            # ⚠️ A copia devolve VAZIO — o caso em que a origem sumiu entre a
            # leitura e a escrita.
            "INSERT INTO desafio.tb001_desafio": [],
        }
    )

    with pytest.raises(RepriseImpossivel):
        await publicar_reprise(sessao, dt_dia=HOJE)

    assert not sessao.sql_executado("INSERT INTO desafio_dia.tb001_desafio_dia")
    assert sessao.commits == 0

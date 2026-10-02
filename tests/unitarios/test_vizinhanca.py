"""🔒 A alternancia entre dias consecutivos: a regra e quem a obedece (02/10/2026).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O dono decidiu que os desafios nascem pre-aprovados, e pos uma condicao:

> *"E claro que sempre precisa garantir a alternancia de jogos/modalidades/
> personagens do desafio de um dia para o outro, para nao termos desafios
> parecidos de um dia para outro."*

A regra mora em `job/vizinhanca.py`. Este arquivo trava tres coisas:

  1. a regra em si (`conflita`, `preferir`);
  2. que as escolhas do gerador DESVIAM dos vizinhos, e so deles;
  3. que o job le a vizinhanca e a entrega ao gerador — e que o desafio nasce
     `aprovado`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from job import __main__ as job_main
from job.gerador import (
    EPOCA_DO_RODIZIO,
    JOGOS_DO_RODIZIO,
    MODALIDADES_POR_JOGO,
    PERSONAGENS,
    escolher_jogo,
    escolher_modalidade,
    escolher_personagem,
)
from job.gravacao import LinhaDeDesafio
from job.repositorio import SQL_VIZINHANCA, RepositorioDoJob
from job.vizinhanca import Ocupante, Vizinhanca, conflita, preferir
from tests.unitarios.fakes_desafio import FakeSessaoSQL

# ═══════════════════════════════════════════════════════════════════════════
# 1. A regra
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "a, b",
    [
        (Ocupante("damas"), Ocupante("damas")),
        (Ocupante("damas", "tex"), Ocupante("pontinhos", "tex")),
        (
            Ocupante("damas", "tex", "anglo"),
            Ocupante("xadrez", "pita", "anglo"),
        ),
        (
            Ocupante(None, None, None, "damas_coroar"),
            Ocupante(None, None, None, "damas_coroar"),
        ),
    ],
    ids=["mesmo jogo", "mesmo personagem", "mesma modalidade", "mesmo tipo"],
)
def test_qualquer_campo_igual_CONFLITA(a: Ocupante, b: Ocupante) -> None:
    """🔒 Basta UM dos quatro repetir para os dois dias ficarem parecidos."""
    assert conflita(a, b)
    assert conflita(b, a), "a regra precisa ser simetrica"


def test_tudo_diferente_NAO_conflita() -> None:
    """🔒 O caso de todo dia: Pontinhos com a Cacau, damas anglo com o Tex."""
    assert not conflita(
        Ocupante("pontinhos", "cacau", None, "pontinhos_paciencia"),
        Ocupante("damas", "tex", "anglo", "damas_coroar"),
    )


def test_campo_AUSENTE_nao_conflita() -> None:
    """🔒 ⚠️ `None` com `None` NAO e "iguais".

    Sem isso, um desafio antigo sem personagem carregado conflitaria com todo
    outro sem personagem, e a compactacao travaria por falta de dado.
    """
    assert not conflita(Ocupante(None, None), Ocupante(None, None))
    assert not conflita(Ocupante("damas", None), Ocupante("pontinhos", None))
    assert not conflita(None, Ocupante("damas"))


def test_preferir_fica_com_o_RODIZIO_quando_nada_o_impede() -> None:
    """🔒 Fila sem vizinho: a resposta e a mesma de antes de 02/10/2026."""
    assert preferir(("a", "b", "c"), indice_do_rodizio=4) == "b"


def test_preferir_ANDA_para_a_proxima_livre() -> None:
    """🔒 Gira a partir da escolha do rodizio, e nao do comeco da lista."""
    assert preferir(("a", "b", "c", "d"), indice_do_rodizio=1, evitar={"b"}) == "c"
    assert preferir(("a", "b", "c", "d"), indice_do_rodizio=3, evitar={"d"}) == "a"


def test_preferir_sem_saida_devolve_o_RODIZIO() -> None:
    """🔒 ⚠️ Ficar sem desafio e pior que repetir: com tudo proibido, o rodizio vence."""
    assert preferir(("a", "b"), indice_do_rodizio=1, evitar={"a", "b"}) == "b"


def test_vizinhanca_junta_os_dois_lados_e_ignora_o_vazio() -> None:
    """🔒 O que os vizinhos usam, sem inventar valor para o lado que nao existe."""
    viz = Vizinhanca(
        anterior=Ocupante("damas", "tex", "anglo"),
        seguinte=Ocupante("pontinhos", "pita", None),
    )
    assert viz.jogos == {"damas", "pontinhos"}
    assert viz.personagens == {"tex", "pita"}
    assert viz.modalidades == {"anglo"}
    assert Vizinhanca().jogos == frozenset()


# ═══════════════════════════════════════════════════════════════════════════
# 2. As escolhas do gerador desviam dos vizinhos
# ═══════════════════════════════════════════════════════════════════════════


def _dia_do_jogo(co_jogo: str) -> date:
    """O primeiro dia, a partir da epoca, em que o rodizio puro escolhe o jogo."""
    dia = EPOCA_DO_RODIZIO
    while escolher_jogo(dia) != co_jogo:
        dia += timedelta(days=1)
    return dia


def test_sem_vizinhos_o_rodizio_NAO_mudou() -> None:
    """🔒 ⛔ A mudanca de 02/10 nao pode mexer na fila sem buraco.

    Toda execucao que gera o FIM da fila tem vizinho so de um lado (ou nenhum),
    e a resposta para trinta dias seguidos, sem `evitar`, tem de ser a de antes.
    """
    for n in range(30):
        dia = EPOCA_DO_RODIZIO + timedelta(days=n)
        dias = (dia - EPOCA_DO_RODIZIO).days
        assert escolher_jogo(dia) == JOGOS_DO_RODIZIO[dias % len(JOGOS_DO_RODIZIO)]
        assert escolher_personagem(dia) == PERSONAGENS[dias % len(PERSONAGENS)]


def test_o_jogo_DESVIA_do_vizinho_que_o_repetiria() -> None:
    """🔒 Buraco num dia "de damas" com damas ao lado: sai Pontinhos."""
    dia = _dia_do_jogo("damas")
    assert escolher_jogo(dia, evitar={"damas"}) == "pontinhos"


def test_o_jogo_sem_saida_fica_com_o_RODIZIO() -> None:
    """🔒 Vizinhos dos dois jogos: nao ha como alternar, e o dia nao fica vazio."""
    dia = _dia_do_jogo("damas")
    assert escolher_jogo(dia, evitar={"damas", "pontinhos"}) == "damas"


def test_o_personagem_DESVIA_dos_dois_vizinhos() -> None:
    """🔒 O personagem do rodizio e o do vizinho: anda para o proximo livre."""
    dia = EPOCA_DO_RODIZIO
    do_rodizio = escolher_personagem(dia)
    outro = PERSONAGENS[(PERSONAGENS.index(do_rodizio) + 1) % len(PERSONAGENS)]
    escolhido = escolher_personagem(dia, evitar={do_rodizio, outro})
    assert escolhido not in {do_rodizio, outro}


def test_o_personagem_RESTRITO_a_um_so_nao_desvia() -> None:
    """🔒 ⚠️ Tipo que so cabe contra a Cacau continua so cabendo contra a Cacau.

    Desviar para o Magno publicaria um desafio que o editorial disse ser
    impossivel contra ele - a restricao do tipo vale mais que a alternancia.
    """
    dia = EPOCA_DO_RODIZIO
    assert escolher_personagem(dia, possiveis=("cacau",), evitar={"cacau"}) == "cacau"


def test_a_modalidade_DESVIA_da_do_vizinho() -> None:
    """🔒 A modalidade do odometro e a do vizinho: anda para a seguinte."""
    dia = _dia_do_jogo("damas")
    do_rodizio = escolher_modalidade("damas", dia)
    assert do_rodizio is not None
    escolhida = escolher_modalidade("damas", dia, evitar={do_rodizio})
    assert escolhida != do_rodizio
    assert escolhida in MODALIDADES_POR_JOGO["damas"]


def test_o_pontinhos_continua_SEM_modalidade() -> None:
    """🔒 `evitar` nao inventa modalidade para quem nao tem."""
    assert escolher_modalidade("pontinhos", EPOCA_DO_RODIZIO, evitar={"anglo"}) is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. O job le a vizinhanca, entrega ao gerador, e o desafio nasce aprovado
# ═══════════════════════════════════════════════════════════════════════════


def test_o_desafio_nasce_APROVADO() -> None:
    """🔒 ⛔ Decisao do dono, 02/10/2026: *"Quero que os desafios gerados ja
    venham pre-aprovados."*

    ⚠️ O valor mora no dataclass, e o `INSERT` o recebe por parametro (ver
    `test_o_desafio_nasce_com_a_curadoria_do_PARAMETRO`). Um `DEFAULT` na
    tabela continuaria proibido: quem decide o estado de nascimento e um
    lugar so, com o motivo escrito ao lado.
    """
    campo = LinhaDeDesafio.__dataclass_fields__["co_curadoria"]
    assert campo.default == "aprovado"


@pytest.mark.asyncio
async def test_o_repositorio_le_os_DOIS_vizinhos_numa_consulta() -> None:
    """🔒 Uma ida ao banco para o dia anterior e o seguinte."""
    dia = date(2026, 10, 10)
    sessao = FakeSessaoSQL(
        respostas={
            "co_curadoria IN ('aprovado', 'candidato')": [
                {
                    "dt_dia": dia - timedelta(days=1),
                    "co_jogo": "damas",
                    "co_modalidade": "anglo",
                    "co_personagem": "tex",
                    "co_tipo_desafio": "damas_coroar",
                }
            ]
        }
    )
    viz = await RepositorioDoJob(sessao).vizinhanca(dia)

    assert viz.anterior == Ocupante("damas", "tex", "anglo", "damas_coroar")
    assert viz.seguinte is None
    _, parametros = sessao.executadas[-1]
    assert parametros == {
        "dt_anterior": dia - timedelta(days=1),
        "dt_seguinte": dia + timedelta(days=1),
    }
    assert "co_curadoria IN ('aprovado', 'candidato')" in SQL_VIZINHANCA


@pytest.mark.asyncio
async def test_cobrir_um_dia_entrega_a_vizinhanca_ao_GERADOR() -> None:
    """🔒 ⛔ A vizinhanca que escolhe o jogo e a MESMA que chega ao gerador.

    Se o job lesse a fila para escolher o jogo e o gerador escolhesse o
    personagem sem ela, o buraco tapado repetiria o Tex de ontem sem nada acusar.
    """
    dia = _dia_do_jogo("damas")
    vistos: list[dict[str, Any]] = []

    def gerar_espiao(dt_dia: date, **kwargs: Any) -> list[Any]:
        vistos.append(kwargs)
        return []  # sem candidato: o dia cai na reprise, que aqui nao importa

    sessao = FakeSessaoSQL(
        respostas={
            "co_curadoria IN ('aprovado', 'candidato')": [
                {
                    "dt_dia": dia + timedelta(days=1),
                    "co_jogo": "damas",
                    "co_modalidade": "casa",
                    "co_personagem": "magno",
                    "co_tipo_desafio": "damas_coroar",
                }
            ]
        }
    )
    await job_main.cobrir_um_dia(
        sessao,
        RepositorioDoJob(sessao),
        dt_dia=dia,
        relatorio=job_main.Relatorio(),
        gerar=gerar_espiao,
    )

    assert len(vistos) == 1
    viz = vistos[0]["vizinhanca"]
    assert viz.seguinte == Ocupante("damas", "magno", "casa", "damas_coroar")
    # E o jogo do dia ja desviou: o dia "de damas" com damas ao lado vira
    # Pontinhos - e e com ele que o rodizio de tipos e consultado.
    jogos_consultados = [
        p["co_jogo"]
        for sql, p in sessao.executadas
        if p and "d.co_jogo = :co_jogo" in sql
    ]
    assert jogos_consultados == ["pontinhos"]

"""🔒 O TIPO EM DESTAQUE: o "Forme a figura" em metade dos dias do Quatro (§8zzzu).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O dono pediu, em 27/10/2026, que a figura não fosse rara (`DECISOES-do-dono.md`
§8zzzu, no frontend): ela passa a ocupar METADE dos dias do Quatro em Linha,
um sim, um não, e o Pontinhos e as damas continuam com os mesmos dias. A regra
mora em `gerador.escolher_tipo` (o tipo) e `gerador.escolher_variante` (qual
figura), e lê a fila pelo `RepositorioDoJob.vizinhos_do_destaque`.

O que se trava:

  1. a regra do tipo: sai o destaque quando o dia anterior do jogo NÃO foi
     dele e o seguinte também não; e, sem a fila, recusa alto;
  2. a simulação do fim da fila: N dias do Quatro dão exatamente N/2 de figura,
     alternados, e a figura muda a cada vez (a variante anda uma casa por
     aparição, na ordem intercalada do editorial);
  3. a leitura da fila no repositório (as três consultas e o que elas viram);
  4. a ligação no job: `cobrir_um_dia` lê a fila só no dia de um jogo com
     destaque, e passa a MESMA resposta à geração e à variante.

⚠️ Os outros jogos ficam como eram: quem prova é `test_adocao_nao_muda_a_fila.py`,
que compara o rodízio do Pontinhos e das damas com uma cópia escrita por
extenso da regra de antes.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from job import __main__ as principal_mod
from job import gerador as gerador_mod
from job.adocao import Frequencia
from job.editorial import EDITORIAL
from job.figuras_quatro import CHAVE_FIGURA
from job.gerador import (
    TIPO_EM_DESTAQUE,
    VizinhosDoDestaque,
    escolher_tipo,
    escolher_variante,
    tipos_do_jogo,
)
from job.repositorio import (
    SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO,
    SQL_TIPO_DO_DIA_SEGUINTE_DO_JOGO,
    SQL_VEZES_DO_TIPO_ANTES_DO_DIA,
    RepositorioDoJob,
)
from tests.unitarios.fakes_desafio import FakeSessaoSQL
from tests.unitarios.test_adocao_nao_muda_a_fila import UM_ANO, _um_dia_do_quatro

#: O tipo em destaque do Quatro, escrito por extenso: um teste que lesse
#: `TIPO_EM_DESTAQUE` para conferir `TIPO_EM_DESTAQUE` passaria com qualquer valor.
FIGURA = "quatro_figura"

#: Um dia qualquer: a regra do tipo não depende da data, só da fila.
DIA = date(2026, 11, 3)


# ═══════════════════════════════════════════════════════════════════════════
# 1. A regra do tipo
# ═══════════════════════════════════════════════════════════════════════════


def test_o_destaque_do_quatro_e_a_figura_e_ela_esta_no_ar() -> None:
    """Sem a figura no ar a regra não valeria nada, e passaria calada."""
    assert TIPO_EM_DESTAQUE == {"quatro": FIGURA}
    assert FIGURA in tipos_do_jogo("quatro")
    # E é UM entre vários: com ele sozinho não haveria "outra metade".
    assert len(tipos_do_jogo("quatro")) > 2


def test_sem_vizinho_de_figura_o_dia_E_da_figura() -> None:
    assert escolher_tipo("quatro", DIA, destaque=VizinhosDoDestaque()) == FIGURA


@pytest.mark.parametrize(
    "destaque",
    [
        VizinhosDoDestaque(anterior_e_destaque=True),
        # O buraco no meio da fila: o dia seguinte já é de figura.
        VizinhosDoDestaque(seguinte_e_destaque=True),
        VizinhosDoDestaque(anterior_e_destaque=True, seguinte_e_destaque=True),
    ],
    ids=["ontem-foi-figura", "amanha-ja-e-figura", "os-dois"],
)
def test_com_vizinho_de_figura_o_dia_e_de_OUTRO_tipo_do_quatro(destaque) -> None:
    tipo = escolher_tipo("quatro", DIA, destaque=destaque)
    assert tipo != FIGURA
    assert tipo in tipos_do_jogo("quatro")


def test_o_dia_de_nao_ainda_respeita_os_RECENTES() -> None:
    """A outra metade é o rodízio de sempre: sem repetir os tipos recentes."""
    outros = [t for t in tipos_do_jogo("quatro") if t != FIGURA]
    fresco = outros[-1]
    recentes = [t for t in outros if t != fresco]
    tipo = escolher_tipo(
        "quatro",
        DIA,
        tipos_recentes=recentes,
        destaque=VizinhosDoDestaque(anterior_e_destaque=True),
    )
    assert tipo == fresco


def test_sem_a_fila_o_quatro_RECUSA_alto() -> None:
    """⛔ Um padrão "sem vizinhos" poria a figura em TODO dia do Quatro."""
    with pytest.raises(ValueError, match="destaque"):
        escolher_tipo("quatro", DIA)


@pytest.mark.parametrize("co_jogo", ["pontinhos", "damas"])
def test_jogo_sem_destaque_nao_precisa_da_fila(co_jogo) -> None:
    assert co_jogo not in TIPO_EM_DESTAQUE
    assert escolher_tipo(co_jogo, DIA) in tipos_do_jogo(co_jogo)


# ═══════════════════════════════════════════════════════════════════════════
# 2. O fim da fila, dia do Quatro após dia do Quatro
# ═══════════════════════════════════════════════════════════════════════════


def _simular(dias_do_quatro: int) -> list[tuple[str, int | None]]:
    """O que o job publicaria em [dias_do_quatro] dias do Quatro seguidos, no
    fim da fila (sem dia seguinte), com a fila respondendo o que foi publicado.

    Returns:
        `(tipo, variante)` de cada dia; a variante só no dia da figura.
    """
    publicados: list[tuple[str, int | None]] = []
    vezes = 0
    variantes = EDITORIAL[FIGURA]
    for n in range(dias_do_quatro):
        destaque = VizinhosDoDestaque(
            anterior_e_destaque=bool(publicados) and publicados[-1][0] == FIGURA,
            vezes_publicado=vezes,
        )
        tipo = escolher_tipo("quatro", DIA, destaque=destaque)
        variante = None
        if tipo == FIGURA:
            variante = escolher_variante(
                "quatro",
                DIA,
                quantas_variantes=len(variantes),
                vezes_do_destaque=destaque.vezes_publicado,
            )
            vezes += 1
        publicados.append((tipo, variante))
    return publicados


def test_a_figura_fica_com_METADE_dos_dias_do_quatro_um_sim_um_nao() -> None:
    publicados = _simular(40)
    tipos = [tipo for tipo, _ in publicados]
    assert tipos.count(FIGURA) == 20
    # Um sim, um não: os pares (figura, outro) se repetem do começo ao fim.
    assert tipos[0::2] == [FIGURA] * 20
    assert FIGURA not in tipos[1::2]


def test_a_figura_MUDA_a_cada_vez_e_passa_por_todas_antes_de_repetir() -> None:
    variantes = EDITORIAL[FIGURA]
    quantas = len(variantes)
    # Duas voltas inteiras de figura: 2 x quantas dias de figura.
    publicados = _simular(4 * quantas)
    indices = [v for _, v in publicados if v is not None]
    assert indices == [n % quantas for n in range(2 * quantas)]
    # E a figura (o desenho, e não só a folga) nunca repete de um dia de
    # figura para o seguinte - nem na virada da volta.
    figuras = [variantes[i].parametros[CHAVE_FIGURA] for i in indices]
    for antes, depois in zip(figuras, figuras[1:]):
        assert antes != depois


def test_a_variante_dos_OUTROS_tipos_continua_pela_data() -> None:
    """`vezes_do_destaque=None` é o odômetro de sempre, que não lê a fila."""
    for dia in UM_ANO[:30]:
        assert escolher_variante("quatro", dia, quantas_variantes=5) == escolher_variante(
            "quatro", dia, quantas_variantes=5, vezes_do_destaque=None
        )
    # E o contador do destaque, quando vem, manda sozinho (a data não pesa).
    assert {
        escolher_variante("quatro", dia, quantas_variantes=5, vezes_do_destaque=7)
        for dia in UM_ANO[:30]
    } == {2}


# ═══════════════════════════════════════════════════════════════════════════
# 3. A leitura da fila
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_o_repositorio_le_os_dois_vizinhos_e_a_contagem() -> None:
    sessao = FakeSessaoSQL(
        respostas={
            SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO: [{"co_tipo_desafio": FIGURA}],
            SQL_TIPO_DO_DIA_SEGUINTE_DO_JOGO: [{"co_tipo_desafio": "quatro_virada"}],
            SQL_VEZES_DO_TIPO_ANTES_DO_DIA: [{"nu_vezes": 5}],
        }
    )
    vizinhos = await RepositorioDoJob(sessao).vizinhos_do_destaque(
        co_jogo="quatro", co_tipo_em_destaque=FIGURA, dt_dia=DIA
    )
    assert vizinhos == VizinhosDoDestaque(
        anterior_e_destaque=True, seguinte_e_destaque=False, vezes_publicado=5
    )
    # Os parâmetros de cada consulta: o jogo nos vizinhos, o TIPO na contagem.
    parametros = {sql: p for sql, p in sessao.executadas}
    assert parametros[SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO] == {"co_jogo": "quatro", "dt_dia": DIA}
    assert parametros[SQL_TIPO_DO_DIA_SEGUINTE_DO_JOGO] == {"co_jogo": "quatro", "dt_dia": DIA}
    assert parametros[SQL_VEZES_DO_TIPO_ANTES_DO_DIA] == {
        "co_tipo_desafio": FIGURA,
        "dt_dia": DIA,
    }


@pytest.mark.asyncio
async def test_o_dia_seguinte_de_figura_tambem_conta() -> None:
    sessao = FakeSessaoSQL(
        respostas={SQL_TIPO_DO_DIA_SEGUINTE_DO_JOGO: [{"co_tipo_desafio": FIGURA}]}
    )
    vizinhos = await RepositorioDoJob(sessao).vizinhos_do_destaque(
        co_jogo="quatro", co_tipo_em_destaque=FIGURA, dt_dia=DIA
    )
    assert vizinhos == VizinhosDoDestaque(seguinte_e_destaque=True)


@pytest.mark.asyncio
async def test_a_fila_vazia_e_nenhum_vizinho_e_zero_vezes() -> None:
    vizinhos = await RepositorioDoJob(FakeSessaoSQL()).vizinhos_do_destaque(
        co_jogo="quatro", co_tipo_em_destaque=FIGURA, dt_dia=DIA
    )
    assert vizinhos == VizinhosDoDestaque()


def test_as_consultas_dos_vizinhos_nao_tem_JANELA() -> None:
    """⚠️ No começo da adoção o Quatro tem um dia em seis: uma janela curta
    acharia "nenhum vizinho", e a figura sairia duas vezes seguidas."""
    for sql in (SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO, SQL_TIPO_DO_DIA_SEGUINTE_DO_JOGO):
        assert "BETWEEN" not in sql
        assert "LIMIT 1" in sql
    assert "BETWEEN" not in SQL_VEZES_DO_TIPO_ANTES_DO_DIA
    # E o anterior é o MAIS PERTO para trás; o seguinte, o mais perto para frente.
    assert "dt_dia < :dt_dia" in SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO
    assert "DESC" in SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO
    assert "dt_dia > :dt_dia" in SQL_TIPO_DO_DIA_SEGUINTE_DO_JOGO
    assert "ASC" in SQL_TIPO_DO_DIA_SEGUINTE_DO_JOGO
    assert "dt_dia < :dt_dia" in SQL_VEZES_DO_TIPO_ANTES_DO_DIA


# ═══════════════════════════════════════════════════════════════════════════
# 4. A ligação no job
# ═══════════════════════════════════════════════════════════════════════════


async def _cobrir_o_dia(sessao: FakeSessaoSQL, dia: date, frequencias) -> dict[str, Any]:
    """Roda `cobrir_um_dia` com uma geração espiã; devolve o que ela recebeu."""
    vistos: list[dict[str, Any]] = []

    def gerar_espiao(dt_dia: date, **kwargs: Any) -> list[Any]:
        vistos.append(kwargs)
        return []  # sem candidato: o dia cai na reprise, que aqui não importa

    await principal_mod.cobrir_um_dia(
        sessao,
        RepositorioDoJob(sessao),
        dt_dia=dia,
        relatorio=principal_mod.Relatorio(),
        gerar=gerar_espiao,
        frequencias=frequencias,
    )
    assert len(vistos) == 1
    return vistos[0]


@pytest.mark.asyncio
async def test_o_job_publica_a_figura_da_VEZ_quando_ontem_nao_foi_figura() -> None:
    frequencias = {"quatro": Frequencia(um_dia_em=3)}
    dia = _um_dia_do_quatro(frequencias)
    sessao = FakeSessaoSQL(
        respostas={
            SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO: [{"co_tipo_desafio": "quatro_virada"}],
            SQL_VEZES_DO_TIPO_ANTES_DO_DIA: [{"nu_vezes": 3}],
        }
    )
    pedido = await _cobrir_o_dia(sessao, dia, frequencias)
    assert pedido["destaque"] == VizinhosDoDestaque(vezes_publicado=3)
    # A 4a aparição da figura usa a variante 3 do editorial (a ordem dele).
    assert pedido["parametros"] == EDITORIAL[FIGURA][3].parametros


@pytest.mark.asyncio
async def test_o_job_publica_OUTRO_tipo_quando_ontem_foi_figura() -> None:
    frequencias = {"quatro": Frequencia(um_dia_em=3)}
    dia = _um_dia_do_quatro(frequencias)
    sessao = FakeSessaoSQL(
        respostas={SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO: [{"co_tipo_desafio": FIGURA}]}
    )
    pedido = await _cobrir_o_dia(sessao, dia, frequencias)
    assert pedido["destaque"] == VizinhosDoDestaque(anterior_e_destaque=True)
    # Os parâmetros não são de nenhuma variante da figura (eles têm o desenho).
    assert CHAVE_FIGURA not in pedido["parametros"]


@pytest.mark.asyncio
async def test_no_dia_de_outro_jogo_a_fila_do_destaque_NAO_e_lida() -> None:
    """Os outros jogos ficam exatamente como eram: nenhuma consulta a mais."""
    dia = next(d for d in UM_ANO if gerador_mod.escolher_jogo(d) == "pontinhos")
    sessao = FakeSessaoSQL()
    pedido = await _cobrir_o_dia(sessao, dia, None)
    assert pedido["destaque"] is None
    for sql in (
        SQL_TIPO_DO_DIA_ANTERIOR_DO_JOGO,
        SQL_TIPO_DO_DIA_SEGUINTE_DO_JOGO,
        SQL_VEZES_DO_TIPO_ANTES_DO_DIA,
    ):
        assert not sessao.sql_executado(sql)

"""A SEQUENCIA DE TIPOS do job (27/10/2026): ler, conferir e gerar na ordem.

O que estes casos protegem, em uma frase cada:

  · **a leitura**: a forma `tipo[filtro]@personagem`, com as virgulas de dentro
    dos colchetes, aspas e espacos tolerados;
  · **a conferencia**: tudo o que nao daria para gerar e recusado de uma vez,
    antes de gastar minutos de geracao;
  · **a execucao**: um pedido por dia livre, na ordem; o pedido que falha passa
    o dia ao seguinte, sem reprise; acabada a lista, o job para; e a fila nao e
    compactada.

⛔ **Nada aqui roda motor**: a geracao e a bancada sao os dubles de
`test_principal_do_job.py`, e o tipo de cada dia e o que o PEDIDO diz.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from job import __main__ as principal_mod
from job import sequencia_de_tipos as seq
from job.editorial import variantes_de
from job.repositorio import SQL_FILA_COM_CURADORIA
from job.tipos_de_desafio import RECEITAS
from tests.unitarios.test_principal_do_job import (
    BANDA_LARGA,
    _Bancada,
    _candidato,
    _sessao_feliz,
)

# ═══════════════════════════════════════════════════════════════════════════
# 1. A leitura
# ═══════════════════════════════════════════════════════════════════════════


def test_a_forma_completa_e_lida() -> None:
    pedidos = seq.ler_sequencia(
        "quatro_figura[figura=i_longo, folga=1]@tex, quatro_segurar_magno"
    )
    assert pedidos == [
        seq.PedidoDoDia(
            "quatro_figura", (("figura", "i_longo"), ("folga", "1")), "tex"
        ),
        seq.PedidoDoDia("quatro_segurar_magno"),
    ]


def test_a_virgula_de_DENTRO_dos_colchetes_nao_separa_itens() -> None:
    """🔒 Um `split(",")` simples quebraria o filtro de dois parametros."""
    assert len(seq.ler_sequencia("quatro_figura[figura=i,folga=2]")) == 1


def test_valor_sem_chave_e_aspas_como_o_dono_escreveu() -> None:
    """`figura["z"]` (a forma do pedido do dono) casa com a variante da figura z."""
    (pedido,) = seq.ler_sequencia('quatro_figura["z"]')
    assert pedido.filtro == ((None, "z"),)
    assert dict(seq.variante_do_pedido(pedido).parametros)["figura"] == "z"


def test_espacos_e_maiusculas_sao_tolerados() -> None:
    (pedido,) = seq.ler_sequencia("  Quatro_Vencer_Em_N [ lances = 7 ] @ Tex ")
    assert pedido == seq.PedidoDoDia("quatro_vencer_em_n", (("lances", "7"),), "tex")


@pytest.mark.parametrize("texto", ["", " , ", "quatro_figura[", "quatro figura"])
def test_texto_fora_da_forma_e_recusado(texto: str) -> None:
    with pytest.raises(seq.SequenciaInvalida):
        seq.ler_sequencia(texto)


def test_descrever_devolve_a_forma_escrita() -> None:
    texto = "quatro_figura[figura=z]@pita"
    (pedido,) = seq.ler_sequencia(texto)
    assert pedido.descrever() == texto


# ═══════════════════════════════════════════════════════════════════════════
# 2. A variante e a conferencia
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_filtro_vale_a_PRIMEIRA_variante() -> None:
    """⚠️ A primeira, e nao o odometro da data: quem testa quer saber o que sai."""
    pedido = seq.PedidoDoDia("quatro_figura")
    assert seq.variante_do_pedido(pedido) == variantes_de("quatro_figura")[0]


def test_o_filtro_escolhe_a_variante_que_CASA() -> None:
    pedido = seq.PedidoDoDia("quatro_figura", (("figura", "quadrado"), ("folga", "3")))
    assert dict(seq.variante_do_pedido(pedido).parametros) == {
        "figura": "quadrado",
        "folga": 3,
    }


def test_o_personagem_pula_a_variante_que_NAO_o_aceita() -> None:
    """A 1a `i_longo` aceita todos; a de folga 1 nao aceita a Cacau."""
    restrita = seq.PedidoDoDia("quatro_figura", (("folga", "1"), ("figura", "i_longo")), "cacau")
    with pytest.raises(seq.SequenciaInvalida):
        seq.variante_do_pedido(restrita)


def test_a_conferencia_recusa_TUDO_de_uma_vez() -> None:
    """🔒 Um erro no 4o item nao pode custar a geracao dos tres primeiros."""
    pedidos = seq.ler_sequencia(
        "quatro_figura[w], quatro_segurar_magno@cacau, quatro_bloquear, "
        "quatro_virada@zeca, pontinhos_cadeia_longa"
    )
    with pytest.raises(seq.SequenciaInvalida) as erro:
        seq.conferir(pedidos, co_jogo="quatro")
    texto = str(erro.value)
    assert "quatro_figura[w]" in texto  # variante que nao existe
    assert "quatro_segurar_magno@cacau" in texto  # personagem que o tipo recusa
    assert "quatro_bloquear" in texto  # tipo fora do ar
    assert "zeca" in texto  # personagem que nao existe
    assert "pontinhos_cadeia_longa" in texto  # outro jogo


def test_uma_sequencia_valida_passa() -> None:
    seq.conferir(seq.ler_sequencia("quatro_figura[z], quatro_virada@magno"))


def test_o_jogo_sozinho_da_UM_pedido_por_tipo_no_ar() -> None:
    pedidos = seq.pedidos_do_jogo("quatro")
    esperados = {
        tipo
        for tipo, receita in RECEITAS.items()
        if receita.co_jogo == "quatro"
    }
    assert [p.co_tipo for p in pedidos] == [
        t for t in RECEITAS if t in esperados
    ]
    assert len(pedidos) == len(set(p.co_tipo for p in pedidos))
    seq.conferir(pedidos, co_jogo="quatro")


def test_jogo_sem_tipo_no_ar_e_recusado() -> None:
    with pytest.raises(seq.SequenciaInvalida):
        seq.pedidos_do_jogo("xadrez")


# ═══════════════════════════════════════════════════════════════════════════
# 3. A execucao
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _plano_padrao(monkeypatch):
    """O plano de 7 dias (`DIAS_MINIMOS`), seja qual for a ordem da suite.

    ⚠️ `setenv` antes do `delenv`: so assim o `monkeypatch` registra o que
    desfazer, e uma variavel deixada por outro arquivo nao muda o plano daqui.
    """
    monkeypatch.setenv(principal_mod.ENV_DIAS_A_COBRIR, "")
    monkeypatch.delenv(principal_mod.ENV_DIAS_A_COBRIR)


#: Dois tipos do Pontinhos com mais de uma variante: o duble de candidato sabe
#: montar posicao de Pontinhos, e o que se prova aqui e a ORDEM e a escolha.
TIPO_A = "pontinhos_chegar_ao_placar"
TIPO_B = "pontinhos_cadeia_longa"


class _Gerador:
    """Uma geracao que obedece o pedido e anota o que recebeu.

    Args:
        falha: os tipos para os quais a geracao nao acha candidato.
    """

    def __init__(self, falha: tuple[str, ...] = ()) -> None:
        self.falha = falha
        self.chamadas: list[dict[str, Any]] = []

    def __call__(self, dt_dia: date, **kwargs: Any) -> list[Any]:
        self.chamadas.append({"dt_dia": dt_dia, **kwargs})
        co_tipo = kwargs["tipo_forcado"]
        if co_tipo in self.falha:
            return []
        return [_candidato(co_tipo, kwargs.get("parametros"))]


def _compactou(sessao: Any) -> bool:
    """A consulta da compactacao rodou? (O texto INTEIRO: as linhas dela se
    repetem em outras consultas do job.)"""
    alvo = " ".join(SQL_FILA_COM_CURADORIA.split())
    return any(" ".join(sql.split()) == alvo for sql, _ in sessao.executadas)


async def _rodar(sequencia: list[seq.PedidoDoDia], gerador: _Gerador):
    sessao = _sessao_feliz()
    relatorio = await principal_mod.executar(
        sessao,
        dt_hoje=date(2026, 9, 20),
        gerar=gerador,
        bancada_de=lambda _c: _Bancada(),
        alvo=BANDA_LARGA,
        nu_execucoes_da_regua=1,
        sequencia=sequencia,
    )
    return sessao, relatorio


@pytest.mark.asyncio
async def test_um_pedido_por_dia_livre_NA_ORDEM() -> None:
    pedidos = seq.ler_sequencia(f"{TIPO_B}, {TIPO_A}[caixas=5]@tex, {TIPO_B}")
    gerador = _Gerador()
    _, relatorio = await _rodar(pedidos, gerador)

    assert [c["tipo_forcado"] for c in gerador.chamadas] == [TIPO_B, TIPO_A, TIPO_B]
    # Dias seguidos, a partir de hoje (o plano inclui hoje).
    assert [c["dt_dia"] for c in gerador.chamadas] == [
        date(2026, 9, 20),
        date(2026, 9, 21),
        date(2026, 9, 22),
    ]
    # A variante do filtro e o personagem fixado chegaram ao gerador.
    assert dict(gerador.chamadas[1]["parametros"]) == {"caixas": 5}
    assert gerador.chamadas[1]["personagens_possiveis"] == ("tex",)
    assert relatorio.gerados == 3
    assert relatorio.sequencia_gerada == [
        f"2026-09-20: {TIPO_B}",
        f"2026-09-21: {TIPO_A}[caixas=5]@tex",
        f"2026-09-22: {TIPO_B}",
    ]
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_FEZ


@pytest.mark.asyncio
async def test_acabada_a_lista_o_job_PARA_de_gerar() -> None:
    """⚠️ O plano tem 7 dias livres; com 2 pedidos, so 2 dias sao gerados."""
    gerador = _Gerador()
    _, relatorio = await _rodar(seq.ler_sequencia(f"{TIPO_A}, {TIPO_B}"), gerador)
    assert len(gerador.chamadas) == 2
    assert not relatorio.nao_cobertos


@pytest.mark.asyncio
async def test_o_pedido_que_FALHA_passa_o_dia_ao_seguinte_SEM_reprise(
    monkeypatch,
) -> None:
    # ⚠️ Uma reprise que SEMPRE da certo: no duble de banco a de verdade falha
    # sozinha, e o caso nao separaria "nao tentou" de "tentou e nao deu".
    reprises: list[date] = []

    async def reprise_que_funciona(_sessao: Any, *, dt_dia: date) -> None:
        reprises.append(dt_dia)

    monkeypatch.setattr(
        principal_mod.reprise_mod, "publicar_reprise", reprise_que_funciona
    )
    gerador = _Gerador(falha=(TIPO_B,))
    _, relatorio = await _rodar(seq.ler_sequencia(f"{TIPO_B}, {TIPO_A}"), gerador)
    assert reprises == []

    # Os dois tentaram o MESMO dia, e o segundo ficou com ele.
    assert [c["dt_dia"] for c in gerador.chamadas] == [date(2026, 9, 20)] * 2
    assert relatorio.sequencia_gerada == [f"2026-09-20: {TIPO_A}"]
    assert relatorio.sequencia_falhou and TIPO_B in relatorio.sequencia_falhou[0]
    # ⛔ Nada de reprise no lugar do pedido.
    assert relatorio.reprisados == 0
    # Quem pediu aquele tipo precisa saber que ele nao veio.
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_DIVERGIU


@pytest.mark.asyncio
async def test_pedidos_que_NAO_cabem_no_plano_sao_avisados() -> None:
    """O plano padrao tem 7 dias; o 8o e o 9o pedidos sobram."""
    pedidos = [seq.PedidoDoDia(TIPO_A)] * 9
    gerador = _Gerador()
    _, relatorio = await _rodar(pedidos, gerador)
    assert len(gerador.chamadas) == 7
    assert relatorio.sequencia_sobrou == [TIPO_A, TIPO_A]
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_DIVERGIU


@pytest.mark.asyncio
async def test_com_sequencia_a_fila_NAO_e_compactada() -> None:
    """⚠️ A compactacao puxaria desafios de depois para os dias livres, e a
    sequencia iria parar mais longe do que quem a pediu espera."""
    sessao, _ = await _rodar(seq.ler_sequencia(TIPO_A), _Gerador())
    assert not _compactou(sessao)


@pytest.mark.asyncio
async def test_sem_sequencia_a_fila_continua_compactada() -> None:
    """O controle do caso acima: sem a sequencia, a consulta da compactacao roda."""
    from tests.unitarios.test_principal_do_job import _gerar_um

    sessao = _sessao_feliz()
    await principal_mod.executar(
        sessao,
        dt_hoje=date(2026, 9, 20),
        gerar=_gerar_um,
        bancada_de=lambda _c: _Bancada(),
        alvo=BANDA_LARGA,
        nu_execucoes_da_regua=1,
    )
    assert _compactou(sessao)

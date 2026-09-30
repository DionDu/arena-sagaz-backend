"""🔒 O ACERVO POR VARIANTE — a lista de moldes que chega a geracao.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

Ate 30/09/2026 o acervo de moldes era da RECEITA, e servia a toda variante do
tipo. A maratona do gerador mostrou o caso em que isso nao fecha: no
`damas_capturar_multipla`, na faixa de 9 a 20 meios-lances, havia **237** moldes
para capturar duas pecas e **2** para capturar tres. O dono escolheu separar o
acervo por variante (`Publicacao.moldes`, `None` = o da receita).

⛔ **O defeito que este arquivo guarda e o acervo que existe e ninguem usa.** Um
campo novo no editorial que o job, o gerador ou o medidor esquecesse de repassar
compilaria, passaria nos cadeados de moldes (que leem o editorial) e publicaria
com o acervo antigo - calado. Foi exatamente assim que o piso de 16/09 quase
entrou: o botao existia e ninguem o ligava (`test_o_JOB_passa_o_piso_da_publicacao`).

Por isso os casos aqui perguntam pelo CAMINHO: o argumento chega ao
`_preparar_damas`, o job o repassa, o medidor o repassa.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from job import gerador as gerador_mod
from job.editorial import variantes_de
from job.tipos_de_desafio import receita_de


class _Parou(Exception):
    """Interrompe a geracao no primeiro sorteio de molde - o resto nao importa."""


def _um_dia_de_damas() -> date:
    """O primeiro dia, a partir de 20/09/2026, em que o rodizio escolhe damas.

    ⚠️ `gerar_candidatos` escolhe o jogo PELA DATA, e o acervo so e lido no ramo
    das damas. Um dia de Pontinhos faria o caso passar sem nunca tocar no acervo.
    """
    dia = date(2026, 9, 20)
    while gerador_mod.escolher_jogo(dia) != "damas":
        dia += timedelta(days=1)
    return dia


def _moldes_que_chegam(monkeypatch, **kwargs) -> tuple[tuple[str, ...], str]:
    """Chama a geracao de verdade: devolve a lista que chegou ao `_preparar_damas`
    e o tipo que o rodizio escolheu naquele dia.

    ⚠️ **O `_preparar_damas` e trocado por um espiao que para a geracao** logo no
    primeiro sorteio: o que se quer saber e QUAL lista foi sorteada, e nao se o
    resto do laco (busca, gabarito, regua) funciona - isso tem os testes dele.
    """
    dia = _um_dia_de_damas()
    co_tipo = gerador_mod.escolher_tipo("damas", dia)
    vistas: list[tuple[str, ...]] = []

    def espiao(_sorteio, _preparo, *, moldes=(), co_modalidade="brasileira"):
        vistas.append(tuple(moldes))
        raise _Parou

    monkeypatch.setattr(gerador_mod, "_preparar_damas", espiao)
    with pytest.raises(_Parou):
        gerador_mod.gerar_candidatos(
            dia, parametros=variantes_de(co_tipo)[0].parametros, **kwargs
        )
    return vistas[0], co_tipo


def test_sem_acervo_da_variante_a_geracao_usa_o_da_RECEITA(monkeypatch) -> None:
    """🔒 `None` e o caminho normal, e nada muda para quem nao declarou acervo."""
    chegou, co_tipo = _moldes_que_chegam(monkeypatch)
    assert chegou == tuple(receita_de(co_tipo).moldes)


def test_o_acervo_da_VARIANTE_substitui_o_da_receita(monkeypatch) -> None:
    """🔒 O acervo declarado chega INTEIRO, e sozinho - sem misturar com a receita."""
    proprio = ("W:W21,22,23:B9,10,11",)
    chegou, _ = _moldes_que_chegam(monkeypatch, moldes=proprio)
    assert chegou == proprio


def test_acervo_da_variante_VAZIO_recusa_alto(monkeypatch) -> None:
    """🔒 ⛔ A lista vazia nao pode virar "parta da posicao inicial" calada.

    ⚠️ `_preparar_damas` trata lista vazia como o caminho de um tipo sem acervo,
    e partiria do tabuleiro inicial - o desafio sairia de uma posicao que ninguem
    escolheu, sem erro nenhum. O gerador recusa antes.
    """
    dia = _um_dia_de_damas()
    co_tipo = gerador_mod.escolher_tipo("damas", dia)
    with pytest.raises(ValueError, match="VAZIO"):
        gerador_mod.gerar_candidatos(
            dia, parametros=variantes_de(co_tipo)[0].parametros, moldes=()
        )


def test_o_padrao_do_argumento_e_None() -> None:
    """🔒 `None`, e nao `()`: a tupla vazia e o engano que o caso acima recusa."""
    assinatura = inspect.signature(gerador_mod.gerar_candidatos)
    assert assinatura.parameters["moldes"].default is None


def test_o_JOB_passa_o_acervo_da_publicacao() -> None:
    """🔒 O campo que existe e o job nao repassa nao serve para nada.

    ⚠️ O espiao em `test_principal_do_job.py` prova o mesmo pelo comportamento;
    este le a fonte, e e o que acusa primeiro se alguem apagar a linha.
    """
    fonte = Path("job/__main__.py").read_text(encoding="utf-8")
    assert "moldes=publicacao.moldes" in fonte


# ═══════════════════════════════════════════════════════════════════════════
# O MEDIDOR - medir com o acervo errado descreve uma execucao que nao existe
# ═══════════════════════════════════════════════════════════════════════════


def _carregar_o_medidor():
    """Carrega o script solto (`scripts/` nao e pacote) pelo caminho do arquivo."""
    caminho = Path("scripts/medir_variantes_do_editorial.py")
    spec = importlib.util.spec_from_file_location("medir_variantes_acervo", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # ⚠️ Registrado antes de executar: o `@dataclass` do script procura o proprio
    # modulo em `sys.modules`, e sem isto estoura ao montar a classe.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


MEDIDOR = _carregar_o_medidor()


def test_as_candidatas_do_editorial_levam_o_ACERVO_de_cada_variante() -> None:
    """🔒 O alvo `no-ar` mede cada variante com o acervo que o job usa."""
    for candidata, publicacao in zip(
        MEDIDOR.candidatas_do_editorial("damas_capturar_multipla"),
        variantes_de("damas_capturar_multipla"),
        strict=True,
    ):
        assert candidata.moldes == publicacao.moldes


def test_o_MEDIDOR_entrega_a_cada_variante_o_acervo_DELA(monkeypatch) -> None:
    """🔒 Cada variante chega a `gerar_candidatos` com o acervo que o job usa.

    ⛔ **Este caso substitui um que lia a fonte, e que travava o defeito.** Ele
    conferia a linha `if getattr(candidata, "moldes", None) is None`, que caia no
    acervo da VARIANTE 0 quando a candidata nao declarava o seu. No
    `damas_capturar_multipla` a variante 0 e a de duas pecas, com acervo proprio:
    em 30/09/2026 a de TRES pecas foi medida com os moldes da de duas, e o mesmo
    FEN apareceu nas duas variantes no mesmo dia. O caso de fonte passava.

    Agora a geracao e trocada por um espiao que anota o acervo e devolve nenhum
    candidato (o medidor segue, e a linha sai SEM DESAFIO - o que nao importa).

    ⚠️ **As candidatas sao escritas aqui, e nao lidas do editorial:** a de tres
    pecas foi aposentada no mesmo dia, e o tipo ficou com uma variante so. O
    defeito precisa das duas formas no MESMO tipo, com a variante 0 carregando
    acervo proprio: uma candidata sem acervo (tem de chegar `None`) e uma com
    outro acervo (tem de chegar o dela, e nao o da variante 0).
    """
    # ⚠️ O tipo tem de ser um cuja variante 0 TEM acervo proprio - senao herdar
    # da variante 0 daria `None` por coincidencia, e o caso passaria com o defeito.
    co_tipo = "damas_capturar_multipla"
    assert variantes_de(co_tipo)[0].moldes is not None
    outro_acervo = ("W:W21,22,23:B9,10,11",)
    candidatas = (
        MEDIDOR.Candidata({"pecas": 2, "lances": 8}),
        MEDIDOR.Candidata({"pecas": 2, "lances": 8}, moldes=outro_acervo),
    )
    vistos: list[tuple[str, ...] | None] = []

    def espiao(_dia, *, moldes=None, **_resto):
        vistos.append(moldes)
        return []

    monkeypatch.setattr(MEDIDOR.gerador_mod, "gerar_candidatos", espiao)
    MEDIDOR.medir(co_tipo, candidatas)

    # As candidatas sao medidas em ordem, um dia de cada vez: primeiro todos os
    # dias da candidata sem acervo, depois todos os da que tem.
    dias = len(vistos) // 2
    assert dias > 0, "o medidor nao chamou a geracao nenhuma vez"
    assert vistos == [None] * dias + [outro_acervo] * dias


def test_o_alvo_no_ar_de_UM_tipo_mede_o_editorial_dele() -> None:
    """🔒 `no-ar:<tipo>` existe para remedir UMA variante sem pagar a rodada inteira."""
    assert MEDIDOR.tipos_do_alvo("no-ar:damas_capturar_multipla") == [
        "damas_capturar_multipla"
    ]
    assert MEDIDOR.e_alvo_no_ar("no-ar:damas_capturar_multipla")


def test_o_alvo_no_ar_de_um_tipo_INEXISTENTE_nao_mede_nada() -> None:
    """🔒 Nome digitado errado sai com a lista vazia (e o script, com codigo 2)."""
    assert MEDIDOR.tipos_do_alvo("no-ar:damas_coroar_errado") == []


def test_o_nome_do_tipo_SEM_prefixo_continua_sendo_a_tabela_de_estudo() -> None:
    """🔒 O alvo antigo nao mudou de sentido: ele le `A_MEDIR`, e nao o editorial."""
    assert not MEDIDOR.e_alvo_no_ar("damas_capturar_multipla")

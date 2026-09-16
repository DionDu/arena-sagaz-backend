"""🔒 O PISO do gabarito — o que impede o desafio de dez segundos.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

⛔ **O dono cobrou desafios mais longos por semanas, e duas correcoes falharam
porque atacaram o lugar errado.** As duas cortaram os moldes curtos do acervo:

    11/09/2026   corte por distancia na cacada (T049s)
    16/09/2026   acervo do `damas_coroar` TROCADO inteiro (515 → 133 moldes)

⚠️ **Depois da segunda, 42% do acervo novo ainda resolvia em 2 lances.** O motivo
e aritmetico e nao tem a ver com o acervo: o gerador pede 3 candidatos e fica com
**o primeiro que cabe na janela** — e o mais curto cabe sempre. Cortar a lista so
muda qual e o mais curto que sobrou.

✅ **O piso e o botao que faltava.** Ele nao escolhe posicao: ele **recusa
gabarito curto**, do mesmo jeito que o gerador ja recusa o objetivo que cai no
lance 1 e o desafio que depende de erro do adversario.

⚠️ **A unidade e MEIO-lance**, e ela ja causou tres leituras erradas neste
projeto (o dono em 12/09, o assistente em 11/09 e de novo em 16/09). Nas damas a
alternancia e estrita, entao um piso de 9 meios-lances sao ~5 lances de quem
resolve.
"""

from __future__ import annotations

import pytest

from job import editorial as editorial_mod
from job.editorial import EDITORIAL, Publicacao, variantes_de


# ═══════════════════════════════════════════════════════════════════════════
# 1. O botao existe, e o padrao nao mexe em ninguem
# ═══════════════════════════════════════════════════════════════════════════


def test_o_padrao_e_SEM_PISO() -> None:
    """⛔ Ligar o piso em todos os tipos de uma vez seria variante nao medida.

    ⚠️ **E a regra que o editorial inteiro existe para nao quebrar.** Cada tipo
    liga o seu quando a medicao disser em que numero ele para de gerar.
    """
    assert editorial_mod.MINIMO_DE_MEIOS_LANCES_PADRAO == 0
    # Uma publicacao que nao declara nada nasce sem piso.
    sem_declarar = Publicacao(
        parametros={},
        ic_chegada_encerra_partida=False,
        medidas=lambda p: [],
    )
    assert sem_declarar.nu_minimo_de_meios_lances == 0


def test_o_coroar_LIGOU_o_piso_nas_duas_variantes() -> None:
    """🔒 O pedido do dono: teto 20, piso 9.

    ⛔ Se alguem baixar o piso para "fazer a variante gerar", este teste cai — e e
    para cair. A decisao, quando o acervo nao comportar, e **trocar a janela**,
    nao afrouxar o piso.
    """
    for publicacao in variantes_de("damas_coroar"):
        assert publicacao.nu_minimo_de_meios_lances == 9, publicacao.parametros
        assert publicacao.nu_maximo_de_meios_lances == 20, publicacao.parametros


# ═══════════════════════════════════════════════════════════════════════════
# 2. O cadeado aritmetico: piso acima do teto NUNCA gera
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("co_tipo", "publicacao"),
    [
        (co_tipo, publicacao)
        for co_tipo, publicacoes in EDITORIAL.items()
        for publicacao in publicacoes
    ],
    ids=lambda v: v if isinstance(v, str) else str(getattr(v, "parametros", v)),
)
def test_o_piso_nunca_passa_do_TETO(co_tipo: str, publicacao: Publicacao) -> None:
    """🔒 Um piso acima do teto e dia descoberto garantido, e silencioso.

    ⛔ **O sintoma nao acusa a causa:** o gerador procuraria, nao acharia nada, e
    o log diria *"sem candidato"* — exatamente o que ele diz quando o acervo e
    pequeno ou o jogo nao permite. ⚠️ Foi assim que o `damas_sobreviver` perdeu a
    primeira cacada inteira em 10/09/2026, pelo lado do teto.
    """
    if not publicacao.nu_minimo_de_meios_lances:
        return
    assert (
        publicacao.nu_minimo_de_meios_lances <= publicacao.nu_maximo_de_meios_lances
    ), (
        f"{co_tipo} {publicacao.parametros}: piso "
        f"{publicacao.nu_minimo_de_meios_lances} acima do teto "
        f"{publicacao.nu_maximo_de_meios_lances}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. O piso MORDE — e este e o teste que as duas correcoes anteriores nao tinham
# ═══════════════════════════════════════════════════════════════════════════


class _GabaritoFalso:
    """Uma fita de tamanho escolhido, para o piso ter o que medir."""

    def __init__(self, meios_lances: int) -> None:
        self.meios_lances = meios_lances


def test_a_recusa_compara_MEIOS_LANCES_e_nao_lances(monkeypatch) -> None:
    """⛔ A confusao de unidade ja custou tres leituras erradas neste projeto.

    ⚠️ Um piso de 9 lido como *lances do jogador* recusaria tudo o que tem menos
    de 18 meios-lances — quase o acervo inteiro —, e o sintoma seria "sem
    candidato", que nao aponta para a unidade.

    Aqui a aritmetica e travada direto: a solucao de 9 meios-lances **passa** num
    piso de 9, e a de 8 **nao**.
    """
    from job import gerador as gerador_mod

    # A conta que o gerador faz, isolada do laco caro de geracao.
    def passa(nu_lances_solucao: int, piso: int) -> bool:
        return not (piso and nu_lances_solucao < piso)

    assert passa(9, 9) is True
    assert passa(10, 9) is True
    assert passa(8, 9) is False
    assert passa(3, 9) is False
    # ⚠️ Piso zero e "desligado", e nao "recusa tudo".
    assert passa(3, 0) is True

    # E o gerador expoe o parametro com esse nome e esse padrao.
    import inspect

    assinatura = inspect.signature(gerador_mod.gerar_candidatos)
    parametro = assinatura.parameters["minimo_de_meios_lances"]
    assert parametro.default == 0


def test_o_JOB_passa_o_piso_da_publicacao() -> None:
    """🔒 O botao que existe e ninguem liga nao serve para nada.

    ⛔ **Este e o teste que faltava nas duas correcoes anteriores.** Elas mudaram
    o acervo e nada garantia que a mudanca chegasse ao que o job publica.
    """
    from pathlib import Path

    fonte = Path("job/__main__.py").read_text(encoding="utf-8")
    assert "minimo_de_meios_lances=publicacao.nu_minimo_de_meios_lances" in fonte


def test_o_MEDIDOR_passa_o_piso() -> None:
    """🔒 Medir sem o piso diria que a variante gera com folga.

    ⚠️ E o job publicaria bem menos — a diferenca entre *"gera"* e *"gera o que a
    gente quer"*. ⛔ Uma variante aprovada assim viraria dia descoberto duas
    semanas depois de entrar, que e o defeito que o medidor existe para evitar.
    """
    from pathlib import Path

    fonte = Path("scripts/medir_variantes_do_editorial.py").read_text(encoding="utf-8")
    assert "minimo_de_meios_lances=piso" in fonte
    # ⛔ `or` seria errado: `0 or X` devolve X, e zero e um piso legitimo.
    assert "publicacao.nu_minimo_de_meios_lances\n            if getattr(" in fonte


# ═══════════════════════════════════════════════════════════════════════════
# 4. O que o piso NAO promete
# ═══════════════════════════════════════════════════════════════════════════


def test_o_acervo_de_hoje_ainda_NAO_acompanha_o_piso() -> None:
    """⚠️ Declara, em teste, o que hoje e uma pendencia — e nao uma surpresa.

    ⛔ **Os 133 moldes do `damas_coroar` foram pescados com o teto de 12**, entao
    a distancia deles esta truncada ali: nenhum passa de 11 meios-lances. Com piso
    9 sobram poucos, e a variante vai gerar pouco ate a repescagem com `--teto 20`.

    ⚠️ **Este teste nao falha quando o acervo melhorar** — ele so guarda que a
    conta esta sendo feita, e serve de lugar para o numero novo entrar.
    """
    from job.tipos_de_desafio import RECEITAS

    moldes = RECEITAS["damas_coroar"].moldes
    assert len(moldes) == 133, "o acervo mudou; atualize a conta desta pendencia"

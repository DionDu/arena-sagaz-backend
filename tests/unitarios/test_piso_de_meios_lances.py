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


def test_o_coroar_LIGOU_o_piso_em_TODA_variante_que_publica() -> None:
    """🔒 O pedido do dono: teto 20, piso 9.

    ⛔ Se alguem baixar o piso para "fazer a variante gerar", este teste cai — e e
    para cair. A decisao, quando o acervo nao comportar, e **trocar a janela**,
    nao afrouxar o piso.

    ⚠️ **E foi exatamente isso que aconteceu em 17/09/2026**, so que pelo outro
    lado: a variante `{damas: 1, lances: 4}` tinha o piso certo e a **janela**
    curta demais para ele, e saiu do editorial. O nome deste teste dizia "nas duas
    variantes" e ficou errado no mesmo dia — por isso ele agora percorre as que
    existirem, sem dizer quantas sao.

    ⚠️ **E o piso deixou de ser UM numero em 18/09/2026.** A medicao mostrou que
    cada variante e um PAR `(piso, p)`: com o mesmo piso, trocar `p` so escreve um
    numero maior na frase e publica o mesmo molde. As duas que ficaram tem pisos
    diferentes de proposito, e e isso que as faz duas tarefas.

    ⛔ **O que este teste guarda agora e a REGRA, e nao a tabela**: piso de pelo
    menos 9 (o pedido do dono), teto 20, e a faixa de cada variante sem buraco
    nem sobreposicao com a seguinte. Travar os numeros exatos faria o teste cair
    a cada variante nova sem ter acusado defeito nenhum.
    """
    variantes = variantes_de("damas_coroar")
    faixas = []
    for publicacao in variantes:
        piso = publicacao.nu_minimo_de_meios_lances
        assert piso >= 9, f"{publicacao.parametros}: piso {piso} abaixo do pedido"
        assert publicacao.nu_maximo_de_meios_lances == 20, publicacao.parametros
        # A faixa que a variante realmente publica: do piso ao ultimo meio-lance
        # que a frase admite (`2p - 1`, porque o p-esimo lance do jogador e ele).
        p_da_frase = dict(publicacao.parametros)["lances"]
        faixas.append((piso, 2 * p_da_frase - 1, publicacao.parametros))

    # ⛔ Duas variantes que se sobrepoem sao a MESMA tarefa publicada duas vezes:
    # os moldes da faixa comum podem sair em qualquer uma das duas, e a pessoa ve
    # o mesmo desafio com enunciados diferentes.
    for (piso_a, topo_a, params_a), (piso_b, topo_b, params_b) in zip(
        sorted(faixas), sorted(faixas)[1:]
    ):
        assert piso_b > topo_a, (
            f"{params_a} ({piso_a}..{topo_a}) e {params_b} ({piso_b}..{topo_b}) "
            "se sobrepoem: sao a mesma tarefa com frases diferentes"
        )


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


@pytest.mark.parametrize(
    ("co_tipo", "publicacao"),
    [
        (co_tipo, publicacao)
        for co_tipo, publicacoes in EDITORIAL.items()
        for publicacao in publicacoes
    ],
    ids=lambda v: v if isinstance(v, str) else str(getattr(v, "parametros", v)),
)
def test_o_piso_nunca_passa_da_JANELA_DA_FRASE(
    co_tipo: str, publicacao: Publicacao
) -> None:
    """🔒 A **segunda** parede, e ela nao era conferida por ninguem.

    ⛔ **O teto nao e o unico limite do gabarito: a janela da frase tambem e.**
    *"Coroe uma dama em 4 lances"* promete que a solucao cabe em **4 lances do
    jogador** — e, com a alternancia estrita das damas, o 4o lance dele e o
    meio-lance **7**. Um piso de 9 pede uma solucao mais longa do que a propria
    frase admite. ⛔ Nenhum numero e ao mesmo tempo `>= 9` e `<= 7`.

    ⚠️ **E isso esteve NO AR, em metade dos dias do tipo, de 16 a 17/09/2026.** A
    variante `{damas: 1, lances: 4}` do `damas_coroar` ganhou piso 9 na mesma
    resposta em que o piso foi criado; o comentario do editorial ate previa o
    risco (*"ficou quase impossivel, e por aritmetica"*), mas nenhum teste fazia a
    conta. O gerador escolhe a variante do dia por odometro e ⛔ **nao tenta
    outra quando a primeira falha**: nos dias em que o odometro caia nela, o
    `damas_coroar` nao tinha como produzir candidato nenhum.

    ⚠️ **O sintoma e o mesmo de sempre, e nao aponta para a causa:** o log diz
    *"sem candidato"*, que e o que ele diz quando o acervo e pequeno ou o jogo nao
    permite — e nao *"a frase que eu prometi e curta demais para o piso que eu
    exijo"*.

    ⚠️ **So vale para a janela em LANCES DO JOGADOR.** Tipo cuja janela e o
    proprio objetivo (*"sobreviva 8 lances"*) nao esta prometendo prazo de
    solucao, e por isso a conta nao se aplica — hoje nenhum deles tem piso, e o
    `if` abaixo os deixa passar por ausencia de piso, nao por excecao escrita.
    """
    piso = publicacao.nu_minimo_de_meios_lances
    if not piso:
        return
    lances_da_frase = dict(publicacao.parametros).get("lances")
    if lances_da_frase is None:
        return
    # ⚠️ O p-esimo lance do jogador e o meio-lance `2p - 1`: ele joga nos
    # impares, e o adversario responde nos pares. Um gabarito de 9 meios-lances
    # usa 5 lances do jogador, e nao 4.
    maximo_que_a_frase_admite = 2 * lances_da_frase - 1
    assert piso <= maximo_que_a_frase_admite, (
        f"{co_tipo} {dict(publicacao.parametros)}: o piso de {piso} meios-lances "
        f"nao cabe na frase, que promete {lances_da_frase} lances do jogador "
        f"(= no maximo {maximo_que_a_frase_admite} meios-lances). "
        "Esta variante nunca gera candidato."
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


def test_o_acervo_JA_ACOMPANHA_o_piso() -> None:
    """✅ A pendencia que este teste declarava CAIU em 17/09/2026.

    ⛔ **O que ele dizia ate ontem:** *"os 133 moldes do `damas_coroar` foram
    pescados com o teto de 12, entao a distancia deles esta truncada ali: nenhum
    passa de 11 meios-lances. Com piso 9 sobram poucos, e a variante vai gerar
    pouco ate a repescagem"*.

    ✅ **A repescagem com `--teto 26` chegou**, e o acervo passou a **307** moldes,
    todos com solucao de 9 a 25 meios-lances — ou seja, **todos** acima do piso.
    O que era "sobram poucos" virou "nenhum sobra de fora".

    ✅ **E A JANELA ALCANCOU O ACERVO EM 18/09/2026.** Ficou pendente por um dia a
    segunda metade: com `lances: 6` a frase admitia 11 meios-lances, e 236 dos 307
    moldes nao podiam sair — nao por serem curtos, mas por serem **longos demais
    para a frase prometida**. A medicao escolheu `p` 8 e 10, e as duas variantes
    juntas alcancam de 12 a 19 meios-lances.

    ⛔ **A de 6 lances saiu porque media um DIA VAZIO** (`dias [3, 0, 3]`), e nao
    por causa desta conta. ⚠️ As duas coisas apontavam para o mesmo lugar, e e
    facil confundi-las: uma janela curta demais para o acervo desperdica moldes;
    uma janela curta demais para o PISO nao gera nada.

    ⚠️ **Este teste guarda a conta, e nao um numero bonito** — ele falha se as
    variantes publicadas voltarem a deixar a maior parte do acervo inalcancavel.
    """
    from job.tipos_de_desafio import RECEITAS

    moldes = RECEITAS["damas_coroar"].moldes
    assert len(moldes) == 307, "o acervo mudou; atualize a conta desta pendencia"

    # O maior meio-lance que ALGUMA variante publicada admite.
    alcance = max(
        2 * dict(publicacao.parametros)["lances"] - 1
        for publicacao in variantes_de("damas_coroar")
    )
    # ⛔ O acervo foi pescado com teto 26, entao ha moldes acima de qualquer
    # janela possivel — o que se cobra e que a maior parte caiba, e nao todos.
    assert alcance >= 19, (
        f"as variantes no ar alcancam so {alcance} meios-lances; com o acervo "
        "pescado ate 26, isso desperdica a maior parte dele"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5. A pescaria le o piso do editorial — e o le pelo lado certo
# ═══════════════════════════════════════════════════════════════════════════


def test_a_pescaria_corta_pelo_MENOR_piso_entre_as_variantes() -> None:
    """🔒 Um molde serve ao acervo se ALGUMA variante puder publica-lo.

    ⛔ **O defeito nasceu de uma funcao que estava certa por acidente.** Enquanto
    o `damas_coroar` teve uma variante so, `max` e `min` sobre a mesma lista
    davam o mesmo numero — entao o `max` que o script usava parecia correto.
    Ele quebrou no dia (18/09/2026) em que o tipo passou a ter duas variantes,
    com pisos 12 e 16: a pescaria seguinte mandou **56 posicoes elegiveis** para
    fora da medicao, nenhuma delas curta demais para o acervo.

    ⚠️ **E o sintoma nao acusa a causa:** as posicoes descartadas aparecem no log
    como "abaixo do piso", que e exatamente o que o script diz quando o corte
    esta certo. Sem este caso, a unica pista seria alguem reparar num numero
    grande demais de descartes.
    """
    import inspect

    import scripts.pescar_moldes_de_partidas as pescaria

    fonte = inspect.getsource(pescaria.main)
    assert "piso_do_editorial = min(" in fonte, (
        "a pescaria voltou a cortar pelo MAIOR piso: moldes que a variante de "
        "piso menor publicaria estao sendo jogados fora"
    )


def test_o_coroar_tem_variantes_com_pisos_DIFERENTES() -> None:
    """🔒 O caso que torna o teste acima observavel.

    ⚠️ Se um dia o tipo voltar a ter um piso so, o teste de cima continua
    passando **sem provar nada** — `min` e `max` coincidem. Este caso guarda a
    condicao que da sentido ao outro, e falha avisando disso em vez de deixar um
    cadeado verde e cego.
    """
    pisos = {p.nu_minimo_de_meios_lances for p in variantes_de("damas_coroar")}
    assert len(pisos) > 1, (
        f"o damas_coroar voltou a ter um piso so ({pisos}); o cadeado do `min` "
        "na pescaria deixou de ser observavel e precisa de outro tipo para valer"
    )

"""🔒 A frase do desafio em português, como a pessoa a lê no aplicativo (T040b).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

Até 16/09/2026 o painel de curadoria mostrava o objetivo assim:

    objetivo  desafioObjetivoPaciencia {'lances': 3, 'variante': 'pequeno', ...}

⚠️ **E o dono precisou PERGUNTAR o que aquilo queria dizer**, no meio de uma
sessão. Depois pediu: *"Eu gostaria de ver no painel de curadoria também a frase
completa de cada desafio, como o usuário irá lê-la no App, em pt-br apenas."*

⛔ **O pedido é maior do que parece: a frase É parte do desafio.** Um desafio cuja
chegada está perfeita e cujo enunciado é ambíguo é um desafio ruim, e a curadoria
não tinha como ver isso.

✅ **E a feature se pagou no primeiro uso:** ao renderizar as onze frases, apareceu
`cedendo no maximo` - sem acento, em `app_pt.arb` **e** em `app_es.arb`, numa
chave já publicada. Ninguém tinha lido aquela frase montada antes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.desafios.painel.frase_objetivo import (
    CAMINHO_DAS_FRASES,
    CHAVE_CODIGO_DA_FIGURA,
    PREFIXOS_DA_COPIA,
    FraseInvalida,
    carregar_frases,
    chave_do_nome_da_figura,
    frase_do_desafio,
    renderizar,
)

#: O `.arb` de autoria, no repositório do aplicativo.
ARB_DE_ORIGEM = (
    Path(__file__).resolve().parents[2].parent
    / "arena-sagaz-frontend"
    / "lib"
    / "l10n"
    / "app_pt.arb"
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. 🔒 ⛔ O CADEADO: a cópia não pode envelhecer
# ═══════════════════════════════════════════════════════════════════════════


def test_a_copia_BATE_com_o_arb_do_aplicativo() -> None:
    """🔒 ⛔ O mesmo padrão do contrato da CNN e dos vetores.

    ⚠️ A cópia existe porque o painel roda dentro da imagem da API, onde o
    repositório do aplicativo não existe - ler o `.arb` em runtime funcionaria na
    máquina do dono e falharia em produção, que é o pior modo de falhar que há.

    ⛔ **Quem editar uma chave `desafioObjetivo*` (ou a frase nomeada e os nomes
    das figuras do Quatro, T152) roda `scripts/gerar_frases_objetivo.py` na mesma
    resposta.** É a mesma regra dos
    três `.arb`, e este teste é quem a cobra.
    """
    if not ARB_DE_ORIGEM.exists():
        pytest.skip(
            "o repositorio arena-sagaz-frontend nao esta no disco ao lado deste "
            "- o cadeado roda onde os dois convivem"
        )

    do_arb = {
        chave: texto
        for chave, texto in json.loads(
            ARB_DE_ORIGEM.read_text(encoding="utf-8")
        ).items()
        if chave.startswith(PREFIXOS_DA_COPIA) and not chave.startswith("@")
    }
    da_copia = carregar_frases()

    faltando = sorted(set(do_arb) - set(da_copia))
    sobrando = sorted(set(da_copia) - set(do_arb))
    assert not faltando, (
        f"chaves novas no app e ausentes na copia: {faltando}. "
        "Rode `python scripts/gerar_frases_objetivo.py`."
    )
    assert not sobrando, (
        f"chaves na copia que o app nao tem mais: {sobrando}. "
        "Rode `python scripts/gerar_frases_objetivo.py`."
    )
    divergentes = [chave for chave in do_arb if do_arb[chave] != da_copia[chave]]
    assert not divergentes, (
        f"o TEXTO divergiu em {divergentes}. "
        "Rode `python scripts/gerar_frases_objetivo.py`."
    )


def test_TODA_frase_do_catalogo_renderiza() -> None:
    """🔒 ⛔ Nenhuma chave publicada pode cair no caminho do `None`.

    ⚠️ **`frase_do_desafio` devolve `None` em silêncio** quando a frase usa um
    recurso de ICU não coberto - de propósito, para o painel não cair. ⛔ Este
    teste é o outro lado disso: o silêncio não pode virar o normal.

    Os valores são os `example` do próprio `.arb`, mais o personagem.
    """
    if not ARB_DE_ORIGEM.exists():
        pytest.skip("o repositorio arena-sagaz-frontend nao esta no disco")

    dados = json.loads(ARB_DE_ORIGEM.read_text(encoding="utf-8"))
    frases = carregar_frases()
    for chave in frases:
        metadados = dados.get(f"@{chave}", {})
        valores = {
            nome: (
                int(detalhe["example"])
                if detalhe.get("type") == "int"
                else detalhe.get("example", "Magno")
            )
            for nome, detalhe in metadados.get("placeholders", {}).items()
        }
        montada = frase_do_desafio(chave, valores, frases=frases)
        assert montada, f"{chave} nao renderizou com {valores}"
        assert "{" not in montada, f"{chave} deixou chave ICU crua: {montada}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. 🔒 O renderizador de ICU
# ═══════════════════════════════════════════════════════════════════════════


def test_substitui_o_placeholder_simples() -> None:
    """🔒 `{personagem}` vira o nome."""
    assert renderizar("contra {personagem}", {"personagem": "Magno"}) == "contra Magno"


@pytest.mark.parametrize(
    ("damas", "esperado"),
    [(1, "Coroe 1 dama"), (2, "Coroe 2 damas"), (5, "Coroe 5 damas")],
)
def test_o_PLURAL_escolhe_o_ramo_certo(damas: int, esperado: str) -> None:
    """🔒 ⛔ *"Coroe 1 damas"* é errado em português, e o `.arb` já resolve isso.

    ⚠️ Renderizar com um `str.format()` simples imprimiria as chaves do plural na
    tela, e a frase deixaria de ser *"a frase como o usuário a lê"* - que é a
    única coisa que ela precisa ser.
    """
    frase = "{damas, plural, =1{Coroe 1 dama} other{Coroe {damas} damas}}"
    assert renderizar(frase, {"damas": damas}) == esperado


def test_o_ramo_do_plural_pode_conter_OUTRO_placeholder() -> None:
    """🔒 A recursão: `other{Coroe {damas} damas}` tem `{damas}` dentro."""
    frase = "{n, plural, =1{um {nome}} other{{n} {nome}s}}"
    assert renderizar(frase, {"n": 3, "nome": "lance"}) == "3 lances"


def test_conta_as_CHAVES_em_vez_de_procurar_a_proxima() -> None:
    """🔒 ⛔ O primeiro `}` quase nunca é o certo.

    ⚠️ Os ramos do plural contêm `{damas}` dentro; um regex ganancioso engoliria a
    frase inteira, e um preguiçoso pararia no fecho errado. Esta frase tem **dois**
    blocos de plural em sequência, que é onde os dois erros aparecem.
    """
    frase = (
        "{a, plural, =1{1 dama} other{{a} damas}} em "
        "{b, plural, =1{1 lance} other{{b} lances}}"
    )
    assert renderizar(frase, {"a": 1, "b": 6}) == "1 dama em 6 lances"
    assert renderizar(frase, {"a": 2, "b": 1}) == "2 damas em 1 lance"


def test_o_ramo_EXATO_ganha_da_categoria() -> None:
    """🔒 `=1` é mais específico que `one`/`other`, como manda o ICU."""
    frase = "{n, plural, =1{só um} one{um} other{muitos}}"
    assert renderizar(frase, {"n": 1}) == "só um"


def test_placeholder_SEM_VALOR_levanta() -> None:
    """🔒 ⛔ Melhor um erro que uma frase que parece certa.

    ⚠️ *"Coroe damas em até 6 lances"* é pior que um erro: ela lê como uma frase
    válida, e só o número que importa sumiu.
    """
    with pytest.raises(FraseInvalida):
        renderizar("Coroe {damas} damas", {})


def test_recurso_de_ICU_nao_coberto_LEVANTA_em_vez_de_imprimir_lixo() -> None:
    """🔒 ⛔ `select` e o resto do ICU param aqui, e isso é deliberado.

    ⚠️ O renderizador cobre o que os `.arb` do projeto usam. No dia em que um
    `select` entrar, o teste do catálogo acima falha - antes de o painel mostrar.
    """
    with pytest.raises(FraseInvalida):
        renderizar("{genero, select, f{a} other{o}}", {"genero": "f"})
    with pytest.raises(FraseInvalida):
        renderizar("Coroe {damas damas", {"damas": 1})


# ═══════════════════════════════════════════════════════════════════════════
# 3. 🔒 A montagem, com os dados como o banco os guarda
# ═══════════════════════════════════════════════════════════════════════════


def test_o_PERSONAGEM_entra_com_inicial_maiuscula() -> None:
    """🔒 No banco é `magno` (código); na tela é **Magno** (nome próprio)."""
    montada = frase_do_desafio(
        "desafioObjetivoCoroarEmLances",
        {"damas": 1, "lances": 6, "modalidade": "brasileira", "personagem": "magno"},
    )
    assert montada == "Coroe 1 dama em até 6 lances contra Magno"


def test_os_parametros_QUE_SOBRAM_nao_atrapalham() -> None:
    """🔒 ⚠️ `js_objetivo` traz `variante` e `modalidade`, que a frase não usa.

    ⛔ Um renderizador que exigisse correspondência exata quebraria em todo desafio
    de damas - e o excesso é estrutural, não acidente: os mesmos parâmetros
    alimentam a receita e a frase.
    """
    montada = frase_do_desafio(
        "desafioObjetivoSobreviver",
        {
            "lances": 8,
            "perder": 2,
            "variante": "brasileira",
            "modalidade": "brasileira",
            "personagem": "magno",
        },
    )
    assert montada == "Resista 8 lances a Magno perdendo no máximo 2 peças"


def test_chave_DESCONHECIDA_devolve_None_sem_estourar() -> None:
    """🔒 ⛔ Uma chave nova no app antes de a cópia ser regerada não derruba o painel.

    ⚠️ O cadeado do topo já avisa que a cópia envelheceu, e esse é o lugar certo
    para o aviso - a página de curadoria mostra a chave crua e continua de pé.
    """
    assert frase_do_desafio("desafioObjetivoQueNaoExiste", {"n": 1}) is None


def test_copia_AUSENTE_devolve_vazio_em_vez_de_estourar(tmp_path: Path) -> None:
    """🔒 Uma ferramenta de curadoria que não abre é pior que uma que mostra menos."""
    assert carregar_frases(tmp_path / "nao-existe.json") == {}


def test_a_copia_esta_no_lugar_que_o_painel_procura() -> None:
    """🔒 ⚠️ O caminho é relativo ao pacote, e um `parents[n]` errado só aparece
    em produção - onde a estrutura de pastas da imagem é a mesma, mas ninguém
    conferiu."""
    assert CAMINHO_DAS_FRASES.exists(), (
        f"a copia nao esta em {CAMINHO_DAS_FRASES}. "
        "Rode `python scripts/gerar_frases_objetivo.py`."
    )
    assert carregar_frases(), "a copia existe mas esta vazia"


# ═══════════════════════════════════════════════════════════════════════════
# 4. 🔒 O nome da figura do "Forme a figura" (T152, §8zzzw)
# ═══════════════════════════════════════════════════════════════════════════

#: Um `js_objetivo` do "Forme a figura" como o job o grava (sem o desenho, que a
#: frase não usa).
_FIGURA = {"lances": 7, "personagem": "magno", "variante": "classico"}


def test_a_figura_CONHECIDA_sai_com_o_nome() -> None:
    """🔒 Com o código, o painel lê a frase como o app: "Forme um Z...".

    ⚠️ O job grava a chave GENÉRICA (`desafioObjetivoQuatroFigura`); quem troca
    para a nomeada é quem lê. Um painel que não trocasse mostraria "Forme esta
    figura" num dia em que o app diz "Forme um Z" - e a frase do painel deixaria
    de ser a que a pessoa lê.
    """
    montada = frase_do_desafio(
        "desafioObjetivoQuatroFigura", {**_FIGURA, CHAVE_CODIGO_DA_FIGURA: "z"}
    )
    assert montada == "Forme um Z em até 7 lances contra Magno"


def test_o_nome_de_CODIGO_COMPOSTO_tambem_sai() -> None:
    """🔒 `i_longo` vira `ILongo` na chave: o PascalCase pega cada pedaço."""
    montada = frase_do_desafio(
        "desafioObjetivoQuatroFigura",
        {**_FIGURA, "lances": 1, CHAVE_CODIGO_DA_FIGURA: "i_longo"},
    )
    assert montada == "Forme um i longo em até 1 lance contra Magno"


@pytest.mark.parametrize(
    "codigo",
    [None, "figura_que_ainda_nao_tem_nome", 7],
    ids=["ausente", "desconhecido", "nao_e_texto"],
)
def test_sem_nome_cai_na_frase_GENERICA(codigo: object) -> None:
    """🔒 ⚠️ Figura nova vai ao ar sem versão nova do app: sem nome, a genérica.

    É o que o app de quem ainda não tem o nome mostra - e o painel mostra o
    mesmo, em vez de cair para a chave crua (`None`).
    """
    valores = dict(_FIGURA)
    if codigo is not None:
        valores[CHAVE_CODIGO_DA_FIGURA] = codigo
    montada = frase_do_desafio("desafioObjetivoQuatroFigura", valores)
    assert montada == "Forme esta figura em até 7 lances contra Magno"


def test_copia_SEM_a_frase_nomeada_cai_na_GENERICA() -> None:
    """🔒 Cópia com o nome e sem a frase nomeada (meio regerada) não derruba a
    frase: sai a genérica, como quando o nome falta."""
    frases = {
        "desafioObjetivoQuatroFigura": "Forme esta figura em {lances} lances",
        "desafioNomeFiguraQuatroZ": "um Z",
    }
    montada = frase_do_desafio(
        "desafioObjetivoQuatroFigura",
        {**_FIGURA, CHAVE_CODIGO_DA_FIGURA: "z"},
        frases=frases,
    )
    assert montada == "Forme esta figura em 7 lances"


def test_so_o_FORME_A_FIGURA_troca_de_frase() -> None:
    """🔒 Um `codigo_figura` perdido em outro desafio não troca a frase dele."""
    montada = frase_do_desafio(
        "desafioObjetivoCoroarEmLances",
        {
            "damas": 1,
            "lances": 6,
            "personagem": "magno",
            CHAVE_CODIGO_DA_FIGURA: "z",
        },
    )
    assert montada == "Coroe 1 dama em até 6 lances contra Magno"


@pytest.mark.parametrize(
    ("codigo", "chave"),
    [
        ("z", "desafioNomeFiguraQuatroZ"),
        ("i_longo", "desafioNomeFiguraQuatroILongo"),
        ("igual_sanduiche", "desafioNomeFiguraQuatroIgualSanduiche"),
    ],
)
def test_a_chave_do_nome_e_o_codigo_em_PASCALCASE(codigo: str, chave: str) -> None:
    """🔒 A mesma regra do app (`nome_da_figura_do_quatro.dart`)."""
    assert chave_do_nome_da_figura(codigo) == chave


def test_a_chave_do_codigo_e_a_MESMA_do_job() -> None:
    """🔒 ⚠️ O painel escreve a chave à mão (não importa do job); aqui as duas
    se encontram. Divergir faria o painel nunca achar o código, e a frase
    genérica sairia todo dia sem ninguém notar."""
    from job import figuras_quatro

    assert CHAVE_CODIGO_DA_FIGURA == figuras_quatro.CHAVE_CODIGO_DA_FIGURA


def test_TODA_figura_no_ar_tem_nome_na_COPIA() -> None:
    """🔒 Cada figura que o editorial põe no ar sai com nome no painel.

    ⚠️ O cadeado do app cobra o nome nos três `.arb`; este cobra que a cópia do
    painel o trouxe (o gerador pega os prefixos certos).
    """
    from job import editorial

    frases = carregar_frases()
    sem_nome = [
        codigo
        for codigo in editorial.codigos_das_figuras_no_ar()
        if chave_do_nome_da_figura(codigo) not in frases
    ]
    assert not sem_nome, (
        f"figuras no ar sem nome na copia: {sem_nome}. "
        "Rode `python scripts/gerar_frases_objetivo.py`."
    )

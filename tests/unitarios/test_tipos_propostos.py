"""OS TIPOS NOVOS PROPOSTOS AO DONO — T049 (RF-DES-128).

⚠️ **Proposta em prosa nao se confere.** Cada `js_chegada` daqui passa pelo
**mesmo avaliador** que julgaria o desafio de verdade, e estes casos provam as
duas coisas que tornam uma proposta aprovavel:

  1. ela e **formalmente valida** — o avaliador a le sem reclamar;
  2. ⛔ ela **nao exige vocabulario novo** — e por isso e publicavel como
     **dado**, sem versao nova do aplicativo. Um tipo que precisasse de uma
     medida nova exigiria codigo no aparelho, e ai deixaria de ser dado e
     viraria release (a fronteira de RF-DES-192).

⚠️ E ha um terceiro caso, que e o mais importante: elas **nao estao em
`RECEITAS`**. Um tipo so vai ao ar com linha na dimensao, chave de i18n e vetor —
e nenhuma das tres e decisao minha.
"""

from __future__ import annotations

import pytest

from job.tipos_de_desafio import RECEITAS
from job.tipos_propostos import (
    PARAMETROS_DE_EXEMPLO,
    PROPOSTAS,
    PROPOSTAS_DAMAS,
    PROPOSTAS_PONTINHOS,
)
from motores.damas import feitos_damas
from motores.damas.motor_damas import MotorDamas, estado_inicial
from motores.pontinhos import feitos_pontinhos
from motores.pontinhos.motor_pontinhos import EstadoPontinhos
from motores.nucleo.chegada import (
    COMPARADORES,
    JANELAS,
    LinhaDeChegada,
    avaliar,
)

IDS = sorted(PROPOSTAS)

#: As chaves que os medidores dos dois jogos ja produzem hoje.
#:
#: ⚠️ Lidas **do codigo dos medidores**, e nao escritas a mao.
#:
#: ⛔ **Ate 12/09/2026 este comentario mentia**: ele prometia derivacao e logo
#: abaixo havia duas listas literais. Elas estavam certas por acaso — e pararam
#: de estar no dia em que `maior_cadeia_capturada` entrou no medidor do
#: Pontinhos: o cadeado reprovou uma chave que o medidor produz, apontando para
#: a proposta em vez de para a lista velha.
#:
#: ⚠️ O risco que ele descreve continua real, e agora esta coberto de verdade:
#: uma lista escrita a mao envelhece, e o cadeado passa a aprovar chave que
#: medidor nenhum calcula — o desafio vai ao ar e o julgamento estoura
#: `ChegadaInvalida` para todo mundo.
def _medidas_que_o_pontinhos_produz() -> set[str]:
    """As chaves que o medidor do Pontinhos devolve — perguntadas a ele."""
    vazio = EstadoPontinhos(lances=())
    return set(feitos_pontinhos.medir(vazio, vazio, jogador=1, lances_do_jogador=0))


def _medidas_que_as_damas_produzem() -> set[str]:
    """As chaves que o medidor das damas devolve — perguntadas a ele."""
    motor = MotorDamas(co_modalidade="brasileira")
    return set(feitos_damas.medir(motor, estado_inicial("brasileira"), [], jogador=1))


MEDIDAS_DO_PONTINHOS = _medidas_que_o_pontinhos_produz()
MEDIDAS_DAS_DAMAS = _medidas_que_as_damas_produzem()


def _chegada(co_tipo: str) -> dict:
    """Monta o `js_chegada` de uma proposta com os parametros de exemplo."""
    receita = PROPOSTAS[co_tipo]
    return receita.montar(PARAMETROS_DE_EXEMPLO[co_tipo])


# ═══════════════════════════════════════════════════════════════════════════
# 1. Ha propostas, e elas cobrem os dois jogos
# ═══════════════════════════════════════════════════════════════════════════


def test_ha_propostas_para_os_dois_jogos():
    """⚠️ **RF-DES-128 e sobre OS DOIS.**

    O dono pediu *"diversos outros tipos criativos de desafios para os 2 jogos"* —
    propor so para as damas cumpriria metade e pareceria completo.
    """
    assert len(PROPOSTAS_PONTINHOS) >= 4
    assert len(PROPOSTAS_DAMAS) >= 5
    assert len(PROPOSTAS) == len(PROPOSTAS_PONTINHOS) + len(PROPOSTAS_DAMAS)


def test_toda_proposta_tem_parametros_de_exemplo():
    """Sem eles nao ha como montar a chegada — nem para o teste, nem para o
    documento que o dono le."""
    assert set(PARAMETROS_DE_EXEMPLO) == set(PROPOSTAS)


def test_nenhuma_proposta_repete_tipo_existente():
    """⛔ Um `co_tipo_desafio` repetido colidiria com o `UNIQUE` da dimensao."""
    assert not set(PROPOSTAS) & set(RECEITAS)


def test_os_numeros_sugeridos_nao_colidem():
    """⚠️ Os 10 primeiros ja existem na `0018`.

    ⛔ Estes numeros sao **sugestao**: quem os fixa e a migracao que o dono
    aprovar. O que este caso garante e que a sugestao nao nasce quebrada.
    """
    numeros = [r.nu_tipo_desafio for r in PROPOSTAS.values()]
    assert len(numeros) == len(set(numeros)), "numero repetido entre propostas"
    assert min(numeros) >= 11, "numero abaixo de 11 colide com a dimensao atual"


# ═══════════════════════════════════════════════════════════════════════════
# 2. ⚠️ Cada uma e formalmente valida
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_tipo", IDS)
def test_a_chegada_proposta_e_valida(co_tipo: str):
    """🔒 O avaliador de verdade le a proposta sem reclamar.

    ⚠️ **E o mesmo `LinhaDeChegada.de_dado` que roda no job e na auditoria.** Uma
    proposta que so "parece certa" seria descoberta na geracao, semanas depois —
    e o candidato seria descartado sem que ninguem soubesse por que.
    """
    chegada = LinhaDeChegada.de_dado(_chegada(co_tipo))
    assert chegada.clausulas, f"{co_tipo}: chegada sem clausula nenhuma"


@pytest.mark.parametrize("co_tipo", IDS)
def test_a_chegada_proposta_usa_so_o_vocabulario_de_hoje(co_tipo: str):
    """⛔ **O criterio de publicabilidade sem versao nova.**

    Um tipo que precisasse de janela, comparador ou medida nova exigiria codigo
    no aparelho — e ai ele deixa de ser **dado** e vira **release**, que e a
    fronteira que RF-DES-192 protege.
    """
    receita = PROPOSTAS[co_tipo]
    dado = _chegada(co_tipo)

    assert dado["janela"]["tipo"] in JANELAS

    permitidas = (
        MEDIDAS_DO_PONTINHOS
        if receita.co_jogo == "pontinhos"
        else MEDIDAS_DAS_DAMAS
    )
    for clausula in dado["clausulas"]:
        # ⛔ Nenhuma proposta usa `predicado`: predicados sao funcoes COMPILADAS
        # no aplicativo, e um predicado novo tambem seria release.
        assert clausula["tipo"] == "medida", (
            f"{co_tipo}: usa `predicado`, que exigiria codigo novo no aparelho"
        )
        assert clausula["comparador"] in COMPARADORES
        assert clausula["chave"] in permitidas, (
            f"{co_tipo}: a medida {clausula['chave']!r} nao existe no medidor de "
            f"{receita.co_jogo}. ⛔ Ela exigiria codigo novo, e o tipo deixaria "
            "de ser publicavel como dado."
        )


@pytest.mark.parametrize("co_tipo", IDS)
def test_a_chegada_proposta_e_JULGAVEL(co_tipo: str):
    """⚠️ Valida **e** julgavel sao coisas diferentes.

    Uma chegada pode passar na leitura e estourar na avaliacao — e o caso da
    chave que nenhum medidor produz. Aqui ela e avaliada contra um conjunto de
    medidas plausivel, e o que se exige e que **nao levante excecao**.
    """
    receita = PROPOSTAS[co_tipo]
    chegada = LinhaDeChegada.de_dado(_chegada(co_tipo))

    # Um "tudo zero" e o pior caso para o avaliador: toda chave existe, e
    # nenhuma clausula tem motivo obvio para passar.
    medidas = {
        chave: 0.0
        for chave in (
            MEDIDAS_DO_PONTINHOS
            if receita.co_jogo == "pontinhos"
            else MEDIDAS_DAS_DAMAS
        )
    }

    # ⚠️ O que importa e nao estourar. O veredito (True/False) depende dos
    # numeros, e este caso nao e sobre eles.
    assert avaliar(chegada, medidas) in (True, False)


# ═══════════════════════════════════════════════════════════════════════════
# 3. ⛔ E elas NAO estao em producao
# ═══════════════════════════════════════════════════════════════════════════


def test_nenhuma_proposta_esta_em_RECEITAS():
    """⛔ **Um tipo so vai ao ar com as tres coisas, e nenhuma e minha.**

    1. linha em `desafio.tb901_tipo_desafio` — e migracao, e o `data-model.md` e
       o que o dono pre-validou;
    2. chave de i18n nos tres `.arb` — a unica coisa que ainda exige versao nova
       do aplicativo, e trabalho do BLOCO 3;
    3. vetor de verificacao (RF-DES-198) — a prova de que Dart e Python leem a
       mesma regra.

    Importar daqui para `RECEITAS` antes disso publicaria um tipo que o aplicativo
    mostraria como chave crua, e cairia na tela de atualizar.
    """
    for co_tipo in PROPOSTAS:
        assert co_tipo not in RECEITAS, (
            f"{co_tipo} entrou em RECEITAS sem passar pelas tres portas. ⛔ Leia "
            "a docstring de `job/tipos_propostos.py`."
        )


@pytest.mark.parametrize("co_tipo", IDS)
def test_cada_proposta_declara_uma_chave_de_i18n(co_tipo: str):
    """⛔ **Nunca a frase pronta** (RF-DES-176): ela viajaria num idioma so.

    ⚠️ A chave e o que ainda **nao existe** nos `.arb` — e e por ela que cada uma
    destas propostas custa uma versao do aplicativo. Declara-la aqui e o que
    permite ao dono ver o preco antes de aprovar.
    """
    chave = PROPOSTAS[co_tipo].co_chave_objetivo
    assert chave.startswith("desafioObjetivo"), (
        f"{co_tipo}: a chave {chave!r} nao segue o padrao das existentes"
    )


@pytest.mark.parametrize("co_tipo", IDS)
def test_a_frase_recebe_o_PERSONAGEM(co_tipo: str):
    """⚠️ **O personagem e parte do enunciado, e nao enfeite** (RF-DES-201).

    E ele que diz o tamanho da tarefa: *"feche 4 caixas em 2 turnos jogando
    contra a Pita"* e outro desafio de *"…contra o Magno"*.
    """
    receita = PROPOSTAS[co_tipo]
    valores = receita.valores_da_frase(PARAMETROS_DE_EXEMPLO[co_tipo], "pita")
    assert valores.get("personagem") == "pita"


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ O TIPO E CUMPRIDO POR QUEM NAO FEZ NADA?
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Este bloco nasceu de um defeito real, achado em 12/09/2026 medindo.** Tres
# dos onze tipos propostos - `pontinhos_nao_entregar_nada`, `pontinhos_paciencia`
# e `damas_armadilha` - davam solucao de **UM meio-lance**, com qualquer numero
# no enunciado. Os testes deste arquivo estavam todos verdes: eles provam que a
# chegada e **bem formada**, e uma chegada bem formada pode ser trivial.
#
# ⛔ **A causa e estrutural, e vale para toda a familia "impeca" / "aguente":** a
# janela e um TETO ("dentro de ate n"), e o juiz para no PRIMEIRO lance em que as
# clausulas valem. Uma clausula que diz *"o adversario nao fechou caixa"* ja e
# verdadeira antes de o adversario jogar.
#
# ✅ **A cura nao custa vocabulario novo:** juntar `lances_do_jogador >= n`. A
# conjuncao so pode ficar verdadeira no n-esimo lance, e `lances_do_jogador` e
# uma MEDIDA que os dois medidores ja produzem.

#: As medidas de quem ainda nao jogou: tudo o que se ACUMULA esta em zero, e o
#: material esta cheio.
#:
#: ⚠️ **Zerar tudo nao serviria**, e e o detalhe que faz este cadeado funcionar:
#: com `material_restante = 0` a clausula *"ainda tenho pecas"* daria falsa, e o
#: tipo passaria escondendo o defeito. O estado inicial de verdade tem material
#: ALTO e deltas em zero.
MEDIDAS_DE_QUEM_NAO_JOGOU: dict[str, float] = {
    # deltas, que comecam em zero
    "caixas_fechadas": 0,
    "caixas_do_adversario": 0,
    "lances_do_jogador": 0,
    "maior_cadeia_capturada": 0,
    "damas_coroadas": 0,
    "capturas_extras": 0,
    "maior_captura": 0,
    # o tabuleiro cheio das damas
    "material_restante": 12,
    "material_do_adversario": 12,
    # marcos
    "vitoria": 0,
    "empate": 0,
}


@pytest.mark.parametrize(
    "co_tipo, receita",
    [
        pytest.param(k, r, id=k)
        for k, r in PROPOSTAS.items()
    ],
)
def test_NENHUM_tipo_proposto_e_cumprido_por_quem_nao_fez_NADA(co_tipo, receita):
    """⛔ Se a chegada vale no estado inicial, o desafio ja nasce resolvido.

    ⚠️ E o pior tipo de defeito para quem joga: o enunciado promete uma tarefa, a
    pessoa faz um lance qualquer, e a tela diz que ela cumpriu. Nada acusa - o
    desafio e valido, gera gabarito e passa por toda a pipeline.
    """
    parametros = PARAMETROS_DE_EXEMPLO[co_tipo]
    chegada = LinhaDeChegada.de_dado(receita.montar(parametros))

    assert not avaliar(chegada, MEDIDAS_DE_QUEM_NAO_JOGOU), (
        f"⛔ {co_tipo} e cumprido por quem nao fez nada. Junte uma clausula de "
        "`lances_do_jogador >= n` a conjuncao: ela e a unica coisa que impede o "
        "juiz de fechar a conta no primeiro lance."
    )


@pytest.mark.parametrize("co_tipo", sorted(RECEITAS))
def test_e_nenhum_tipo_NO_AR_tambem_e_cumprido_por_quem_nao_fez_nada(co_tipo):
    """⚠️ O mesmo cadeado, aplicado ao que ja esta publicado.

    ⛔ Hoje **nenhum** dos cinco tem o defeito, e isso nao e sorte: os cinco pedem
    que algo ACONTECA (feche caixas, coroe, capture), e uma clausula assim e
    falsa antes do primeiro lance. ⚠️ Mas a familia que falta no catalogo e
    justamente a do *"impeca"* / *"aguente"*, e quando o primeiro tipo dessa
    familia for publicado este caso e o que o segura.

    ⚠️ Os parametros saem do EDITORIAL, e nao de numeros escritos aqui: e com
    eles que o tipo vai ao ar.
    """
    from job import editorial as editorial_mod

    for variante in editorial_mod.variantes_de(co_tipo):
        parametros = dict(variante.parametros)
        # ⚠️ `acima_do_guloso` so vira numero depois de o gerador medir o guloso
        # na posicao; aqui um valor qualquer basta, porque o que se testa e a
        # FORMA da conjuncao.
        if editorial_mod.alvo_sai_da_posicao(parametros):
            parametros = editorial_mod.parametros_efetivos(parametros, guloso=3)

        chegada = LinhaDeChegada.de_dado(RECEITAS[co_tipo].montar(parametros))
        assert not avaliar(chegada, MEDIDAS_DE_QUEM_NAO_JOGOU), (
            f"⛔ {co_tipo} {dict(variante.parametros)} esta NO AR e e cumprido "
            "por quem nao fez nada."
        )


#: As propostas que julgam igual a um tipo publicado, e o aviso ja escrito na
#: receita de cada uma.
#:
#: ⛔ **Elas nao sao apagadas** (nada e apagado neste projeto), mas tambem nao
#: entram em `EM_AVALIACAO`: medi-las seria pagar horas de maquina por uma linha
#: cujo resultado ja se conhece.
#:
#: ⚠️ **As duas foram achadas pelo proprio cadeado, em 12/09/2026** - nenhuma
#: tinha sido notada em revisao de codigo, e as duas estavam ha dias no arquivo.
DUPLICATAS_CONHECIDAS = [
    # A forma e `pontinhos_fechar_caixas` com `turnos: 1`.
    "pontinhos_escada_em_um_turno julga igual a pontinhos_fechar_caixas",
    # ⛔ E literalmente `damas_coroar` com `damas: 2` - que o dono pediu em
    # 11/09/2026 e JA ESTA PUBLICADO como `{damas: 2, lances: 8}`.
    "damas_dupla_coroacao julga igual a damas_coroar",
]


def test_nenhuma_proposta_repete_a_CHEGADA_de_um_tipo_que_ja_esta_no_ar():
    """⛔ Um tipo proposto que julga igual a um publicado e trabalho repetido.

    ⚠️ **Isto ja aconteceu**, e so a medicao pegou: `pontinhos_escada_em_um_turno`
    queria dizer *"feche N caixas de uma vez"*, que e literalmente o que
    `pontinhos_cadeia_longa` publica - `maior_cadeia_capturada >= N`.

    ⚠️ **A comparacao e pela FORMA, e nao pelos numeros:** o que identifica um
    tipo e o par (janela, chaves+comparadores das clausulas). Dois tipos que
    diferem so no valor sao o mesmo tipo com parametros diferentes, e parametro
    e dado.

    ⛔ Este caso e sobre o CATALOGO, e nao sobre codigo: ele falha quando alguem
    propuser um tipo que ja existe, que e exatamente quando se quer saber.
    """
    from job import editorial as editorial_mod

    def forma(js_chegada):
        janela = js_chegada["janela"]
        return (
            janela["tipo"],
            tuple(
                sorted(
                    (c.get("chave"), c["comparador"])
                    for c in js_chegada["clausulas"]
                )
            ),
        )

    no_ar: dict[tuple, str] = {}
    for co_tipo, receita in RECEITAS.items():
        for variante in editorial_mod.variantes_de(co_tipo):
            parametros = dict(variante.parametros)
            if editorial_mod.alvo_sai_da_posicao(parametros):
                parametros = editorial_mod.parametros_efetivos(parametros, guloso=3)
            no_ar[forma(receita.montar(parametros))] = co_tipo

    repetidos = []
    for co_tipo, receita in PROPOSTAS.items():
        f = forma(receita.montar(PARAMETROS_DE_EXEMPLO[co_tipo]))
        if f in no_ar:
            repetidos.append(f"{co_tipo} julga igual a {no_ar[f]}")

    assert sorted(repetidos) == sorted(DUPLICATAS_CONHECIDAS), (
        "⛔ mudou a lista de propostas que julgam igual a um tipo no ar.\n"
        f"   agora: {sorted(repetidos)}\n"
        f"   registradas: {sorted(DUPLICATAS_CONHECIDAS)}\n"
        "⚠️ Se apareceu uma NOVA, ela e parametro de um tipo existente, e nao "
        "tipo novo - escreva o aviso na receita dela e registre aqui. Se uma "
        "SUMIU, alguem mudou a forma de um tipo no ar, e isso merece olhada."
    )

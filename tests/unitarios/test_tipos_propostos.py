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

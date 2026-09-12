"""🔒 O parâmetro que sai da POSIÇÃO, e não do editorial (forma "a" do dono).

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE MUDA, E POR QUE ISSO É ESTRUTURAL
═══════════════════════════════════════════════════════════════════════════

Até 11/09/2026 a tarefa era fixa: o editorial publicava *"chegue a 7 caixas"* e o
gerador procurava uma posição em que isso desse certo. Agora o editorial publica
*"supere o guloso em N"*, e o número absoluto **sai de cada posição**.

⛔ **A consequência: a chegada e o enunciado deixam de ser montados uma vez só.**
Eles passam a ser montados dentro do laço, depois de a posição existir — e este
arquivo existe para travar isso, porque um `js_chegada` calculado fora do laço
publicaria o número de **outra** posição, sem erro nenhum.

⚠️ **O `montar()` da receita continua recebendo `caixas`**, de propósito: mexer no
contrato obrigaria a refazer os vetores de verificação e a cópia do app. Quem
traduz `acima_do_guloso` em `caixas` é o gerador, que é quem tem a posição.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from job import editorial as editorial_mod  # noqa: E402
from job import gerador  # noqa: E402
from job import semente as semente_mod  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.pontinhos.guloso import caixas_do_guloso  # noqa: E402
from motores.pontinhos.politica import JogadorPontinhos  # noqa: E402

#: O tipo cujo objetivo é *"feche N caixas ou mais"*, com janela de partida.
TIPO = "pontinhos_chegar_ao_placar"


def _primeiro_dia_do_tipo() -> date:
    """O primeiro dia em que o rodízio cai neste tipo.

    ⚠️ **Perguntado ao gerador, e não escrito à mão.** Jogo e tipo saem de um
    rodízio por data; uma data fixa no teste passaria a apontar para outro tipo no
    dia em que o rodízio mudasse — e o teste falharia por um motivo que não tem
    nada a ver com o que ele investiga.
    """
    for n in range(60):
        dia = date(2026, 9, 20) + timedelta(days=n)
        if gerador.escolher_jogo(dia) == "pontinhos":
            if gerador.escolher_tipo("pontinhos", dia) == TIPO:
                return dia
    raise AssertionError(f"o rodízio não cai em {TIPO} em 60 dias")


DIA_DE_PONTINHOS = _primeiro_dia_do_tipo()

#: O teto de lances DESTE tipo, lido do editorial.
#:
#: ⚠️ **Não é o padrão de 12.** A janela deste objetivo é a partida inteira, e a
#: solução medida usa ~22 lances: com 12 nunca se chega a sete caixas, e o teste
#: acusaria "não gerou nada" num código que está certo. O editorial já sabe disso
#: (`nu_maximo_de_meios_lances=34`), e lê-lo de lá evita que os dois números divirjam.
TETO = editorial_mod.variantes_de(TIPO)[0].nu_maximo_de_meios_lances

#: Quantos traços a posição de partida já traz marcados.
#:
#: ⛔ **O padrão de 8 NÃO serve para este tipo**, e descobrir isso custou uma
#: execução: com 8 traços o tabuleiro é começo de jogo, **não há cadeia formada**,
#: e todo lance que entrega caixa é erro de verdade — a recusa por erro do
#: adversário barrava 100% dos candidatos.
#:
#: ⚠️ **O double dealing só existe com o tabuleiro cheio**, quando as cadeias já
#: se fecharam e recusar as duas últimas passa a valer a pena. Foi com 14 traços
#: que a medição em posições reais achou `D > G` em 27% delas.
PREPARO = 14


@pytest.fixture(scope="module")
def candidatos():
    """Gera com `acima_do_guloso`, o parâmetro que depende da posição.

    ⚠️ Roda o gerador **de verdade** (CNN incluída): é um teste de integração, e
    tem de ser, porque o que se quer provar é justamente a costura entre o cálculo
    do guloso, a montagem da chegada e a busca do gabarito.
    """
    return gerador.gerar_candidatos(
        DIA_DE_PONTINHOS,
        parametros={"acima_do_guloso": 1},
        quantos=2,
        tentativas_por_candidato=12,
        maximo_de_meios_lances=TETO,
        lances_de_preparo=PREPARO,
    )


def test_o_tipo_do_dia_e_o_esperado() -> None:
    """🔒 A premissa do arquivo, dita em voz alta."""
    assert gerador.escolher_jogo(DIA_DE_PONTINHOS) == "pontinhos"
    assert gerador.escolher_tipo("pontinhos", DIA_DE_PONTINHOS) == TIPO


def test_gerou_alguma_coisa(candidatos) -> None:
    """🔒 ⚠️ Se isto falhar, os testes abaixo passariam por vacuidade.

    Um `for` sobre lista vazia passa em qualquer asserção — e o arquivo inteiro
    ficaria verde provando nada.
    """
    assert candidatos, "nenhum candidato: os testes seguintes não provariam nada"


def test_o_objetivo_publicado_SUPERA_o_guloso(candidatos) -> None:
    """🔒 ⛔ A propriedade central: quem só captura NÃO resolve.

    Recalcula `G` na posição publicada e confere que o número do enunciado está
    acima dele. ⚠️ É o que torna o desafio auto-verificável: a solução ingênua é
    excluída por construção, e não por alguém ter julgado que era fácil demais.
    """
    motor_politica = JogadorPontinhos()
    for candidato in candidatos:
        alvo = candidato.js_chegada["clausulas"][0]["valor"]
        guloso = caixas_do_guloso(
            motor_politica,
            motor_politica.arbitro,
            candidato.estado_inicial,
            candidato.js_posicao_inicial["vez_de"],
            nivel=NivelDeMotor.SAGAZ,
            nivel_do_adversario=gerador.NIVEL_POR_PERSONAGEM[candidato.co_personagem],
            semente_do_lance=semente_mod.semente_do_lance,
            nu_semente=candidato.nu_semente,
        )
        assert alvo > guloso, (
            f"o enunciado pede {alvo} e o guloso já faz {guloso}: "
            "este desafio se resolve sem double dealing"
        )


def test_o_ENUNCIADO_traz_o_numero_absoluto(candidatos) -> None:
    """🔒 ⚠️ A frase diz *"capture 7 ou mais"*, e não *"supere o guloso em 1"*.

    ⛔ `acima_do_guloso` é vocabulário **interno**: quem joga não sabe o que o
    guloso faria, e uma frase com esse número seria ininteligível.
    """
    for candidato in candidatos:
        alvo = candidato.js_chegada["clausulas"][0]["valor"]
        assert candidato.js_objetivo.get("caixas") == alvo
        assert "acima_do_guloso" not in candidato.js_objetivo


def test_posicoes_DIFERENTES_podem_pedir_numeros_diferentes(candidatos) -> None:
    """🔒 ⚠️ A prova de que a conta é por posição, e não uma só para todas.

    ⛔ Este é o teste que pega o defeito de montar `js_chegada` fora do laço: lá o
    número seria idêntico em todos os candidatos, **sem erro nenhum**, e todos
    menos o primeiro estariam publicando o alvo de outra posição.

    ⚠️ Não se exige que sejam diferentes — duas posições podem legitimamente dar o
    mesmo `G`. Exige-se que cada um seja coerente com a **sua** posição, que é o
    teste acima; aqui só se confere que o número não é o do editorial.
    """
    for candidato in candidatos:
        alvo = candidato.js_chegada["clausulas"][0]["valor"]
        assert alvo != 1, "o alvo virou o `acima_do_guloso` cru, sem somar o guloso"
        assert 1 <= alvo <= 12, f"alvo fora do tabuleiro de 12 caixas: {alvo}"


def test_o_tipo_de_parametro_FIXO_continua_funcionando(candidatos) -> None:
    """🔒 O controle: sem `acima_do_guloso`, nada muda.

    ⚠️ A mudança mexeu em código que **todos** os tipos atravessam. Um tipo de
    parâmetro fixo tem de continuar publicando exatamente o número do editorial.
    """
    fixos = gerador.gerar_candidatos(
        DIA_DE_PONTINHOS,
        parametros={"caixas": 5},
        quantos=1,
        tentativas_por_candidato=12,
        maximo_de_meios_lances=TETO,
        lances_de_preparo=PREPARO,
    )
    for candidato in fixos:
        assert candidato.js_chegada["clausulas"][0]["valor"] == 5


def test_a_regra_de_recusa_NAO_e_aplicada_a_este_tipo(monkeypatch) -> None:
    """🔒 ⛔ A decisão do dono de 12/09/2026, travada.

    A regra *"se o adversário entregou caixas e existia um traço que entregava
    zero, recusa"* continua valendo nos tipos de alvo fixo. Aqui, **não**: o alvo
    é `G + k`, e `G` é medido na mesma posição contra o mesmo personagem — um erro
    dele levanta os dois lados da conta e se cancela.

    ⚠️ **Medido, e é por isso que o teste existe:** com a regra ligada esta
    variante deu **pior dia 0** (dia descoberto na fila); sem ela, **3**.
    """
    chamadas: list[str] = []

    def espiao(*a, **k):
        chamadas.append("perguntou")
        return None

    monkeypatch.setattr(gerador, "motivo_de_erro_do_adversario", espiao)

    gerador.gerar_candidatos(
        DIA_DE_PONTINHOS,
        parametros={"acima_do_guloso": 1},
        quantos=1,
        tentativas_por_candidato=4,
        maximo_de_meios_lances=TETO,
        lances_de_preparo=PREPARO,
    )
    assert not chamadas, "a recusa por erro do adversario foi consultada neste tipo"

    # ⚠️ **O controle.** Sem ele, o caso passaria igual se a regra tivesse sido
    # desligada para todo mundo — que é exatamente o que a decisão NÃO foi.
    gerador.gerar_candidatos(
        DIA_DE_PONTINHOS,
        parametros={"caixas": 5},
        quantos=1,
        tentativas_por_candidato=4,
        maximo_de_meios_lances=TETO,
        lances_de_preparo=PREPARO,
    )
    assert chamadas, "a recusa deixou de ser consultada tambem no tipo de alvo fixo"


def test_o_candidato_CARREGA_os_parametros_com_que_foi_montado(candidatos) -> None:
    """🔒 ⛔ Quem publica as medidas de saída lê daqui, e não do editorial.

    O editorial desta variante nem tem a chave `caixas` — ele traz
    `acima_do_guloso`. ⚠️ Sem este campo, `publicacao.medidas(...)` estouraria com
    `KeyError: 'caixas'` **depois** de o candidato ter sido gerado, medido e
    aprovado; e um `vr_max` do editorial pagaria nota cheia por um alvo diferente
    do que a frase pediu.
    """
    for candidato in candidatos:
        alvo = candidato.js_chegada["clausulas"][0]["valor"]
        assert candidato.parametros["caixas"] == alvo
        assert "acima_do_guloso" not in candidato.parametros

"""🔒 As receitas dos onze tipos do xadrez (T072 da spec 012).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO GUARDA
═══════════════════════════════════════════════════════════════════════════

  1. os onze tipos existem, TODOS fora do ar, com os numeros da `0040`;
  2. ⚠️ **cada receita monta exatamente a chegada de cada vetor do juiz**
     (`contratos/vetores-juiz-xadrez.json`). Os vetores nasceram na T069, antes
     das receitas, com as chegadas escritas a mao no gerador; desde a T072 o
     gerador as monta por aqui, e este caso confere, vetor a vetor, que a
     troca nao mudou nada. Vetor nao se edita: se uma receita divergir, quem
     esta errada e a receita;
  3. a frase: a chave do enunciado existe na copia do `.arb`, os valores sao
     exatamente os espacos dela, e as pecas que o cartao de feito repete
     (`pecas_do_objetivo` do manifesto, T071) estao entre eles;
  4. o editorial: a versao 1.6.0, a chegada valida e so com o que o xadrez
     mede, ninguem cumpre sem jogar, so o mate encerra a partida, e as medidas
     de saida fecham.

⚠️ **As pecas nao vem do editorial** (sao da posicao do dia, T073): onde a
receita precisa delas, este arquivo usa [PECAS_DE_EXEMPLO].
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from job.editorial import (
    EDITORIAL,
    EDITORIAL_FORA_DO_AR,
    VERSAO_MINIMA_DO_XADREZ,
    parametros_para_conferencia,
)
from job.medidas_de_saida import conferir
from job.medidas_do_feito import frases_declaradas
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR
from motores.nucleo.chegada import JANELAS, LinhaDeChegada, avaliar

RAIZ = Path(__file__).resolve().parents[2]
MIGRACAO = RAIZ / "migrations" / "versions" / "0040_desafio_xadrez.py"
VETORES = json.loads(
    (RAIZ / "contratos" / "vetores-juiz-xadrez.json").read_text(encoding="utf-8")
)["vetores"]
FRASES = json.loads(
    (RAIZ / "contratos" / "frases_objetivo_pt.json").read_text(encoding="utf-8")
)
CATALOGO = {
    linha["co_feito"]: linha
    for linha in json.loads(
        (RAIZ / "contratos" / "catalogo_feitos.json").read_text(encoding="utf-8")
    )["feitos"]
}

#: Os doze tipos do xadrez no banco, na ordem dos numeros 60 a 71: os onze da
#: 1a leva (PRD §8.4) e as duas espias (71, 21/11/2026, no lugar da troca, que
#: fica no banco e fora do ar; `DECISOES-do-dono.md` §8zzzz64).
TIPOS = (
    "xadrez_espia_comer",
    "xadrez_espia_proteger",
    "xadrez_espia_atravessar",
    "xadrez_espia_xeque",
    "xadrez_espia_alvo",
    "xadrez_comer_com",
    "xadrez_nao_perder",
    "xadrez_xeques_seguidos",
    "xadrez_sem_levar_xeque",
    "xadrez_troca",
    "xadrez_dar_mate",
    "xadrez_duas_espias",
)

#: A migracao do 71.
MIGRACAO_DAS_DUAS_ESPIAS = RAIZ / "migrations" / "versions" / "0041_desafio_xadrez_duas_espias.py"

#: As receitas do xadrez, no ar ou fora dele (a promocao da T078 MOVE).
RECEITAS_DO_XADREZ = {
    co_tipo: receita
    for co_tipo, receita in {**RECEITAS, **RECEITAS_FORA_DO_AR}.items()
    if receita.co_jogo == "xadrez"
}

#: Os codigos de peca que a posicao do dia poria nos parametros (T073). Um de
#: cada espaco, com `comida` presente (o caso sem ela tem teste proprio).
PECAS_DE_EXEMPLO = {
    "espia": "cavalo",
    "espia2": "torre",
    "alvo": "torre",
    "come": "cavalo",
    "comida": "peao",
    "peca": "peao",
    "minha": "bispo",
    "dele": "cavalo",
}

#: Todas as variantes do editorial, achatadas, para os casos parametrizados.
VARIANTES = [
    (co_tipo, publicacao)
    for co_tipo in TIPOS
    for publicacao in {**EDITORIAL, **EDITORIAL_FORA_DO_AR}.get(co_tipo, ())
]


def _parametros(publicacao) -> dict:
    """Os parametros de uma variante como o job os teria ao publicar: os
    numeros do editorial, o `L` de exemplo e as pecas da posicao."""
    return {**parametros_para_conferencia(publicacao.parametros), **PECAS_DE_EXEMPLO}


def _id(valor) -> str:
    """O nome legivel de cada caso no relatorio do pytest."""
    if isinstance(valor, str):
        return valor
    return str(dict(getattr(valor, "parametros", {})))


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os onze, e onde eles moram
# ═══════════════════════════════════════════════════════════════════════════


def test_os_doze_existem_e_TODOS_estao_fora_do_ar() -> None:
    """⚠️ Ate a regua (T077) e a promocao (T078), nenhum tipo do xadrez e
    publicavel: "tipo no banco nao e tipo no ar"."""
    assert sorted(RECEITAS_DO_XADREZ) == sorted(TIPOS)
    assert not set(TIPOS) & set(RECEITAS)
    assert not set(TIPOS) & set(EDITORIAL)


def test_os_numeros_sao_os_da_0040() -> None:
    """🔒 O numero da receita e o da linha que a migracao gravou na dimensao."""
    texto = MIGRACAO.read_text(encoding="utf-8") + MIGRACAO_DAS_DUAS_ESPIAS.read_text(
        encoding="utf-8"
    )
    # As linhas da 0040 e da 0041 sao `(  60, 'xadrez_espia_comer', ...)`.
    gravados = {
        tipo: int(numero)
        for numero, tipo in re.findall(r"\(\s*(\d+),\s*'(xadrez_\w+)'", texto)
    }
    assert gravados == {t: RECEITAS_DO_XADREZ[t].nu_tipo_desafio for t in TIPOS}
    assert [RECEITAS_DO_XADREZ[t].nu_tipo_desafio for t in TIPOS] == list(range(60, 72))


# ═══════════════════════════════════════════════════════════════════════════
# 2. 🔒 As receitas montam as chegadas dos vetores do juiz
# ═══════════════════════════════════════════════════════════════════════════


def _parametros_da_chegada(co_tipo: str, chegada: dict) -> dict:
    """Os parametros que dao aquela chegada, lidos dela: o N da janela, o K da
    clausula de contagem e o tipo de peca do `nao_perder`.

    ⚠️ Ler da chegada e o que permite conferir sem gravar os parametros no
    vetor (vetor nao se edita): a receita tem de devolver EXATAMENTE a chegada
    de onde os numeros sairam - qualquer outra clausula, ordem ou comparador
    reprova.
    """
    parametros = {"lances": chegada["janela"]["n"], **PECAS_DE_EXEMPLO}
    primeira = chegada["clausulas"][0]
    if co_tipo in ("xadrez_espia_comer", "xadrez_comer_com", "xadrez_duas_espias"):
        parametros["capturas"] = primeira["valor"]
    if co_tipo in ("xadrez_espia_xeque", "xadrez_xeques_seguidos"):
        parametros["xeques"] = primeira["valor"]
    if co_tipo == "xadrez_nao_perder":
        parametros["peca"] = chegada["clausulas"][1]["chave"].removeprefix("pecas_perdidas_")
    return parametros


@pytest.mark.parametrize("vetor", VETORES, ids=lambda v: v["id"])
def test_a_receita_monta_EXATAMENTE_a_chegada_do_vetor(vetor) -> None:
    receita = RECEITAS_DO_XADREZ[vetor["co_tipo_desafio"]]
    assert vetor["nu_tipo_desafio"] == receita.nu_tipo_desafio
    parametros = _parametros_da_chegada(vetor["co_tipo_desafio"], vetor["js_chegada"])
    assert receita.montar(parametros) == vetor["js_chegada"]


def test_os_vetores_passam_pelos_onze_tipos() -> None:
    """Sem este caso, o parametrizado acima passaria com um tipo sem vetor."""
    assert {v["co_tipo_desafio"] for v in VETORES} == set(TIPOS)


def test_cada_chegada_recebe_o_SEU_dicionario() -> None:
    """⚠️ A clausula da espia viva e uma funcao, e nao uma constante: alterar a
    chegada de um desafio nao pode alterar a de outro."""
    p = {"lances": 8, "capturas": 2, **PECAS_DE_EXEMPLO}
    receita = RECEITAS_DO_XADREZ["xadrez_espia_comer"]
    uma, outra = receita.montar(p), receita.montar(p)
    uma["clausulas"][1]["valor"] = 99
    assert outra["clausulas"][1]["valor"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3. A frase
# ═══════════════════════════════════════════════════════════════════════════


def _espacos_da_frase(frase: str) -> set[str]:
    """Os nomes dos espacos de uma frase ICU: `{lances}`, `{espia, select,`..."""
    return set(re.findall(r"\{(\w+)(?:\}|,)", frase))


@pytest.mark.parametrize("co_tipo", TIPOS)
def test_os_valores_sao_EXATAMENTE_os_espacos_da_frase(co_tipo: str) -> None:
    """🔒 Valor a menos deixa a frase muda no app; valor a mais e um numero que
    a pessoa nunca le e alguem acha que ela le."""
    receita = RECEITAS_DO_XADREZ[co_tipo]
    assert receita.co_chave_objetivo.startswith("desafioObjetivoXadrez")
    frase = FRASES[receita.co_chave_objetivo]
    p = {"lances": 8, "capturas": 2, "xeques": 3, **PECAS_DE_EXEMPLO}
    valores = receita.valores_da_frase(p, "tex")
    assert set(valores) == _espacos_da_frase(frase), co_tipo
    assert valores["personagem"] == "tex"


@pytest.mark.parametrize("co_tipo", TIPOS)
def test_as_pecas_do_cartao_estao_nos_valores(co_tipo: str) -> None:
    """🔒 O cartao de feito repete as pecas do enunciado (`pecas_do_objetivo`,
    T071): uma que o job nao publicasse deixaria o cartao mudo para sempre."""
    receita = RECEITAS_DO_XADREZ[co_tipo]
    entrada = frases_declaradas()[receita.co_chave_objetivo]
    assert entrada["co_jogo"] == "xadrez"
    p = {"lances": 8, "capturas": 2, "xeques": 3, **PECAS_DE_EXEMPLO}
    valores = receita.valores_da_frase(p, "tex")
    for espaco in entrada["pecas_do_objetivo"]:
        assert isinstance(valores.get(espaco), str), (co_tipo, espaco)


def test_sem_comida_o_comer_com_nao_publica_o_espaco() -> None:
    """`comida` e opcional: sem ela o valor nao viaja (o app cai em "pecas"), e
    um `None` no lugar seria um codigo que o `select` nao conhece."""
    receita = RECEITAS_DO_XADREZ["xadrez_comer_com"]
    p = {"lances": 8, "capturas": 2, "come": "cavalo"}
    assert "comida" not in receita.valores_da_frase(p, "tex")
    assert receita.valores_da_frase({**p, "comida": None}, "tex").get("comida") is None
    assert "comida" not in receita.valores_da_frase({**p, "comida": None}, "tex")


# ═══════════════════════════════════════════════════════════════════════════
# 4. O editorial
# ═══════════════════════════════════════════════════════════════════════════


def test_todo_tipo_tem_ao_menos_uma_variante() -> None:
    assert {co_tipo for co_tipo, _ in VARIANTES} == set(TIPOS)


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_todos_saem_na_versao_que_traz_o_jogo(co_tipo, publicacao) -> None:
    """A 1.6.0 (RF-XDR-187): um app 1.5 cai na tela de atualizar."""
    assert VERSAO_MINIMA_DO_XADREZ == "1.6.0"
    assert publicacao.co_versao_minima == VERSAO_MINIMA_DO_XADREZ


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_a_chegada_e_valida_e_usa_so_o_que_o_xadrez_mede(co_tipo, publicacao) -> None:
    """🔒 O avaliador aceita a chegada, e toda medida dela e de tabuleiro, do
    xadrez ou comum a todos os jogos (o medidor do xadrez as produz)."""
    chegada = LinhaDeChegada.de_dado(RECEITAS_DO_XADREZ[co_tipo].montar(_parametros(publicacao)))
    assert chegada.janela.tipo in JANELAS
    assert chegada.janela.tipo == "lances_do_jogador"
    for clausula in chegada.clausulas:
        assert clausula.tipo == "medida", (co_tipo, clausula.tipo)
        linha = CATALOGO[clausula.chave]
        assert linha["co_procedencia"] == "tabuleiro", (co_tipo, clausula.chave)
        assert linha["co_jogo"] in (None, "xadrez"), (co_tipo, clausula.chave)


#: As medidas de quem ainda nao jogou: nada aconteceu.
MEDIDAS_DE_QUEM_NAO_JOGOU = {
    chave: 0
    for chave, linha in CATALOGO.items()
    if linha["co_procedencia"] == "tabuleiro" and linha["co_jogo"] in (None, "xadrez")
}


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_ninguem_cumpre_sem_jogar(co_tipo, publicacao) -> None:
    """⛔ A chegada nao vale antes do primeiro lance. O caso que importa sao os
    tres "Passe N": a espia viva, nenhuma peca perdida e nenhum xeque recebido
    ja valem no inicio, e quem segura e `lances_do_jogador >= N`."""
    chegada = LinhaDeChegada.de_dado(RECEITAS_DO_XADREZ[co_tipo].montar(_parametros(publicacao)))
    assert not avaliar(chegada, MEDIDAS_DE_QUEM_NAO_JOGOU)


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_so_o_mate_encerra_a_partida(co_tipo, publicacao) -> None:
    """🔒 `ic_chegada_encerra_partida` e TRUE se e so se a chegada pede
    `vitoria` (o mate). Nos outros dez o desafio fecha no meio, e o app deixa a
    pessoa continuar jogando."""
    chaves = {
        c["chave"]
        for c in RECEITAS_DO_XADREZ[co_tipo].montar(_parametros(publicacao))["clausulas"]
    }
    assert publicacao.ic_chegada_encerra_partida is ("vitoria" in chaves)
    assert ("vitoria" in chaves) is (co_tipo == "xadrez_dar_mate")


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_o_teto_cobre_a_janela_e_o_piso_cabe_nele(co_tipo, publicacao) -> None:
    """O gabarito cabe na janela (N lances da pessoa = `2N - 1` meios-lances),
    e um piso acima do teto nunca geraria candidato."""
    n = publicacao.parametros["lances"]
    assert publicacao.nu_maximo_de_meios_lances == 2 * n - 1
    assert publicacao.nu_minimo_de_meios_lances <= publicacao.nu_maximo_de_meios_lances


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_os_limites_do_PRD(co_tipo, publicacao) -> None:
    """PRD §8.4: os xeques seguidos vao no maximo a 4 (com mais, a repeticao
    tripla pode empatar antes), e o mate e em ate 5 lances."""
    if co_tipo == "xadrez_xeques_seguidos":
        assert 2 <= publicacao.parametros["xeques"] <= 4
    if co_tipo == "xadrez_dar_mate":
        assert publicacao.parametros["lances"] <= 5


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_as_medidas_de_saida_fecham(co_tipo, publicacao) -> None:
    """🔒 Os pesos somam 1, toda chave e do catalogo e de tabuleiro, e cada
    normalizacao tem os seus campos (`conferir`, a mesma do job)."""
    conferir(publicacao.medidas(_parametros(publicacao)))


def test_o_nao_perder_pontua_a_peca_da_POSICAO() -> None:
    """A medida que pontua e a do tipo de peca que a posicao escolheu."""
    publicacao = EDITORIAL_FORA_DO_AR["xadrez_nao_perder"][0]
    for peca in ("peao", "torre", "dama"):
        linhas = publicacao.medidas({**_parametros(publicacao), "peca": peca})
        assert linhas[0]["co_feito"] == f"pecas_perdidas_{peca}"

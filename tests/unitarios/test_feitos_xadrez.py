"""T069 (spec 012) - os feitos do xadrez e os vetores do juiz.

═══════════════════════════════════════════════════════════════════════════
TRÊS NÍVEIS, E SÓ DOIS PODEM PULAR
═══════════════════════════════════════════════════════════════════════════

| nível | o que confere | pode pular? |
|---|---|---|
| **a medida** | a forma do arquivo, os casos obrigatórios, e a conta de `feitos_xadrez.medir` sobre os FATOS gravados em cada vetor (sem o executável) | ⛔ **nunca** |
| **o motor** | que o executável de hoje ainda devolve os mesmos fatos, e que o juiz inteiro (reprodução + medida) dá o esperado | sim, só sem o executável compilado |
| **as cópias** | o arquivo do app = o daqui, byte a byte | sim, sem o repositório do app ao lado |

O primeiro nível é o que importa no CI: a regra da troca, da sequência de
xeques e da última fileira é conferida ali, sobre fatos que não mudam.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from motores.juiz import julgar_desafio
from motores.nucleo.chegada import LinhaDeChegada
from motores.nucleo.medidor_por_fita import julgar
from motores.xadrez import contrato_xadrez, feitos_xadrez
from motores.xadrez.jogador_xadrez import (
    JogadorXadrez,
    MotorDartIndisponivel,
    MotorXadrezRecusou,
)

RAIZ = Path(__file__).resolve().parents[2]
COPIA_DAQUI = RAIZ / "contratos" / "vetores-juiz-xadrez.json"
COPIA_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "test"
    / "modulos"
    / "jogos"
    / "xadrez"
    / "vetores_juiz_xadrez.json"
)
MANIFESTO_DO_CATALOGO = RAIZ / "contratos" / "catalogo_feitos.json"

#: Os casos de `contracts/desafio-xadrez.md` §3, escritos aqui À MÃO de
#: propósito: se o gerador perdesse um, a lista dele perderia junto.
CASOS_DO_CONTRATO = {
    "espia_comida_en_passant",
    "torre_espia_no_roque",
    "peao_espiao_promovido",
    "xeque_descoberto_da_espia",
    "troca_ordem_1",
    "troca_ordem_2",
    "troca_ordem_2_sem_retomada",
    "repeticao_tripla_nos_xeques_seguidos",
}

#: Os onze tipos (`data-model.md` §3.1), também à mão.
TIPOS_DO_XADREZ = {
    "xadrez_espia_comer": 60,
    "xadrez_espia_proteger": 61,
    "xadrez_espia_atravessar": 62,
    "xadrez_espia_xeque": 63,
    "xadrez_espia_alvo": 64,
    "xadrez_comer_com": 65,
    "xadrez_nao_perder": 66,
    "xadrez_xeques_seguidos": 67,
    "xadrez_sem_levar_xeque": 68,
    "xadrez_troca": 69,
    "xadrez_dar_mate": 70,
}

#: As três medidas comuns a todo jogo (`lances_do_jogador`, `vitoria`, `empate`).
UNIVERSAIS = {"lances_do_jogador", "vitoria", "empate"}

#: Os dois marcos do xadrez: valem 0 ou 1, e uma vez 1 ficam 1.
MARCOS = {"espia_na_ultima_fileira", "alvo_comido_pela_espia"}


@pytest.fixture(scope="module")
def documento() -> dict:
    """O arquivo daqui. ⛔ Ausência é falha, e não motivo para pular."""
    assert COPIA_DAQUI.is_file(), (
        f"os vetores não estão em {COPIA_DAQUI}. Gere-os com "
        "`.venv\\Scripts\\python scripts\\gerar_vetores_juiz_xadrez.py`."
    )
    return json.loads(COPIA_DAQUI.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def motor():
    """O executável, ou o pulo com a receita (só o nível "o motor" o usa)."""
    try:
        with JogadorXadrez() as jogador:
            yield jogador
    except MotorDartIndisponivel as erro:
        pytest.skip(f"sem o executável do xadrez compilado: {erro}")


def _validos(documento: dict) -> list[dict]:
    """Os vetores cuja fita é uma partida (todos menos os `dado_invalido`)."""
    return [v for v in documento["vetores"] if v["esperado"]["veredito"] != "dado_invalido"]


def _passos(vetor: dict) -> list[dict]:
    """Os passos gravados no vetor, no formato que `feitos_xadrez.medir` lê."""
    return [
        {"lance": l["lance"], "fatos": l["fatos"], "marcas": l["marcas"]}
        for l in vetor["lances"]
        if "fatos" in l
    ]


def _julgar_pelos_fatos_gravados(vetor: dict):
    """O julgamento do vetor SEM o executável: a medida pura sobre os fatos.

    É o `julgar` do núcleo, o mesmo que o juiz chama, com o `medir_ate` lendo
    os passos do arquivo em vez de os pedir ao motor.
    """
    passos = _passos(vetor)
    return julgar(
        chegada=LinhaDeChegada.de_dado(vetor["js_chegada"]),
        fita=vetor["lances"],
        jogador=vetor["jogador"],
        medir_ate=lambda quantos: feitos_xadrez.medir(
            vetor["js_posicao_inicial"], passos[:quantos]
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. A medida (nunca pula)
# ═══════════════════════════════════════════════════════════════════════════


def test_os_casos_obrigatorios_do_contrato_tem_vetor(documento):
    """Cada caso do §3 tem pelo menos um vetor, e o arquivo declara os mesmos."""
    assert set(documento["casos_obrigatorios"]) == CASOS_DO_CONTRATO
    marcados = {v["caso_obrigatorio"] for v in documento["vetores"]}
    assert CASOS_DO_CONTRATO <= marcados, sorted(CASOS_DO_CONTRATO - marcados)


def test_a_forma_do_arquivo(documento):
    """Ids únicos, os onze tipos com os números da 0040, os três vereditos."""
    assert documento["versao"] == 1
    ids = [v["id"] for v in documento["vetores"]]
    assert len(ids) == len(set(ids))
    for vetor in documento["vetores"]:
        assert vetor["co_jogo"] == "xadrez"
        assert TIPOS_DO_XADREZ[vetor["co_tipo_desafio"]] == vetor["nu_tipo_desafio"]
        assert vetor["co_modalidade"] in contrato_xadrez.modalidades_declaradas()
        assert vetor["js_posicao_inicial"]["cor_da_pessoa"] in {"branca", "preta"}
        assert vetor["esperado"]["veredito"] in {"cumpriu", "nao_cumpriu", "dado_invalido"}
        # A chegada é dado do vocabulário fechado: o leitor de produção a aceita.
        LinhaDeChegada.de_dado(vetor["js_chegada"])


def test_todo_tipo_tem_um_vetor_que_cumpre_e_um_que_nao(documento):
    """A regra 1 dos vetores da 009: sem o "não cumpre por pouco", dois lados
    que erram igual concordariam."""
    por_tipo: dict[str, set[str]] = {}
    for vetor in documento["vetores"]:
        por_tipo.setdefault(vetor["co_tipo_desafio"], set()).add(vetor["esperado"]["veredito"])
    assert set(por_tipo) == set(TIPOS_DO_XADREZ)
    for tipo, vereditos in por_tipo.items():
        assert {"cumpriu", "nao_cumpriu"} <= vereditos, (tipo, vereditos)
    assert any(v["esperado"]["veredito"] == "dado_invalido" for v in documento["vetores"])


def test_as_chaves_sao_as_do_catalogo(documento):
    """As 19 medidas do xadrez são exatamente as do manifesto do catálogo, e o
    extrato de todo vetor válido traz as 22 (zero também é medida)."""
    catalogo = json.loads(MANIFESTO_DO_CATALOGO.read_text(encoding="utf-8"))
    do_xadrez = {f["co_feito"] for f in catalogo["feitos"] if f["co_jogo"] == "xadrez"}
    assert len(do_xadrez) == 19
    assert set(feitos_xadrez.CHAVES_DAS_MEDIDAS) == do_xadrez | UNIVERSAIS
    assert documento["chaves_das_medidas"] == list(feitos_xadrez.CHAVES_DAS_MEDIDAS)
    for vetor in _validos(documento):
        assert set(vetor["esperado"]["feitos"]) == set(feitos_xadrez.CHAVES_DAS_MEDIDAS)


#: Os ids dos vetores válidos, lidos na coleta para o `parametrize` dar um caso
#: por vetor. Sem o arquivo a lista sai vazia, e quem reprova é a fixture
#: `documento` dos outros testes (ausência é falha, e não pulo).
_IDS_VALIDOS = (
    [
        v["id"]
        for v in json.loads(COPIA_DAQUI.read_text(encoding="utf-8"))["vetores"]
        if v["esperado"]["veredito"] != "dado_invalido"
    ]
    if COPIA_DAQUI.is_file()
    else []
)


@pytest.mark.parametrize("identificador", _IDS_VALIDOS)
def test_a_medida_sobre_os_fatos_gravados_da_o_esperado(documento, identificador, monkeypatch):
    """Cada vetor válido, julgado SÓ pelos fatos do arquivo: o veredito, as 22
    medidas e o lance em que o objetivo caiu.

    ⚠️ O executável é DESLIGADO aqui (`jogador_compartilhado` explode): é a
    prova de que `medir` é pura, e o que deixa este nível rodar no CI.
    """
    vetor = next(v for v in documento["vetores"] if v["id"] == identificador)

    def sem_motor():
        raise AssertionError("a medida pediu o executável")

    monkeypatch.setattr(feitos_xadrez, "jogador_compartilhado", sem_motor)
    julgamento = _julgar_pelos_fatos_gravados(vetor)
    esperado = vetor["esperado"]
    assert julgamento.veredito == esperado["veredito"]
    assert julgamento.feitos == esperado["feitos"]
    assert julgamento.nu_lance_cumpre_desafio == esperado["nu_lance_cumpre_desafio"]


def test_as_19_so_crescem_ao_longo_da_fita(documento):
    """A coluna "evolução" da `data-model.md` §3.2: nenhuma das 19 diminui de
    um prefixo para o seguinte, e os dois marcos ficam 0 ou 1."""
    so_crescem = set(feitos_xadrez.CHAVES_DAS_MEDIDAS) - UNIVERSAIS
    for vetor in _validos(documento):
        passos = _passos(vetor)
        anterior = feitos_xadrez.medir(vetor["js_posicao_inicial"], [])
        for quantos in range(1, len(passos) + 1):
            agora = feitos_xadrez.medir(vetor["js_posicao_inicial"], passos[:quantos])
            for chave in so_crescem:
                assert agora[chave] >= anterior[chave], (vetor["id"], quantos, chave)
            for chave in MARCOS:
                assert agora[chave] in (0, 1), (vetor["id"], chave)
            anterior = agora


def test_sem_marcas_as_medidas_da_espia_sao_zero(documento):
    """Uma partida sem espiã nem alvo mede zero neles, e não erro."""
    vetor = next(v for v in documento["vetores"] if v["id"] == "xadrez-dar-mate-em-4")
    medidas = feitos_xadrez.medir(vetor["js_posicao_inicial"], _passos(vetor))
    for chave in ("capturas_da_espia", "xeques_da_espia", "espia_comida",
                  "espia_na_ultima_fileira", "alvo_comido_pela_espia",
                  "capturas_da_classe_marcada", "trocas_feitas"):
        assert medidas[chave] == 0


def test_uma_captura_so_conta_uma_troca():
    """A pessoa que retoma o cavalo com OUTRO bispo cumpre as duas ordens no
    mesmo lance; é uma troca, e não duas (`_fechou_troca`)."""
    posicao = {"cor_da_pessoa": "branca", "troca": {"minha": "bispo", "dele": "cavalo"}}
    passos = [
        # Fatos escritos à mão no formato do motor: o teste é da CONTA.
        {"fatos": {"peca_movida": "bispo", "para": "e4", "comida": None, "xeque_por": []}},
        {"fatos": {"peca_movida": "cavalo", "para": "e4",
                   "comida": {"peca": "bispo", "casa": "e4"}, "xeque_por": []}},
        {"fatos": {"peca_movida": "bispo", "para": "e4",
                   "comida": {"peca": "cavalo", "casa": "e4"}, "xeque_por": []}},
    ]
    assert feitos_xadrez.medir(posicao, passos)["trocas_feitas"] == 1


def test_a_ordem_1_exige_comer_a_peca_que_comeu():
    """Depois de o cavalo comer o bispo, comer OUTRO cavalo (noutra casa) não
    fecha a troca da ordem 1."""
    posicao = {"cor_da_pessoa": "branca", "troca": {"minha": "torre", "dele": "cavalo"}}
    passos = [
        {"fatos": {"peca_movida": "rei", "para": "d1", "comida": None, "xeque_por": []}},
        {"fatos": {"peca_movida": "cavalo", "para": "e4",
                   "comida": {"peca": "torre", "casa": "e4"}, "xeque_por": []}},
        {"fatos": {"peca_movida": "dama", "para": "g6",
                   "comida": {"peca": "cavalo", "casa": "g6"}, "xeque_por": []}},
    ]
    assert feitos_xadrez.medir(posicao, passos)["trocas_feitas"] == 0
    passos[2]["fatos"]["para"] = "e4"
    passos[2]["fatos"]["comida"]["casa"] = "e4"
    assert feitos_xadrez.medir(posicao, passos)["trocas_feitas"] == 1


def test_a_ordem_2_conta_tambem_no_meio_da_partida():
    """Os vetores da ordem 2 comem no 1º lance; aqui a captura vem no 3º, com
    um lance do adversário antes (que não comeu nada)."""
    posicao = {"cor_da_pessoa": "branca", "troca": {"minha": "bispo", "dele": "cavalo"}}
    passos = [
        {"fatos": {"peca_movida": "rei", "para": "d1", "comida": None, "xeque_por": []}},
        {"fatos": {"peca_movida": "peao", "para": "h6", "comida": None, "xeque_por": []}},
        {"fatos": {"peca_movida": "bispo", "para": "f6",
                   "comida": {"peca": "cavalo", "casa": "f6"}, "xeque_por": []}},
    ]
    assert feitos_xadrez.medir(posicao, passos)["trocas_feitas"] == 1


def test_a_classe_comida_tambem_e_conferida():
    """"Coma peões com o cavalo": o cavalo que come um BISPO não conta. Sem
    `comida` nos parâmetros, qualquer peça comida pelo cavalo conta."""
    passos = [
        {"fatos": {"peca_movida": "cavalo", "para": "b5",
                   "comida": {"peca": "bispo", "casa": "b5"}, "xeque_por": []}},
    ]
    com_peao = {"cor_da_pessoa": "branca", "classes": {"come": "cavalo", "comida": "peao"}}
    sem_comida = {"cor_da_pessoa": "branca", "classes": {"come": "cavalo"}}
    assert feitos_xadrez.medir(com_peao, passos)["capturas_da_classe_marcada"] == 0
    assert feitos_xadrez.medir(sem_comida, passos)["capturas_da_classe_marcada"] == 1


def test_posicao_sem_cor_e_recusada():
    """Sem `cor_da_pessoa` não se sabe de quem é o desafio: `ValueError`."""
    with pytest.raises(ValueError, match="cor_da_pessoa"):
        feitos_xadrez.medir({"cor_da_pessoa": "azul"}, [])


def test_fita_fora_da_alternancia_e_dado_invalido(documento):
    """No xadrez a vez alterna: uma fita que diz outra coisa não é partida. A
    conferência vem ANTES do executável (este teste não precisa dele)."""
    vetor = next(v for v in documento["vetores"] if v["id"] == "xadrez-dar-mate-em-4")
    fita = [{k: l[k] for k in ("n", "jogador", "lance")} for l in vetor["lances"]]
    fita[1]["jogador"] = 1
    julgamento = julgar_desafio(
        co_jogo="xadrez",
        js_posicao_inicial=vetor["js_posicao_inicial"],
        js_chegada=vetor["js_chegada"],
        fita=fita,
    )
    assert julgamento.veredito == "dado_invalido"
    assert "alterna" in julgamento.de_motivo


def test_modalidade_desconhecida_e_dado_invalido(documento):
    """A modalidade vem da posição, e o contrato a confere antes do motor."""
    vetor = next(v for v in documento["vetores"] if v["id"] == "xadrez-dar-mate-em-4")
    posicao = dict(vetor["js_posicao_inicial"], modalidade="sonda_que_nao_existe")
    julgamento = julgar_desafio(
        co_jogo="xadrez",
        js_posicao_inicial=posicao,
        js_chegada=vetor["js_chegada"],
        fita=[{k: l[k] for k in ("n", "jogador", "lance")} for l in vetor["lances"]],
    )
    assert julgamento.veredito == "dado_invalido"


# ═══════════════════════════════════════════════════════════════════════════
# 2. O motor (pula só sem o executável)
# ═══════════════════════════════════════════════════════════════════════════


def test_o_executavel_ainda_devolve_os_fatos_gravados(documento, motor):
    """Cada vetor reproduzido pelo executável de hoje dá os mesmos fatos e as
    mesmas marcas, e o lance recusado é recusado com o mesmo código."""
    for vetor in documento["vetores"]:
        lances = [l["lance"] for l in vetor["lances"]]
        gravados = _passos(vetor)
        reproduzidos = feitos_xadrez.reproduzir(
            vetor["js_posicao_inicial"], lances[: len(gravados)], motor=motor
        )
        assert reproduzidos == gravados, vetor["id"]
        if len(gravados) < len(lances):
            recusa = vetor["lances"][len(gravados)]["recusa"]
            with pytest.raises(MotorXadrezRecusou) as erro:
                feitos_xadrez.reproduzir(
                    vetor["js_posicao_inicial"], lances[: len(gravados) + 1], motor=motor
                )
            assert erro.value.codigo == recusa, vetor["id"]


def test_o_juiz_inteiro_da_o_esperado(documento, motor):
    """`julgar_desafio`, a porta de produção: reproduz pelo executável e mede."""
    for vetor in documento["vetores"]:
        julgamento = julgar_desafio(
            co_jogo="xadrez",
            js_posicao_inicial=vetor["js_posicao_inicial"],
            js_chegada=vetor["js_chegada"],
            fita=[{k: l[k] for k in ("n", "jogador", "lance")} for l in vetor["lances"]],
            jogador=vetor["jogador"],
        )
        esperado = vetor["esperado"]
        assert julgamento.veredito == esperado["veredito"], vetor["id"]
        assert julgamento.feitos == esperado["feitos"], vetor["id"]
        assert julgamento.nu_lance_cumpre_desafio == esperado["nu_lance_cumpre_desafio"]


def test_a_vez_do_fen_tem_de_ser_a_da_pessoa(documento, motor):
    """Uma posição que diz "a pessoa joga de pretas" com a vez das brancas no
    FEN seria julgada do lado errado: a reprodução recusa."""
    vetor = next(v for v in documento["vetores"] if v["id"] == "xadrez-dar-mate-em-4")
    posicao = dict(vetor["js_posicao_inicial"], cor_da_pessoa="preta")
    with pytest.raises(ValueError, match="lado errado"):
        feitos_xadrez.reproduzir(posicao, ["e2e4"], motor=motor)


def test_o_gerador_reproduz_o_arquivo(documento, motor):
    """O arquivo é o que o gerador escreve hoje: um vetor editado à mão, ou um
    fato do motor que mudou, aparece aqui."""
    import importlib.util

    caminho = RAIZ / "scripts" / "gerar_vetores_juiz_xadrez.py"
    especificacao = importlib.util.spec_from_file_location("gerar_vetores_juiz_xadrez", caminho)
    gerador = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(gerador)
    assert gerador.montar(motor) == documento


# ═══════════════════════════════════════════════════════════════════════════
# 3. As cópias (pula sem o repositório do app ao lado)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_copia_do_app_e_byte_identica():
    """O medidor do app (T070) lê a cópia de lá; ela tem de ser esta."""
    if not COPIA_DO_APP.is_file():
        pytest.skip(f"sem a cópia do app em {COPIA_DO_APP}")
    daqui = hashlib.sha256(COPIA_DAQUI.read_bytes()).hexdigest()
    do_app = hashlib.sha256(COPIA_DO_APP.read_bytes()).hexdigest()
    assert daqui == do_app, (
        "a cópia do app divergiu; rode `scripts\\gerar_vetores_juiz_xadrez.py`, "
        "que escreve as duas"
    )

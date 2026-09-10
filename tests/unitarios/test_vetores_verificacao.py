"""T027 - os vetores de verificacao: SHA-256 das duas copias e forma do arquivo.

═══════════════════════════════════════════════════════════════════════════
DOIS NIVEIS, E SO UM DELES PODE PULAR
═══════════════════════════════════════════════════════════════════════════

| nivel | o que confere | pode pular? |
|---|---|---|
| **CI** | a forma do arquivo daqui: ids unicos, vocabularios fechados, a regra dos tres vetores por tipo | ⛔ **nunca** |
| **local** | as duas copias byte a byte, por SHA-256 | sim, com motivo, quando o frontend nao esta no disco |

E o mesmo desenho do RF-DES-143a, e pela mesma razao: no CI cada repositorio roda
sozinho. Uma comparacao entre repositorios **nao e executavel** la — e um teste
que exigisse o impossivel seria desligado na primeira semana.

⚠️ **O nivel local nao e decoracao.** E ele que pega a copia editada a mao: quem
mexer num vetor daqui e esquecer de rodar o gerador vai ver o vermelho na propria
maquina, antes do commit.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
COPIA_DAQUI = RAIZ / "contratos" / "vetores-verificacao-desafio.json"
COPIA_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "contracts"
    / "vetores-verificacao-desafio.json"
)

# Os tres vocabularios fechados de `js_chegada` (RF-DES-191). Escritos aqui a
# mao de proposito: e o fechamento deles que mantem a linha de chegada **dado**
# em vez de codigo publicado no aparelho dos outros (RF-DES-192).
JANELAS = {
    "partida",
    "lances_do_jogador",
    "turnos_do_jogador",
    "turnos_do_adversario",
}
COMPARADORES = {
    "maior_ou_igual",
    "menor_ou_igual",
    "igual",
    "diferente",
    "em",
    "fora_de",
}
TIPOS_DE_CLAUSULA = {"medida", "predicado"}

VEREDITOS = {"cumpriu", "nao_cumpriu", "dado_invalido"}


@pytest.fixture(scope="module")
def documento() -> dict:
    """O arquivo daqui. ⛔ Ausencia e falha, nao motivo para pular."""
    assert COPIA_DAQUI.is_file(), (
        f"os vetores nao estao em {COPIA_DAQUI}. Gere-os com "
        "`.venv\\Scripts\\python scripts/gerar_vetores_verificacao.py`."
    )
    return json.loads(COPIA_DAQUI.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# 1. Nivel LOCAL — as duas copias
# ═══════════════════════════════════════════════════════════════════════════


def test_as_duas_copias_sao_byte_identicas() -> None:
    """SHA-256 das duas copias. ⚠️ Pula com motivo se o frontend nao estiver aqui.

    ⚠️ E o unico teste deste arquivo que pode pular, e o motivo esta escrito no
    proprio `skip`: no CI do backend o outro repositorio nao existe no disco, e um
    teste que exigisse o impossivel seria desligado — e desligado ele nao guarda
    nem o que podia.
    """
    if not COPIA_DO_APP.is_file():
        pytest.skip(
            "o repositorio arena-sagaz-frontend nao esta no disco ao lado deste "
            "(esperado em CI). A conferencia de forma continua rodando."
        )

    daqui = COPIA_DAQUI.read_bytes()
    do_app = COPIA_DO_APP.read_bytes()
    assert hashlib.sha256(daqui).hexdigest() == hashlib.sha256(do_app).hexdigest(), (
        "as duas copias dos vetores divergiram.\n"
        f"  {COPIA_DAQUI}: {len(daqui)} bytes\n"
        f"  {COPIA_DO_APP}: {len(do_app)} bytes\n"
        "Conserto: rode `python scripts/gerar_vetores_verificacao.py`, que "
        "escreve as duas. ⛔ Nao edite uma delas a mao."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Nivel CI — a forma do arquivo. ⛔ Nada aqui pula.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_varredura_enxerga_alguma_coisa(documento: dict) -> None:
    """Um cadeado que percorre uma lista vazia passa sempre."""
    assert documento["versao"] >= 1
    assert len(documento["vetores"]) >= 6


def test_todo_identificador_e_unico(documento: dict) -> None:
    """O `id` e como um vetor e citado numa falha — repetido, ele mente.

    ⚠️ E ele tambem e a chave da regra 4 do contrato: *vetor nunca e apagado nem
    editado*. Dois vetores com o mesmo `id` tornariam impossivel dizer qual dos
    dois o passado usou.
    """
    contagem = Counter(v["id"] for v in documento["vetores"])
    repetidos = {k: n for k, n in contagem.items() if n > 1}
    assert not repetidos, f"identificadores repetidos: {repetidos}"


def test_todo_veredito_esta_no_vocabulario(documento: dict) -> None:
    """Tres valores, e so tres.

    ⚠️ `dado_invalido` **nao e** um terceiro grau de "nao cumpriu": e a recusa da
    fita. Lance ilegal e dado corrompido, e tratar os dois como a mesma coisa
    faria uma sincronizacao com defeito parecer uma tentativa fracassada (D-05).
    """
    fora = {
        v["id"]: v["esperado"]["veredito"]
        for v in documento["vetores"]
        if v["esperado"]["veredito"] not in VEREDITOS
    }
    assert not fora, f"vereditos fora do vocabulario: {fora}"


def test_os_tres_vocabularios_de_chegada_sao_fechados(documento: dict) -> None:
    """🔒 A fronteira entre publicar DADO e publicar CODIGO (RF-DES-192).

    ⛔ Ficam de fora, de proposito: `OU`/`NAO` aninhados, aritmetica entre chaves,
    chave livre e expressao avaliada em tempo de execucao. Um vetor que usasse
    qualquer um deles seria a primeira pedra do caminho que a spec fechou.
    """
    problemas: list[str] = []
    for vetor in documento["vetores"]:
        chegada = vetor["js_chegada"]
        janela = chegada["janela"]["tipo"]
        if janela not in JANELAS:
            problemas.append(f"{vetor['id']}: janela {janela!r}")

        # ⚠️ Sempre uma CONJUNCAO: havendo mais de uma clausula, todas precisam
        # valer. Nao ha campo para dizer "ou" — e essa ausencia e a decisao.
        assert isinstance(chegada["clausulas"], list)
        for clausula in chegada["clausulas"]:
            if clausula["tipo"] not in TIPOS_DE_CLAUSULA:
                problemas.append(f"{vetor['id']}: clausula {clausula['tipo']!r}")
            if clausula["comparador"] not in COMPARADORES:
                problemas.append(
                    f"{vetor['id']}: comparador {clausula['comparador']!r}"
                )
    assert not problemas, "fora do vocabulario fechado: " + "; ".join(problemas)


def test_cada_tipo_presente_tem_os_TRES_casos(documento: dict) -> None:
    """🔒 A regra 1 do contrato: cumpre · nao cumpre por pouco · dado invalido.

    ⚠️ **O do meio e o que importa mais.** "Cumpriu" e facil de acertar nos dois
    lados; onde duas implementacoes divergem de verdade e na **fronteira** — o
    parametro menos um, o limite da janela, o comparador trocado por `>`.

    ⚠️ Este teste cobra so dos tipos **presentes** no arquivo. Quem cobra que todo
    tipo publicavel tenha vetor e o gerador (regra 2 do contrato: tipo sem vetor
    nao e publicavel) — aqui nao daria: o arquivo nao sabe quais tipos existem.
    """
    por_tipo: dict[str, set[str]] = {}
    for vetor in documento["vetores"]:
        por_tipo.setdefault(vetor["co_tipo_desafio"], set()).add(
            vetor["esperado"]["veredito"]
        )

    incompletos = {
        tipo: sorted(VEREDITOS - vereditos)
        for tipo, vereditos in por_tipo.items()
        if vereditos != VEREDITOS
    }
    assert not incompletos, (
        f"tipos sem os tres casos (faltando): {incompletos}"
    )


def test_o_invalido_nao_declara_feitos(documento: dict) -> None:
    """Fita recusada nao produz medida — declarar uma seria inventar dado.

    Se um dia um vetor invalido trouxer feitos, alguem confundiu "a fita esta
    corrompida" com "a pessoa nao conseguiu", e o extrato de XP passaria a ter
    linhas de uma partida que o servidor nao consegue reproduzir.
    """
    com_feitos = [
        v["id"]
        for v in documento["vetores"]
        if v["esperado"]["veredito"] == "dado_invalido" and v["esperado"]["feitos"]
    ]
    assert not com_feitos, f"vetores invalidos com feitos: {com_feitos}"


def test_todo_vetor_valido_declara_pelo_menos_uma_medida(documento: dict) -> None:
    """⚠️ `esperado.feitos` nao e enfeite.

    Dois lados podem concordar no **veredito** e discordar na **medida** — e e a
    medida que vira `Q`, que vira a ordem do quadro. Um vetor sem feitos provaria
    metade do que precisa provar.
    """
    sem_feitos = [
        v["id"]
        for v in documento["vetores"]
        if v["esperado"]["veredito"] != "dado_invalido" and not v["esperado"]["feitos"]
    ]
    assert not sem_feitos, f"vetores sem medida declarada: {sem_feitos}"


def test_a_clausula_de_medida_aponta_para_o_catalogo(documento: dict) -> None:
    """🔒 Chave de medida tem de existir em `tb902_catalogo_feito`.

    Uma chave inventada aqui produziria um desafio que **nunca** pode ser
    cumprido: o medidor procuraria uma medida que nenhum jogo produz, e o
    resultado seria "nao cumpriu" para todo mundo, sem erro nenhum.
    """
    manifesto = json.loads(
        (RAIZ / "contratos" / "catalogo_feitos.json").read_text(encoding="utf-8")
    )
    conhecidas = {linha["co_feito"] for linha in manifesto["feitos"]}

    desconhecidas: list[str] = []
    for vetor in documento["vetores"]:
        for clausula in vetor["js_chegada"]["clausulas"]:
            if clausula["tipo"] == "medida" and clausula["chave"] not in conhecidas:
                desconhecidas.append(f"{vetor['id']}: {clausula['chave']}")
        # O mesmo vale para as medidas declaradas em `esperado.feitos`.
        for chave in vetor["esperado"]["feitos"]:
            if chave not in conhecidas:
                desconhecidas.append(f"{vetor['id']}: esperado.{chave}")
    assert not desconhecidas, f"chaves fora do catalogo: {desconhecidas}"


def test_o_formato_da_posicao_combina_com_o_jogo(documento: dict) -> None:
    """`sequencia_lances` no Pontinhos, `fen` nas damas — e a razao e do jogo.

    Nas damas cada peca carrega a sua cor na propria casa, e a FEN traz de quem e
    a vez no prefixo. No Pontinhos a posse de uma caixa e **historico**: o
    tabuleiro fisico nao guarda quem a fechou, e por isso a posicao so existe como
    sequencia.
    """
    esperado = {"pontinhos": "sequencia_lances", "damas": "fen"}
    errados = {
        v["id"]: v["co_formato_posicao"]
        for v in documento["vetores"]
        if v["co_formato_posicao"] != esperado.get(v["co_jogo"])
    }
    assert not errados, f"formato de posicao incompativel com o jogo: {errados}"


def test_a_posicao_do_pontinhos_declara_vez_e_placar(documento: dict) -> None:
    """Os dois sao DERIVADOS, e estao na linha como conferencia.

    Quem le reconstroi a sequencia e compara; divergiu, nao publica. Sem eles, o
    vetor descreveria uma posicao ambigua — no Pontinhos, o mesmo desenho de
    tabuleiro e compativel com a vez de qualquer um dos dois jogadores, e a
    diferenca muda o desafio inteiro.
    """
    for vetor in documento["vetores"]:
        if vetor["co_jogo"] != "pontinhos":
            continue
        posicao = vetor["js_posicao_inicial"]
        assert posicao["vez_de"] in (1, -1), vetor["id"]
        assert set(posicao["placar"]) == {"j1", "j2"}, vetor["id"]
        assert isinstance(posicao["lances"], list), vetor["id"]


def test_o_arquivo_diz_que_e_gerado(documento: dict) -> None:
    """Um JSON sem procedencia vira "arquivo que alguem editou a mao um dia"."""
    assert "gerar_vetores_verificacao.py" in documento["de_documento"]
    assert "nao edite a mao" in documento["de_documento"]

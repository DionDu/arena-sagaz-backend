"""A modalidade-sonda atravessa o jogador do xadrez (spec 012, T065; R-24, SC-011).

A sonda é uma modalidade de MENTIRA (`tests/dados/contrato_sonda_xadrez.json`,
cópia do contrato de teste da T023): o xadrez com os 50 lances trocados por 30 e
**sem a Pita**. Aqui ela entra pelo mesmo `contrato_xadrez` e pelo mesmo
`JogadorXadrez` da modalidade de verdade, e joga uma partida inteira pelo
executável. Se fazê-la passar exigisse uma linha de produção que a citasse, seria
o defeito que ela existe para achar: o conserto é na produção, nunca na sonda.

E o cadeado de fonte: o nome da modalidade de hoje, e o da sonda, não aparecem
entre aspas em `motores/xadrez/` nem em `job/`.

⚠️ Os casos que jogam PULAM com motivo sem o executável compilado
(`scripts/compilar_motor_xadrez.py`), como os do jogador.

⚠️ **Este arquivo CRESCE** nas fases seguintes (os feitos e o juiz do desafio);
não se refaz.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from motores.nucleo.papeis import NivelDeMotor
from motores.xadrez import contrato_xadrez as cx
from motores.xadrez import jogador_xadrez as jx

RAIZ = Path(__file__).resolve().parents[2]
CONTRATO_DA_SONDA = RAIZ / "tests" / "dados" / "contrato_sonda_xadrez.json"

#: O nome da modalidade de mentira, lido do PRÓPRIO contrato de teste (a única
#: que ele declara), e não escrito aqui.
SONDA = next(iter(json.loads(CONTRATO_DA_SONDA.read_text("utf-8"))["por_modalidade"]))

#: A cópia do laboratório, quando os repositórios moram lado a lado.
NO_LABORATORIO = (
    RAIZ.parent / "ia" / "jogos" / "jogo_xadrez" / "motor_rust" / "tests" / "dados"
    / "contrato_sonda_xadrez.json"
)

#: Um freio para a partida (as regras do fim já a terminam muito antes).
LIMITE_DE_MEIOS_LANCES = 600


@pytest.fixture
def na_sonda(monkeypatch):
    """Aponta o contrato do backend para o da sonda, só durante o teste.

    `monkeypatch` desfaz a troca do caminho no fim; o cache dos bytes do
    contrato é limpo antes (para ler a sonda) e depois (para o próximo teste
    voltar ao espelho).
    """
    monkeypatch.setattr(cx, "CAMINHO_DO_CONTRATO", CONTRATO_DA_SONDA)
    cx._bytes_do_contrato.cache_clear()
    yield
    cx._bytes_do_contrato.cache_clear()


def semente_do_lance(mestra: int, ordem: int) -> int:
    """A fórmula do contrato (a mesma do app): ordem a partir de 1."""
    return (mestra + ordem * 2654435761) & 0x7FFFFFFF


@pytest.mark.skipif(not NO_LABORATORIO.is_file(), reason="o laboratorio nao esta ao lado")
def test_a_copia_e_a_do_laboratorio():
    # Sem o CR: o laboratório pode estar num checkout que converteu o fim de
    # linha; o que importa é o conteúdo linha a linha.
    def sem_cr(p: Path) -> bytes:
        return p.read_bytes().replace(b"\r\n", b"\n")

    assert sem_cr(CONTRATO_DA_SONDA) == sem_cr(NO_LABORATORIO)


def test_a_sonda_entra_pelo_mesmo_contrato_e_perde_a_pita(na_sonda):
    assert cx.modalidades_declaradas() == (SONDA,)
    # Sem a Pita no contrato, o degrau dela some; os outros três ficam.
    assert cx.niveis_disponiveis(SONDA) == (NivelDeMotor.CACAU, NivelDeMotor.TEX, NivelDeMotor.SAGAZ)
    with pytest.raises(cx.ContratoXadrezInvalido, match="não traz o nível 'pita'"):
        cx.parametros_do_nivel(SONDA, NivelDeMotor.PITA)
    assert cx.parametros_do_nivel(SONDA, NivelDeMotor.TEX).teto_de_nos > 0


def test_uma_partida_inteira_da_sonda_pelo_executavel(na_sonda):
    try:
        jx.caminho_do_executavel()
    except jx.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do xadrez não está compilado: {erro}")

    # O MESMO jogador da produção: abre com `--contrato` apontando para a sonda,
    # e as três travas valem (o SHA-256 que ele anuncia é o dos bytes da sonda).
    with jx.JogadorXadrez() as motor:
        assert motor.abertura["modalidades"] == [SONDA]
        assert motor.abertura["sha256_do_contrato"] == cx.sha256_do_contrato()
        fen = cx.fen_inicial(SONDA)
        lances: list[str] = []
        # A Cacau de brancas contra o Tex de pretas, com a semente da fórmula.
        lado = {0: NivelDeMotor.CACAU, 1: NivelDeMotor.TEX}
        fim = None
        operacoes = set()
        while fim is None:
            assert len(lances) < LIMITE_DE_MEIOS_LANCES, "a partida da sonda nao terminou"
            estado = motor.estado(modalidade=SONDA, fen_inicial=fen, lances=lances)
            operacoes.add("estado")
            if len(lances) == 0:
                # Uma vez cada, no começo: as operações que a tela usa.
                assert motor.recusa(modalidade=SONDA, fen_inicial=fen, lances=lances, de="e1", para="g1")
                assert motor.radar(modalidade=SONDA, fen_inicial=fen, lances=lances, lado="branca") == []
                assert motor.jogada_ideal(modalidade=SONDA, fen_inicial=fen, lances=lances)["lance"]
                assert motor.perft(modalidade=SONDA, fen_inicial=fen, lances=lances, profundidade=2) == 400
                operacoes |= {"recusa", "radar", "jogada_ideal", "perft"}
            resposta = motor.buscar(
                modalidade=SONDA, fen_inicial=fen, lances=lances,
                nivel=lado[len(lances) % 2], semente=semente_do_lance(20_261_117, len(lances) + 1),
            )
            # O lance do personagem passa pelo `aplicar`, que devolve os fatos.
            origem, destino = resposta["lance"][:2], resposta["lance"][2:4]
            assert destino in estado["lances_legais"][origem]
            fatos = motor.aplicar(modalidade=SONDA, fen_inicial=fen, lances=lances, lance=resposta["lance"])
            operacoes |= {"buscar", "aplicar"}
            assert fatos["fatos"]["fim"] == resposta["fatos"]["fim"]
            lances.append(resposta["lance"])
            fim = resposta["fatos"]["fim"]

    # Acabou por um fim que o contrato da sonda declara, e as sete operações
    # passaram pela sonda.
    assert fim["motivo"] in json.loads(CONTRATO_DA_SONDA.read_text("utf-8"))["por_modalidade"][SONDA]["fim"]
    assert operacoes == {"estado", "aplicar", "recusa", "buscar", "jogada_ideal", "radar", "perft"}


def test_o_magno_da_sonda_e_recusado_antes_do_pedido_quando_sai_do_build(na_sonda, monkeypatch):
    dados = cx.carregar_contrato()
    dados["magno_no_build"] = False
    monkeypatch.setattr(cx, "carregar_contrato", lambda: dados)
    assert cx.niveis_disponiveis(SONDA) == (NivelDeMotor.CACAU, NivelDeMotor.TEX)


# ── O cadeado de fonte ───────────────────────────────────────────────────────

# Os nomes entre aspas simples ou duplas. ⚠️ Montados em duas partes para este
# arquivo não reprovar a si mesmo se um dia entrar na varredura.
_NOMES = ("tradi" + "cional", "son" + "da")
_LITERAL = re.compile(r"""['"](?:""" + "|".join(_NOMES) + r""")['"]""")


def test_o_cadeado_acha_o_literal_quando_ele_existe():
    """O controle: a expressão pega as aspas, e não a palavra solta."""
    for nome in _NOMES:
        assert _LITERAL.search(f"x = '{nome}'")
        assert _LITERAL.search(f'x = "{nome}"')
        assert not _LITERAL.search(f"a modalidade {nome} tem regras")


def test_o_nome_da_modalidade_nao_esta_escrito_no_codigo_do_xadrez_nem_no_job():
    """⛔ Modalidade é DADO (RF-XDR-013): quem escolhe é quem chama, pelo contrato.

    Varre `motores/xadrez/` inteiro (o `contrato_xadrez.py` também: ele lê as
    modalidades do arquivo, sem nomeá-las) e `job/`, achados na pasta e não numa
    lista escrita à mão, que ficaria cega para o arquivo novo.
    """
    achados = []
    for pasta in (RAIZ / "motores" / "xadrez", RAIZ / "job"):
        arquivos = sorted(pasta.rglob("*.py"))
        assert arquivos, f"nenhum .py em {pasta}"
        for arquivo in arquivos:
            for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
                if _LITERAL.search(linha):
                    achados.append(f"{arquivo.relative_to(RAIZ)}:{n}: {linha.strip()}")
    assert not achados, (
        "o nome de uma modalidade está escrito no código; leia-o do contrato "
        "(contrato_xadrez.modalidades_declaradas()):\n  " + "\n  ".join(achados)
    )

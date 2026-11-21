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


# ═══════════════════════════════════════════════════════════════════════════
# A SONDA CRESCE (fase 2, T081): ela atravessa os feitos e o JUIZ do desafio
# ═══════════════════════════════════════════════════════════════════════════
#
# A sonda entra no juiz pela mesma porta da modalidade de verdade: a
# `modalidade` da POSIÇÃO publicada (no xadrez o juiz não lê `co_modalidade`),
# o contrato e o executável. Se fazê-la passar exigisse uma linha em
# `motores/juiz.py` ou em `motores/xadrez/feitos_xadrez.py` que a citasse, seria
# o defeito que ela existe para achar.
#
# ⚠️ **E ela tem o que a de verdade não tem: o empate dos 30 lances**, no lugar
# dos 50. A mesma fita, na mesma posição, termina empatada na sonda e segue no
# tradicional: é a prova de que a regra chega ao veredito pelo contrato, e não
# por um número escrito no caminho.

from motores.juiz import julgar_desafio  # noqa: E402
from motores.nucleo.medidor_por_fita import CUMPRIU, DADO_INVALIDO, NAO_CUMPRIU  # noqa: E402
from motores.xadrez import feitos_xadrez as fx  # noqa: E402

#: Brancas a jogar, com o relógio dos lances sem captura em 58 MEIOS-lances
#: (29 lances de cada lado): dois lances quietos o levam a 60, que é o limite da
#: sonda (30 lances) e não o do tradicional (50). Os peões são para a posição
#: não ser material insuficiente, que acabaria a partida antes.
FEN_DO_RELOGIO = "4k3/p7/8/8/8/8/P2N4/4K3 w - - 58 80"

#: A pessoa de brancas, com o cavalo de d2 como espiã.
ESPIA = "d2"

#: Três lances da pessoa, todos com o cavalo espião, e dois do adversário.
FITA_LONGA = ["d2f3", "e8d8", "f3e5", "d8e8", "e5f3"]


def _posicao_do_relogio(modalidade: str) -> dict:
    """A posição publicada, no formato do contrato §1, na [modalidade]."""
    return {
        "jogo": "xadrez",
        "modalidade": modalidade,
        "fen": FEN_DO_RELOGIO,
        "cor_da_pessoa": "branca",
        "marcas": {"espia": ESPIA},
        "origem": "base_equilibrada",
    }


#: "Proteja a espiã por 3 lances" (o `xadrez_espia_proteger`), na forma que a
#: receita monta: a janela de 3 lances da pessoa, os 3 lances jogados e a espiã
#: nunca comida.
CHEGADA_PROTEGER_3 = {
    "versao": 1,
    "janela": {"tipo": "lances_do_jogador", "n": 3},
    "clausulas": [
        {"tipo": "medida", "chave": "lances_do_jogador", "comparador": "maior_ou_igual", "valor": 3},
        {"tipo": "medida", "chave": "espia_comida", "comparador": "menor_ou_igual", "valor": 0},
    ],
}


def _fita(lances: list[str]) -> list[dict]:
    """A fita do juiz: a pessoa (`+1`) abre, e a vez alterna."""
    return [
        {"n": i, "jogador": 1 if i % 2 == 1 else -1, "lance": lance}
        for i, lance in enumerate(lances, start=1)
    ]


@pytest.fixture
def motor_da_sonda(na_sonda, monkeypatch):
    """Um executável aberto com o contrato da sonda, entregue aos feitos.

    ⚠️ **Os feitos usam o executável DESTA THREAD** (`jogador_compartilhado`),
    e um que outro teste já abriu com o contrato de verdade não conhece a
    sonda. A troca é só aqui, no teste: a produção continua chamando o mesmo
    `reproduzir`, sem saber qual contrato o motor leu.
    """
    try:
        jx.caminho_do_executavel()
    except jx.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do xadrez não está compilado: {erro}")
    with jx.JogadorXadrez() as motor:
        assert motor.abertura["modalidades"] == [SONDA]
        monkeypatch.setattr(fx, "jogador_compartilhado", lambda: motor)
        yield motor


@pytest.fixture
def motor_de_verdade(monkeypatch):
    """O executável com o contrato de verdade, entregue aos feitos do mesmo jeito."""
    try:
        jx.caminho_do_executavel()
    except jx.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do xadrez não está compilado: {erro}")
    with jx.JogadorXadrez() as motor:
        monkeypatch.setattr(fx, "jogador_compartilhado", lambda: motor)
        yield motor


def test_a_sonda_atravessa_os_feitos_e_empata_nos_30_lances(motor_da_sonda):
    """Os fatos do motor da sonda chegam às medidas: dois lances, e é empate."""
    posicao = _posicao_do_relogio(SONDA)
    passos = fx.reproduzir(posicao, FITA_LONGA[:2])
    assert passos[-1]["fatos"]["fim"] == {"motivo": "cinquenta_lances", "vencedor": None}
    medidas = fx.medir(posicao, passos)
    assert medidas["empate"] == 1 and medidas["vitoria"] == 0
    assert medidas["lances_do_jogador"] == 1
    # E a espiã foi seguida pelo motor da sonda (ela andou, não foi comida).
    assert passos[0]["marcas"]["espia"]["casa"] == "f3"
    assert medidas["espia_comida"] == 0


def test_no_tradicional_a_mesma_fita_segue_e_nao_empata(motor_de_verdade):
    """O controle: com os 50 lances, o relógio em 60 meios-lances não é fim."""
    modalidade = cx.modalidades_declaradas()[0]
    posicao = _posicao_do_relogio(modalidade)
    passos = fx.reproduzir(posicao, FITA_LONGA)
    assert all(passo["fatos"]["fim"] is None for passo in passos)
    assert fx.medir(posicao, passos)["empate"] == 0


def test_a_sonda_atravessa_o_juiz(motor_da_sonda):
    """O "proteja a espiã por 3 lances", julgado na sonda.

    A partida empata no 2º meio-lance, com 1 lance da pessoa: o desafio NÃO é
    cumprido (ela não chegou aos 3). E a fita que continua depois do fim é dado
    inválido: o motor da sonda recusa o lance, e o juiz não inventa um veredito.
    """
    args = dict(
        co_jogo="xadrez",
        js_posicao_inicial=_posicao_do_relogio(SONDA),
        js_chegada=CHEGADA_PROTEGER_3,
        jogador=1,
    )
    curta = julgar_desafio(fita=_fita(FITA_LONGA[:2]), **args)
    assert curta.veredito == NAO_CUMPRIU
    assert curta.feitos["empate"] == 1
    assert julgar_desafio(fita=_fita(FITA_LONGA), **args).veredito == DADO_INVALIDO


def test_no_tradicional_o_mesmo_desafio_e_cumprido(motor_de_verdade):
    """O controle do juiz: sem o empate dos 30, os três lances cumprem."""
    modalidade = cx.modalidades_declaradas()[0]
    julgamento = julgar_desafio(
        co_jogo="xadrez",
        js_posicao_inicial=_posicao_do_relogio(modalidade),
        js_chegada=CHEGADA_PROTEGER_3,
        fita=_fita(FITA_LONGA),
        jogador=1,
    )
    assert julgamento.veredito == CUMPRIU
    # O instante do objetivo é o 3º lance da pessoa, o 5º da fita.
    assert julgamento.nu_lance_cumpre_desafio == 5


def test_a_chegada_e_a_que_a_receita_monta():
    """A chegada acima não é escrita à mão por gosto: é a da receita de verdade."""
    from job.tipos_de_desafio import RECEITAS

    assert RECEITAS["xadrez_espia_proteger"].montar({"lances": 3, "espia": "cavalo"}) == (
        CHEGADA_PROTEGER_3
    )


def test_o_juiz_e_o_nucleo_tambem_nao_citam_a_modalidade():
    """O cadeado de fonte, estendido ao que a sonda atravessa nesta fase."""
    achados = []
    arquivos = [RAIZ / "motores" / "juiz.py", *sorted((RAIZ / "motores" / "nucleo").rglob("*.py"))]
    for arquivo in arquivos:
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if _LITERAL.search(linha):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{n}: {linha.strip()}")
    assert not achados, "\n  ".join(achados)

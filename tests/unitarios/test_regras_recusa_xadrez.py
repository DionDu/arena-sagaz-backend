"""🔒 Os códigos da `jogo_xadrez.tb901_regra_recusa` são os que o MOTOR emite (T066).

A lição gravada no cabeçalho da 0012: o documento das damas tinha oito códigos de
recusa e o motor emitia sete. Um código que o app manda e o banco não conhece cai
no sentinela 9999 calado; um que o banco tem e o motor nunca emite é ruído. Por
isso a lista da migração é conferida contra o motor, por dois caminhos:

1. **o fonte espelhado** (`src/recusa.rs`, a função `codigo()`), que está no
   repositório e por isso NUNCA pula: a lista inteira, na ordem dos números;
2. **o executável**, quando compilado: cada uma das onze regras pedida ao motor
   num gesto feito para ela (as posições dos testes do próprio motor,
   `tests/recusa.rs`), e o código que volta tem de estar na migração.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motores.xadrez import contrato_xadrez as cx
from motores.xadrez import jogador_xadrez as jx
from tests.unitarios.leitura_de_migracao import sql_do_upgrade

RAIZ = Path(__file__).resolve().parents[2]
MIGRACAO = RAIZ / "migrations" / "versions" / "0039_schema_jogo_xadrez.py"
RECUSA_RS = jx.FONTES_DO_MOTOR / "src" / "recusa.rs"

#: Um gesto para cada regra: `(fen, de, para, regra)`. As posições são as de
#: `ia/jogos/jogo_xadrez/motor_rust/tests/recusa.rs`; `para = None` é o toque
#: numa peça, sem destino.
GESTOS = (
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e7", "e5", "nao_e_sua_peca"),
    ("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1", "e4", "e3", "peca_nao_anda_assim"),
    ("4k3/8/8/8/4p3/4P3/8/4K3 w - - 0 1", "e3", "e4", "caminho_bloqueado"),
    ("4k3/8/8/8/8/3N4/4P3/4K3 w - - 0 1", "e2", "d3", "casa_ocupada_por_peca_sua"),
    ("4k3/8/8/8/8/8/3N4/r3K3 w - - 0 1", "d2", "b3", "rei_em_xeque"),
    ("4k3/8/8/8/8/8/3r4/K7 w - - 0 1", "a1", "a2", "rei_ficaria_em_xeque"),
    ("4k3/8/8/8/8/8/8/R3K2R w Q - 0 1", "e1", "g1", "roque_sem_direito"),
    ("4k3/8/8/8/8/8/4r3/R3K2R w KQ - 0 1", "e1", "g1", "roque_com_rei_em_xeque"),
    ("4kr2/8/8/8/8/8/8/R3K2R w KQ - 0 1", "e1", "g1", "roque_atravessa_casa_atacada"),
    ("4k3/8/8/8/8/8/8/RN2K2R w KQ - 0 1", "e1", "c1", "roque_caminho_ocupado"),
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "c1", None, "peca_sem_lance"),
)


def codigos_da_migracao() -> dict[int, str]:
    """`{nu_regra: co_regra}` do `INSERT` da `tb901` na migração (o SQL executado)."""
    sql = sql_do_upgrade(MIGRACAO)
    inicio = sql.index("INSERT INTO jogo_xadrez.tb901_regra_recusa")
    trecho = sql[inicio : sql.index("CREATE TABLE", inicio)]
    # Cada linha do VALUES: `(numero, 'codigo', 'nome')`.
    return {int(n): c for n, c in re.findall(r"\(\s*(\d+)\s*,\s*'([a-z_]+)'", trecho)}


def codigos_do_fonte() -> list[str]:
    """Os códigos da `fn codigo()` do `recusa.rs` espelhado, na ordem do `match`."""
    fonte = RECUSA_RS.read_text(encoding="utf-8")
    corpo = fonte[fonte.index("pub fn codigo(self)") :]
    corpo = corpo[: corpo.index("\n    }\n")]
    return re.findall(r'=> "([a-z_]+)"', corpo)


def test_a_migracao_tem_os_codigos_do_motor_na_ordem_e_o_sentinela():
    da_migracao = codigos_da_migracao()
    do_fonte = codigos_do_fonte()
    assert len(do_fonte) == 11, f"o recusa.rs mudou de forma: {do_fonte}"
    # Os números 1..11 na ordem em que o motor declara as regras, e o 9999.
    assert da_migracao == {**{n: c for n, c in enumerate(do_fonte, 1)}, 9999: "desconhecido"}


def test_cada_gesto_do_teste_cobre_uma_regra_diferente():
    """O controle da tabela de gestos: as onze regras, uma vez cada."""
    assert sorted(g[3] for g in GESTOS) == sorted(codigos_do_fonte())


@pytest.mark.parametrize("fen,de,para,regra", GESTOS, ids=[g[3] for g in GESTOS])
def test_o_executavel_emite_cada_regra_da_migracao(fen, de, para, regra):
    try:
        jx.caminho_do_executavel()
    except jx.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do xadrez não está compilado: {erro}")
    with jx.JogadorXadrez() as motor:
        obtido = motor.recusa(
            modalidade=cx.modalidades_declaradas()[0], fen_inicial=fen, lances=[], de=de, para=para
        )
    assert obtido == regra
    assert obtido in codigos_da_migracao().values()

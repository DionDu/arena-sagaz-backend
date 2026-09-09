"""T021 - a `0020` alarga `partida.co_modo`, e este teste guarda o CONTEUDO.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE, TENDO O CADEADO DE MIGRACAO ADITIVA
═══════════════════════════════════════════════════════════════════════════

`test_migracoes_aditivas.py` passou a aceitar o par `DROP CONSTRAINT` +
`ADD CONSTRAINT` do mesmo nome na mesma migracao — sem isso, nenhum `CHECK`
poderia ser alargado nunca, porque o Postgres nao tem
`ALTER TABLE ... ALTER CONSTRAINT ... CHECK`.

⚠️ **Mas aquele cadeado nao le o conteudo do `CHECK`.** Para ele, trocar

    CHECK (co_modo IN ('vs_cpu', 'pvp_local', 'pvp_online'))

por

    CHECK (co_modo IN ('desafio'))

seria a mesma operacao: um par DROP+ADD do mesmo nome. E isso **rejeitaria toda
partida ja gravada** — a migracao falharia no ar, e o diagnostico seria confuso.

Este arquivo fecha essa metade: o vocabulario novo tem de **conter** o antigo.
Duas conferencias, porque nenhuma das duas basta sozinha.

⚠️ E ele nao toca banco nenhum: le o arquivo de migracao. A `0020` e uma proposta
que ainda nao rodou em lugar algum.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MIGRACAO = RAIZ / "migrations" / "versions" / "0020_partida_modo_desafio.py"

# Os tres modos que existem em producao desde a `0003`. Escritos aqui a mao, de
# proposito: se o teste os lesse do mesmo lugar que a migracao, os dois erros se
# cancelariam e o cadeado nao guardaria nada.
MODOS_EM_PRODUCAO = ("vs_cpu", "pvp_local", "pvp_online")

# Os tres estados que a `0006` ja tem, e que o desafio NAO precisa alargar.
STATUS_EM_PRODUCAO = ("concluida", "abandonada", "em_andamento")


def _comandos_executados(fonte: str) -> list[str]:
    """Os textos SQL passados a `op.execute(...)`, lidos com `ast`.

    Le a ARVORE do arquivo, nao o texto: assim a prosa das docstrings — que
    explica em detalhe o SQL que a migracao NAO faz — fica de fora.

    Devolve a parte literal das f-strings tambem: o verbo e a tabela de um
    comando estao sempre na parte fixa, e e isso que interessa conferir.
    """
    encontrados: list[str] = []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if not (isinstance(alvo, ast.Attribute) and alvo.attr == "execute"):
            continue
        for argumento in no.args:
            if isinstance(argumento, ast.Constant) and isinstance(argumento.value, str):
                encontrados.append(argumento.value)
            elif isinstance(argumento, ast.JoinedStr):
                # f-string: junta so os pedacos literais.
                encontrados.append(
                    "".join(
                        p.value
                        for p in argumento.values
                        if isinstance(p, ast.Constant) and isinstance(p.value, str)
                    )
                )
    return encontrados


@pytest.fixture(scope="module")
def fonte() -> str:
    """O texto da migracao. `scope="module"` le o arquivo uma vez so."""
    assert MIGRACAO.is_file(), f"a migracao sumiu: {MIGRACAO}"
    return MIGRACAO.read_text(encoding="utf-8")


def _modos_declarados(fonte: str) -> tuple[list[str], str]:
    """Os modos que a migracao declara, e o nome da variavel de onde saem.

    A `0020` escreve a lista **uma vez** e a usa no `upgrade` e no `downgrade`,
    para que os dois nao possam divergir por digitacao. Este teste le essa mesma
    lista — e confere separadamente que ela e de fato usada nos dois lugares.
    """
    casa = re.search(r"MODOS_ANTIGOS\s*=\s*\(([^)]*)\)", fonte)
    assert casa, "a migracao nao declara MODOS_ANTIGOS"
    # Aceita aspa simples ou dupla: qual das duas o arquivo usa e assunto do
    # formatador, nao deste cadeado.
    return re.findall(r"['\"]([a-z_]+)['\"]", casa.group(1)), "MODOS_ANTIGOS"


def test_o_vocabulario_novo_CONTEM_o_antigo(fonte: str) -> None:
    """🔒 O teste que o cadeado generico nao consegue fazer.

    Uma constraint nova mais restritiva **nao passaria despercebida no banco** —
    o `ADD CONSTRAINT` revalida a tabela e a migracao falharia. Mas falharia
    depois de o dono ter rodado o `alembic upgrade` apontando para producao, com
    um erro que nao diz "voce esqueceu um modo".
    """
    antigos, _ = _modos_declarados(fonte)
    faltando = [m for m in MODOS_EM_PRODUCAO if m not in antigos]
    assert not faltando, (
        f"a 0020 esqueceu modos que ja existem em producao: {faltando}. "
        "O ADD CONSTRAINT recusaria as partidas ja gravadas com eles."
    )


def test_o_modo_novo_e_exatamente_um_e_e_desafio(fonte: str) -> None:
    """Alargar um vocabulario de producao e acrescentar UMA palavra.

    Se um dia esta migracao trouxer dois modos novos, ela deixou de ser "o
    `CHECK` que o desafio precisa" e virou outra coisa — que merece migracao
    propria e justificativa propria.
    """
    casa = re.search(r"MODO_NOVO\s*=\s*['\"]([a-z_]+)['\"]", fonte)
    assert casa, "a migracao nao declara MODO_NOVO"
    assert casa.group(1) == "desafio"


def test_a_lista_e_escrita_uma_vez_so_e_usada_nos_dois_sentidos(fonte: str) -> None:
    """O `upgrade` e o `downgrade` leem a MESMA lista.

    Escrever os modos duas vezes e o tipo de duplicacao que envelhece torto: o
    dia em que um quarto modo entrar, alguem atualiza um dos dois e o
    `downgrade` passa a recusar dado valido — sem que nada acuse.
    """
    assert fonte.count("MODOS_ANTIGOS") >= 3, (
        "MODOS_ANTIGOS precisa ser declarada e usada no upgrade E no downgrade"
    )
    # O `upgrade` acrescenta o modo novo; o `downgrade` usa a lista pura.
    assert "(*MODOS_ANTIGOS, MODO_NOVO)" in fonte, (
        "o upgrade nao esta montando o CHECK a partir da lista + o modo novo"
    )
    assert "_lista_sql(MODOS_ANTIGOS)" in fonte, (
        "o downgrade nao esta voltando exatamente a lista antiga"
    )


def test_a_constraint_e_derrubada_e_recriada_com_o_MESMO_nome(fonte: str) -> None:
    """Nome diferente deixaria a constraint velha de pe, recusando `'desafio'`.

    E o defeito seria silencioso na migracao (ela roda, tudo verde) e barulhento
    meses depois, na primeira gravacao de uma partida de desafio.
    """
    derrubadas = re.findall(r"DROP\s+CONSTRAINT\s+([a-z_]+)", fonte)
    criadas = re.findall(r"ADD\s+CONSTRAINT\s+([a-z_]+)", fonte)
    assert derrubadas, "nada e derrubado — o CHECK nao esta sendo trocado"
    assert set(derrubadas) == set(criadas) == {"ck_partida_modo"}, (
        f"derrubadas={set(derrubadas)} criadas={set(criadas)}"
    )


def test_so_a_tabela_de_partida_e_tocada(fonte: str) -> None:
    """⛔ `partida` tem dado real: esta migracao nao pode ir alem do `CHECK`.

    Nada de coluna nova, nada de tabela nova, nada de `UPDATE`. O que o Desafio
    do Dia precisa de novo mora nos schemas `desafio` e `desafio_dia`, que sao
    vazios e onde a regra do dropa-e-recria vale.
    """
    tabelas = set(re.findall(r"ALTER\s+TABLE\s+([a-z_][a-z0-9_.]*)", fonte))
    assert tabelas == {"partida.tb001_partida"}, f"tabelas tocadas: {tabelas}"

    executados = " ".join(_comandos_executados(fonte)).upper()
    for proibido in ("CREATE TABLE", "ADD COLUMN", "UPDATE ", "INSERT INTO"):
        assert proibido not in executados, (
            f"a 0020 faz {proibido!r} — ela deveria alargar um CHECK e mais nada"
        )


def test_co_status_NAO_ganha_valor_novo(fonte: str) -> None:
    """Os tres estados da `0006` ja bastam, e o teste registra a conferencia.

    Sao exatamente os tres caminhos de saida de `em_andamento` que o dono
    desenhou em 08/09/2026: fim natural (`concluida`), sair da tela
    (`abandonada`) e o job de expiracao de 7 dias (`abandonada`).

    ⚠️ O que **falta** nao e valor de `CHECK`: e o ingestor, que grava com
    `ON CONFLICT DO NOTHING` e descartaria em silencio o envio que completa a
    partida. Isso e codigo, tem tarefa propria, e nao se conserta por migracao.
    """
    # ⚠️ A conferencia olha o que a migracao EXECUTA, nao o texto do arquivo.
    # A propria docstring acima cita os tres estados para explicar por que eles
    # bastam — um teste que procurasse o texto cru encontraria a explicacao e se
    # auto-reprovaria. E o mesmo erro que os cadeados do BLOCO 1 cometeram, e a
    # correcao e a mesma: `ast`.
    executados = " ".join(_comandos_executados(fonte)).upper()
    assert "CK_PARTIDA_STATUS" not in executados, (
        "a 0020 esta mexendo no CHECK de co_status — ele ja tem os tres estados"
    )
    assert "CO_STATUS" not in executados, (
        "a 0020 executa um comando que menciona co_status — ela deveria alargar "
        "o CHECK de co_modo e mais nada"
    )


def test_a_migracao_se_encaixa_na_corrente(fonte: str) -> None:
    """`down_revision` aponta para a 0019, e o id cabe no limite do Alembic.

    ⚠️ O id de revisao tem limite de 32 caracteres. Passar disso faz o upgrade
    RODAR o DDL inteiro e falhar so no fim, revertendo tudo — caro de
    diagnosticar, e a licao ja esta escrita na `0012`.
    """
    casa = re.search(r'^revision:\s*str\s*=\s*"([^"]+)"', fonte, re.M)
    assert casa, "a migracao nao declara `revision`"
    assert len(casa.group(1)) <= 32, f"id longo demais: {casa.group(1)}"

    casa = re.search(r'^down_revision:.*=\s*"([^"]+)"', fonte, re.M)
    assert casa and casa.group(1) == "0019_schema_desafio_dia", (
        f"down_revision inesperada: {casa.group(1) if casa else None}"
    )

"""🔒 As travas do `scripts/consultar_prd.py` — o script que fala com PRODUÇÃO.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 16/09/2026 o dono abriu uma exceção à regra *"o assistente não fala com o
`prd`"*, e a abriu **com o motivo escrito**: o `des` tem 1.777 posições de damas,
todas jogadas por ele mesmo em teste, enquanto o `prd` tem partidas de usuários
reais. A leitura é só `SELECT`.

⛔ **Uma exceção autorizada de boca vira regra do código no dia seguinte**, e é
isso que este arquivo impede. Ele trava as duas propriedades que fazem a exceção
ser segura:

  1. **cada script lê a SUA variável**, e nenhum dos dois consegue apontar para o
     banco do outro — é por isso que `consultar_prd.py` é arquivo novo, e não um
     `--ambiente` no script antigo. Um parâmetro faria um erro de digitação virar
     escrita em produção;
  2. **no `prd` a consulta começa com `SELECT` ou `WITH`**, que é a quarta trava,
     a única que o irmão do `des` não tem.

⚠️ **Nenhum teste aqui conecta em banco nenhum.** Todos param nas conferências,
que rodam antes de qualquer conexão — e é essa ordem que o arquivo também
descreve.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# O script mora em `scripts/`, que não é pacote instalado: entra no caminho aqui.
RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts.consultar_prd import conferir_que_comeca_com_select  # noqa: E402


def so_o_codigo(caminho: Path) -> str:
    """O arquivo sem a prosa: sem comentários e sem docstrings, mas COM as
    strings que o código usa de verdade.

    ⚠️ **Este recorte é o que faz o cadeado abaixo funcionar, e ele é fino.** Os
    dois scripts *explicam* um ao outro no cabeçalho: o do `prd` cita
    `DATABASE_URL_DES` na prosa, para dizer por que **não** a usa. Um cadeado que
    varresse o arquivo inteiro acusaria a própria explicação.

    ⛔ **E não dá para jogar fora todas as strings**, que seria o corte fácil: o
    nome da variável de ambiente *é* uma string literal (`chave == "DATABASE_..."`).
    Tirar as strings apagaria justamente o que se quer medir.

    A AST resolve os dois de uma vez. `ast.parse` devolve a árvore do programa,
    onde comentário simplesmente **não existe** (o analisador os descarta), e
    docstring é um caso reconhecível: o primeiro comando de um módulo, função ou
    classe, sendo uma string solta. Tiramos esses e serializamos o resto com
    `ast.dump`, que escreve as strings literais que sobraram.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        # Só estes quatro tipos de nó podem ter docstring.
        if not isinstance(
            no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        primeiro = no.body[0] if no.body else None
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            no.body = no.body[1:]
    return ast.dump(arvore)


class TestComecaComSelect:
    """A quarta trava: no banco dos usuários reais, a consulta começa por SELECT."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1",
            "select count(*) from partida.tb001_partida",
            "WITH recentes AS (SELECT 1) SELECT * FROM recentes",
            "(SELECT 1) UNION (SELECT 2)",
            # ⚠️ Herdado do irmão: comentário em português não atrapalha, e é o
            # falso positivo de 11/09/2026 que ensinou a olhar só o código.
            "-- os lances do Jogo das Damas, em ordem\nSELECT 1",
            "  \n\t SELECT 1",
        ],
    )
    def test_o_que_PASSA(self, sql: str) -> None:
        """🔒 Consulta de verdade passa — inclusive comentada e indentada."""
        conferir_que_comeca_com_select(sql)  # não levanta

    @pytest.mark.parametrize(
        "sql",
        [
            # ⛔ `EXPLAIN ANALYZE` **executa** o plano de verdade. Num `SELECT` é
            # inofensivo, mas a trava não sabe o que vem depois do `ANALYZE`.
            "EXPLAIN ANALYZE SELECT 1",
            "SET search_path TO publico",
            "LISTEN canal",
            "VACUUM",
            "\\dt",
            "",
            "-- só um comentário, sem consulta nenhuma",
        ],
    )
    def test_o_que_e_RECUSADO(self, sql: str) -> None:
        """🔒 Tudo o que não é consulta para aqui, antes de abrir conexão."""
        with pytest.raises(SystemExit):
            conferir_que_comeca_com_select(sql)


class TestCadaScriptLeASuaVariavel:
    """🔒 ⛔ A trava que sustenta a exceção inteira.

    ⚠️ Este é o cadeado que vale por todos os outros. Se um dia alguém "limpar a
    duplicação" fundindo os dois scripts num só com `--ambiente`, **estes dois
    casos caem** — e é exatamente aí que alguém precisa ser avisado.
    """

    def test_o_script_do_DES_nao_conhece_a_variavel_do_PRD(self) -> None:
        """🔒 `consultar_des.py` não consegue apontar para produção."""
        codigo = so_o_codigo(RAIZ / "scripts" / "consultar_des.py")
        assert "DATABASE_URL_DES" in codigo
        assert "DATABASE_URL_PRD" not in codigo

    def test_o_script_do_PRD_nao_conhece_a_variavel_do_DES(self) -> None:
        """🔒 E a recíproca: o de produção não cai no `des` por engano.

        ⚠️ Ele **importa** do irmão (as conferências são uma fonte só), mas a URL
        é dele: `DATABASE_URL_DES` não pode aparecer no código deste arquivo.
        """
        codigo = so_o_codigo(RAIZ / "scripts" / "consultar_prd.py")
        assert "DATABASE_URL_PRD" in codigo
        assert "DATABASE_URL_DES" not in codigo


class TestAsQuatroTravasRodamAntesDaConexao:
    """🔒 A ordem importa: nenhuma conferência pode acontecer com o socket aberto."""

    def test_main_confere_antes_de_executar(self) -> None:
        """🔒 No `main`, as duas conferências vêm antes do `asyncio.run`.

        ⚠️ Cadeado por leitura de fonte, de propósito: o alternativo seria abrir
        conexão num teste, que é justamente o que não se faz com produção.
        """
        fonte = (RAIZ / "scripts" / "consultar_prd.py").read_text(encoding="utf-8")
        corpo = fonte.split("def main(")[1]
        posicao_leitura = corpo.index("conferir_leitura(sql)")
        posicao_select = corpo.index("conferir_que_comeca_com_select(sql)")
        posicao_execucao = corpo.index("asyncio.run(")
        assert posicao_leitura < posicao_execucao
        assert posicao_select < posicao_execucao

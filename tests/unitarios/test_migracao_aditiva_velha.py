"""A migracao 0011 e PURAMENTE ADITIVA — e isto e um cadeado, nao uma promessa.

POR QUE ESTE TESTE EXISTE
-------------------------
Ha usuarios reais em `prd` desde 04/08/2026. Em 2026-08-06 o dono cravou a regra
para tudo o que o jogo novo trouxer:

    "Tome muito cuidado para nao usar DELETE, TRUNCATE, DROP. Nos ja temos
     usuarios no ambiente PRD."

Um comentario dizendo "esta migracao e aditiva" vale enquanto alguem o le. Este
teste LE O ARQUIVO da migracao e falha se encontrar qualquer uma das tres no
`upgrade()`. A afirmacao deixa de ser do autor e passa a ser do CI.

O QUE ELE NAO PEGA (e por que esta certo assim)
-----------------------------------------------
Ele nao roda a migracao contra um Postgres — isso e trabalho de integracao e
depende de banco. O que ele garante e o mais barato e o mais valioso: que
ninguem ACRESCENTE um comando destrutivo a esta migracao depois, numa correcao
apressada, sem que o CI grite.

O `downgrade()` e ignorado de proposito: ele derruba o schema, existe para o
ambiente local e nunca roda em producao.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# `parents[2]` sobe de tests/unitarios/ ate a raiz do repositorio do backend.
RAIZ = Path(__file__).resolve().parents[2]
MIGRACAO = RAIZ / "migrations" / "versions" / "0011_schema_jogo_velha.py"

# As tres palavras proibidas, como PALAVRA inteira e sem depender de caixa.
# `\b` evita falso positivo em algo como "DROPDOWN" ou "id_droptable".
PROIBIDOS = ("DELETE", "TRUNCATE", "DROP")


def _corpo_do_upgrade() -> str:
    """Devolve o codigo-fonte APENAS da funcao `upgrade()`.

    Le o arquivo com `ast` em vez de recortar por texto: recortar por "def
    downgrade" quebraria no dia em que alguem trocasse a ordem das funcoes, e o
    teste passaria a olhar o pedaco errado sem avisar.
    """
    fonte = MIGRACAO.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef) and no.name == "upgrade":
            return ast.get_source_segment(fonte, no) or ""
    pytest.fail("a migracao 0011 nao tem uma funcao upgrade()")


def _sem_comentarios(codigo: str) -> str:
    """Tira comentarios e docstrings, e normaliza as quebras de linha.

    Tirar comentarios e necessario porque o proprio arquivo EXPLICA que nao usa
    DROP — e a palavra aparece na explicacao. Um teste que olhasse o texto cru
    falharia por causa do comentario que existe para tranquilizar o leitor, o
    que seria comico e ensinaria a apagar comentarios uteis.

    A normalizacao existe porque `ast.unparse` devolve as strings de varias
    linhas com `\\n` **literal** (dois caracteres), e nao com a quebra de linha.
    Sem trocar um pelo outro, `.strip()` nao tira o inicio e o comando parece
    comecar por uma barra invertida.
    """
    arvore = ast.parse(codigo)
    # `ast.unparse` reconstroi o codigo a partir da arvore — e a arvore nao tem
    # comentarios. Docstrings sobrevivem como strings, e sao tiradas abaixo.
    limpo = ast.unparse(arvore)
    # Remove literais de string de uma linha que sejam docstrings soltas.
    limpo = re.sub(r"^\s*(\"\"\"|''').*?(\"\"\"|''')\s*$", "", limpo, flags=re.S | re.M)
    return limpo.replace("\\n", "\n")


def _sem_clausula_on_delete(codigo: str) -> str:
    """Tira o `ON DELETE CASCADE` das definicoes de chave estrangeira.

    ⚠️ **Nao e uma brecha na regra — e a distincao entre duas coisas com o mesmo
    nome.** `ON DELETE CASCADE` nao apaga nada: e uma clausula que diz o que
    fazer com a linha filha **se** a linha pai for apagada um dia. Um comando
    `DELETE FROM ...` apaga agora.

    E a semantica correta aqui: a extensao e 1:1 com a jogada generica, e uma
    extensao orfa (apontando para uma jogada que nao existe mais) seria lixo. E
    exatamente o desenho da irma do Pontinhos
    (`jogo_pontinhos.tb002_jogada`), conferido em `0006_redesenho_log_treino.py`.

    Sem esta funcao o teste acusaria a propria FK como comando destrutivo — um
    alarme falso, e alarme falso e o comeco de todo teste ignorado.
    """
    return re.sub(r"ON\s+DELETE\s+CASCADE", "", codigo, flags=re.IGNORECASE)


class TestMigracaoAditiva:
    def test_o_arquivo_existe(self):
        assert MIGRACAO.is_file(), f"migracao nao encontrada em {MIGRACAO}"

    @pytest.mark.parametrize("palavra", PROIBIDOS)
    def test_upgrade_nao_contem_comando_destrutivo(self, palavra: str):
        codigo = _sem_clausula_on_delete(_sem_comentarios(_corpo_do_upgrade()))
        achado = re.search(rf"\b{palavra}\b", codigo, flags=re.IGNORECASE)
        assert achado is None, (
            f"a migracao 0011 usa {palavra} no upgrade(). "
            "Ha usuarios reais em prd — nada de destrutivo nesta fase."
        )

    def test_upgrade_nao_contem_alter_drop(self):
        """`ALTER TABLE ... DROP COLUMN` some sozinho da regra acima?

        Nao: a palavra DROP ja o pegaria. Este caso existe para deixar claro que
        a intencao inclui o `ALTER` destrutivo, e nao so o `DROP TABLE`.
        """
        codigo = _sem_clausula_on_delete(_sem_comentarios(_corpo_do_upgrade()))
        assert re.search(r"ALTER\s+TABLE.*DROP", codigo, flags=re.I | re.S) is None

    def test_upgrade_so_acrescenta(self):
        """O que a migracao PODE conter, listado explicitamente.

        Vira do avesso o teste acima: em vez de listar o proibido, confere que
        todo comando executado e um dos permitidos. Pega o destrutivo que um dia
        chegue com um nome que ninguem previu.
        """
        codigo = _sem_comentarios(_corpo_do_upgrade())
        # Cada string passada a `op.execute(...)` deve comecar por um destes.
        permitidos = ("CREATE SCHEMA", "CREATE TABLE", "INSERT INTO", "CREATE VIEW")
        comandos = re.findall(r"op\.execute\(\s*(?:'|\")(.*?)(?:'|\")", codigo, re.S)
        assert comandos, "nenhum op.execute encontrado — o teste esta olhando o lugar errado"
        for c in comandos:
            inicio = c.strip().upper()
            assert inicio.startswith(permitidos), f"comando nao permitido: {c[:60]}"


class TestConteudoDaDimensao:
    """A dimensao precisa nascer completa — inclusive o sentinela."""

    def test_os_seis_codigos_e_o_sentinela(self):
        fonte = MIGRACAO.read_text(encoding="utf-8")
        esperados = (
            "minimax_otimo",
            "minimax_deslize",
            "epsilon_aleatorio",
            "abertura_sorteada",
            "bloqueio_forcado",
            "timeout_auto",
        )
        for co in esperados:
            assert f"'{co}'" in fonte, f"falta o codigo {co} na dimensao"

    def test_o_sentinela_9999_existe(self):
        """Sem ele, um app mais novo que o backend estoura a FK e toma 500.

        A consequencia nao e um erro na tela: o evento fica **preso para
        sempre** na fila de sincronizacao daquele aparelho, e a partida da
        pessoa nunca sobe.
        """
        fonte = MIGRACAO.read_text(encoding="utf-8")
        assert "9999" in fonte
        assert "'desconhecido'" in fonte


class TestLarguraDeCoCelula:
    """A V-1 — o defeito do PRD que rejeitaria todo INSERT."""

    def test_co_celula_tem_folga(self):
        """O PRD §7.2 escrevia `VARCHAR(3)`, e `'C_1_2'` tem 5 caracteres.

        Com 3, **nenhum** valor valido caberia: todo INSERT estouraria. O dono
        aprovou `VARCHAR(15)`, igual ao `co_aresta` do Pontinhos.
        """
        fonte = MIGRACAO.read_text(encoding="utf-8")
        achado = re.search(r"co_celula\s+VARCHAR\((\d+)\)", fonte)
        assert achado, "co_celula nao encontrada na migracao"
        largura = int(achado.group(1))
        assert largura >= 5, "VARCHAR(3) rejeitaria todo INSERT — ver V-1"
        assert largura == 15, "o dono aprovou VARCHAR(15), igual ao Pontinhos"

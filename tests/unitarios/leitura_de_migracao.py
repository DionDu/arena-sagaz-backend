"""COMO SE LE UMA MIGRACAO — a peca que os cadeados de migracao compartilham.

⚠️ **Nao e um arquivo de teste**: nao tem caso nenhum. Ele existe porque ler o
SQL de uma migracao tem sutileza suficiente para que duas implementacoes acabem
discordando — e a que discordasse em silencio seria a mais perigosa.

O historico e curto e caro, e explica cada linha daqui:

  · **09/09/2026** — `test_migracoes_aditivas.py` ignorava
    `op.execute(f"...")` INTEIRO: o padrao exigia a aspa logo apos o parenteses,
    e o prefixo `f` nao casava. Uma migracao escrita com f-strings nao teria um
    unico comando conferido, e o teste passaria varrendo uma lista vazia.
  · **09/09/2026** — `test_migracao_bate_com_data_model.py` nao enxergava os
    `CREATE INDEX`, escritos como strings adjacentes que o Python junta na
    compilacao. Nenhum regex casa com a aspa, a quebra de linha e a indentacao
    que ficam no meio.
  · **10/09/2026** — o cadeado do sentinela `9999` lia o **arquivo inteiro**, e
    cobrava sentinela de uma migracao que apenas *mencionava* uma dimensao no
    cabecalho, para explicar que **nao** a toca. Foi o caso da `0020`.

  · **10/09/2026** — e o quarto, ja fora das migracoes: o cadeado de T043a
    (*"a auditoria nao chama `escolher_lance`"*) foi escrito com `in fonte` e
    **reprovou o codigo correto**, porque a docstring do modulo auditado
    menciona `escolher_lance` exatamente para dizer que ele nao o chama. O
    conserto foi ler imports e chamadas com `ast`
    (`test_auditoria_de_resolucoes.py`).

Os quatro sao a mesma especie de defeito: **o cadeado confundiu o que o codigo
diz com o que ele faz**. A resposta e sempre `ast` — ler o que o codigo executa,
e nao como ele esta escrito.

⚠️ **E o padrao se repete fora das migracoes**, como o quarto caso mostra: todo
cadeado que pergunta *"este arquivo faz X?"* le `ast`, e nunca texto. Um `in
fonte` acerta enquanto ninguem escrever um comentario sobre o assunto — e o
comentario sobre o assunto e justamente o que um arquivo bem documentado tem.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


def sql_da_migracao(caminho: Path) -> str:
    """Todo o SQL que uma migracao executa, junto, lido com `ast`.

    Percorre a arvore do arquivo atras de toda chamada `.execute(...)` — o
    `op.execute` do Alembic — e junta o texto dos argumentos:

      · `ast.Constant` e a string comum, **ja com as adjacentes unidas** pelo
        proprio Python (`"CREATE INDEX " "ON tabela"` chega aqui como uma so);
      · `ast.JoinedStr` e a f-string: fica o que e literal, e o `{...}`
        interpolado sai de fora. Para o que os cadeados conferem — qual comando
        esta sendo executado, sobre qual tabela — isso basta: o verbo e o nome
        estao sempre na parte fixa.

    Args:
        caminho: o arquivo da migracao.

    Returns:
        Os comandos separados por quebra de linha, na ordem em que aparecem.

    ⚠️ **O que fica de fora e de proposito**: docstring, comentario de Python e
    qualquer texto que a migracao **nao executa**. Era exatamente o que fazia o
    cadeado do sentinela `9999` reprovar a `0020` por causa de uma frase no
    cabecalho.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    pedacos: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        # `op.execute(...)`: o que interessa e o nome do atributo chamado, e nao
        # o objeto — assim tanto `op.execute` quanto `conexao.execute` entram.
        if not (isinstance(alvo, ast.Attribute) and alvo.attr == "execute"):
            continue
        for argumento in no.args:
            if isinstance(argumento, ast.Constant) and isinstance(argumento.value, str):
                pedacos.append(argumento.value)
            elif isinstance(argumento, ast.JoinedStr):
                pedacos.append(
                    "".join(
                        parte.value
                        for parte in argumento.values
                        if isinstance(parte, ast.Constant)
                        and isinstance(parte.value, str)
                    )
                )
    return "\n".join(pedacos)


# ═══════════════════════════════════════════════════════════════════════════
# O DDL: que tabelas o texto declara, com que colunas e que constraints
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Isto morava dentro de `test_migracao_bate_com_data_model.py`, e subiu para
# ca em 10/09/2026**, quando o cadeado do `INSERT` do job (T049b) precisou da
# mesma leitura. Ele confere se toda coluna obrigatoria de `tb001_desafio`
# aparece no `INSERT` que o job executa — a mesma pergunta ("o que a migracao
# declara?"), feita contra outro arquivo.
#
# ⛔ **Um segundo leitor de DDL era o caminho errado**, e este modulo existe
# justamente por isso: a docstring do topo ja dizia que tres cadeados o usam e
# que tres implementacoes acabariam discordando. Agora sao quatro.

def sem_comentarios_sql(texto: str) -> str:
    """Tira os comentarios `--` do SQL, preservando as linhas.

    O `data-model.md` documenta cada coluna com um `--` ao lado; a migracao usa
    comentarios de Python acima do bloco. Comparar com eles dentro produziria
    divergencia em toda linha comentada de um lado so.
    """
    return "\n".join(linha.split("--")[0] for linha in texto.splitlines())


def _dividir_no_topo(corpo: str) -> list[str]:
    """Divide por virgulas do NIVEL MAIS ALTO dos parenteses.

    ⚠️ Um `split(",")` simples quebraria `VARCHAR(30)` e
    `CHECK (co_modo IN ('a', 'b'))` no meio — e o resultado seria um monte de
    pedacos que nao sao nem coluna nem constraint.
    """
    partes: list[str] = []
    atual: list[str] = []
    profundidade = 0
    for caractere in corpo:
        if caractere == "(":
            profundidade += 1
        elif caractere == ")":
            profundidade -= 1
        if caractere == "," and profundidade == 0:
            partes.append("".join(atual))
            atual = []
            continue
        atual.append(caractere)
    if "".join(atual).strip():
        partes.append("".join(atual))
    return [p.strip() for p in partes if p.strip()]


def _corpo_da_tabela(texto: str, inicio: int) -> str:
    """O conteudo entre os parenteses do `CREATE TABLE`, casando o fechamento."""
    abre = texto.index("(", inicio)
    profundidade = 0
    for posicao in range(abre, len(texto)):
        if texto[posicao] == "(":
            profundidade += 1
        elif texto[posicao] == ")":
            profundidade -= 1
            if profundidade == 0:
                return texto[abre + 1 : posicao]
    raise AssertionError("CREATE TABLE sem parentese de fechamento")


def tabelas_do_sql(texto: str) -> dict[str, dict[str, object]]:
    """Extrai `{tabela: {colunas: [(nome, tipo)], constraints: {nome: tipo}}}`.

    O `tipo` de coluna e normalizado: maiusculas, espacos colapsados, e sem a
    clausula `REFERENCES` — a FK inline e comparada como constraint, e o
    `data-model.md` a escreve quebrada em varias linhas.
    """
    limpo = sem_comentarios_sql(texto)
    achadas: dict[str, dict[str, object]] = {}

    for casa in re.finditer(
        r"CREATE TABLE\s+([a-z_][a-z0-9_.]*)\s*\(", limpo, re.I
    ):
        nome = casa.group(1).lower()
        corpo = _corpo_da_tabela(limpo, casa.start())

        colunas: list[tuple[str, str]] = []
        constraints: dict[str, str] = {}

        for parte in _dividir_no_topo(corpo):
            normalizada = " ".join(parte.split())
            if normalizada.upper().startswith("CONSTRAINT "):
                nome_da_constraint = normalizada.split()[1].lower()
                # A ESPECIE da constraint (UNIQUE, CHECK, FOREIGN KEY), e nao o
                # texto dela — ver a docstring do modulo.
                especie = "outra"
                for candidata in ("UNIQUE", "CHECK", "FOREIGN KEY", "PRIMARY KEY"):
                    if candidata in normalizada.upper():
                        especie = candidata
                        break
                constraints[nome_da_constraint] = especie
                continue

            campos = normalizada.split(None, 1)
            if len(campos) != 2:
                continue
            nome_da_coluna, resto = campos[0].lower(), campos[1]
            # Tira a FK inline: ela vira constraint anonima, e o que importa
            # dela (para onde aponta) o proprio banco guarda.
            resto = re.split(r"\bREFERENCES\b", resto, flags=re.I)[0]
            colunas.append((nome_da_coluna, " ".join(resto.upper().split())))

        achadas[nome] = {"colunas": colunas, "constraints": constraints}

    return achadas

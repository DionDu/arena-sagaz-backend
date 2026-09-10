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

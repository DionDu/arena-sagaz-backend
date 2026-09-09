"""`api/desafios/` — o que a API faz com o Desafio do Dia.

⚠️ **A API aqui LE muito e escreve pouco**, e isso e a fronteira do banco vista
do lado do codigo:

    schema `desafio`      → escrito pelo JOB (`job/`). A API so le.
    schema `desafio_dia`  → escrito pelo APP, pelo caminho de sincronizacao.

Por isso os modelos estao em **dois** arquivos, e nao num so:

| arquivo | schema | quem escreve as linhas |
|---|---|---|
| `modelos_producao.py` | `desafio` | o job em batch do Railway |
| `modelos_evento.py` | `desafio_dia` | o aplicativo |

Juntar os dois num arquivo faria a fronteira sumir do codigo — e ela e a decisao
central do modelo de dados (Bloco X, 04/09/2026).

⛔ **Nenhum endpoint de motor** (RF-DES-166). `motores/` e camada **importada**
pelo job; ela nao serve rota, e nada aqui deve expo-la.
"""

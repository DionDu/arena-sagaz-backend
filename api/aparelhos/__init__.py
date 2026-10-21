"""O aparelho e o uso de cada dia - o 1º passo de analytics (T118 da spec 010).

Duas tabelas no schema `log` (migração `0036_log_aparelho`): o aparelho
(`tb003`, uma linha por INSTALAÇÃO do app) e o dia dele (`tb004`, uma linha por
aparelho por dia local, com a maior versão vista). É a amostra que a adoção
gradual do jogo novo no Desafio do Dia lê (`job/adocao.py`, T119).

Duas rotas escrevem:

* a leitura do desafio do dia (`GET /v1/desafios/hoje`), que grava a versão de
  **qualquer** app - inclusive o 1.3, que já a chama;
* o envio diário dos detalhes (`POST /v1/aparelhos/detalhes`), só do app 1.4
  em diante.

⚠️ **"Aparelho" é a instalação, e não o hardware**: o código é gerado pelo
app, e nenhum identificador do aparelho é lido. Ver `regras.py`.
"""

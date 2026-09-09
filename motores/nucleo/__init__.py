"""Núcleo da camada de motores: o que é comum a TODOS os jogos.

⚠️ **"Núcleo" aqui não é o mesmo "núcleo" do banco nem o do app.** A palavra
aparece três vezes na spec 009, com três cortes diferentes:

| onde | o que "núcleo" significa lá |
|---|---|
| **aqui, `motores/nucleo/`** | os **papéis** e as peças comuns aos motores dos jogos |
| no banco (schema `desafio`) | a **linha de produção**, escrita só pelo job em batch |
| no app (`lib/core/desafios/`) | o código **genérico que julga**, sem o dia |

O que mora aqui é só o que os motores dos jogos têm em comum de verdade — os dois
papéis, o orçamento de busca e o carimbo. ⛔ Nada de regra de jogo: a de damas é
do laboratório, a do Pontinhos é da CNN, e a camada os reúne **sem uniformizar**
(RF-DES-160).
"""

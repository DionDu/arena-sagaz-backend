"""Camada de motores de jogo do backend — irmã de `api/`, e não parte dela.

═══════════════════════════════════════════════════════════════════════════
O QUE É ESTA PASTA
═══════════════════════════════════════════════════════════════════════════

Um pacote Python de **primeiro nível**, ao lado de `api/` e de `job/`, que reúne
os motores dos jogos da Arena atrás de uma fronteira declarada (RF-DES-160). Ela
é **importada**, nunca chamada por HTTP: ⛔ **nenhum endpoint de motor existe
nesta entrega** (RF-DES-166, determinação do dono de 04/09/2026).

Nesta feature o motor tem exatamente dois consumidores, ambos no mesmo processo:

    job/gerador.py   → usa o papel JOGADOR  (gera candidatos, mede a régua)
    job/auditoria.py → usa o papel ÁRBITRO  (audita a resolução que chegou)

═══════════════════════════════════════════════════════════════════════════
AS TRÊS REGRAS QUE ESTA CAMADA NÃO PODE QUEBRAR
═══════════════════════════════════════════════════════════════════════════

1. **Não existe "o motor da Arena".** O de damas é o Python do laboratório
   (RF-DES-018); o do Pontinhos é uma CNN mais a política portada
   (RF-DES-018b/c). A camada os **reúne sem uniformizar** — o que é comum são os
   dois *papéis*, não a implementação.

2. **A camada não conhece desafio** (RF-DES-165). Não importa modelo de desafio,
   não abre conexão de banco, e não sabe o que é "dia", "coleção", "resolução",
   "quadro" ou "XP". Recebe posição e regras; devolve lance ou veredito.
   ⚠️ Isso é travado por teste: `tests/unitarios/test_motores_nao_conhecem_desafio.py`
   (o **cadeado 2**), que **nunca pula**.

3. **Nenhuma assinatura menciona requisição, resposta, sessão ou token**
   (RF-DES-166). É o critério de aceitação declarado da spec, e é verificável por
   leitura — e, aqui, também por teste.

═══════════════════════════════════════════════════════════════════════════
POR QUE FORA DE `api/`
═══════════════════════════════════════════════════════════════════════════

Porque um motor que precise da API para funcionar não serve ao job em batch — que
é um container sem porta e sem rota (RF-DES-011a) — e não serviria a um bot de
PvP amanhã. Morando fora, o sentido do import fica de mão única: `api/` e `job/`
importam `motores/`; `motores/` não importa ninguém dos dois.
"""

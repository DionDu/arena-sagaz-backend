# Defeito: US2 — Double-Dealing Nunca Dispara (Código Morto)

**Data**: 2026-05-05  
**Severidade**: Crítica  
**Status**: Corrigido  
**Arquivos afetados**: `gerador_dados/jogo_pontinhos/correntes_pontinhos_3_4.py`

---

## Sintoma

Em avaliações de 200+ partidas (`ia-pontinhos-3-4` vs Minimax puro), a telemetria
mostra **0 ocorrências** de `co_acao = "sacrificio_double_cross"` ou
`co_acao = "captura_completa"` (ambas do Passo 2). O agente **sempre** cai no
Passo 1 (captura gulosa) ou Passo 3+4 (CNN + Minimax).

## Causa Raiz

Dois defeitos encadeados em `correntes_pontinhos_3_4.py`:

### Defeito 1 — `detectar_estruturas` exclui caixas grau-3 do grafo (viola FR-009)

Linhas 209-213: o grafo dual é construído **somente** com caixas grau-2.
Caixas grau-3 (aquelas prontas para captura) não são incluídas como nós.

A spec (FR-009) diz explicitamente:
> "um grafo onde cada nó é uma caixa de grau 2 **(ou grau 3 que faz parte da
> estrutura sendo avaliada)**"

A parte entre parênteses não foi implementada.

### Defeito 2 — `trigger_double_dealing` compara conjuntos disjuntos

Linhas 369-376: compara `grau_3_set` (caixas grau-3) com `estrutura.caixas[-2:]`
(caixas grau-2). Como os dois conjuntos são **disjuntos por definição**, a
igualdade **nunca é verdadeira** e a função retorna `False` em 100% dos casos.

### Defeito 3 — `estado_apos_double_cross` simulava cascata antes do sacrifício

A simulação do double-cross fazia uma cascata de capturas e depois o sacrifício.
Porém, o `escolher_jogada` retorna **uma única aresta** por chamada. Quando o
agente decide pelo sacrifício, deve retornar **diretamente** a aresta de
double-cross (entre as 2 caixas grau-2 que serão oferecidas ao adversário),
sem cascata prévia.

## Exemplo Concreto

Corrente de 5 caixas: `[A(g2)] - [B(g2)] - [C(g2)] - [D(g2)] - [E(g3)]`

O adversário abriu o lado E. O agente captura E (turno 1), D (turno 2) via
Passo 1 (captura gulosa). No turno 3, o estado é:

```
[A(g2)] - [B(g2)] - [C(g3)]
```

**Esperado**: O Passo 2 deve disparar. Corrente de 3 caixas (longa), com C grau-3
na extremidade e 2 caixas grau-2 restantes (A, B). O agente avalia via Minimax:
- Opção A (captura completa): capturar C → B → A (3 caixas para o agente).
- Opção B (sacrifício): preencher aresta A-B (entrega A, B, C ao adversário,
  que é forçado a abrir a próxima estrutura).

**Observado**: `detectar_estruturas` retorna corrente `[A, B]` (exclui C).
`trigger_double_dealing` falha: `{C} != {A, B}` → `False`. Cai no Passo 1
(captura gulosa). Agente engole a corrente inteira sem avaliar o sacrifício.

## Impacto

O double-dealing é a técnica mais importante de Dots-and-Boxes (Berlekamp,
*Winning Ways*). Sem ele, o agente **sempre** engole correntes inteiras,
entregando o controle de paridade ao adversário. O adversário Minimax puro
descobre o sacrifício naturalmente pela profundidade de busca.

## Correção

1. **`detectar_estruturas`**: Incluir caixas grau-3 (abertas) como nós do grafo.
2. **`estrutura_ativa`**: Simplificar para verificar se todas as grau-3 estão
   contidas em exatamente 1 estrutura.
3. **`trigger_double_dealing`**: Nova condição — grau-3 contíguas numa
   extremidade da corrente, com exatamente 2 caixas grau-2 restantes.
4. **`aresta_double_cross`**: Identificar par de sacrifício (extremidade oposta
   à abertura grau-3).
5. **`estado_apos_double_cross`**: Simplificar — apenas preenche a aresta de
   double-cross, sem cascata prévia (coerente com o modelo stateless de
   `escolher_jogada`).

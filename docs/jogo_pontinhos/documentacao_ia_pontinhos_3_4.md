# Documentação Técnica e de Negócio — Agente `ia-pontinhos-3-4`

**Status**: STUB ratificado em 2026-05-01 (será preenchido durante a
implementação da feature 003).

> **FR-031**: este documento é obrigatório por força da spec; deve cobrir
> negócio + técnico do agente híbrido em um único lugar legível para
> mantenedores e LLMs futuros. O conteúdo abaixo é o ESQUELETO; cada seção
> será detalhada conforme a implementação avança.

---

## 1. Visão de Negócio

> A preencher na implementação. Cobertura prevista:
>
> - Por que um agente híbrido (resumo de
>   `docs/tcc/argumentacao_cnn_vs_minimax.md`).
> - Modos de uso no Arena Sagaz (humano vs IA, IA vs IA, telemetria).
> - 4 níveis de dificuldade e seu impacto na experiência do jogador.

---

## 2. Arquitetura Resumida

> A preencher. Diagrama de blocos com:
>
> - Tier 1 (genérico): `tabuleiro_pontinhos`, `minimax_pontinhos`,
>   `contrato_codificacao_pontinhos`.
> - Tier 2 (3×4): `tipos_pontinhos_3_4`, `correntes_pontinhos_3_4`,
>   `cnn_inferencia_pontinhos_3_4`, `ia_pontinhos_3_4`.
> - Fluxo de import (Tier 2 → Tier 1 → Tier 0).
>
> Ver detalhes em `specs/003-jogador-hibrido/plan.md`.

---

## 3. Pipeline dos 4 Passos

> A preencher. Para cada passo:
>
> 1. **Captura segura/gulosa** — quando dispara, exemplo numérico, edge cases.
> 2. **Exceção do sacrifício / double-dealing** — trigger, geração de Estado A
>    e B, decisão por Minimax depth=3, tie-break por B.
> 3. **Fase tática (CNN)** — codificação do tabuleiro, normalização, TOP-5.
> 4. **Validação Minimax (TOP-5)** — depth=N, alpha-beta, argmax, tie-break.

---

## 4. Estruturas de Dados

> A preencher. Referência cruzada com
> `specs/003-jogador-hibrido/data-model.md`. Cobrir:
>
> - `ConfiguracaoAgente` (níveis e overrides).
> - `MetadadosTurno` (origem dos UUIDs e timestamp).
> - `ResultadoJogada` (campos comuns e opcionais; padrão por User Story
>   originadora).
> - `Estrutura` (corrente / ciclo / ramificada / isolada).

---

## 5. Detecção de Correntes e Ciclos

> A preencher. Algoritmo do grafo dual:
>
> - Definição de vértice e aresta-do-grafo.
> - BFS para componentes conexas.
> - Classificação por graus internos.
> - `estrutura_ativa` e trigger de double-dealing.
> - Cálculo da aresta de sacrifício (corrente vs ciclo).
> - Edge cases canônicos (corrente de tamanho 2, 3, 4, 5; ciclo de tamanho 4).

---

## 6. Inferência CNN

> A preencher. Cobertura:
>
> - Bibliotec a (`tensorflow.lite.Interpreter`).
> - Carregamento e cache de interpretadores.
> - Thread-safety via `threading.Lock`.
> - Normalização (referência a
>   `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json`).
> - Filtragem de arestas livres e TOP-K.
> - Tratamento de NaN/inf.

---

## 7. Minimax com DI

> A preencher. Cobertura:
>
> - Mudança em `minimax_pontinhos.minimax(..., fn_avaliacao=avaliar)`.
> - Compatibilidade retroativa.
> - Como o agente injeta a função de avaliação.
> - Quando introduzir features posicionais (gatilho via SC-006).

---

## 8. Determinismo e Aleatoriedade

> A preencher. Cobertura:
>
> - Tabela de tie-breakers.
> - Uso de `np.random.default_rng(seed)` por chamada.
> - Escopo da aleatoriedade (Passo 4 apenas; Passos 1 e 2 sempre
>   determinísticos).

---

## 9. Tratamento de Erros

> A preencher. Tabela completa em
> `specs/003-jogador-hibrido/contracts/api-python-pontinhos-3-4.md`. Resumir
> aqui as mensagens em pt-BR e o motivo da política de erro duro.

---

## 10. Performance e Concorrência

> A preencher. Cobertura:
>
> - Metas SC-005 (média ≤ 500ms, p95 ≤ 1000ms, p99 ≤ 1500ms).
> - Modelo single-thread + Lock no TFLite.
> - Resultados empíricos da bateria de performance.

---

## 11. Estratégia de Testes

> A preencher. Referência cruzada com a seção "Estratégia de Testes" do
> `plan.md`. Detalhar:
>
> - Cobertura por módulo.
> - Mocks da CNN e do Minimax.
> - Markers `@pytest.mark.lento` para testes opt-in.
> - Cenários canônicos da literatura usados para validar US2.

---

## 12. Roadmap Pós-Feature 003

> A preencher quando a feature for concluída. Cobertura prevista:
>
> - Persistência da telemetria (`tb002_jogada`).
> - Sincronização local↔servidor.
> - Portabilidade para App Flutter (TFLite nativo + Dart).
> - Generalização para outras dimensões (`ia-pontinhos-5-5`,
>   `ia-pontinhos-7-5`).
> - Eventual evolução para MCTS / AlphaZero-like (fora do escopo do TCC).

---

## Referências Cruzadas

- Spec ratificada: `specs/003-jogador-hibrido/spec.md`
- Plano técnico: `specs/003-jogador-hibrido/plan.md`
- Pesquisa técnica: `specs/003-jogador-hibrido/research.md`
- Modelo de dados: `specs/003-jogador-hibrido/data-model.md`
- Contrato Python: `specs/003-jogador-hibrido/contracts/api-python-pontinhos-3-4.md`
- Quickstart: `specs/003-jogador-hibrido/quickstart.md`
- Argumentação CNN vs Minimax (TCC): `docs/tcc/argumentacao_cnn_vs_minimax.md`
- Métricas e conceitos: `docs/metricas_e_conceitos.md`
- Histórico de decisões: `docs/historico_decisoes.md` (entrada de 2026-05-01).

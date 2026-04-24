# Por que 200.000–300.000 amostras? O Ponto de Equilíbrio entre Aprendizado e Viabilidade

Esta é a pergunta clássica de qualquer banca avaliadora de Machine Learning e
Inteligência Artificial: *"Por que esse tamanho de dataset?"*

A escolha de **200.000–300.000 registros** não foi um "chute". É o resultado
de três iterações de engenharia: início com 50k (subótimo), migração para
processamento paralelo (viabilizou volumes maiores), e adoção de soft targets
(mudou a relação volume × qualidade do sinal).

---

## 1. Por que não 5.000 amostras? (O Problema do Subtreinamento)

O Jogo dos Pontinhos, mesmo no tabuleiro Pequeno (4×3 caixas), possui 31
traços e um espaço de estados da ordem de 2³¹ combinações teóricas (embora
muitos sejam inalcançáveis nas regras reais).

Com apenas 5.000 tabuleiros, a CNN sofreria de **Subtreinamento (Underfitting)**
ou **Decoreba (Overfitting)**:

1. Ela não veria exemplos suficientes das variadas formas geométricas (cantos
   perigosos, corredores longos, caixas com 2 ou 3 lados preenchidos).
2. Como não entende as regras formalmente, tentaria "decorar" as posições vistas.
   Qualquer posição ligeiramente diferente produziria decisões erradas por
   incapacidade de generalização.

---

## 2. Por que 200.000–300.000 e não apenas 50.000?

O primeiro experimento usou 50.000 amostras. Os resultados foram:

- **CNN clássica:** acurácia colapsou para ~4% (arquitetura inadequada para
  representação heterogênea da matriz).
- **MLP:** overfitting severo — treino 42% / validação 28%.
- **BoxNet v2 (CNN com preprocessing geométrico):** val_top1 ≈ 36%, mas
  val_top3 ≈ 70% — o modelo aprendia a região certa, mas não a jogada exata.

O diagnóstico foi duplo: (a) volume insuficiente para 31 classes com a nova
função de perda; (b) ruído sistemático nos rótulos causado pelo sorteio entre
jogadas empatadas (ver `soft_targets_kl_divergence.md`).

Com soft targets (KL Divergence), o volume efetivo é diferente:
- Cada estado gera um **vetor de 31 probabilidades** em vez de um rótulo único.
- A rede aprende a distribuição de scores — mais informação por amostra.
- Com 4× simetria no notebook: 200k estados → 800k exemplos efetivos de treino.

O sweet spot estimado para 31 classes com essa abordagem é **200k registros
únicos**. Gerar 300k oferece margem de segurança e cobre melhor as regiões
de borda (menor frequência natural no dataset).

---

## 3. A Evolução do Hardware: de Semanas para Horas

Na primeira versão do gerador, o script rodava em uma única thread Python.
Um processador Ryzen de 16 threads ficava em ~7% de uso — apenas 1 núcleo
trabalhando. Gerar 50.000 registros em profundidade 7 levava **cerca de 1 semana**.

Após a migração para `ProcessPoolExecutor` com `cpu_count - 2` workers:

| Versão | Threads | Profundidade | Tempo por 50k |
|---|---|---|---|
| Single-thread | 1 | 7 | ~168h (1 semana) |
| Paralelo | 14+ | 5 | ~1h |
| Paralelo | 14+ | 6 | ~1.5–2h (estimado) |

Com essa capacidade, gerar 200k leva ~3–4h e 300k leva ~5–6h ininterruptos —
viável dentro do calendário acadêmico em uma única sessão ou em sessões
retomáveis (`--retomar`).

> **Para a banca:** se questionarem sobre o custo computacional, o argumento
> é que a paralelização via `multiprocessing` do Python distribuiu a explosão
> combinatória do Minimax (complexidade O(b^d)) por todos os núcleos
> disponíveis, reduzindo o tempo de parede em aproximadamente 14×.

---

## 4. O Truque de Mestre: Data Augmentation por Simetria

Se a banca questionar se 200k–300k não é pouco para Deep Learning em geral,
aqui está a "carta na manga": **a geometria do jogo multiplica os dados de graça**.

O tabuleiro do Jogo dos Pontinhos possui **simetria D₂** (grupo de simetria
de um retângulo): espelhamento horizontal, espelhamento vertical, e rotação
de 180°. Se você pegar um tabuleiro e espelhá-lo, a "melhor jogada" também
é espelhada — e o resultado do jogo não muda.

No notebook de treinamento, cada um dos 200k–300k estados originais é
transformado nas 4 variantes simétricas (identidade, flip H, flip V,
rotação 180°). Isso significa:

- **Volume efetivo de treino:** 200k × 4 = 800k exemplos (ou 300k × 4 = 1,2M)
- **Custo computacional extra:** zero — a transformação é uma operação de índice
  em NumPy, sem precisar recalcular nenhum Minimax.
- **Benefício para bordas:** jogadas de borda esquerda viram direita, topo vira
  base — a rede aprende que a borda é borda independentemente de qual lado.

O rótulo também é remapeado deterministicamente:
```
H_0_1  + flip vertical  →  H_8_1   (linha 0 → linha 8 = 8 - 0)
V_1_0  + flip horizontal →  V_1_6   (coluna 0 → coluna 6 = 6 - 0)
```

---

## 5. Resumo da Resposta para a Banca

Se perguntarem: *"Aluno, por que 200.000–300.000 amostras?"*

> *"O volume foi determinado iterativamente. Comecei com 50.000 registros,
> que produziram overfitting severo no MLP e val_top1 de apenas 36% na CNN.
> O diagnóstico revelou dois problemas independentes: volume insuficiente para
> 31 classes e ruído nos rótulos causado pelo sorteio entre jogadas Minimax
> equivalentes.*
>
> *Para o segundo problema, adotei soft targets com KL Divergence: em vez de
> um rótulo único, o gerador grava o vetor completo de scores do Minimax para
> todas as 31 jogadas disponíveis. Isso aumenta a informação por amostra e
> elimina o ruído. Para o primeiro problema, aumentei o volume para 200–300k,
> viabilizado pela paralelização do gerador com ProcessPoolExecutor (redução
> de ~14× no tempo de geração). Com Data Augmentation por simetria D₂ durante
> o treinamento, o volume efetivo chega a 800k–1,2M exemplos sem custo adicional
> de geração."*

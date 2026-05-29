# Arena de Autodiagnóstico — Derrotas da CNN de referência (Pontinhos pequeno)

Infraestrutura **permanente** para descobrir, de forma empírica, **onde** a CNN
de referência erra — em vez de adivinhar a partir de poucas partidas humanas.
A ideia é deixar o modelo jogar em escala contra uma população diversa de
adversários, coletar os fracassos reais e deixar a **distribuição empírica dos
erros** apontar as fraquezas (hard-example mining / análise de exploitabilidade).

Decisão de rota registrada em `docs/historico_decisoes.md`
(entrada *2026-05-29 (noite) — arena de autodiagnóstico*).

> **Por que não injetar dados de "concessão" direto?** Porque o diagnóstico
> inicial (CNN erra a continuação após capturar caixas doadas) veio de poucas
> partidas e era confirmatório. Há contra-evidência: a CNN às vezes **doa caixas
> de propósito e vence** (sacrifício correto). Medir antes de prescrever evita
> ensinar a CNN a parar de sacrificar bem.

## Os 4 pilares

1. **Diversidade** (`adversarios_pontinhos.py`) — sem aleatoriedade, Minimax
   determinístico × CNN argmax produz **uma** partida repetida. Geramos variedade
   com (a) **aberturas aleatórias** de *k* lances e (b) **adversários
   estocásticos/descuidados** (Minimax com ε de lance *unsafe* na abertura/1ª metade).
   A CNN fica em **argmax** (política de produção): a diversidade entra pela
   abertura e pelo adversário, não por ruído na própria CNN.

2. **Localização do erro por *value-swing*** (`forense_value_swing_pontinhos.py`)
   — o erro decisivo é o lance onde o **valor Minimax** cruza de "CNN ganha/empata"
   para "CNN perde". Isso distingue **sacrifício bom** (valor nunca fica negativo)
   de **erro real**. Reaproveita o oráculo Minimax já existente
   (`minimax_pontinhos._scores_de_todas_jogadas`).
   **Recorte de exatidão:** a forense só avalia lances onde a busca **alcança o
   terminal** (lances_restantes ≤ profundidade). Só aí o valor é EXATO (a função
   `avaliar` do Minimax só vale no fim do jogo); na abertura seria aproximado e
   caríssimo. Felizmente é onde moram os erros decisivos (transição p/ o endgame).

3. **Filtro de variância** — só conta como erro da CNN a derrota onde ela tinha
   posição **ganha/empatada e a jogou fora** (regret > 0 cruzando o sinal).
   Descarta azar e posições genuinamente cara-ou-coroa.

4. **Funil de 2 etapas** (`arena_pontinhos.py`) — Etapa 1: jogo em massa **barato**
   (Minimax raso) gravando a trajetória completa. Etapa 2: **filtra** só as
   derrotas/empates-ruins. Etapa 3 (cara): a forense profunda roda **só** no
   conjunto filtrado.

## Saída — corpus de erros decisivos

Cada erro vira um registro com tudo que permite clusterizar a falha:

| Campo | Origem |
|---|---|
| `numero_jogada`, `qtd_tracos`, `fase` | trajetória |
| `traco_cnn`, `traco_minimax`, `classificacao_traco_cnn` | jogada vs ótimo |
| `regret`, `valor_otimo`, `valor_jogado`, `decisivo` | value-swing |
| `qtd_cadeias_longas`, `tamanho_max_cadeia_longa` | `extrair_stats_cadeias` |
| `canais` (4,3,12) | `extrair_canais` |
| `havia_lance_safe` | classificação dos lances disponíveis |
| `matriz_antes` | reconstrução/visualização |

A clusterização desse corpus (por fase, canais, paridade, transição de cadeias)
é o **diagnóstico**: erro concentrado → buraco de dados (gerável/treinável);
erro espalhado → capacidade/busca (dados não resolvem).

## Módulos

| Arquivo | Papel |
|---|---|
| `adversarios_pontinhos.py` | População de adversários + classificação de lances (segura/doação/captura) + abertura aleatória |
| `arena_pontinhos.py` | Partida instrumentada (trajetória completa) + funil etapas 1–2 (coletar derrotas) |
| `forense_value_swing_pontinhos.py` | Etapa 3: localização de blunders por value-swing → corpus de erros |
| `executar_diagnostico.py` | CLI que encadeia as etapas e imprime a taxonomia-resumo |

## Como rodar

A partir da **raiz do repositório**, com o `.venv`. **Jogue RASO, julgue FUNDO**
(o adversário p=6 custa ~5,5 s/lance; p=3 custa ~87 ms e basta).

```bash
# Smoke test sem TFLite (referência = Minimax raso, perde de propósito):
.venv\Scripts\python -m ...executar_diagnostico --partidas 40 --prof-ref 2 \
    --prof-adversario 4 --prof-forense 11

# PILOTO (recomendado): mede a taxa de derrota p/ dimensionar a rodada cheia:
.venv\Scripts\python -m ...executar_diagnostico \
    --modelo "modelos/..._addaug_todos_8p3M.tflite" --partidas 2000 \
    --prof-adversario 3 --prof-forense 13 --eps-descuido 0.2 --abertura-aleatoria 4

# RODADA CHEIA paralela (use ~n_cores-1) com parada automática na base alvo:
.venv\Scripts\python -m ...executar_diagnostico \
    --modelo "modelos/..._addaug_todos_8p3M.tflite" --partidas 200000 \
    --prof-adversario 3 --prof-forense 13 --alvo-erros-decisivos 5000 --workers 8
```

`--workers N` paraleliza por processos (cada um com seu Interpreter TFLite,
padrão do `avaliador_partidas_pontinhos`). Resultado é **idêntico** ao sequencial
(partidas determinísticas por seed; corpus ordenado por seed na gravação).
`--workers` não entra no hash de config — dá para **retomar uma rodada sequencial
em modo paralelo** (mesmo comando + `--workers 8`) para acelerar o que falta.

### Retomada (sobrevive a desligar o PC)

O corpus é gravado **incrementalmente** (`corpus_erros.csv`) e um `checkpoint.json`
guarda o último seed concluído. **Ctrl+C / queda de energia** deixam tudo durável;
reabrir **com o mesmo comando** retoma do ponto exato. Como cada partida é
determinística pelo seed, o resultado em N pedaços é **idêntico** ao de uma rodada
única. Cada config vira uma subpasta `saidas/exec_<hash>/` (ou `--run-id`); mudar
profundidade/eps cria rodada nova (não mistura corpus incompatível).

## Dimensionamento (base boa para diagnóstico)

| Item | Estimativa |
|---|---|
| Erros decisivos/derrota | ~1–3 |
| **Base alvo** | **~5.000 erros decisivos** (≥100–300 por cluster) |
| Derrotas necessárias | ~3.000–8.000 |
| Taxa de derrota | **desconhecida** → medir no piloto |
| Partidas a jogar | ~30k–160k (milhões é exagero) |

Comece pelo **piloto** (1–2k partidas): a arena reporta taxa de derrota, erros/derrota
e tempo/partida → daí calcula-se o tamanho da rodada cheia.

## Onde roda

CPU puro. Cada partida é independente → paralelismo trivial. **Sua máquina**
(multiprocessing) para até alguns milhares de derrotas; **Databricks**
(PySpark `mapInPandas`, mesmo padrão da Fase 2/3) para a rodada grande — o corpus
é particionável por faixa de seed.

## Estado atual (v1)

Pilares 1–4 implementados, retomáveis, **paralelizados** (`--workers`) e validados
ponta-a-ponta (smoke test: N-pedaços == rodada única; paralelo == sequencial).
**Pendente:** adaptação Databricks (PySpark), persistência do corpus em NPZ para
re-treino, e o módulo de clusterização/taxonomia rica (a v1 imprime um resumo agregado).

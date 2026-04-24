# Guia Completo: Geração de Dados e Simulador - Fase Zero

Com base na documentação e no código gerado para a **Fase Zero** do projeto Arena Sagaz, este é o guia passo a passo para iniciar a geração de dados, monitorar o progresso, visualizar as matrizes e testar o simulador tático.

Certifique-se de estar dentro da pasta `arena-sagaz-backend` e com seu ambiente virtual ativado.

---

## 0. Preparando o Ambiente Virtual (Windows)

Antes de executar os scripts, você precisa criar e ativar um ambiente virtual isolado para instalar as dependências do projeto.

Abra o terminal (PowerShell ou Prompt de Comando) na pasta `arena-sagaz-backend` e execute:

### Criar o ambiente virtual
```powershell
python -m venv .venv
```

### Ativar o ambiente virtual
```powershell
.venv\Scripts\activate
```
*(Nota: Se usar PowerShell e ocorrer erro de permissão, execute `Set-ExecutionPolicy Unrestricted -Scope CurrentUser` primeiro e tente ativar novamente.)*

Quando ativado, você verá `(.venv)` no início da linha de comando.

### Instalar dependências
```powershell
pip install -r requirements.txt
```

---

## 1. Como rodar a geração de dados

O script principal para gerar os dados de treinamento é o `gerador.py`. Ele utiliza o algoritmo Minimax com Poda Alpha-Beta para criar os cenários e calcular a jogada perfeita.

Para iniciar a geração, execute:

```bash
# Recomendado para o tabuleiro pequeno (Q-values + soft targets)
python -m gerador_dados.gerador --tamanho pequeno --total 200000 --profundidade 6
```

**Parâmetros disponíveis:**
- `--tamanho`: O tamanho do tabuleiro (`pequeno`, `medio` ou `grande`).
- `--total`: A quantidade total de estados/jogadas que você quer gerar.
- `--profundidade` *(Opcional)*: A profundidade do Minimax (padrão: `7`). Use `6` para o `pequeno` se quiser equilíbrio velocidade/qualidade; `5` só se realmente precisar acelerar (qualidade do "professor" cai).
- `--retomar` *(Opcional)*: Continua de onde parou caso tenha interrompido com `Ctrl+C`. Os lotes já salvos não são regerados; o checkpoint guarda `total_gerado` e `ultimo_lote`.

**Quanto gerar (tabuleiro `pequeno`, 31 classes):**
- **100k** — mínimo viável (~2h). Já se beneficia bastante dos soft targets.
- **200k** — *sweet spot* recomendado (~3–4h). Com 4× simetria no notebook = 800k efetivos.
- **>300k** — retorno decrescente; prefira aumentar `--profundidade` para `7`.

**Interromper e retomar:** pressione `Ctrl+C` a qualquer momento. O script termina os cálculos em andamento, salva o lote parcial, atualiza o checkpoint e sai limpo. Para continuar:

```bash
python -m gerador_dados.gerador --tamanho pequeno --total 200000 --profundidade 6 --retomar
```

---

## 2. Onde os dados serão salvos

Tudo será salvo automaticamente na pasta **`dados/`** (na raiz do backend), dividido em lotes de 5.000 registros:

- **`dataset_pequeno_0001.npz`**: Arquivos compactados NumPy. Cada um contém:
  - `estados` — matrizes do tabuleiro `(N, 9, 7)` em `int8`.
  - `rotulos` — string da jogada ótima (argmax) para cada estado, ex.: `H_2_3`. Mantido para métricas e compatibilidade.
  - `scores` — vetor de Q-values do Minimax `(N, 31)` em `float32`. Slots indisponíveis (jogadas já preenchidas) marcados com `-1e9` e devem ser mascarados antes do softmax. **Este é o alvo principal do treino com `KLDivergence`.**
  - `indices` — índice global do registro.
  - `labels_canonicos` — vetor `(31,)` de strings com a ordem canônica dos slots, mapeando posição ↔ rótulo.
- **`checkpoint_pequeno.json`**: Arquivo de controle que salva o status da geração.

> ⚠️ **Atenção sobre dados antigos:** datasets gerados antes da introdução do campo `scores` **não são compatíveis** com o novo notebook de treino (que usa soft targets). Apague o conteúdo de `dados/` antes de rodar a nova geração:
>
> ```bash
> rm dados/dataset_pequeno_*.npz dados/checkpoint_pequeno.json
> ```

---

## 3. Como avaliar se tudo está rodando bem

O script emite um log no formato JSON a cada 1.000 registros gerados. No terminal, você verá:

```json
{"registros_gerados": 1000, "total_alvo": 50000, "porcentagem": 2.0, "tempo_decorrido_s": 15.4, "estimativa_restante_s": 754.6}
```

Isso informa:
- A quantidade gerada.
- A porcentagem de conclusão.
- A estimativa de tempo restante (`estimativa_restante_s`), útil para calibrar a `--profundidade`.

---

## 4. Como enxergar os dados no formato PNG

Para extrair e visualizar as matrizes como imagens PNG, você pode executar o seguinte comando diretamente no terminal:

```bash
# Gera imagens PNG de todas as matrizes de um arquivo .npz específico
python -c "from gerador_dados.visualizador import lote_para_png; lote_para_png('dados/dataset_pequeno_0001.npz', 'visualizacoes/lote_01/')"
```

Isso criará a pasta `visualizacoes/lote_01/` com imagens PNG onde:
- **Cinza**: Traços (arestas preenchidas, sem distinção de jogador).
- **Azul**: Caixas fechadas pela IA (Jogador 1).
- **Vermelho**: Caixas fechadas pelo Humano (Jogador 2).
- **Preto/Branco**: Pontos da grade e espaços vazios.

---

## 5. Como testar o modelo treinado

Após treinar a CNN e exportar o modelo `.tflite`, existem duas formas de testar: o **Simulador Interativo** (Pygame) e o **Avaliador Automático** (partidas em lote contra o Minimax).

> ⚠️ **Compatibilidade de versão TFLite:** Se o modelo foi exportado no Google Colab (TensorFlow 2.16+), você **deve** usar o ambiente `.venv_tf` (TF 2.21) para carregá-lo. O ambiente `.venv_gpu` (TF 2.10) não reconhece opcodes mais recentes do TFLite e gerará o erro `Didn't find op for builtin opcode 'FULLY_CONNECTED' version '12'`.

### 5.1 Simulador Interativo (Pygame)

Jogue partidas ao vivo contra a IA treinada. É útil para avaliar qualitativamente o comportamento da CNN.

#### Jogar contra o Minimax (sem modelo treinado)
```powershell
.venv_tf\Scripts\python.exe -m gerador_dados.simulador.simulador_tatico --tamanho pequeno --modo minimax
```

#### Jogar contra a CNN treinada
```powershell
.venv_tf\Scripts\python.exe -m gerador_dados.simulador.simulador_tatico --tamanho pequeno --modo cnn --modelo modelos/pontinhos_pequeno_profundidade_8.tflite
```

**Parâmetros disponíveis:**
- `--tamanho`: O tamanho do tabuleiro (`pequeno`, `medio` ou `grande`).
- `--modo`: O agente adversário (`cnn` ou `minimax`).
- `--profundidade`: Profundidade do Minimax (só para `--modo minimax`).
- `--modelo`: Caminho para o arquivo `.tflite` (obrigatório para `--modo cnn`).

**Controles:**
- **Mouse**: Clique nos espaços entre os pontos na tela para fazer um traço. A IA jogará em seguida.
- Tecla **`R`**: Reinicia a partida atual.
- Tecla **`Q`**: Sai do jogo.

O simulador imprime o **tempo de decisão da IA** em milissegundos no terminal a cada jogada.

### 5.2 Avaliador Automático (CNN vs Minimax em lote)

Joga centenas de partidas automatizadas entre a CNN e o Minimax em diferentes profundidades, medindo taxa de vitória, empates e velocidade de decisão. Utiliza **todos os núcleos do processador** via `ProcessPoolExecutor` para acelerar a avaliação.

#### Via linha de comando (recomendado)
```powershell
.venv_tf\Scripts\python.exe -m gerador_dados.avaliador_partidas --modelo modelos/pontinhos_pequeno_profundidade_7.tflite --tamanho pequeno --partidas 200 --profundidades 1 3 5 6
```

**Parâmetros disponíveis:**
- `--modelo`: Caminho para o arquivo `.tflite` (obrigatório).
- `--tamanho`: Tamanho do tabuleiro (`pequeno`, `medio` ou `grande`).
- `--partidas`: Total de partidas por profundidade (padrão: `200`). Metade com CNN como primeiro jogador, metade como segundo.
- `--profundidades`: Lista de profundidades do Minimax para testar (padrão: `1 3 5 6`).

#### Via Notebook (alternativa)

O notebook `notebooks/Avaliacao_CNN_vs_Minimax.ipynb` executa a mesma avaliação. Certifique-se de selecionar o kernel **`.venv_tf`** antes de executar.

**Estimativa de tempo (Ryzen 5700X, 200 partidas por profundidade, multi-core):**

| Profundidade | Tempo aproximado |
|:---:|---|
| 1 | < 10 segundos |
| 3 | ~30 segundos |
| 5 | ~5 minutos |
| 6 | ~20–30 minutos |

**Exemplo de saída:**
```
========================================================================
AVALIAÇÃO POR PARTIDAS REAIS — CNN vs Minimax
========================================================================

  Adversário: Minimax(p=5)  (200 partidas)
  Vitórias CNN           180  ( 90.0%)
  Empates                 10  (  5.0%)
  Derrotas CNN            10  (  5.0%)
  Tempo médio CNN:  0.15 ms/jogada
  Tempo médio Minimax(p=5): 245.3 ms/jogada
  CNN é 1635× mais rápida
========================================================================
```

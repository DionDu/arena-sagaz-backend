# `dados/jogo_pontinhos/` — o acervo de posições de partida do desafio

## O que tem aqui

`posicoes_de_autoplay_pequeno.npz` — **897.125 posições de tabuleiro 4×3 sem
nenhuma caixa fechada**, extraídas dos estados de *autoplay de minimax* com que a
CNN do aplicativo foi treinada.

É de onde o job tira a **posição inicial** de todo desafio do Jogo dos Pontinhos
(T049h, decisão do dono de 11/09/2026 — `../../../arena-sagaz-frontend/docs/DECISOES-do-dono.md` §8h).

| campo | tipo | o que é |
|---|---|---|
| `nu_mascara` | `uint32[897125]` | uma posição por entrada: o bit `i` ligado significa que o traço `co_rotulo[i]` está marcado |
| `co_rotulo` | `<U5[31]` | os 31 rótulos na **ordem canônica** (`H_0_1`, `H_0_3`, …) |

Tamanho no disco: **2,58 MB** (contra 106 MB dos NPZ de origem).

## ⚠️ Por que autoplay, e não traços sorteados

Até 11/09/2026 o gerador sorteava os traços às cegas. ⛔ **É o mesmo argumento
que o projeto já testou e descartou no treino da CNN**: dataset de tabuleiros
aleatórios deu rede ruim, porque dois jogadores quase nunca chegam àqueles
estados — foi por isso que se passou ao autoplay.

E aqui a consequência é concreta: **o gabarito do desafio é produzido pela
própria CNN** (o backend roda o mesmo `.tflite` do aplicativo, e o portão T001
prova que os dois runtimes concordam). Posição fora da distribuição de treino
gera solução de referência subótima, a régua mede a coisa errada, e ⛔ **nada no
log denuncia**.

## ⚠️ Por que só as posições sem caixa fechada

O desafio guarda uma **sequência de lances**, não uma matriz: a posse de uma
caixa é histórico, e de quem é a vez depende de quem fechou caixa. Os NPZ têm só
a matriz `9×7`, e os valores `{0, 1, 8, 9}` dizem *que* uma caixa está fechada,
mas não **de quem** ela é.

✅ Sem caixa fechada, a ponte fecha: o placar é 0-0, a vez sai da paridade, e
**qualquer ordem dos mesmos traços dá o mesmo estado**. Por isso a posição é o
*conjunto* de traços — e 31 traços cabem num `uint32`.

Essa propriedade vale porque "sem caixa fechada" é **monótono**: se o conjunto
final não fecha caixa nenhuma, nenhum prefixo dele fecha. Toda ordem é uma
sequência legal.

## A distribuição, por fase da partida

Medido em 11/09/2026, sobre 3.423.460 estados de 419 NPZ — dos quais 1.362.893
não têm caixa fechada, e 897.125 são distintos:

| traços | posições | | traços | posições |
|---:|---:|---|---:|---:|
| 1 | 31 | | 11 | 76.910 |
| 2 | 465 | | 12 | 64.540 |
| 3 | 4.495 | | 13 | 50.403 |
| 4 | 30.500 | | 14 | **36.000** |
| 5 | 82.504 | | 15 | 24.317 |
| 6 | 104.219 | | 16 | 14.194 |
| 7 | 108.706 | | 17 | 5.350 |
| 8 | **107.577** | | 18 | 1.414 |
| 9 | 97.560 | | 19 | 231 |
| 10 | 87.692 | | 20 | 17 |

Em negrito as duas fases que o editorial usa hoje: `pontinhos_chegar_ao_placar`
prepara com **8** traços e `pontinhos_fechar_caixas` com **14**.

⛔ **Acima de 20 traços não existe posição sem caixa fechada no 4×3** — para
chegar lá, alguma caixa teve de ser fechada. Um `nu_lances_de_preparo` maior que
isso faz o job falhar alto, com a mensagem dizendo o porquê.

## Como reconstruir

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python -u scripts\extrair_posicoes_de_autoplay_pontinhos.py
```

Leva poucos segundos. A origem é `../ia/dados/jogo_pontinhos/profundidade_minimax_11_adaptativo/`,
que é do **laboratório** e não viaja no repositório do backend.

⚠️ **A saída é ordenada de forma determinística** (por quantidade de traços e,
dentro dela, pelo valor da máscara), então rodar de novo sobre a mesma origem
produz um arquivo byte-idêntico.

⚠️ **As três pastas de `ia/dados/jogo_pontinhos/` carregam os mesmos estados** —
medido: 3.423.460 em cada uma, com as mesmas 897.125 posições sem caixa fechada.
O que muda entre elas são os rótulos e os canais, não os tabuleiros. A escolhida
é a que nomeia a procedência.

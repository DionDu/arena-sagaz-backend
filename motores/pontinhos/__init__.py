"""O motor do Jogo dos Pontinhos no backend — CNN mais política.

⚠️ **O adversário do Pontinhos não é "a CNN".** É a CNN **mais a política** de
cada nível: sem `epsilon` e `usaCapturaGulosa`, os quatro níveis seriam o mesmo
jogador quatro vezes, e a régua de dificuldade mediria quatro vezes a mesma
coisa. A rede mora em `motor_pontinhos.py`; a política, em `politica.py`.

⛔ **Nada aqui reimplementa a codificação** (RF-DES-018b). Quem transforma o
tabuleiro em tensor é `extrair_canais`, o código do laboratório que vive no
espelho — o mesmo que o app porta em Dart, e o mesmo que o contrato descreve.

⚠️ **E `ia/jogos/jogo_pontinhos/motor/minimax_pontinhos.py` NÃO é o adversário do
app** (RF-DES-018a). O minimax e o oráculo do laboratório existem para *medir* a
CNN, não para jogar contra gente. O que o job precisa enfrentar é o que a pessoa
enfrenta.

⚠️ **Nasce no tabuleiro pequeno**, 4×3 caixas, porque é o único `.tflite` que
existe (RF-DES-018d). Não é limitação desta entrega; é o estado do ativo.
"""

"""O Quatro em Linha no backend: o ÁRBITRO em Python e o JOGADOR em Dart compilado.

⚠️ **O primeiro jogo que nasce sem segunda escrita.** As damas e o Pontinhos
tiveram, cada um, um episódio de divergência entre a regra do app e a do
servidor. Aqui, quem escolhe lance é o executável compilado do MESMO pacote Dart
que o aparelho embarca (`jogador_dart_quatro.py`, T109); o Python só sabe as
regras (`motor_quatro.py`, T105), lidas do contrato (`contrato_quatro.py`), e é
isso que o avaliador do desafio enxerga.

⛔ **Modalidade é DADO.** Nada neste pacote cita uma modalidade pelo nome; o
cadeado da T108 reprova o literal.
"""

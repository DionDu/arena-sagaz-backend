"""O xadrez no backend: o JOGADOR em Rust compilado, sem árbitro em Python.

⚠️ **O segundo jogo que nasce sem segunda escrita, e o primeiro sem árbitro.** O
Quatro em Linha ainda tem as regras em Python (`motores/quatro/motor_quatro.py`);
aqui nem isso: toda pergunta de regra (o lance é legal? a partida acabou? quem
venceu?) vai ao executável `servidor_de_lances_xadrez`, compilado do MESMO crate
que o aparelho embarca (RF-XDR-043, `research.md` R-20). Este pacote só sabe
abrir o executável e ler o contrato:

- `contrato_xadrez.py`: o contrato lido do espelho (as modalidades, os níveis,
  `magno_no_build`, o SHA-256 que o executável anuncia, a versão do motor);
- `jogador_xadrez.py`: o processo do executável e as operações dele (T063).

⛔ **Modalidade é DADO.** Nada neste pacote cita uma modalidade pelo nome fora do
`contrato_xadrez.py` (o cadeado da T065).
"""

"""Diagnósticos de campo — o app contando ao servidor o que deu errado nele.

Hoje há um só: **o motor nativo não carregou neste aparelho** (T199b). O módulo
nasceu genérico de propósito — `co_jogo` e `co_motor` são colunas, não schemas —
porque a mesma pergunta ("o binário carregou?") vale para o TFLite do Pontinhos
e para qualquer motor nativo que venha depois.

⚠️ **Diagnóstico não é log de partida.** Ver o cabeçalho da migração
`0016_diagnostico_motor_nativo` para o argumento que separou os dois; em uma
linha: com a trava da T199 ligada ninguém joga no Sagaz naquele aparelho, então
o aviso viajaria pendurado em partidas que nada têm a ver com ele.
"""

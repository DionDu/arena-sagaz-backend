"""O motor de damas do backend — um ADAPTADOR, não uma reimplementação.

⚠️ **Nenhuma regra de damas é escrita aqui.** Quem sabe jogar é o Python do
laboratório (RF-DES-018), que mora em `espelho_laboratorio/` como cópia
byte-idêntica (RF-DES-148). Este pacote só o **veste** com os dois papéis da
camada de motores — `Arbitro` e `JogadorDeMotor` — e traduz o estado para uma
forma serializável (RF-DES-162).

É a mesma disciplina que o app já aplica: *"o motor decide, o app pergunta"*.
Aqui o motor decide e **o job pergunta**.

⛔ Se algum dia parecer necessário "só ajustar uma regrinha" neste pacote, a
resposta é não: o ajuste vai no laboratório, o espelho é refeito, e o cadeado 6
prova que os bytes bateram. Uma regra corrigida aqui faria o servidor calibrar um
jogo que ninguém joga.
"""

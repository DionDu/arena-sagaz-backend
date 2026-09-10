"""`api/desafios/painel/` — O PAINEL DE CURADORIA (RF-DES-012a a 012f, T039/T040).

═══════════════════════════════════════════════════════════════════════════
O QUE ELE E, EM UMA FRASE
═══════════════════════════════════════════════════════════════════════════

Uma **pagina HTML servida pelo proprio backend**, protegida por token, onde o
dono ve os candidatos gerados pelo job e decide: **aprovar**, **descartar** (com
motivo) ou **agendar noutra data**.

⛔ **Nada vai ao ar sem essa visita** (RF-DES-012a). O job grava tudo como
`candidato`, e so `aprovado` e servido ao aplicativo.

═══════════════════════════════════════════════════════════════════════════
POR QUE HTML CRU, E NAO UM APLICATIVO
═══════════════════════════════════════════════════════════════════════════

RF-DES-012e e explicito: *"pagina administrativa servida pelo proprio backend,
protegida por token, sem app novo e **sem build de Flutter Web**"*. O Flutter Web
foi **descontinuado como alvo em 2026-07**, e ressuscita-lo para uma ferramenta
interna de um usuario so criaria um segundo pipeline de build, um segundo deploy
e um segundo lugar onde a identidade visual envelhece.

⚠️ **O `painel/` que existe na raiz do ecossistema NAO e este.** Aquele e a
bancada de telemetria da CNN, em Flutter, e o nome coincidir e um acidente
historico — vale a pena ler duas vezes antes de mexer no arquivo errado.

═══════════════════════════════════════════════════════════════════════════
AS PECAS, E POR QUE SAO SEPARADAS
═══════════════════════════════════════════════════════════════════════════

| modulo | o que faz | por que separado |
|---|---|---|
| `seguranca.py` | quem pode entrar | e a unica peca que le segredo; misturada com rota, a checagem viraria um `if` a se esquecer |
| `repositorio.py` | o SQL, so ele | a leitura e sempre pela VIEW, e um lugar so torna isso conferivel |
| `vigilancia.py` | as duas secoes de alerta (T040) | elas existem **sem** a fila de candidatos, e vao continuar existindo quando a fila estiver cheia |
| `servico.py` | as regras da curadoria | descartar exige motivo, agendar exige aprovado — regra e regra, e nao formulario |
| `pagina.py` | o HTML | trocar a aparencia nao pode obrigar a mexer em consulta |
| `rotas.py` | as rotas HTTP | so amarra as pecas |

═══════════════════════════════════════════════════════════════════════════
⚠️ O VOCABULARIO: APROVAR E AGENDAR SAO ATOS DIFERENTES
═══════════════════════════════════════════════════════════════════════════

E a precisao que RF-DES-153 acrescentou em 04/09/2026, e ela e a razao de este
painel ter **duas** acoes onde parecia haver uma:

  · **aprovar** e sobre o **desafio** (`desafio.tb001_desafio.co_curadoria`), e
    acontece **antes** de ele entrar em colecao nenhuma;
  · **agendar** e o **vinculo** com um dia
    (`desafio_dia.tb001_desafio_dia`) — e e ele que "trocar a data" muda.

⛔ **So desafio aprovado pode ser agendado.** A regra vive em `servico.py`, e nao
num `disabled` no HTML: um botao desabilitado na tela e uma decoracao que um
`curl` ignora.
"""

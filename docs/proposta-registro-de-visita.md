# ⛔ DECISÃO PENDENTE DO DONO — onde a visita ao desafio incompatível se grava

> **Estado:** aberta em **10/09/2026**, durante a T043. As outras duas rotas do
> envio (`/resolucao` e `/dica`) foram entregues; **`POST /v1/desafios/visita`
> não**, e a razão está aqui.
>
> **O que é preciso de você:** escolher entre as três opções da última seção. A
> escrita da migração e do código leva minutos depois da escolha.

---

## O requisito, e por que ele não cabe no que existe

**RF-DES-024** (precisado por você em 03/09/2026):

> "Não podia participar" quer dizer **uma** coisa: ela **abriu o app** e o desafio
> do dia exigia versão que ela não tem. Nesse caso o dia **não conta contra** ela —
> e, como não existe sequência de desafios separada, quem precisa ser protegida é
> **a chama**. A solução escolhida é a mais simples que existe: o app registra a
> visita **como se fosse um dia jogado**, pelo mesmo caminho que já alimenta a
> chama.

O problema é que **esse caminho não existe como endpoint**. A chama é
**derivada**, e não incrementada — `RepositorioSincronizacao.recalcular_chama`
(`api/sincronizacao/repositorio.py`) a recalcula assim:

```sql
SELECT DISTINCT ((COALESCE(dh_fim, dh_inicio) AT TIME ZONE 'UTC')
                   + make_interval(mins => COALESCE(nu_offset_minuto_j1, 0)))::date
  FROM partida.tb001_partida
 WHERE id_usuario = :id
   AND ic_pontua = true
   AND co_status = 'concluida'
```

Ou seja: **os dias saem das partidas concluídas que pontuam**. Uma visita não é
partida, e uma partida de desafio tem `ic_pontua = FALSE` (é o anti-farm que já
existia no `pvp_local`).

⚠️ **E foi você quem fechou a porta de trás, com razão.** A correção definitiva
da chama, em 2026-08, foi justamente parar de guardar um contador e passar a
derivar tudo do histórico:

> "O total de dias **NÃO é persistido de propósito**: ele é derivado do log e
> recalculado a cada leitura, como a sequência. Guardá-lo (…) criaria uma segunda
> cópia da mesma verdade, que é justamente a origem do defeito que isto conserta."

Então gravar o dia direto em `progressao.tb001_progressao_usuario` **não
funcionaria**: o próximo recálculo autoritativo o sobrescreveria, e o defeito
seria intermitente — o pior tipo.

---

## ⛔ Por que eu parei em vez de decidir sozinho

`tests/unitarios/test_migracao_bate_com_data_model.py` diz, no cabeçalho:

> · a migração divergiu do que ele validou → conserta-se a migração;
> · o modelo é que precisa mudar → ⛔ **é decisão dele**, e o `data-model.md` muda
>   primeiro, com o registro em `DECISOES-do-dono.md`.

Acrescentar uma tabela é **mudar o modelo que você pré-validou em 08/09/2026**.
Fazer isso por conta própria transformaria a sua pré-validação num cheque em
branco, que é exatamente o que aquele cadeado existe para impedir.

⚠️ **E há um custo operacional junto:** as `0018`/`0019`/`0020` já estão
aplicadas no `des` desde 10/09. Uma tabela nova exige ou uma `0021` aditiva, ou o
`downgrade 0017` + `upgrade head` da regra §8b — em qualquer caso, **um comando
que você roda**, não eu.

---

## As três opções

### Opção A — uma tabela nova em `desafio_dia` (recomendada)

```sql
CREATE TABLE desafio_dia.tb007_visita (
    id_visita        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_usuario       UUID        NOT NULL REFERENCES conta.tb001_usuario(id_usuario),
    dt_dia_local     DATE        NOT NULL,   -- ⚠️ o dia do RELÓGIO DA PESSOA
    id_desafio_dia   UUID        REFERENCES desafio_dia.tb001_desafio_dia(id_desafio_dia),
    co_motivo        VARCHAR(30) NOT NULL,
    nu_offset_minuto SMALLINT,
    dh_visita        TIMESTAMPTZ NOT NULL,
    dh_registro      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT un001_visita UNIQUE (id_usuario, dt_dia_local),
    CONSTRAINT ck001_motivo CHECK (co_motivo IN
        ('jogo_desconhecido', 'modalidade_desconhecida', 'forma_desconhecida',
         'chave_desconhecida', 'versao_insuficiente'))
);
```

E `recalcular_chama` passa a unir os dois conjuntos de dias:

```sql
SELECT dia FROM (… as partidas, como hoje …)
UNION
SELECT dt_dia_local FROM desafio_dia.tb007_visita WHERE id_usuario = :id
```

**A favor:**
- ⚠️ **A chama continua DERIVADA**, que é a decisão que consertou o bug de 08/2026.
  Nada de contador; o dia da visita vira mais uma linha de histórico, do mesmo
  jeito que uma partida.
- `dt_dia_local` já gravado resolve o fuso na origem — ⚠️ sem ele, uma visita às
  21h no Brasil cairia no **dia seguinte** em UTC, que é literalmente o bug que a
  chama já teve uma vez.
- `un001_visita` torna o endpoint idempotente de graça: abrir o app cinco vezes
  no mesmo dia grava uma linha.
- `id_desafio_dia` é **anulável de propósito**: quem cai neste caminho pode não
  ter conseguido nem ler a resposta do desafio (versão mínima maior, chave
  desconhecida). Exigi-lo faria falhar justamente o caso que a rota cobre.
- Fica em `desafio_dia`, que ⛔ **ainda não existe no `prd`** — então nada disso
  toca schema com dado real de usuário.

**Contra:** uma migração a mais para você rodar, e `data-model.md` a atualizar.

### Opção B — adiar a rota para o BLOCO 3

A rota só é **chamada** pelo app, e nenhuma tela existe antes da T050. Dá para
fechar o servidor sem ela e implementá-la junto da tela de atualizar.

**A favor:** nada muda agora, e a decisão de banco vem junto do resto do app.
**Contra:** ⚠️ a T050 é o portão de aceite do **servidor**, e ela fecharia com um
requisito do servidor por fora — exatamente o tipo de dívida que a ordem-portão
foi criada para evitar.

### Opção C — não registrar a visita

A chama quebra para quem abre o app num dia de desafio incompatível.

**Contra:** contraria RF-DES-024 diretamente, e o caso não é hipotético — ele
acontece **toda vez** que um jogo ou tipo novo entra no rodízio e há gente na
versão anterior.

---

## O que já está pronto e esperando a decisão

- `api/desafios/modelos_envio.py` → `EnvioDeVisita`, com os cinco motivos e o
  `nu_offset_minuto`, já escrito e comentado.
- A rota em si são ~15 linhas: ela recebe o payload, grava a linha e responde
  `204`. ⚠️ O que falta é **só** onde gravar.

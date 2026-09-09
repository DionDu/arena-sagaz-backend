"""O schema `desafio_dia` — O EVENTO: tudo o que sai do aparelho da pessoa.

Revision ID: 0019_schema_desafio_dia
Revises: 0018_schema_desafio
Create Date: 2026-09-09

⛔⛔⛔ **PROPOSTA — NAO FOI APLICADA EM NENHUM BANCO.** ⛔⛔⛔

Antes de qualquer `alembic upgrade`, rodar `scripts/identificar_banco.py` — o
`AMBIENTE` do `.env` **nao e prova** de para onde a conexao aponta.

    DES = hopper.proxy.rlwy.net:21165
    PRD = hayabusa.proxy.rlwy.net:42857

═══════════════════════════════════════════════════════════════════════════
A FRONTEIRA: ESTE SCHEMA E ESCRITO PELO APLICATIVO
═══════════════════════════════════════════════════════════════════════════

    desafio      = a linha de producao  → escreve o JOB   (migracao 0018)
    desafio_dia  = o evento             → escreve o APP   (esta)

Tudo o que sai do aparelho cai aqui, pelo caminho de sincronizacao que ja existe:
resolucao, tentativa, extrato de XP, poder consumido e reacao.

⚠️ **As setas apontam num sentido so.** O evento conhece o desafio e conhece a
partida; nem o desafio nem a partida sabem que o evento existe.

═══════════════════════════════════════════════════════════════════════════
⚠️ A TENTATIVA PRECEDE A RESOLUCAO — e essa ordem e a decisao central daqui
═══════════════════════════════════════════════════════════════════════════

**A RESOLUCAO E UMA PARTIDA** (determinacao do dono, 04/09/2026, item 1c), e ela
usa o log que ja existe: `partida.tb001_partida` com `co_modo = 'desafio'` e
`ic_pontua = FALSE` (a coluna ja existe — e o anti-farm do `pvp_local`).

⛔ **Nao ha log de lances proprio do desafio.** O replay do desafio e o replay de
uma partida. E por isso que:

    tb002_tentativa  → aponta para `partida.tb001_partida`  (RF-DES-215)
    tb003_resolucao  → aponta para a TENTATIVA que deu certo

A ideia de a resolucao apontar direto para a partida foi descartada: uma pessoa
tenta varias vezes, e cada tentativa e uma partida. Quem sabe qual delas venceu e
a resolucao, e ela chega la **pela tentativa**.

⚠️ **O poder pende da TENTATIVA, nao do dia** (RF-DES-217): e ali que a dica foi
de fato gasta. O teto continua sendo de duas dicas por **desafio**, e o contador
do dia vira uma soma — ver o comentario de `tb005_poder_consumido`.

═══════════════════════════════════════════════════════════════════════════
⚠️ FORMA FINAL, PELA REGRA §8b
═══════════════════════════════════════════════════════════════════════════

`docs/DECISOES-do-dono.md` §8b: enquanto nao houver o primeiro `upgrade` no PRD,
defeito de modelagem **dropa e recria dentro desta propria migracao**. Nada de
`ALTER` de remendo, e nada de campo importante no fim da tabela.

⚠️ A regra **nao vale** para `partida`, que tem dado real — por isso a `0020` e
estritamente aditiva.
"""

from typing import Sequence, Union

from alembic import op

# "0019_schema_desafio_dia" tem 23 caracteres — dentro do limite de 32 do Alembic.
revision: str = "0019_schema_desafio_dia"
down_revision: Union[str, None] = "0018_schema_desafio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria o schema `desafio_dia` inteiro, dimensoes antes dos fatos."""
    op.execute("CREATE SCHEMA IF NOT EXISTS desafio_dia")

    # ══ Dimensoes ═══════════════════════════════════════════════════════════
    #
    # ⚠️ **AS TRES RECEBEM CODIGO VINDO DO APLICATIVO**, e por isso as tres levam
    # o sentinela `9999`. Nao e simetria decorativa: sem um destino valido, um
    # aparelho com versao mais nova que o backend estoura a FK, toma 500, e o
    # evento fica preso PARA SEMPRE na fila de sincronizacao — a partida daquela
    # pessoa nunca sobe. A licao e da `0011`, e custou caro.

    # ── Que TIPO de linha de XP e esta ──────────────────────────────────────
    #
    # A formula de produto e `XP = 30 x (0,60 + 0,40 x Q)`, ou seja
    # `XP = 18 + 12 x Q`, com `Q` formado por quatro parcelas: tentativas 0,30 ·
    # tempo 0,20 · dica 0,25 · merito 0,25.
    #
    # Cada linha de `tb004_xp_desafio` vale `12 x vr_peso x vr_normalizado`, e a
    # linha `base` vale os 18 fixos. Uma formula so, verificavel por teste em toda
    # linha gravada.
    #
    # ⚠️ `merito` (5) e `medida` (6) sao os dois tipos que **apontam para um
    # feito**; e essa a dupla que o `ck003_feito` da tabela de fato exige. A
    # diferenca entre eles: `medida` e feito medido e exibido no Raio-X que **nao
    # pontua** (peso zero).
    op.execute(
        """
        CREATE TABLE desafio_dia.tb901_tipo_xp_desafio (
            nu_tipo_xp SMALLINT    PRIMARY KEY,
            co_tipo_xp VARCHAR(20) NOT NULL UNIQUE,
            no_tipo_xp VARCHAR(40) NOT NULL
        )
        """
    )
    op.execute(
        """
        INSERT INTO desafio_dia.tb901_tipo_xp_desafio
            (nu_tipo_xp, co_tipo_xp, no_tipo_xp) VALUES
            (   1, 'base',         'Piso por resolver'),
            (   2, 'tentativas',   'Parcela de tentativas'),
            (   3, 'tempo',        'Parcela de tempo'),
            (   4, 'dica',         'Parcela de dica'),
            (   5, 'merito',       'Merito do jogo (um feito)'),
            (   6, 'medida',       'Feito medido que nao pontua'),
            (   7, 'consolo',      'Tentou e nao resolveu'),
            (   8, 'ajuste',       'Ajuste do teto diario'),
            (9999, 'desconhecido', 'Desconhecido');
        """
    )

    # ── Que poder foi gasto ─────────────────────────────────────────────────
    #
    # ⚠️ **O MESMO vocabulario da `0017`** (RF-DES-183). La, `co_poder` e
    # `VARCHAR` com `CHECK` dentro de `partida.tb002_jogada`; aqui e dimensao,
    # porque este schema recebe codigo do aplicativo e precisa do sentinela.
    # Duas formas, um vocabulario: `dica` e `voltar_jogada` significam a mesma
    # coisa nos dois lugares, e um teste confere que as listas nao divergiram.
    op.execute(
        """
        CREATE TABLE desafio_dia.tb902_tipo_poder (
            nu_tipo_poder SMALLINT    PRIMARY KEY,
            co_tipo_poder VARCHAR(30) NOT NULL UNIQUE,
            no_tipo_poder VARCHAR(40) NOT NULL
        )
        """
    )
    op.execute(
        """
        INSERT INTO desafio_dia.tb902_tipo_poder
            (nu_tipo_poder, co_tipo_poder, no_tipo_poder) VALUES
            (   1, 'dica',          'Dica'),
            (   2, 'voltar_jogada', 'Voltar jogada'),
            (9999, 'desconhecido',  'Desconhecido');
        """
    )

    # ── Com que emoticon se reage a uma linha do quadro ─────────────────────
    #
    # `co_emoji` tem 16 caracteres e nao 2 de proposito: um emoji pode ser uma
    # SEQUENCIA de pontos de codigo (base + seletor de variacao + modificador de
    # tom de pele), e cortar no meio produz um caractere invalido.
    #
    # ⚠️ **`no_tipo_reacao` NAO e o rotulo da tela.** Leitor de tela e dica de
    # toque leem no idioma da pessoa, e este banco nao fala tres idiomas: o app le
    # `co_chave_i18n` e resolve pelo `.arb`. O `no_` e para o painel de curadoria.
    op.execute(
        """
        CREATE TABLE desafio_dia.tb903_tipo_reacao (
            nu_tipo_reacao SMALLINT    PRIMARY KEY,
            co_tipo_reacao VARCHAR(20) NOT NULL UNIQUE,
            no_tipo_reacao VARCHAR(30) NOT NULL,
            co_emoji       VARCHAR(16) NOT NULL,
            co_chave_i18n  VARCHAR(40) NOT NULL,
            nu_ordem       SMALLINT    NOT NULL,
            ic_ativo       BOOLEAN     NOT NULL DEFAULT TRUE,
            CONSTRAINT un001_ordem UNIQUE (nu_ordem)
        )
        """
    )

    # ⏳ **ESTAS LINHAS SAO PROVISORIAS — T090 as refaz.**
    #
    # O dono esta definindo as reacoes no Claude Design; quando os artefatos
    # chegarem, este `INSERT` e refeito com o conjunto real (RF-DES-226).
    #
    # ⚠️ Elas entram assim mesmo, em vez de ficarem de fora, por um motivo
    # pratico: `tb006_reacao` tem FK para ca, e uma dimensao vazia faria toda a
    # cadeia de reacao ficar inexercitavel ate o Design responder — inclusive nos
    # testes. Tres reacoes provisorias custam um `INSERT` para trocar; uma cadeia
    # sem teste custa muito mais.
    #
    # ⚠️ O sentinela entra com `ic_ativo = FALSE`: ele existe para **receber**
    # codigo desconhecido, nunca para aparecer na barra de reacoes.
    op.execute(
        """
        INSERT INTO desafio_dia.tb903_tipo_reacao
            (nu_tipo_reacao, co_tipo_reacao, no_tipo_reacao, co_emoji,
             co_chave_i18n, nu_ordem, ic_ativo) VALUES
            (   1, 'palmas',       'Palmas',       '\U0001F44F',
                'reacaoPalmas',       1, TRUE),
            (   2, 'uau',          'Uau',          '\U0001F62E',
                'reacaoUau',          2, TRUE),
            (   3, 'fogo',         'Fogo',         '\U0001F525',
                'reacaoFogo',         3, TRUE),
            (9999, 'desconhecido', 'Desconhecido', '❔',
                'reacaoDesconhecida', 99, FALSE);
        """
    )

    # ══ Fatos ═══════════════════════════════════════════════════════════════

    # ── Qual desafio e o de hoje ────────────────────────────────────────────
    #
    # Duas restricoes, duas regras de produto:
    #
    # `un001_dia` e a **idempotencia do job**: rodar duas vezes na mesma data nao
    # troca o desafio publicado, porque a segunda insercao falha. A garantia mora
    # no banco, e nao numa checagem do codigo, porque duas execucoes simultaneas
    # passariam pela checagem e so o banco as separa.
    #
    # `un002_desafio` e *"um desafio e publicado UMA VEZ SO"*. A reprise passa sem
    # excecao porque ela e uma **copia**, com `id_desafio` proprio apontando para
    # a origem — dois desafios identicos, dois identificadores, dois quadros.
    op.execute(
        """
        CREATE TABLE desafio_dia.tb001_desafio_dia (
            id_desafio_dia  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            dt_dia          DATE        NOT NULL,
            id_desafio      UUID        NOT NULL
                REFERENCES desafio.tb001_desafio(id_desafio),
            dh_encerramento TIMESTAMPTZ NOT NULL,
            dh_publicacao   TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT un001_dia     UNIQUE (dt_dia),
            CONSTRAINT un002_desafio UNIQUE (id_desafio)
        )
        """
    )

    # ── Toda tentativa, com ou sem sucesso ──────────────────────────────────
    #
    # ⚠️ **Tentativa NUNCA aparece no quadro. Falhar e privado.** Ela existe para
    # tres coisas: o XP de consolo, o denominador da fracao de participacao, e a
    # medicao de adocao.
    #
    # `nu_tempo_ms` e o tempo **desta** tentativa — do primeiro lance dela ate o
    # objetivo (ou ate desistir). O tempo total do dia e a soma das tentativas, e
    # a soma se faz na consulta. Cabe folgado num `INT`: o limite sao ~2,1 bilhoes
    # de milissegundos, ou 24 dias.
    #
    # `id_partida` e `UNIQUE`: uma partida e de uma tentativa so.
    op.execute(
        """
        CREATE TABLE desafio_dia.tb002_tentativa (
            id_tentativa    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_desafio_dia  UUID     NOT NULL
                REFERENCES desafio_dia.tb001_desafio_dia(id_desafio_dia),
            id_usuario      UUID     NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),

            id_partida      UUID     NOT NULL UNIQUE
                REFERENCES partida.tb001_partida(id_partida),

            nu_sequencia    SMALLINT NOT NULL,
            ic_resolveu     BOOLEAN  NOT NULL,
            nu_tempo_ms     INT      NOT NULL,
            dh_inicio       TIMESTAMPTZ NOT NULL,
            dh_fim          TIMESTAMPTZ NOT NULL,
            dh_registro     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT un001_tentativa UNIQUE (id_desafio_dia, id_usuario,
                                               nu_sequencia),
            CONSTRAINT ck001_sequencia CHECK (nu_sequencia > 0),
            CONSTRAINT ck002_tempo     CHECK (nu_tempo_ms >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix001_tentativa_usuario "
        "ON desafio_dia.tb002_tentativa (id_usuario, id_desafio_dia)"
    )

    # ── A tentativa que deu certo ───────────────────────────────────────────
    #
    # `un001_resolucao` e, ao mesmo tempo, a regra *"uma resolucao por pessoa por
    # desafio"* e a **chave de idempotencia do envio**: reenviar o mesmo resultado
    # nao cria uma segunda linha. A chave natural ja e a chave de idempotencia —
    # nao foi preciso inventar uma.
    #
    # `nu_lance_cumpre_desafio` e o `nu_ordem` da jogada em que a ultima clausula
    # passou a valer; o replay do Raio-X abre **em torno dele**.
    #
    # ⚠️ **E `nu_ordem`, nao `nu_lance`.** `nu_ordem` e sequencia continua de
    # eventos: nunca recua e nunca se repete. `nu_lance` e o numero do lance no
    # tabuleiro e **recua** quando alguem desfaz uma jogada, podendo repetir. Como
    # ponteiro para uma linha so, `nu_ordem` e o unico que serve. No desafio os
    # dois coincidem hoje — "voltar jogada" nao existe ali —, mas apontar pelo
    # numero que pode repetir seria uma armadilha esperando o dia em que passe a
    # existir.
    #
    # `nu_xp` fica entre 18 e 30 por `CHECK`: 18 e o piso por resolver, e o teto de
    # 30/dia e **da colecao** — ele entra como linha de `ajuste` em
    # `tb004_xp_desafio`, nunca como corte aqui.
    #
    # ⚠️ `co_auditoria` **nao pune ninguem**. `divergente` marca a linha para
    # investigacao: punir automaticamente com base num recalculo que pode ter bug
    # proprio faria o app tirar XP de gente honesta na primeira versao errada do
    # arbitro.
    op.execute(
        """
        CREATE TABLE desafio_dia.tb003_resolucao (
            id_resolucao    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_desafio_dia  UUID     NOT NULL
                REFERENCES desafio_dia.tb001_desafio_dia(id_desafio_dia),
            id_usuario      UUID     NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),

            id_tentativa    UUID     NOT NULL UNIQUE
                REFERENCES desafio_dia.tb002_tentativa(id_tentativa),

            nu_lance_cumpre_desafio SMALLINT NOT NULL,

            nu_xp           SMALLINT NOT NULL,

            nu_versao_catalogo SMALLINT NOT NULL,
            co_auditoria    VARCHAR(12) NOT NULL DEFAULT 'pendente',
            de_auditoria    TEXT,
            dh_resolucao    TIMESTAMPTZ NOT NULL,
            dh_registro     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT un001_resolucao UNIQUE (id_desafio_dia, id_usuario),
            CONSTRAINT ck001_xp        CHECK (nu_xp BETWEEN 18 AND 30),
            CONSTRAINT ck002_lance     CHECK (nu_lance_cumpre_desafio > 0),
            CONSTRAINT ck003_auditoria CHECK (co_auditoria IN
                                         ('pendente', 'confere', 'divergente'))
        )
        """
    )

    # ── Os feitos E a conversao em XP, linha a linha ────────────────────────
    #
    # Irma de `partida.tb003_xp_partida`, e e por causa desta segunda tabela de XP
    # que o cadeado 7 (T047) nasce agora: a uniao das origens de XP e uma VIEW que,
    # esquecida, **nao da erro** — o ranking simplesmente conta menos, em silencio.
    #
    # ⚠️ **Uma linha carrega a conta inteira**: a medida crua (`vr_medida`), a
    # mesma medida normalizada em [0,1] (`vr_normalizado`), o peso dentro de `Q`
    # (`vr_peso`) e a parcela em XP (`vr_xp`). Guardar so o XP faria o Raio-X
    # mostrar *"+1,8"* sem poder dizer de onde saiu.
    #
    # ⚠️ **Tres das quatro parcelas correm AO CONTRARIO**: mais tentativas, mais
    # tempo e mais dicas dao MENOS XP; so o merito cresce junto com `Q`. A inversao
    # acontece no `vr_normalizado`, e a direcao de cada feito vem de
    # `desafio.tb902_catalogo_feito.co_direcao` — nao e escrita de novo aqui. Uma
    # parcela na direcao errada **nao daria erro nenhum**: so pagaria mais a quem
    # jogou pior.
    #
    # `vr_xp` e `NUMERIC` e nao `INT` de proposito: as parcelas tem casas decimais,
    # e arredondar cada uma faria a soma nao bater com o total. O unico inteiro e o
    # `nu_xp` da resolucao, arredondado **uma vez**, no fim.
    #
    # As tres ancoras, e por que a terceira e nula nas duas colunas:
    #   parcela de resolucao  → id_resolucao
    #   consolo de tentativa  → id_tentativa
    #   ajuste do teto do dia → as duas nulas — o ajuste e **do dia**, nao de um
    #                           evento. E ele que permite o extrato dizer "voce fez
    #                           37, o teto do dia cortou 7" em vez de esconder a
    #                           conta.
    op.execute(
        """
        CREATE TABLE desafio_dia.tb004_xp_desafio (
            id_xp_desafio   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_desafio_dia  UUID     NOT NULL
                REFERENCES desafio_dia.tb001_desafio_dia(id_desafio_dia),
            id_usuario      UUID     NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),

            id_resolucao    UUID
                REFERENCES desafio_dia.tb003_resolucao(id_resolucao)
                ON DELETE CASCADE,
            id_tentativa    UUID
                REFERENCES desafio_dia.tb002_tentativa(id_tentativa)
                ON DELETE CASCADE,

            nu_tipo_xp      SMALLINT NOT NULL
                REFERENCES desafio_dia.tb901_tipo_xp_desafio(nu_tipo_xp),

            nu_feito        SMALLINT
                REFERENCES desafio.tb902_catalogo_feito(nu_feito),

            vr_medida       NUMERIC(12,3),
            vr_normalizado  NUMERIC(5,4),
            vr_peso         NUMERIC(4,3),
            vr_xp           NUMERIC(6,3) NOT NULL,

            dh_registro     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck001_normalizado CHECK (vr_normalizado IS NULL
                                           OR vr_normalizado BETWEEN 0 AND 1),
            CONSTRAINT ck002_peso        CHECK (vr_peso IS NULL
                                           OR vr_peso BETWEEN 0 AND 1),
            CONSTRAINT ck003_feito       CHECK ((nu_feito IS NULL) <>
                                                (nu_tipo_xp IN (5, 6)))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix001_xp_resolucao "
        "ON desafio_dia.tb004_xp_desafio (id_resolucao)"
    )
    op.execute(
        "CREATE INDEX ix002_xp_usuario "
        "ON desafio_dia.tb004_xp_desafio (id_usuario)"
    )

    # ── Dica gasta, presa a TENTATIVA ───────────────────────────────────────
    #
    # ⚠️ **O teto e de duas dicas por DESAFIO, nao por tentativa.** Fechar o app
    # encerra a tentativa, nao o dia; se o contador vivesse na tentativa, reabrir
    # zeraria o contador e daria dicas infinitas. Com a tabela pendurada na
    # tentativa, o contador do dia e uma soma:
    #
    #     SELECT count(*)
    #       FROM desafio_dia.vw005_poder_consumido pc
    #       JOIN desafio_dia.vw002_tentativa t ON t.id_tentativa = pc.id_tentativa
    #      WHERE t.id_usuario = :usuario AND t.id_desafio_dia = :dia;
    #
    # O grau (1 = regiao ou peca · 2 = o lance) fica na linha porque as duas dicas
    # nao sao a mesma coisa, e a segunda so faz sentido depois da primeira.
    #
    # ⚠️ **Premiado nao completado NAO grava linha**: a dica so se registra quando
    # o anuncio se completa.
    op.execute(
        """
        CREATE TABLE desafio_dia.tb005_poder_consumido (
            id_poder_consumido UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_tentativa   UUID     NOT NULL
                REFERENCES desafio_dia.tb002_tentativa(id_tentativa)
                ON DELETE CASCADE,
            nu_tipo_poder  SMALLINT NOT NULL
                REFERENCES desafio_dia.tb902_tipo_poder(nu_tipo_poder),
            nu_grau        SMALLINT NOT NULL,
            dh_consumo     TIMESTAMPTZ NOT NULL,
            dh_registro    TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT un001_poder UNIQUE (id_tentativa, nu_tipo_poder, nu_grau),
            CONSTRAINT ck001_grau  CHECK (nu_grau BETWEEN 1 AND 2)
        )
        """
    )

    # ── Palmas, uau, fogo numa linha do quadro ──────────────────────────────
    #
    # `un001_reacao` e a regra *"uma reacao por pessoa, por linha do quadro"* — a
    # pessoa pode **trocar** a sua (e um `UPDATE`), nao acumular.
    #
    # ⚠️ Reacao pende da **resolucao**, nao da tentativa: o quadro so mostra quem
    # resolveu, e nao se reage ao que nao aparece. Mascote nao recebe reacao.
    op.execute(
        """
        CREATE TABLE desafio_dia.tb006_reacao (
            id_reacao       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_resolucao    UUID     NOT NULL
                REFERENCES desafio_dia.tb003_resolucao(id_resolucao)
                ON DELETE CASCADE,
            id_usuario      UUID     NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),
            nu_tipo_reacao  SMALLINT NOT NULL
                REFERENCES desafio_dia.tb903_tipo_reacao(nu_tipo_reacao),
            dh_reacao       TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT un001_reacao UNIQUE (id_resolucao, id_usuario)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix001_reacao_resolucao "
        "ON desafio_dia.tb006_reacao (id_resolucao)"
    )

    # ══ VIEWs ═══════════════════════════════════════════════════════════════
    #
    # ⚠️ A leitura nunca toca a tabela, e as colunas sao listadas uma a uma —
    # `SELECT *` congela a lista no instante da criacao, e coluna nova nao aparece
    # sem que ninguem seja avisado.
    #
    # ⚠️ E aqui as VIEWs de fato **entregam o `JOIN` com as dimensoes ja
    # resolvido**, para ninguem precisar lembrar de faze-lo.

    op.execute(
        """
        CREATE VIEW desafio_dia.vw901_tipo_xp_desafio AS
        SELECT nu_tipo_xp, co_tipo_xp, no_tipo_xp
          FROM desafio_dia.tb901_tipo_xp_desafio
        """
    )
    op.execute(
        """
        CREATE VIEW desafio_dia.vw902_tipo_poder AS
        SELECT nu_tipo_poder, co_tipo_poder, no_tipo_poder
          FROM desafio_dia.tb902_tipo_poder
        """
    )
    op.execute(
        """
        CREATE VIEW desafio_dia.vw903_tipo_reacao AS
        SELECT nu_tipo_reacao, co_tipo_reacao, no_tipo_reacao, co_emoji,
               co_chave_i18n, nu_ordem, ic_ativo
          FROM desafio_dia.tb903_tipo_reacao
        """
    )

    op.execute(
        """
        CREATE VIEW desafio_dia.vw001_desafio_dia AS
        SELECT id_desafio_dia, dt_dia, id_desafio, dh_encerramento, dh_publicacao
          FROM desafio_dia.tb001_desafio_dia
        """
    )
    op.execute(
        """
        CREATE VIEW desafio_dia.vw002_tentativa AS
        SELECT id_tentativa, id_desafio_dia, id_usuario, id_partida,
               nu_sequencia, ic_resolveu, nu_tempo_ms, dh_inicio, dh_fim,
               dh_registro
          FROM desafio_dia.tb002_tentativa
        """
    )

    # ⚠️ Esta VIEW devolve o `nu_tempo_ms` da tentativa vencedora ao lado da
    # resolucao: e dele que o quadro tira o **desempate** quando duas pessoas
    # empatam em XP, e sem o `JOIN` pronto cada consulta o refaria por conta.
    op.execute(
        """
        CREATE VIEW desafio_dia.vw003_resolucao AS
        SELECT r.id_resolucao,
               r.id_desafio_dia,
               r.id_usuario,
               r.id_tentativa,
               t.id_partida,
               t.nu_tempo_ms,
               r.nu_lance_cumpre_desafio,
               r.nu_xp,
               r.nu_versao_catalogo,
               r.co_auditoria,
               r.de_auditoria,
               r.dh_resolucao,
               r.dh_registro
          FROM desafio_dia.tb003_resolucao r
          JOIN desafio_dia.tb002_tentativa t
            ON t.id_tentativa = r.id_tentativa
        """
    )

    # ⚠️ Devolve `co_tipo_xp` e `co_feito` ao lado dos numeros: e o que faz o
    # extrato do Raio-X ser legivel sem duas juncoes escritas a mao.
    op.execute(
        """
        CREATE VIEW desafio_dia.vw004_xp_desafio AS
        SELECT x.id_xp_desafio,
               x.id_desafio_dia,
               x.id_usuario,
               x.id_resolucao,
               x.id_tentativa,
               x.nu_tipo_xp,
               tx.co_tipo_xp,
               tx.no_tipo_xp,
               x.nu_feito,
               cf.co_feito,
               cf.co_unidade,
               cf.co_direcao,
               x.vr_medida,
               x.vr_normalizado,
               x.vr_peso,
               x.vr_xp,
               x.dh_registro
          FROM desafio_dia.tb004_xp_desafio x
          JOIN desafio_dia.tb901_tipo_xp_desafio tx
            ON tx.nu_tipo_xp = x.nu_tipo_xp
          LEFT JOIN desafio.tb902_catalogo_feito cf
            ON cf.nu_feito = x.nu_feito
        """
    )

    op.execute(
        """
        CREATE VIEW desafio_dia.vw005_poder_consumido AS
        SELECT p.id_poder_consumido,
               p.id_tentativa,
               p.nu_tipo_poder,
               tp.co_tipo_poder,
               p.nu_grau,
               p.dh_consumo,
               p.dh_registro
          FROM desafio_dia.tb005_poder_consumido p
          JOIN desafio_dia.tb902_tipo_poder tp
            ON tp.nu_tipo_poder = p.nu_tipo_poder
        """
    )

    op.execute(
        """
        CREATE VIEW desafio_dia.vw006_reacao AS
        SELECT r.id_reacao,
               r.id_resolucao,
               r.id_usuario,
               r.nu_tipo_reacao,
               tr.co_tipo_reacao,
               tr.co_emoji,
               tr.co_chave_i18n,
               r.dh_reacao
          FROM desafio_dia.tb006_reacao r
          JOIN desafio_dia.tb903_tipo_reacao tr
            ON tr.nu_tipo_reacao = r.nu_tipo_reacao
        """
    )


def downgrade() -> None:
    """Derruba o schema inteiro.

    ⚠️ **So para o ambiente local.** E o unico lugar deste arquivo onde um `DROP`
    aparece — o teste de migracao aditiva ignora o `downgrade()` por isso.
    """
    op.execute("DROP SCHEMA IF EXISTS desafio_dia CASCADE")

"""Schema `jogo_damas` — a extensao de PARTIDA, de JOGADA e de RECUSA do 3o jogo.

CONTEXTO
--------
O Jogo das Damas (spec 008) e o terceiro jogo da Arena Sagaz. Como os dois
anteriores, ele grava a partida e a jogada GENERICAS em `partida.tb001_partida` /
`partida.tb002_jogada`, e o que e so dele num schema proprio. Esta migracao cria
esse schema.

⚠️ NOTA DE ACENTUACAO: este arquivo nao usa acentos, seguindo a convencao das
migracoes 0009, 0010 e 0011 (conferido: zero acentos nas tres). O resto do
projeto e acentuado normalmente; aqui a convencao e local, e mante-la evita
surpresa de encoding no console do Alembic no Windows.

POR QUE ELE E MAIOR QUE O DA VELHA
-----------------------------------
A velha tem UMA tabela de jogada e uma dimensao. As damas tem tres tabelas de
fato, e cada uma existe por um motivo que as outras nao cobrem:

1. **`tb001_partida` — a extensao de PARTIDA, e ela e o primeiro caso do app.**
   Nenhum jogo tinha extensao de partida ate agora. Ela existe porque o replay
   depende de saber COM QUAL MOTOR a partida foi jogada: uma regra corrigida muda
   a lista de lances legais, e um replay rodado com motor diferente reconstroi
   uma partida que **nunca aconteceu** — sem que nada no dado denuncie.

2. **`tb002_jogada` — uma linha por LANCE**, com a posicao de antes em FEN e a
   telemetria da busca. E o que permite reexaminar cada decisao da CPU.

3. **`tb003_recusa` — as tentativas que a REGRA barrou.** Nao cabem na jogada
   generica: varias recusas acontecem antes de um unico lance efetivado, e
   `partida.tb002_jogada` tem `UNIQUE (id_partida, nu_ordem)`. Enfiar recusas ali
   quebraria a chave. Elas medem se o jogo esta sendo **justo** com quem joga —
   uma recusa seguida de abandono e o sintoma mais forte de recusa indevida.

⚠️ ESTA MIGRACAO E PURAMENTE ADITIVA — E ISSO E VERIFICADO, NAO PROMETIDO
-------------------------------------------------------------------------
**Ha usuarios reais em `prd` desde 04/08/2026.** A regra do dono (2026-08-06):
nada de `DELETE`, `TRUNCATE` ou `DROP`. O `upgrade()` abaixo contem APENAS
`CREATE SCHEMA`, `CREATE TABLE`, `INSERT` nas dimensoes, `CREATE INDEX` e
`CREATE VIEW`. Nenhuma tabela, coluna ou view existente e tocada.

O `downgrade()` derruba o schema, e e a unica excecao — ele existe para o
ambiente local e **nunca roda em producao**.

COMPATIBILIDADE COM QUEM NAO VAI ATUALIZAR O APP
------------------------------------------------
Nada aqui afeta o app antigo, e o motivo e o mesmo da 0011: um schema novo e
invisivel para quem nao o consulta. Um app publicado hoje nao conhece
`jogo_damas`, nunca envia `partida["damas"]`, e continua lendo e escrevendo
exatamente as mesmas tabelas de antes.

⚠️ E O CONTRARIO TAMBEM JA E VERDADE, DESDE ANTES DESTA MIGRACAO. Um app **mais
novo** que o servidor tambem nao quebra: `_avisar_extensao_desconhecida`
(`api/sincronizacao/repositorio.py`) **aceita** o evento e so registra `warning`,
e `co_jogo` e texto livre (sem `CHECK`, sem `FK`). Hoje uma partida de damas ja
sobe — a partida generica e o XP entram, e so o objeto `damas` e descartado. E a
decisao **V-5 da spec 007**, e ela e assimetrica de proposito: *"ignorar perde o
detalhe; rejeitar perde a partida"*.

Consequencia pratica para o deploy: esta migracao **pode ser aplicada a qualquer
momento**, antes ou depois de o app com damas subir. O que se ganha aplicando-a
antes e nao perder a telemetria das primeiras partidas.

O PORTAO DO DONO
----------------
`specs/008-jogo-das-damas/data-model.md` §11, itens **V-1 a V-11**, todos
aprovados em **18/08/2026**. Em especial:

- **V-1**: o schema com as seis tabelas abaixo;
- **V-3**: `co_fen_antes` em TODA jogada (custa ~400 B comprimidos por partida);
- **V-7**: `VARCHAR(255)` nos FEN e `VARCHAR(120)` no lance, ja pensando no 10x10;
- **V-8**: `qt_captura_pedra` + `qt_captura_dama` **decompostas**, em vez de um
  total com um subconjunto — somar e trivial, separar depois e impossivel;
- **V-9**: a modalidade numa **tabela de relacionamento** (`tb903`), nunca como
  sufixo do codigo da regra;
- **V-10**: `co_cor_j1` gravada, mesmo sendo hoje sempre `'branca'` no modo CPU;
- **V-11**: `nu_avaliacao_brancas` guarda a nota da BUSCA, nao a avaliacao
  estatica da posicao de `co_fen_antes`.

⚠️ AS DIMENSOES VIERAM DO MOTOR, NAO DO DOCUMENTO
--------------------------------------------------
O `data-model.md` §2.5 listava **oito** codigos de recusa. Sao **sete**, e nao
sao os mesmos: os do documento foram escritos no papel, e a T137 (20/08/2026)
descobriu isso ao implementar o mapeador do app. Duas correcoes que ficam
gravadas aqui:

- `pedra_nao_recua` e `coroacao_encerra` **nao existem como recusa**. O motor nao
  as emite: um gesto que as violasse simplesmente nao esta entre os lances
  legais, e sai como `lance_inexistente`. Mante-las na dimensao criaria dois
  codigos que nunca apareceriam em linha nenhuma;
- `tema_turco` chama-se `bloqueado_por_condenada` — o nome do **sintoma**, nao o
  do artigo do regulamento. E o que o motor diz.

A fonte da verdade e `identificadoresDeRecusa`, em
`explicacao_de_recusa_damas.dart` — arquivo que e copia byte-identica do
laboratorio, com teste de hash. O documento e que envelheceu, e foi corrigido na
mesma resposta desta migracao.

⚠️ O APP MANDA STRING; O BANCO GUARDA NUMERO
---------------------------------------------
O payload traz `co_regra: "captura_obrigatoria"` e
`co_motivo_parada_busca: "nos"` — **texto**. As tabelas guardam `nu_regra` e
`nu_motivo_parada_busca` — **SMALLINT com FK**. A traducao e feita na camada de
repositorio, e o sentinela `9999` existe para o caso em que ela falha (ver
abaixo, na `tb901`).
"""

from typing import Sequence, Union

from alembic import op

# ⚠️ O id de revisao do Alembic tem limite de 32 caracteres. Passar disso faz o
# upgrade RODAR o DDL inteiro e falhar so no fim, revertendo tudo — um erro caro
# de diagnosticar. "0012_schema_jogo_damas" tem 22.
revision: str = "0012_schema_jogo_damas"
down_revision: Union[str, None] = "0011_schema_jogo_velha"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria o schema `jogo_damas` inteiro. So acrescenta."""
    op.execute("CREATE SCHEMA IF NOT EXISTS jogo_damas")

    # ══ Dimensoes ═══════════════════════════════════════════════════════════
    #
    # Vem ANTES das tabelas de fato, porque estas tem FK para elas.

    # ── A regra que recusou um lance ────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_damas.tb901_regra_recusa (
            nu_regra SMALLINT    PRIMARY KEY,
            co_regra VARCHAR(30) NOT NULL UNIQUE,
            no_regra VARCHAR(60) NOT NULL
        )
        """
    )

    # Os 7 codigos que o MOTOR emite, mais o sentinela.
    #
    # ⚠️ A numeracao comeca em 1 e NAO continua a da velha: sao dimensoes de
    # schemas diferentes, e a chave e (schema, nu_regra), nao um contador global.
    #
    # ⚠️ Um `nu_regra` NUNCA muda de significado depois de gravado. Acrescentar e
    # migracao nova; reescrever o sentido de um existente falsifica todo o
    # historico ja gravado — e o historico e o motivo de esta tabela existir.
    #
    # ⚠️ O `9999` e INEGOCIAVEL, e a licao e da 0011: sem um destino valido, um
    # app MAIS NOVO que o backend estoura a FK, toma 500, e o evento fica preso
    # PARA SEMPRE na fila de sincronizacao do aparelho — a partida daquela pessoa
    # nunca sobe. Com o sentinela, o evento entra e a string crua vai para
    # `js_extra` da partida.
    op.execute(
        """
        INSERT INTO jogo_damas.tb901_regra_recusa (nu_regra, co_regra, no_regra) VALUES
            (1,    'captura_obrigatoria',     'Ha captura disponivel'),
            (2,    'lei_da_maioria',          'Existe captura maior'),
            (3,    'lei_da_qualidade',        'Existe captura de melhor qualidade'),
            (4,    'sequencia_incompleta',    'A captura multipla pode continuar'),
            (5,    'bloqueado_por_condenada', 'A peca ja comida ainda bloqueia'),
            (6,    'lance_inexistente',       'O destino nao e um lance legal'),
            (7,    'peca_sem_lance',          'Essa peca nao tem lance nenhum'),
            (9999, 'desconhecido',            'Desconhecido')
        """
    )

    # ── Por que a busca parou ───────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_damas.tb902_motivo_parada_busca (
            nu_motivo_parada_busca SMALLINT    PRIMARY KEY,
            co_motivo_parada_busca VARCHAR(20) NOT NULL UNIQUE,
            no_motivo_parada_busca VARCHAR(40) NOT NULL
        )
        """
    )

    # ⚠️ SAO QUATRO, e nao tres. O `data-model.md` dizia "os tres valores sao
    # exatamente os que o motor produz", e a conferencia da T134 achou um quarto
    # em `busca_damas.dart`: `decidido`, quando a busca ve vitoria ou derrota
    # forcada e aprofundar deixa de mudar qualquer coisa.
    #
    # Nao e caso raro: numa partida do Magno, os finais decididos sao exatamente
    # onde ele fecha o jogo. Deixa-lo cair no sentinela apagaria a informacao
    # mais interessante do log — a partir de que lance a partida ja estava
    # decidida.
    #
    # E o `3` (tempo) recorrente e diagnostico de aparelho lento: e o sinal de
    # que o ritmo do Magno vai estourar naquele modelo, ANTES de alguem reclamar.
    op.execute(
        """
        INSERT INTO jogo_damas.tb902_motivo_parada_busca
            (nu_motivo_parada_busca, co_motivo_parada_busca, no_motivo_parada_busca) VALUES
            (1,    'profundidade',  'Terminou a profundidade'),
            (2,    'nos',           'Esgotou o teto de nos'),
            (3,    'tempo',         'Esgotou o tempo'),
            (4,    'decidido',      'Vitoria ou derrota forcada'),
            (9999, 'desconhecido',  'Desconhecido')
        """
    )

    # ── Em QUAIS modalidades cada regra pode recusar um lance ────────────────
    #
    # ⚠️ Uma linha por par (V-9). Substituiu uma coluna `co_modalidades` que
    # guardaria a lista separada por virgula: nome no plural, conteudo nao
    # normalizado, e sem como fazer JOIN.
    #
    # ⚠️ POR QUE A MODALIDADE NAO ENTRA NO NOME DO CODIGO. A alternativa seria
    # sufixar — `lei_da_qualidade_portuguesa`. Tres motivos contra:
    #
    #  1. a modalidade JA esta gravada na partida (`co_variante`). Sufixar
    #     guardaria o mesmo dado duas vezes, e a segunda copia e a que fica
    #     errada quando as duas discordam;
    #  2. a italiana tambem tem Lei da Qualidade. Com o sufixo, ela precisaria de
    #     um segundo codigo para a MESMA regra, e "quantas vezes a Lei da
    #     Qualidade recusou um lance" viraria uma soma sobre dois codigos —
    #     exatamente o problema que normalizar existe para resolver;
    #  3. um codigo nunca muda de significado depois de gravado. `lei_da_qualidade`
    #     descreve a regra, e a regra e a mesma onde quer que valha.
    #
    # Quando a italiana chegar, o custo e `INSERT`.
    op.execute(
        """
        CREATE TABLE jogo_damas.tb903_regra_modalidade (
            nu_regra      SMALLINT    NOT NULL
                REFERENCES jogo_damas.tb901_regra_recusa(nu_regra),
            co_modalidade VARCHAR(30) NOT NULL,
            PRIMARY KEY (nu_regra, co_modalidade)
        )
        """
    )

    # As linhas sao DERIVADAS do contrato, nao opinadas. Conferido em
    # `assets/jogos/damas/contrato_damas.json → regulamentos.*`, em 20/08/2026:
    #
    #   modalidade   captura_maxima_obrigatoria   desempate_por_qualidade
    #   brasileira            True                       False
    #   portuguesa            True                       True
    #   anglo                 False                      False
    #   casa                  False                      False
    #
    # E e exatamente o que `regraPodeOcorrerEm(coRegra, regulamento)` responde no
    # app (`recusas_damas.dart`): so DUAS das sete regras sao condicionais; as
    # outras cinco valem em qualquer modalidade, porque toda modalidade tem
    # captura obrigatoria, sequencia a terminar, tema turco e gestos que
    # simplesmente nao sao lance nenhum.
    op.execute(
        """
        INSERT INTO jogo_damas.tb903_regra_modalidade (nu_regra, co_modalidade) VALUES
            -- universais: valem nas quatro
            (1,'brasileira'),(1,'casa'),(1,'portuguesa'),(1,'anglo'),  -- captura_obrigatoria
            (4,'brasileira'),(4,'casa'),(4,'portuguesa'),(4,'anglo'),  -- sequencia_incompleta
            (5,'brasileira'),(5,'casa'),(5,'portuguesa'),(5,'anglo'),  -- bloqueado_por_condenada
            (6,'brasileira'),(6,'casa'),(6,'portuguesa'),(6,'anglo'),  -- lance_inexistente
            (7,'brasileira'),(7,'casa'),(7,'portuguesa'),(7,'anglo'),  -- peca_sem_lance
            -- restritas: so onde o regulamento as liga
            (2,'brasileira'),(2,'portuguesa'),                         -- lei_da_maioria
            (3,'portuguesa')                                           -- lei_da_qualidade
        """
    )

    # ══ Tabelas de fato ═════════════════════════════════════════════════════

    # ── A extensao 1:1 da PARTIDA ───────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_damas.tb001_partida (
            id_partida         UUID PRIMARY KEY
                REFERENCES partida.tb001_partida(id_partida) ON DELETE CASCADE,
            co_versao_motor    VARCHAR(20)  NOT NULL,
            co_versao_contrato VARCHAR(20)  NOT NULL,
            co_fen_inicial     VARCHAR(255) NOT NULL,
            co_cor_j1          VARCHAR(6)   NOT NULL,
            nu_semente_partida BIGINT,
            js_extra           JSONB,
            -- O banco fala o vocabulario do JOGO DE DAMAS, nunca o do tema do
            -- app. Azul e vermelho sao decisao de tema (RF-DAM-038), e temas
            -- mudam; a cor das damas nao muda ha duzentos anos. A ponte
            -- azul<->branca e feita no app, uma vez, e o banco nunca ouve falar
            -- de azul.
            CONSTRAINT ck_damas_cor_j1 CHECK (co_cor_j1 IN ('branca', 'preta'))
        )
        """
    )

    # ⚠️ Sobre `co_cor_j1` (V-10): hoje ela e SEMPRE 'branca' no modo CPU, e
    # mesmo assim vale os 6 bytes por partida. Tres razoes:
    #
    #  · sem ela, o replay de uma partida ANGLO-AMERICANA — onde quem abre e o
    #    vermelho — nao sabe quem era quem;
    #  · e derivavel por inferencia (o FEN inicial diz quem abre, e o lance de
    #    `nu_ordem = 1` diz de quem foi), mas a inferencia quebra no primeiro
    #    caso especial: uma partida abandonada ANTES do primeiro lance;
    #  · um modo futuro em que o jogador escolha a cor exigiria `ALTER` numa
    #    tabela JA COM DADOS, deixando as partidas antigas sem o campo.
    #
    # ⚠️ Sobre `co_fen_inicial` ser sempre o mesmo valor por modalidade hoje: o
    # tabuleiro sempre comeca montado normal NESTA VERSAO (RF-DAM-119), mas as
    # 196 aberturas oficiais de torneio ja estao extraidas e validadas no
    # laboratorio. Quando entrarem, o campo ja esta no lugar — e nenhuma partida
    # antiga fica ambigua.

    # ── A extensao 1:1 da JOGADA ────────────────────────────────────────────
    #
    # Uma linha por LANCE, nao por salto. Uma captura tripla e UM lance.
    op.execute(
        """
        CREATE TABLE jogo_damas.tb002_jogada (
            id_jogada                UUID PRIMARY KEY
                REFERENCES partida.tb002_jogada(id_jogada) ON DELETE CASCADE,
            co_jogador               SMALLINT     NOT NULL,
            co_lance                 VARCHAR(120) NOT NULL,
            co_fen_antes             VARCHAR(255) NOT NULL,
            qt_captura_pedra         SMALLINT     NOT NULL DEFAULT 0,
            qt_captura_dama          SMALLINT     NOT NULL DEFAULT 0,
            ic_promoveu              BOOLEAN      NOT NULL DEFAULT FALSE,
            co_tipo_peca_inicio      VARCHAR(10)  NOT NULL,
            qt_nos_visitados         INTEGER,
            nu_profundidade_atingida SMALLINT,
            nu_motivo_parada_busca   SMALLINT
                REFERENCES jogo_damas.tb902_motivo_parada_busca(nu_motivo_parada_busca),
            nu_tempo_busca_ms        INTEGER,
            nu_avaliacao_brancas     INTEGER,
            nu_semente               BIGINT,
            js_extra                 JSONB,
            -- +1 (J1) / -1 (J2): o SINAL, como no Pontinhos e na velha. O
            -- generico usa nu_jogador 1/2; a extensao usa o sinal. Sao
            -- convencoes diferentes de proposito, e o CHECK impede que uma vire
            -- a outra por descuido.
            CONSTRAINT ck_damas_jogador CHECK (co_jogador IN (1, -1)),
            CONSTRAINT ck_damas_tipo_peca
                CHECK (co_tipo_peca_inicio IN ('pedra', 'dama')),
            -- Uma dama nao promove: o par ('dama', true) e impossivel, e a
            -- invariante I-10 do contrato do log diz que ele NUNCA e gravado.
            -- O CHECK e a segunda linha de defesa, no banco.
            CONSTRAINT ck_damas_dama_nao_promove
                CHECK (NOT (co_tipo_peca_inicio = 'dama' AND ic_promoveu)),
            -- Se houve busca, houve semente. Sem a semente, o replay daquele
            -- lance nao reproduz — e e justamente nos niveis que ERRAM DE
            -- PROPOSITO que ela decide o resultado.
            CONSTRAINT ck_damas_semente_da_cpu
                CHECK (qt_nos_visitados IS NULL OR nu_semente IS NOT NULL)
        )
        """
    )

    # ⚠️ Sobre a telemetria ser ANULAVEL: `NULL` = lance do HUMANO. Nao ha busca
    # a medir, e um zero gravado falsearia qualquer media sobre esta tabela.
    # `NULL` significa "nao se aplica", que e a verdade. Mesma logica do
    # `ic_otimo` da velha (V-4 da spec 007).
    #
    # ⚠️ Sobre `nu_avaliacao_brancas` (V-11): e a nota que a BUSCA devolveu, nao
    # a avaliacao estatica da posicao em `co_fen_antes`. Sao numeros diferentes,
    # e confundi-los inutilizaria a analise. A unidade e CENTESIMOS DE PEDRA, e o
    # referencial e sempre o das BRANCAS — quando quem move e preto, o valor sai
    # invertido (invariante I-12).
    #
    # ⚠️ Sobre `co_tipo_peca_inicio`: descreve a peca no INICIO do lance. Uma
    # pedra que come tres pecas e coroa no ultimo salto grava
    # ('pedra', ic_promoveu=true) — nao ('dama', ...).

    # ── As tentativas que a REGRA barrou ────────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_damas.tb003_recusa (
            id_recusa       UUID PRIMARY KEY,
            id_partida      UUID NOT NULL
                REFERENCES partida.tb001_partida(id_partida) ON DELETE CASCADE,
            nu_ordem        SMALLINT NOT NULL,
            nu_sequencia    SMALLINT NOT NULL,
            nu_casa_origem  SMALLINT NOT NULL,
            nu_casa_destino SMALLINT NOT NULL,
            nu_regra        SMALLINT NOT NULL
                REFERENCES jogo_damas.tb901_regra_recusa(nu_regra),
            dh_recusa       TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_damas_recusa UNIQUE (id_partida, nu_ordem, nu_sequencia)
        )
        """
    )

    # ⚠️ A ARMADILHA DE LEITURA DESTA TABELA, e ela e sutil.
    #
    # `nu_ordem` aqui NAO e o mesmo `nu_ordem` da jogada generica, apesar do nome
    # igual (e o nome e igual de proposito, para o JOIN ser obvio):
    #
    #   · em `partida.tb002_jogada`, e o numero de um lance que ACONTECEU;
    #   · aqui, e o numero do lance que ESTAVA SENDO TENTADO — e que pode nunca
    #     acontecer, se a pessoa abandonar a partida logo depois da recusa.
    #
    # Duas consequencias praticas:
    #
    #  1. NAO HA FK desta tabela para a jogada, e nao pode haver: a linha-alvo
    #     nao existe no momento da insercao, e pode nunca existir. E por isso que
    #     a FK aqui aponta para a PARTIDA;
    #  2. um `INNER JOIN` entre as duas PERDERIA as recusas orfas — justamente as
    #     mais interessantes, porque recusa seguida de abandono e o sintoma mais
    #     forte de recusa indevida. **Use `LEFT JOIN`.** A `vw003_recusa` abaixo
    #     ja o faz.
    #
    # ⚠️ Teto de 50 recusas por partida, contado PELO APP. Passado o teto, ele
    # para de gravar e NAO descarta a partida. Um defeito em laco nao pode inflar
    # o log nem a fila de sincronizacao.
    #
    # ⚠️ `nu_casa_*` e numerica (e nao `co_`, como o `co_celula` da velha) porque
    # a casa e um NUMERO de 1 a 32 — 1 a 50 no 10x10 —, nao um rotulo que
    # codifica linha e coluna. Um SMALLINT permite
    # `WHERE nu_casa_origem BETWEEN 21 AND 32` sem conversao.

    # ── Indices ─────────────────────────────────────────────────────────────
    #
    # As tabelas 1:1 nao precisam: a PK ja e a coluna do JOIN. A recusa precisa,
    # porque ela e consultada POR PARTIDA e a sua PK e o `id_recusa`.
    op.execute(
        "CREATE INDEX ix_damas_recusa_partida "
        "ON jogo_damas.tb003_recusa (id_partida)"
    )

    # ══ VIEWs — le-se SEMPRE pela VIEW (regra do ecossistema) ═══════════════
    op.execute(
        "CREATE VIEW jogo_damas.vw901_regra_recusa AS "
        "SELECT * FROM jogo_damas.tb901_regra_recusa"
    )
    op.execute(
        "CREATE VIEW jogo_damas.vw902_motivo_parada_busca AS "
        "SELECT * FROM jogo_damas.tb902_motivo_parada_busca"
    )
    op.execute(
        "CREATE VIEW jogo_damas.vw903_regra_modalidade AS "
        "SELECT * FROM jogo_damas.tb903_regra_modalidade"
    )
    op.execute(
        "CREATE VIEW jogo_damas.vw001_partida AS "
        "SELECT * FROM jogo_damas.tb001_partida"
    )

    # A VIEW da jogada ja traz o motivo de parada POR EXTENSO. Quem le um log no
    # suporte quer ver 'nos', nao o numero 2 — e sem isso todo `SELECT` viria
    # acompanhado do mesmo JOIN escrito a mao.
    op.execute(
        """
        CREATE VIEW jogo_damas.vw002_jogada AS
        SELECT j.*,
               m.co_motivo_parada_busca,
               m.no_motivo_parada_busca
          FROM jogo_damas.tb002_jogada j
          LEFT JOIN jogo_damas.tb902_motivo_parada_busca m
                 ON m.nu_motivo_parada_busca = j.nu_motivo_parada_busca
        """
    )

    # ⚠️ `LEFT JOIN` nos DOIS lados desta VIEW, e por motivos diferentes:
    #
    #  · para `tb901`, porque e o padrao defensivo — a FK ja garante a linha, mas
    #    um INNER aqui transformaria qualquer inconsistencia futura em
    #    DESAPARECIMENTO SILENCIOSO de recusas, que e o pior modo de falha
    #    possivel para uma tabela de auditoria;
    #  · para `tb002_jogada`, porque a recusa PODE SER ORFA por construcao (ver a
    #    armadilha acima). Um INNER aqui apagaria exatamente as linhas que mais
    #    interessam.
    op.execute(
        """
        CREATE VIEW jogo_damas.vw003_recusa AS
        SELECT r.*,
               g.co_regra,
               g.no_regra,
               p.co_variante AS co_modalidade,
               -- A recusa aconteceu numa modalidade onde a regra NEM EXISTE?
               -- Se vier `true`, e bug de tela, nao comportamento do jogo.
               NOT EXISTS (
                   SELECT 1
                     FROM jogo_damas.tb903_regra_modalidade m
                    WHERE m.nu_regra = r.nu_regra
                      AND m.co_modalidade = p.co_variante
               ) AS ic_regra_impossivel_na_modalidade
          FROM jogo_damas.tb003_recusa r
          LEFT JOIN jogo_damas.tb901_regra_recusa g ON g.nu_regra = r.nu_regra
          LEFT JOIN partida.tb001_partida p ON p.id_partida = r.id_partida
        """
    )


def downgrade() -> None:
    """Derruba o schema inteiro.

    ⚠️ **So para o ambiente local.** Nunca rodar em `prd` — ha usuarios reais, e
    o `CASCADE` levaria junto as partidas de damas ja gravadas. E o unico lugar
    deste arquivo onde um `DROP` aparece, e o teste de migracao aditiva ignora o
    `downgrade()` exatamente por isso.
    """
    op.execute("DROP SCHEMA IF EXISTS jogo_damas CASCADE")

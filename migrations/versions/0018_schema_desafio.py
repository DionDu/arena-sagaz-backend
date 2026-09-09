"""O schema `desafio` — a LINHA DE PRODUCAO do Desafio do Dia.

Revision ID: 0018_schema_desafio
Revises: 0017_poder_e_probing_base
Create Date: 2026-09-09

⛔⛔⛔ **PROPOSTA — NAO FOI APLICADA EM NENHUM BANCO.** ⛔⛔⛔

Este arquivo existe para ser **lido e aprovado** pelo dono antes de rodar, pela
regra permanente do projeto: nada de banco sem o OK dele. Antes de qualquer
`alembic upgrade`, rodar `scripts/identificar_banco.py` — o `AMBIENTE` do `.env`
**nao e prova** de para onde a conexao aponta.

    DES = hopper.proxy.rlwy.net:21165
    PRD = hayabusa.proxy.rlwy.net:42857

═══════════════════════════════════════════════════════════════════════════
QUEM ESCREVE AQUI, E POR QUE ISSO DEFINE O SCHEMA
═══════════════════════════════════════════════════════════════════════════

**So o job em batch do Railway insere neste schema.** A API le; o aplicativo
nunca chega perto. Essa e a fronteira, decidida pelo dono em 04/09/2026 (Bloco X):
no banco, o corte entre `desafio` e `desafio_dia` **e quem escreve a linha**.

    desafio      = a linha de producao  → escreve o JOB
    desafio_dia  = o evento             → escreve o APP (migracao 0019)

⚠️ **"Nucleo" significa duas coisas no projeto, e nao e o mesmo corte.** No
aplicativo, nucleo e o codigo generico que julga (`lib/core/desafios/`); no banco,
e esta linha de producao. Confundir os dois foi o que levou a spec a ser reescrita.

As setas apontam num sentido so: o evento conhece o desafio e conhece a partida;
nem o desafio nem a partida sabem que o evento existe.

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTA MIGRACAO CRIA AS TABELAS **NA FORMA FINAL** — E ISSO E REGRA
═══════════════════════════════════════════════════════════════════════════

`docs/DECISOES-do-dono.md` §8b, e vale enquanto nao houver o primeiro `upgrade`
publicado no PRD:

  ⛔ Defeito de modelagem que aparecer aqui **DROPA E RECRIA dentro desta
     propria migracao**. Nada de `ALTER` de remendo numa migracao seguinte, e
     ⛔ nada de campo importante no fim da tabela, porque a ordem das colunas e
     como a tabela se le meses depois.

  ⚠️ **A regra NAO vale para o schema `partida`** — ele esta em producao com dado
     real, e por isso a migracao `0020` e estritamente aditiva.

E **uma migracao por schema**, nao uma por tabela: as seis tabelas daqui nascem
juntas, e metade delas no ar sem a outra metade nao serve para nada.

═══════════════════════════════════════════════════════════════════════════
A ORDEM DENTRO DO `upgrade()`, E POR QUE ELA NAO E ARBITRARIA
═══════════════════════════════════════════════════════════════════════════

1. as **tres dimensoes** (`tb901`, `tb902`, `tb903`), porque `tb001_desafio` tem
   FK para duas delas e `tb003_feito_desafio` para a terceira;
2. `tb001_desafio`;
3. `tb002_medicao_regua` e `tb003_feito_desafio`, que apontam para ele.

⚠️ **As linhas das dimensoes NAO entram aqui** — elas sao a T022, que edita este
mesmo arquivo. A excecao declarada e `tb903_perfil_dificuldade`, que fica **vazia
de proposito**: quem a preenche e o job, ao carregar o arquivo de perfil pela
primeira vez. Uma migracao que soubesse os numeros de dificuldade de cada jogo
estaria publicando calibracao por `INSERT`, que e exatamente o que a fronteira de
`js_chegada` existe para impedir.

═══════════════════════════════════════════════════════════════════════════
POR QUE HA `VARCHAR` COM `CHECK` AO LADO DE DIMENSOES DE VERDADE
═══════════════════════════════════════════════════════════════════════════

`co_formato_posicao`, `co_curadoria` e `co_personagem` sao `VARCHAR` com `CHECK`,
e **nao** dimensoes: pouquissimos valores fechados, escritos so pelo job, nunca
enviados pelo aplicativo. Uma dimensao custaria um `JOIN` em toda consulta para
nao entregar nada — a mesma escolha que a `0017` fez com `co_poder` e a `0013`
com `co_motor_busca`.

O contrario tambem tem regra: dimensao que **recebe codigo vindo do aplicativo**
leva o sentinela `9999` (aqui, so `tb902_catalogo_feito`). Sem um destino valido,
um app mais novo que o backend estoura a FK, toma 500, e o evento fica preso para
sempre na fila de sincronizacao daquele aparelho — a partida da pessoa nunca sobe.
"""

from typing import Sequence, Union

from alembic import op

# ⚠️ O id de revisao do Alembic tem limite de 32 caracteres. Passar disso faz o
# upgrade RODAR o DDL inteiro e falhar so no fim, revertendo tudo — um erro caro
# de diagnosticar. "0018_schema_desafio" tem 19.
revision: str = "0018_schema_desafio"
down_revision: Union[str, None] = "0017_poder_e_probing_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria o schema `desafio` inteiro, com as tres dimensoes antes dos fatos."""
    op.execute("CREATE SCHEMA IF NOT EXISTS desafio")

    # ══ Dimensoes ═══════════════════════════════════════════════════════════
    #
    # Vem ANTES das tabelas de fato, porque estas tem FK para elas.

    # ── Os tipos de desafio ─────────────────────────────────────────────────
    #
    # O tipo e a IDENTIDADE do desafio: e ele que da a frase, o rodizio (para nao
    # cair o mesmo tipo dois dias seguidos) e o agrupamento na curadoria.
    #
    # ⚠️ **Tipo nao e forma de chegada.** A forma esta em `js_chegada` e diz
    # *como se julga*; varios tipos diferentes usam hoje a mesma forma. Foi por
    # confundir os dois que "o lance unico" e "final da base" pareceram, por um
    # tempo, nao ter forma propria — eles sao tipos, e a linha de chegada deles e
    # a comum.
    #
    # ⚠️ Esta dimensao NAO leva o sentinela `9999`: ela e escrita pelo job e so
    # viaja do servidor para o aplicativo, nunca de volta.
    op.execute(
        """
        CREATE TABLE desafio.tb901_tipo_desafio (
            nu_tipo_desafio SMALLINT    PRIMARY KEY,
            co_tipo_desafio VARCHAR(40) NOT NULL UNIQUE,
            no_tipo_desafio VARCHAR(60) NOT NULL,
            co_jogo         VARCHAR(30) NOT NULL
        )
        """
    )

    # ── O catalogo de feitos: as MEDIDAS que existem no hub ─────────────────
    #
    # ⚠️ **Feito e MEDIDA, nunca XP.** Quem converte medida em pontos e quem
    # agrupa (a colecao); o catalogo so diz o que existe, em que unidade, para
    # que lado e de onde sai.
    #
    # Este catalogo e **o mesmo** de `lib/core/feitos/catalogo_feitos.dart`, que
    # ja existe no aplicativo com 27 testes. O cadeado 4 (T026) compara os dois
    # lados e falha listando a chave divergente: um vocabulario, nao dois.
    #
    # `co_direcao` e o campo que evita o defeito mais silencioso da economia de
    # XP: uma parcela na direcao errada nao da erro nenhum — so paga mais a quem
    # jogou pior. Mais tempo, mais tentativas e mais dica REDUZEM; mais merito
    # aumenta. A direcao mora aqui, uma vez, e nao e escrita de novo em T037.
    #
    # `co_procedencia` separa o que o servidor consegue RECALCULAR do que ele so
    # pode receber: `tabuleiro` sai dos lances gravados em `partida.tb002_jogada`
    # e e reconferido; `sessao` (tempo, tentativas, dicas) nao tem como sair do
    # log, e e cruzado com o que o servidor ja sabe por outro caminho.
    #
    # ⚠️ Esta dimensao RECEBE codigo vindo do aplicativo — por isso ela leva o
    # sentinela `9999`.
    #
    # ⚠️ **DUAS CORRECOES DE MODELAGEM ENTRARAM AQUI, pela regra §8b** (dropa e
    # recria dentro da propria migracao, sem `ALTER` de remendo). Elas sairam do
    # confronto com a fonte da verdade — `lib/core/feitos/catalogo_feitos.dart`,
    # que ja esta em campo com 27 testes:
    #
    #   (a) `co_direcao` aceitava DOIS valores; o catalogo tem **tres**. Falta
    #       `marco_atingido` (`DirecaoFeito.marcoAtingido`), que e a direcao de
    #       "venceu", "empate", "partida perfeita" e "desafio concluido" — feitos
    #       que **nao tem gradacao**: ou se atingiu, ou nao. Sem ele, quatro das
    #       dezesseis chaves nao entrariam, e o cadeado 4 (T026) reprovaria.
    #
    #   (b) `co_direcao` era `VARCHAR(10)`, e `marco_atingido` tem 14 caracteres.
    #       Esta e a especie de defeito que so aparece no `INSERT`, ja no ar.
    #
    # O `data-model.md` foi corrigido na mesma resposta.
    op.execute(
        """
        CREATE TABLE desafio.tb902_catalogo_feito (
            nu_feito       SMALLINT    PRIMARY KEY,
            co_feito       VARCHAR(40) NOT NULL UNIQUE,
            no_feito       VARCHAR(60) NOT NULL,
            co_unidade     VARCHAR(20) NOT NULL,
            co_direcao     VARCHAR(20) NOT NULL,
            co_procedencia VARCHAR(12) NOT NULL,
            co_jogo        VARCHAR(30),
            CONSTRAINT ck001_direcao CHECK (co_direcao IN
                                            ('maior_melhor', 'menor_melhor',
                                             'marco_atingido')),
            CONSTRAINT ck002_procedencia CHECK (co_procedencia IN
                                            ('tabuleiro', 'sessao'))
        )
        """
    )

    # ── Com que numeros se mediu ────────────────────────────────────────────
    #
    # O perfil de dificuldade e o conjunto de numeros que define Cacau, Pita, Tex
    # e Magno **em cada jogo**: taxa de erro, teto de nos, temperatura da CNN,
    # tempo de pensar. Eles sao afinados de tempos em tempos, e quando mudam,
    # *"a Pita resolve este desafio em 14 de 20 execucoes"* deixa de ser verdade
    # **sem que nada no banco mude**. Este carimbo e o que permite descobrir isso.
    #
    # ⚠️ Os numeros vivem em DOIS lugares, com papeis diferentes, e nenhum dos
    # dois sozinho bastava:
    #
    #   o que RODA    → `motores/perfis/<versao>.json`, versionado no Git. Perfil
    #                   e codigo: muda por commit, passa por revisao, tem teste.
    #   o que EXPLICA → esta tabela, gravada pelo job com o SHA-256 do arquivo.
    #
    # So o arquivo nao bastava: daqui a um ano seria preciso descobrir qual commit
    # estava no ar naquele dia. So a tabela tambem nao: o job nao pode ler os seus
    # proprios parametros de execucao de uma tabela que alguem edita com `UPDATE`
    # — isso e publicar codigo por `INSERT`.
    #
    # `js_perfil` e JSONB e nao colunas porque **a forma e por jogo**: damas nao
    # tem temperatura de CNN, e Pontinhos nao tem multiplicador de motor.
    op.execute(
        """
        CREATE TABLE desafio.tb903_perfil_dificuldade (
            id_perfil        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            co_versao_perfil VARCHAR(40)  NOT NULL,
            co_jogo          VARCHAR(30)  NOT NULL,
            co_personagem    VARCHAR(10)  NOT NULL,
            js_perfil        JSONB        NOT NULL,
            co_arquivo       VARCHAR(120) NOT NULL,
            co_sha256        CHAR(64)     NOT NULL,
            dh_vigencia      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT un001_perfil     UNIQUE (co_versao_perfil, co_jogo,
                                                co_personagem),
            CONSTRAINT ck001_personagem CHECK (co_personagem IN
                                               ('cacau', 'pita', 'tex', 'magno'))
        )
        """
    )

    # ══ As linhas das dimensoes (T022) ══════════════════════════════════════
    #
    # ⚠️ Elas entram na MIGRACAO, e nao num script de carga, porque sem elas as
    # tabelas de fato nao aceitam uma linha sequer: `tb001_desafio` tem FK para
    # `tb901`, e `tb003_feito_desafio` para `tb902`. Uma migracao que criasse as
    # tabelas e deixasse as dimensoes vazias entregaria um schema que nao recebe
    # dado — e o erro so apareceria na primeira execucao do job, no Railway.

    # ── Os dez tipos do catalogo ────────────────────────────────────────────
    #
    # A lista e **piso, nao teto**: tipo novo entra por `INSERT` numa migracao
    # seguinte, sem tocar em nada disto.
    #
    # ⚠️ Um `nu_tipo_desafio` NUNCA muda de significado depois de gravado —
    # reescrever o sentido de um existente falsificaria todos os desafios ja
    # publicados com ele. Acrescentar e barato; reinterpretar e proibido.
    op.execute(
        """
        INSERT INTO desafio.tb901_tipo_desafio
            (nu_tipo_desafio, co_tipo_desafio, no_tipo_desafio, co_jogo) VALUES
            ( 1, 'pontinhos_fechar_caixas',   'Fechar caixas',         'pontinhos'),
            ( 2, 'pontinhos_nao_entregar',    'Nao entregar caixa',    'pontinhos'),
            ( 3, 'pontinhos_lance_unico',     'O lance unico',         'pontinhos'),
            ( 4, 'pontinhos_chegar_ao_placar','Chegar ao placar',      'pontinhos'),
            ( 5, 'damas_sacrificio',          'Sacrificio',            'damas'),
            ( 6, 'damas_coroar',              'Coroar uma dama',       'damas'),
            ( 7, 'damas_final_da_base',       'Final da base',         'damas'),
            ( 8, 'damas_capturar_multipla',   'Captura multipla',      'damas'),
            ( 9, 'damas_sobreviver',          'Sobreviver N turnos',   'damas'),
            (10, 'damas_vencer',              'Vencer a partir daqui', 'damas');
        """
    )

    # ── O catalogo de feitos: as DEZESSEIS chaves do hub, mais o sentinela ──
    #
    # ⚠️ **A FONTE DA VERDADE E O APLICATIVO**, e nao esta migracao:
    # `lib/core/feitos/catalogo_feitos.dart` ja existe, ja esta em campo e ja tem
    # 27 testes. A ordem do dono sobre essa peca foi *"consumir, nao refazer"* —
    # entao estas linhas sao a COPIA dela, e o cadeado 4 (T026) falha listando a
    # chave divergente no dia em que os dois se separarem.
    #
    # ⚠️ **A numeracao e por BLOCOS, com folga entre eles**, e isso e decisao
    # desta tarefa: comuns em 1-9, Pontinhos em 10-19, velha em 20-29, damas em
    # 30-39, sessao em 40-49. Numeracao corrida obrigaria a intercalar um jogo
    # novo no meio dos numeros de outro — e como um `nu_feito` nunca muda de
    # significado, o resultado seria um catalogo em que a numeracao nao diz nada.
    #
    # ⚠️ **`lances_otimos` e da VELHA, nao comum.** Ele mede acerto contra a
    # solucao otima, e so a velha tem uma. Marcar como comum aqui faria a
    # curadoria oferece-lo em desafios de Pontinhos, onde ele nao existe.
    #
    # ⚠️ O `9999` e INEGOCIAVEL, e a licao vem da `0011`: sem um destino valido,
    # um aplicativo MAIS NOVO que o backend estoura a FK, toma 500, e o evento
    # fica preso PARA SEMPRE na fila de sincronizacao daquele aparelho — a
    # partida da pessoa nunca sobe.
    op.execute(
        """
        INSERT INTO desafio.tb902_catalogo_feito
            (nu_feito, co_feito, no_feito, co_unidade, co_direcao,
             co_procedencia, co_jogo) VALUES
            (   1, 'vitoria',              'Venceu',
                'marco',        'marco_atingido', 'tabuleiro', NULL),
            (   2, 'empate',               'Empatou',
                'marco',        'marco_atingido', 'tabuleiro', NULL),
            (   3, 'lances_do_jogador',    'Lances do jogador',
                'contagem',     'menor_melhor',   'tabuleiro', NULL),
            (   4, 'desafio_concluido',    'Desafio concluido',
                'marco',        'marco_atingido', 'tabuleiro', NULL),
            (  10, 'caixas_fechadas',      'Caixas fechadas',
                'contagem',     'maior_melhor',   'tabuleiro', 'pontinhos'),
            (  11, 'caixas_do_adversario', 'Caixas do adversario',
                'contagem',     'menor_melhor',   'tabuleiro', 'pontinhos'),
            (  20, 'lances_otimos',        'Lances otimos',
                'contagem',     'maior_melhor',   'tabuleiro', 'velha'),
            (  21, 'partida_perfeita',     'Partida perfeita',
                'marco',        'marco_atingido', 'tabuleiro', 'velha'),
            (  30, 'damas_coroadas',       'Damas coroadas',
                'contagem',     'maior_melhor',   'tabuleiro', 'damas'),
            (  31, 'capturas_extras',      'Capturas extras',
                'contagem',     'maior_melhor',   'tabuleiro', 'damas'),
            (  32, 'maior_captura',        'Maior captura',
                'contagem',     'maior_melhor',   'tabuleiro', 'damas'),
            (  33, 'material_restante',    'Material restante',
                'contagem',     'maior_melhor',   'tabuleiro', 'damas'),
            (  34, 'material_do_adversario','Material do adversario',
                'contagem',     'menor_melhor',   'tabuleiro', 'damas'),
            (  40, 'tempo_ate_resolver',   'Tempo ate resolver',
                'milissegundos','menor_melhor',   'sessao',    NULL),
            (  41, 'tentativas',           'Tentativas',
                'contagem',     'menor_melhor',   'sessao',    NULL),
            (  42, 'dicas_usadas',         'Dicas usadas',
                'contagem',     'menor_melhor',   'sessao',    NULL),
            (9999, 'desconhecido',         'Desconhecido',
                'contagem',     'maior_melhor',   'sessao',    NULL);
        """
    )

    # ── E `tb903_perfil_dificuldade` fica VAZIA, de proposito ───────────────
    #
    # ⚠️ Esta e a unica dimensao do schema que a migracao NAO semeia, e a razao
    # esta escrita no `data-model.md`: quem a preenche e **o job**, ao carregar o
    # arquivo `motores/perfis/<versao>.json` pela primeira vez.
    #
    # Uma migracao que soubesse a taxa de erro da Cacau e o teto de nos do Magno
    # estaria publicando **calibracao por `INSERT`** — a mesma fronteira que
    # `js_chegada` existe para defender: dado se publica, codigo se versiona.
    #
    # ⚠️ Consequencia operacional, e ela e real: o primeiro `INSERT` em
    # `tb001_desafio` **falha** enquanto o job nao tiver gravado pelo menos uma
    # linha por (perfil, jogo, mascote) — a FK composta `fk001_perfil` recusa. E
    # o comportamento desejado: desafio medido com um perfil que ninguem declarou
    # nao entra.

    # ══ Fatos ═══════════════════════════════════════════════════════════════

    # ── A unidade jogavel ───────────────────────────────────────────────────
    #
    # Uma linha aqui e UM desafio: a posicao de partida, a linha de chegada, o
    # enunciado, o adversario, o gabarito e a calibracao.
    #
    # ⚠️ **Um desafio e publicado UMA VEZ SO.** A reprise (T041) e uma COPIA, com
    # identificador proprio e `id_desafio_origem` apontando para o original —
    # nunca um estado especial dentro da linha antiga.
    #
    # Sobre as colunas que costumam gerar duvida:
    #
    # `co_formato_posicao` + `js_posicao_inicial` sao um par. O Pontinhos precisa
    # da SEQUENCIA de lances (a posse de uma caixa e historico: ela nao esta no
    # tabuleiro); as damas cabem numa FEN (cada peca carrega a sua cor na propria
    # casa). Duas formas de escrever posicao, uma coluna que diz qual e — e e isso
    # que faz um jogo novo caber aqui sem migracao.
    #
    # `co_chave_objetivo` + `js_objetivo` tambem sao um par, e sao dois campos de
    # proposito: a chave e de i18n (⛔ **nunca a frase pronta** — ela viajaria em
    # um idioma so), e o JSON traz os valores que entram nos espacos da frase.
    #
    # `ic_chegada_encerra_partida` e DERIVADO das clausulas em T030, nao digitado:
    # "feche 4 caixas" num tabuleiro de 12 nao encerra a partida, e digitar isso a
    # mao erraria calado no dia em que o tabuleiro mudasse de tamanho.
    #
    # `nu_semente` e o que faz **o mesmo adversario para todo mundo**.
    #
    # `nu_tempo_piso_ms`/`nu_tempo_teto_ms` sao a regua contra a qual "rapido"
    # significa alguma coisa. Saem da medicao (T037): o piso e o tempo do gabarito
    # jogado direto; o teto e onde a parcela de tempo zera.
    #
    # `nu_versao_catalogo` carimba com que versao do catalogo de feitos as linhas
    # de `tb003_feito_desafio` foram escritas. E ele que mantem uma resolucao
    # antiga **explicavel** depois de o catalogo crescer.
    op.execute(
        """
        CREATE TABLE desafio.tb001_desafio (
            id_desafio         UUID PRIMARY KEY DEFAULT gen_random_uuid(),

            co_jogo            VARCHAR(30)  NOT NULL,
            co_modalidade      VARCHAR(30),
            co_variante        VARCHAR(30)  NOT NULL,
            co_formato_posicao VARCHAR(20)  NOT NULL,
            js_posicao_inicial JSONB        NOT NULL,

            nu_tipo_desafio    SMALLINT     NOT NULL
                REFERENCES desafio.tb901_tipo_desafio(nu_tipo_desafio),
            js_chegada         JSONB        NOT NULL,
            ic_chegada_encerra_partida BOOLEAN NOT NULL,

            co_chave_objetivo  VARCHAR(60)  NOT NULL,
            js_objetivo        JSONB        NOT NULL,

            co_personagem      VARCHAR(10)  NOT NULL,
            nu_semente         BIGINT       NOT NULL,

            js_solucao         JSONB        NOT NULL,
            nu_lances_solucao  SMALLINT     NOT NULL,

            nu_tempo_piso_ms   INT          NOT NULL,
            nu_tempo_teto_ms   INT          NOT NULL,

            nu_versao_catalogo SMALLINT     NOT NULL,

            co_versao_minima   VARCHAR(20)  NOT NULL,
            co_versao_perfil   VARCHAR(40)  NOT NULL,
            co_versao_motor    VARCHAR(40)  NOT NULL,
            nu_teto_log        INT          NOT NULL,

            co_curadoria       VARCHAR(12)  NOT NULL,
            de_motivo_descarte TEXT,
            id_desafio_origem  UUID REFERENCES desafio.tb001_desafio(id_desafio),
            ic_reprise         BOOLEAN      NOT NULL DEFAULT FALSE,

            dh_geracao         TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT ck001_formato_posicao CHECK (co_formato_posicao IN
                                             ('sequencia_lances', 'fen')),
            CONSTRAINT ck002_personagem    CHECK (co_personagem IN
                                             ('cacau', 'pita', 'tex', 'magno')),
            CONSTRAINT ck003_curadoria     CHECK (co_curadoria IN
                                             ('candidato', 'aprovado', 'descartado')),
            CONSTRAINT ck004_motivo        CHECK (co_curadoria <> 'descartado'
                                                  OR de_motivo_descarte IS NOT NULL),
            CONSTRAINT ck005_solucao       CHECK (nu_lances_solucao > 0),
            CONSTRAINT ck006_semente       CHECK (nu_semente BETWEEN 1 AND 4294967295),
            CONSTRAINT ck007_regua_tempo   CHECK (nu_tempo_piso_ms > 0
                                                  AND nu_tempo_teto_ms > nu_tempo_piso_ms),
            CONSTRAINT fk001_perfil        FOREIGN KEY
                (co_versao_perfil, co_jogo, co_personagem)
                REFERENCES desafio.tb903_perfil_dificuldade
                (co_versao_perfil, co_jogo, co_personagem)
        )
        """
    )

    # A curadoria pergunta "o que esta esperando aprovacao?" o tempo todo, e o
    # painel (T039) e a unica tela que le esta tabela de verdade.
    op.execute(
        "CREATE INDEX ix001_desafio_curadoria "
        "ON desafio.tb001_desafio (co_curadoria)"
    )

    # ── A regua: quantas vezes cada mascote resolveu ────────────────────────
    #
    # Uma linha **por mascote**, e e isso que a torna tabela em vez de um par de
    # colunas em `tb001`: descartar um desafio por "duro demais" e por "banal" sao
    # motivos diferentes, e e a taxa **por nivel** que os separa. E a evidencia de
    # que a Pita resolve e a Cacau nao, medida em 20 execucoes antes da aprovacao.
    #
    # ⚠️ `co_jogo` e `co_personagem` sao repetidos do desafio DE PROPOSITO: e o
    # que fecha a FK composta do perfil sem um `JOIN`. Um teste confere que eles
    # batem com os do desafio apontado (T046).
    op.execute(
        """
        CREATE TABLE desafio.tb002_medicao_regua (
            id_medicao       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_desafio       UUID        NOT NULL
                REFERENCES desafio.tb001_desafio(id_desafio) ON DELETE CASCADE,
            co_jogo          VARCHAR(30) NOT NULL,
            co_personagem    VARCHAR(10) NOT NULL,
            nu_execucoes     SMALLINT    NOT NULL,
            nu_resolveu      SMALLINT    NOT NULL,
            co_versao_perfil VARCHAR(40) NOT NULL,
            co_versao_motor  VARCHAR(40) NOT NULL,
            dh_medicao       TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT un001_medicao   UNIQUE (id_desafio, co_personagem,
                                               co_versao_perfil),
            CONSTRAINT ck001_personagem CHECK (co_personagem IN
                                               ('cacau', 'pita', 'tex', 'magno')),
            CONSTRAINT ck002_resolveu   CHECK (nu_resolveu BETWEEN 0 AND nu_execucoes),
            CONSTRAINT fk001_perfil     FOREIGN KEY
                (co_versao_perfil, co_jogo, co_personagem)
                REFERENCES desafio.tb903_perfil_dificuldade
                (co_versao_perfil, co_jogo, co_personagem)
        )
        """
    )

    # ── Que medidas ESTE desafio produz, e com que peso ─────────────────────
    #
    # Isto era um JSONB `js_feitos_medidos` dentro de `tb001_desafio`, e o dono
    # desfez a escolha com o argumento certo: **um catalogo que ninguem referencia
    # nao e catalogo**. A chave apontava para `tb902` por uma string dentro de um
    # JSON — quer dizer, por nada: `caixas_fechada` (sem o "s") entrava no banco,
    # viajava para o aparelho e so falhava na hora de pontuar.
    #
    # O que se ganha: chave inexistente **nao entra**; cada feito aparece uma vez
    # so por desafio; e a curadoria consegue perguntar "quais desafios medem
    # cadeias?" com um `WHERE`.
    #
    # O que se paga, dito em voz alta: a resposta publicada continua sendo um JSON
    # com a mesma forma — quem o monta agora e a API, a partir destas linhas. Um
    # `JOIN` a mais na publicacao, uma vez por dia, por uma integridade que vale
    # todos os dias.
    #
    # ⚠️ **Peso zero e legitimo, nao desperdicio.** O feito continua sendo medido
    # e exibido no Raio-X, so nao conta para a nota: "quantas cadeias voce criou"
    # interessa em qualquer desafio de Pontinhos, mas so e MERITO num desafio cujo
    # objetivo seja cria-las. O `ck003_faixa` amarra os dois — `nenhuma` so existe
    # com peso zero.
    #
    # Os pesos somam 1,000 por desafio; quem confere e um teste (T046), nao um
    # `CHECK`: soma entre linhas nao cabe num `CHECK` de linha.
    op.execute(
        """
        CREATE TABLE desafio.tb003_feito_desafio (
            id_feito_desafio UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_desafio       UUID     NOT NULL
                REFERENCES desafio.tb001_desafio(id_desafio) ON DELETE CASCADE,
            nu_feito         SMALLINT NOT NULL
                REFERENCES desafio.tb902_catalogo_feito(nu_feito),

            nu_ordem         SMALLINT NOT NULL,

            vr_peso          NUMERIC(4,3) NOT NULL,

            co_normalizacao  VARCHAR(10) NOT NULL,
            vr_min           NUMERIC(12,3),
            vr_max           NUMERIC(12,3),
            co_sobre         VARCHAR(40),

            CONSTRAINT un001_feito  UNIQUE (id_desafio, nu_feito),
            CONSTRAINT un002_ordem  UNIQUE (id_desafio, nu_ordem),
            CONSTRAINT ck001_peso   CHECK (vr_peso BETWEEN 0 AND 1),
            CONSTRAINT ck002_norma  CHECK (co_normalizacao IN
                                           ('faixa', 'fracao', 'nenhuma')),
            CONSTRAINT ck003_faixa  CHECK (
                (co_normalizacao = 'faixa'   AND vr_min IS NOT NULL
                                             AND vr_max IS NOT NULL AND vr_max > vr_min
                                             AND co_sobre IS NULL)
             OR (co_normalizacao = 'fracao'  AND co_sobre IS NOT NULL
                                             AND vr_min IS NULL AND vr_max IS NULL)
             OR (co_normalizacao = 'nenhuma' AND vr_min IS NULL AND vr_max IS NULL
                                             AND co_sobre IS NULL AND vr_peso = 0)),
            CONSTRAINT ck004_ordem  CHECK (nu_ordem > 0)
        )
        """
    )

    op.execute(
        "CREATE INDEX ix001_feito_desafio "
        "ON desafio.tb003_feito_desafio (id_desafio)"
    )

    # ══ VIEWs ═══════════════════════════════════════════════════════════════
    #
    # ⚠️ **A leitura nunca toca a tabela** — convencao do projeto desde a `0001`.
    # Uma por tabela, mesmo quando nao ha `JOIN` a fazer.
    #
    # ⚠️ E as colunas sao listadas UMA A UMA, nunca `SELECT *`. Uma VIEW criada com
    # `SELECT *` congela a lista de colunas no instante da criacao: acrescentar
    # coluna a tabela nao a faz aparecer na VIEW, e ninguem e avisado. Listar
    # explicitamente ao menos deixa o esquecimento visivel no diff.

    op.execute(
        """
        CREATE VIEW desafio.vw901_tipo_desafio AS
        SELECT nu_tipo_desafio,
               co_tipo_desafio,
               no_tipo_desafio,
               co_jogo
          FROM desafio.tb901_tipo_desafio
        """
    )

    op.execute(
        """
        CREATE VIEW desafio.vw902_catalogo_feito AS
        SELECT nu_feito,
               co_feito,
               no_feito,
               co_unidade,
               co_direcao,
               co_procedencia,
               co_jogo
          FROM desafio.tb902_catalogo_feito
        """
    )

    op.execute(
        """
        CREATE VIEW desafio.vw903_perfil_dificuldade AS
        SELECT id_perfil,
               co_versao_perfil,
               co_jogo,
               co_personagem,
               js_perfil,
               co_arquivo,
               co_sha256,
               dh_vigencia
          FROM desafio.tb903_perfil_dificuldade
        """
    )

    # A VIEW do desafio entrega o tipo ja resolvido: quem le nao precisa lembrar
    # de juntar a dimensao para saber que `nu_tipo_desafio = 1` e "fechar caixas".
    op.execute(
        """
        CREATE VIEW desafio.vw001_desafio AS
        SELECT d.id_desafio,
               d.co_jogo,
               d.co_modalidade,
               d.co_variante,
               d.co_formato_posicao,
               d.js_posicao_inicial,
               d.nu_tipo_desafio,
               t.co_tipo_desafio,
               t.no_tipo_desafio,
               d.js_chegada,
               d.ic_chegada_encerra_partida,
               d.co_chave_objetivo,
               d.js_objetivo,
               d.co_personagem,
               d.nu_semente,
               d.js_solucao,
               d.nu_lances_solucao,
               d.nu_tempo_piso_ms,
               d.nu_tempo_teto_ms,
               d.nu_versao_catalogo,
               d.co_versao_minima,
               d.co_versao_perfil,
               d.co_versao_motor,
               d.nu_teto_log,
               d.co_curadoria,
               d.de_motivo_descarte,
               d.id_desafio_origem,
               d.ic_reprise,
               d.dh_geracao
          FROM desafio.tb001_desafio d
          JOIN desafio.tb901_tipo_desafio t
            ON t.nu_tipo_desafio = d.nu_tipo_desafio
        """
    )

    op.execute(
        """
        CREATE VIEW desafio.vw002_medicao_regua AS
        SELECT id_medicao,
               id_desafio,
               co_jogo,
               co_personagem,
               nu_execucoes,
               nu_resolveu,
               co_versao_perfil,
               co_versao_motor,
               dh_medicao
          FROM desafio.tb002_medicao_regua
        """
    )

    # ⚠️ Esta e a VIEW que a publicacao le para montar o bloco de feitos da
    # resposta: ela devolve `co_feito`, `co_unidade` e `co_direcao` ao lado do
    # peso, para o endpoint nao precisar saber juntar duas tabelas.
    op.execute(
        """
        CREATE VIEW desafio.vw003_feito_desafio AS
        SELECT f.id_feito_desafio,
               f.id_desafio,
               f.nu_feito,
               c.co_feito,
               c.no_feito,
               c.co_unidade,
               c.co_direcao,
               c.co_procedencia,
               f.nu_ordem,
               f.vr_peso,
               f.co_normalizacao,
               f.vr_min,
               f.vr_max,
               f.co_sobre
          FROM desafio.tb003_feito_desafio f
          JOIN desafio.tb902_catalogo_feito c
            ON c.nu_feito = f.nu_feito
        """
    )


def downgrade() -> None:
    """Derruba o schema inteiro.

    ⚠️ **So para o ambiente local.** Este e o unico lugar do arquivo onde um
    `DROP` aparece, e o teste de migracao aditiva ignora o `downgrade()`
    exatamente por isso.

    ⚠️ Enquanto nao houver o primeiro `upgrade` publicado no PRD, este
    `downgrade` e tambem a ferramenta do dropa-e-recria da §8b: consertar
    modelagem aqui e `downgrade` + editar o `upgrade` + `upgrade` de novo, no
    ambiente `des`. Depois da publicacao, isso deixa de valer.
    """
    op.execute("DROP SCHEMA IF EXISTS desafio CASCADE")

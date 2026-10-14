"""Schema `jogo_quatro` - a extensao de PARTIDA e de JOGADA do 4o jogo.

CONTEXTO
--------
O Quatro em Linha (spec 010 do app) e o quarto jogo da Arena Sagaz. Como os
tres anteriores, ele grava a partida e a jogada GENERICAS em
`partida.tb001_partida` / `partida.tb002_jogada`, e o que e so dele num schema
proprio. Esta migracao cria esse schema.

⚠️ NOTA DE ACENTUACAO: este arquivo nao usa acentos, seguindo a convencao das
migracoes de schema de jogo (0011, 0012): evita surpresa de encoding no console
do Alembic no Windows.

O PORTAO DO DONO
----------------
`arena-sagaz-frontend/specs/010-jogo-quatro-em-linha/data-model.md` §2, VALIDADO
em 13/10/2026 (T003, `docs/DECISOES-do-dono.md` §8zzz). Nenhum item do log foi
retificado: os nomes, os tipos e a ordem das colunas abaixo sao os de la, e o
cadeado `tests/unitarios/test_migracao_quatro_bate_com_data_model.py` compara
os dois lados mecanicamente.

O QUE ESTE SCHEMA TEM, E O QUE NAO TEM
---------------------------------------
- **`tb001_partida`**, a extensao 1:1 da partida, no molde das damas: a versao
  do motor e do contrato (o replay precisa saber COM QUAL regra a partida foi
  jogada), a posicao de onde ela partiu (`co_lances_iniciais`, como SEQUENCIA de
  lances), quem fez o 1o lance e o que a pessoa escolheu no "quem comeca".
- **`tb002_jogada`**, uma linha por lance: o lance como `{tipo, coluna}`, e a
  telemetria da busca nos lances da CPU (`NULL` no lance do humano).
- **Tres dimensoes**: a acao da CPU (por que aquela coluna), o motivo de parada
  da busca e o TIPO do lance. O tipo e dimensao, e nao texto, porque e a peca
  que a modalidade prevista exige (o Pop Out entra com um `INSERT`, sem `ALTER`
  numa tabela com dados; RF-QTR-012).
- ⛔ **Sem tabela de recusa** (as damas tem): a coluna cheia e recusa de
  interface, sem varias causas a diagnosticar. ⛔ **Sem a posicao antes de cada
  lance** (as damas guardam o FEN): reprocessar 41 lances de gravidade custa
  microssegundos, e a sequencia inicial mais a ordem bastam.

⚠️ ESTA MIGRACAO E PURAMENTE ADITIVA - E ISSO E VERIFICADO, NAO PROMETIDO
-------------------------------------------------------------------------
Ha usuarios reais em `prd`. O `upgrade()` contem APENAS `CREATE SCHEMA`,
`CREATE TABLE`, `INSERT` nas dimensoes e `CREATE VIEW`; nenhum objeto existente
e tocado (RF-QTR-182). O cadeado `test_migracoes_aditivas.py` le o arquivo e
recusa qualquer outro comando.

COMPATIBILIDADE COM QUEM NAO VAI ATUALIZAR O APP
------------------------------------------------
Um schema novo e invisivel para quem nao o consulta: um app sem o Quatro nunca
envia `partida["quatro"]`. E o contrario tambem vale desde a spec 007 (V-5): um
app MAIS NOVO que o servidor nao quebra - a extensao desconhecida e aceita e
ignorada com um `warning`, e a partida generica e o XP entram. Por isso a
migracao pode ser aplicada antes do app que grava nela, e e o que a T078 faz.
"""

from typing import Sequence, Union

from alembic import op

# ⚠️ O id de revisao do Alembic tem limite de 32 caracteres; passar disso faz o
# upgrade rodar o DDL inteiro e falhar so no fim. "0033_schema_jogo_quatro" tem
# 23.
revision: str = "0033_schema_jogo_quatro"
down_revision: Union[str, None] = "0032_regua_nova_na_liberacao"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria o schema `jogo_quatro` inteiro. So acrescenta."""
    op.execute("CREATE SCHEMA IF NOT EXISTS jogo_quatro")

    # ══ Dimensoes ═══════════════════════════════════════════════════════════
    #
    # Vem ANTES das tabelas de fato, porque a jogada tem FK para as tres.
    #
    # ⚠️ A numeracao repete a dos precedentes, para o mesmo numero dizer a mesma
    # coisa nos tres schemas de jogo (tb901 = a acao da CPU, como na velha;
    # tb902 = o motivo de parada, como nas damas).
    #
    # ⚠️ Um numero NUNCA muda de significado depois de gravado. Acrescentar e
    # migracao nova; reescrever o sentido de um existente falsifica o historico.
    #
    # ⚠️ O `9999` e INEGOCIAVEL (a licao da 0011): sem um destino valido, um app
    # MAIS NOVO que o backend, mandando um codigo que este banco nao conhece,
    # estouraria a FK, tomaria 500, e o evento ficaria preso para sempre na fila
    # de sincronizacao do aparelho. Com o sentinela, a jogada entra.

    # ── Por que a CPU escolheu aquela coluna ────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_quatro.tb901_jogada_acao (
            nu_acao SMALLINT    PRIMARY KEY,
            co_acao VARCHAR(30) NOT NULL UNIQUE,
            no_acao VARCHAR(40) NOT NULL
        )
        """
    )

    # Os codigos sao os que a politica de dificuldade do motor devolve
    # (`politica_dificuldade_quatro.dart`, conferidos por grep em 14/10/2026).
    # Sem esta dimensao, a abertura sorteada do Magno (de proposito) e o erro
    # epsilon da Cacau pareceriam defeito do motor numa consulta.
    op.execute(
        """
        INSERT INTO jogo_quatro.tb901_jogada_acao (nu_acao, co_acao, no_acao) VALUES
            (1,    'busca_melhor',      'Busca - melhor lance'),
            (2,    'epsilon_aleatorio', 'Erro epsilon (fora do melhor)'),
            (3,    'abertura_sorteada', 'Abertura sorteada do Magno'),
            (4,    'vitoria_imediata',  'Filtro: venceu com 4 na mao'),
            (5,    'bloqueio_imediato', 'Filtro: tapou a vitoria do outro'),
            (6,    'empate_sorteado',   'Empate de valor, sorteado'),
            (9999, 'desconhecido',      'Desconhecido')
        """
    )

    # ── Por que a busca parou ───────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_quatro.tb902_motivo_parada_busca (
            nu_motivo_parada_busca SMALLINT    PRIMARY KEY,
            co_motivo_parada_busca VARCHAR(20) NOT NULL UNIQUE,
            no_motivo_parada_busca VARCHAR(40) NOT NULL
        )
        """
    )

    # Os MESMOS numeros das damas para os mesmos significados. O `6 base_finais`
    # das damas nao entra: este jogo nao tem base de finais.
    #
    # ⚠️ O `3` (tempo) e o numero que mais importa (RF-QTR-051, SC-005): parada
    # por tempo recorrente e a rede de 10 s mordendo, isto e, o aparelho jogando
    # mais fraco que o nivel.
    op.execute(
        """
        INSERT INTO jogo_quatro.tb902_motivo_parada_busca
            (nu_motivo_parada_busca, co_motivo_parada_busca, no_motivo_parada_busca) VALUES
            (1,    'profundidade', 'Terminou a profundidade'),
            (2,    'nos',          'Esgotou o teto de nos'),
            (3,    'tempo',        'Esgotou o tempo'),
            (4,    'decidido',     'Vitoria ou derrota forcada'),
            (5,    'lance_unico',  'Lance unico: nao houve busca'),
            (9999, 'desconhecido', 'Desconhecido')
        """
    )

    # ── O TIPO do lance ─────────────────────────────────────────────────────
    #
    # Sem precedente nos outros jogos: as damas gravam o lance como texto e a
    # velha como celula. Aqui o lance e `{tipo, coluna}`, e o tipo e dimensao.
    op.execute(
        """
        CREATE TABLE jogo_quatro.tb903_tipo_lance (
            nu_tipo_lance SMALLINT    PRIMARY KEY,
            co_tipo_lance VARCHAR(20) NOT NULL UNIQUE,
            no_tipo_lance VARCHAR(40) NOT NULL
        )
        """
    )
    op.execute(
        """
        INSERT INTO jogo_quatro.tb903_tipo_lance
            (nu_tipo_lance, co_tipo_lance, no_tipo_lance) VALUES
            (1,    'soltar',       'Soltar uma peca'),
            (9999, 'desconhecido', 'Desconhecido')
        """
    )

    # ══ Tabelas de fato ═════════════════════════════════════════════════════

    # ── A extensao 1:1 da PARTIDA ───────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_quatro.tb001_partida (
            id_partida              UUID PRIMARY KEY
                REFERENCES partida.tb001_partida(id_partida) ON DELETE CASCADE,
            co_versao_motor         VARCHAR(60)  NOT NULL,
            co_versao_contrato      VARCHAR(20)  NOT NULL,
            co_lances_iniciais      VARCHAR(255) NOT NULL DEFAULT '',
            nu_jogador_abertura     SMALLINT     NOT NULL,
            co_preferencia_abertura VARCHAR(12)  NOT NULL,
            nu_semente_partida      BIGINT,
            js_extra                JSONB,
            -- Quem fez o 1o lance: +1 (J1) ou -1 (J2), o SINAL, como nas
            -- extensoes dos outros jogos.
            CONSTRAINT ck_quatro_jogador_abertura
                CHECK (nu_jogador_abertura IN (1, -1)),
            -- Os valores do `enum QuemComeca` do app.
            CONSTRAINT ck_quatro_preferencia_abertura
                CHECK (co_preferencia_abertura IN ('j1', 'j2', 'alternado')),
            -- So a FORMA da notacao (`s4s4s3`): letra do tipo e coluna de um
            -- ou dois algarismos. Quantas colunas existem e regra da
            -- modalidade, e nao do banco.
            CONSTRAINT ck_quatro_lances_iniciais
                CHECK (co_lances_iniciais ~ '^([a-z][0-9]{1,2})*$')
        )
        """
    )

    # ⚠️ Sobre `co_lances_iniciais`: a posicao de onde a partida partiu, como
    # SEQUENCIA de lances. Vazia numa partida comum; a posicao publicada num
    # desafio. A sequencia, e nao um desenho do tabuleiro, porque ela tambem diz
    # a ORDEM (o replay precisa dela) e serve ao Pop Out sem mudar. 255
    # caracteres cabem 85 lances de 3, o dobro das 42 casas.
    #
    # ⚠️ Sobre `nu_jogador_abertura`: num jogo resolvido, quem abre decide a
    # partida, e e o recorte de toda analise do Magno. Nao e derivavel de uma
    # partida abandonada ANTES do 1o lance (o mesmo argumento do `co_cor_j1` das
    # damas).

    # ── A extensao 1:1 da JOGADA ────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_quatro.tb002_jogada (
            id_jogada                UUID PRIMARY KEY
                REFERENCES partida.tb002_jogada(id_jogada) ON DELETE CASCADE,
            co_jogador               SMALLINT    NOT NULL,
            nu_tipo_lance            SMALLINT    NOT NULL
                REFERENCES jogo_quatro.tb903_tipo_lance(nu_tipo_lance),
            nu_coluna                SMALLINT    NOT NULL,
            nu_acao                  SMALLINT
                REFERENCES jogo_quatro.tb901_jogada_acao(nu_acao),
            qt_nos_visitados         INTEGER,
            nu_profundidade_atingida SMALLINT,
            nu_motivo_parada_busca   SMALLINT
                REFERENCES jogo_quatro.tb902_motivo_parada_busca(nu_motivo_parada_busca),
            nu_tempo_busca_ms        INTEGER,
            nu_avaliacao_j1          INTEGER,
            nu_semente               BIGINT,
            co_motor_busca           VARCHAR(10),
            js_extra                 JSONB,
            -- +1 (J1) / -1 (J2): o SINAL, como nos outros jogos.
            CONSTRAINT ck_quatro_jogador CHECK (co_jogador IN (1, -1)),
            -- Sem teto: o teto (7) e da modalidade, e um BETWEEN 1 AND 7 faria
            -- o primeiro tabuleiro maior pedir ALTER numa tabela com dados.
            CONSTRAINT ck_quatro_coluna CHECK (nu_coluna >= 1),
            -- Se houve busca, houve semente: sem ela o replay daquele lance nao
            -- reproduz, e e nos niveis que ERRAM de proposito que ela decide.
            CONSTRAINT ck_quatro_semente_da_cpu
                CHECK (qt_nos_visitados IS NULL OR nu_semente IS NOT NULL),
            CONSTRAINT ck_quatro_motor_busca
                CHECK (co_motor_busca IS NULL OR co_motor_busca IN ('dart', 'rust'))
        )
        """
    )

    # ⚠️ Sobre a telemetria ser ANULAVEL: `NULL` = lance do HUMANO (ou a jogada
    # automatica do relogio). Um zero gravado falsearia qualquer media.
    #
    # ⚠️ Sobre `nu_avaliacao_j1`: a nota que a BUSCA devolveu, sempre no
    # referencial do J1 (invertida quando quem busca e o J2), como a
    # `nu_avaliacao_brancas` das damas.
    #
    # ⚠️ Sobre `co_motor_busca` desde o dia 1, mesmo sendo hoje sempre 'dart': a
    # bancada pode um dia mandar Rust, e acrescentar a coluna depois seria ALTER
    # com dados (o caminho que as damas fizeram em duas migracoes, 0012 e 0013).

    # Nenhum indice: as duas tabelas de fato sao 1:1, e a PK ja e a coluna do
    # JOIN (o mesmo raciocinio da 0012).

    # ══ VIEWs - le-se SEMPRE pela VIEW (regra do ecossistema) ═══════════════
    op.execute(
        "CREATE VIEW jogo_quatro.vw901_jogada_acao AS "
        "SELECT * FROM jogo_quatro.tb901_jogada_acao"
    )
    op.execute(
        "CREATE VIEW jogo_quatro.vw902_motivo_parada_busca AS "
        "SELECT * FROM jogo_quatro.tb902_motivo_parada_busca"
    )
    op.execute(
        "CREATE VIEW jogo_quatro.vw903_tipo_lance AS "
        "SELECT * FROM jogo_quatro.tb903_tipo_lance"
    )

    # ⚠️ Nas views de FATO as colunas sao LISTADAS, e nao `SELECT *`: a licao da
    # 0017 - uma VIEW com `SELECT *` congela a lista de colunas na criacao e nao
    # enxerga a coluna que entrar depois.
    op.execute(
        """
        CREATE VIEW jogo_quatro.vw001_partida AS
        SELECT p.id_partida,
               p.co_versao_motor,
               p.co_versao_contrato,
               p.co_lances_iniciais,
               p.nu_jogador_abertura,
               p.co_preferencia_abertura,
               p.nu_semente_partida,
               p.js_extra
          FROM jogo_quatro.tb001_partida p
        """
    )

    # A jogada ja com os tres codigos POR EXTENSO: quem le um log quer ver
    # 'nos' e 'soltar', e nao os numeros 2 e 1.
    #
    # ⚠️ `LEFT JOIN` nas tres dimensoes: a acao e o motivo sao NULL no lance do
    # humano, e um INNER JOIN apagaria exatamente esses lances da view.
    op.execute(
        """
        CREATE VIEW jogo_quatro.vw002_jogada AS
        SELECT j.id_jogada,
               j.co_jogador,
               j.nu_tipo_lance,
               t.co_tipo_lance,
               j.nu_coluna,
               j.nu_acao,
               a.co_acao,
               j.qt_nos_visitados,
               j.nu_profundidade_atingida,
               j.nu_motivo_parada_busca,
               m.co_motivo_parada_busca,
               j.nu_tempo_busca_ms,
               j.nu_avaliacao_j1,
               j.nu_semente,
               j.co_motor_busca,
               j.js_extra
          FROM jogo_quatro.tb002_jogada j
          LEFT JOIN jogo_quatro.tb903_tipo_lance t
                 ON t.nu_tipo_lance = j.nu_tipo_lance
          LEFT JOIN jogo_quatro.tb901_jogada_acao a
                 ON a.nu_acao = j.nu_acao
          LEFT JOIN jogo_quatro.tb902_motivo_parada_busca m
                 ON m.nu_motivo_parada_busca = j.nu_motivo_parada_busca
        """
    )


def downgrade() -> None:
    """Derruba o schema inteiro.

    ⚠️ **So para o ambiente local.** Nunca rodar em `prd`: o `CASCADE` levaria
    junto as partidas do Quatro em Linha ja gravadas. E o unico `DROP` deste
    arquivo, e so desfaz o que a propria revisao criou (como na 0011 e na 0012).
    """
    op.execute("DROP SCHEMA IF EXISTS jogo_quatro CASCADE")

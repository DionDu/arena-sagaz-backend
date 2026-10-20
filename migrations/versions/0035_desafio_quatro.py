"""O Desafio do Dia do Quatro em Linha: os dez tipos e as sete medidas.

Revision ID: 0035_desafio_quatro
Revises: 0034_acoes_de_descuido_quatro
Create Date: 2026-10-20

═══════════════════════════════════════════════════════════════════════════
O QUE ESTA MIGRACAO FAZ
═══════════════════════════════════════════════════════════════════════════

So INSERT em duas dimensoes que ja existem (`data-model.md` §3 da spec 010,
validado pelo dono na folha de aval da T003, 13/10/2026, com a retificacao
"10 tipos de desafio e 7 medidas", §8zzz):

- `desafio.tb901_tipo_desafio`: os tipos 40 a 49, todos do jogo `quatro`. A
  faixa 40 deixa livres os numeros dos jogos que ja existem (o maior em uso e
  o 22, da 0023). Eram tres; o dono achou "muito pobre" e aprovou mais sete.
- `desafio.tb902_catalogo_feito`: as medidas 50 a 56, na faixa do jogo (10 e o
  Pontinhos, 20 a velha, 30 as damas, 40 as de sessao).

⚠️ **Tipo no banco nao e tipo no ar.** O INSERT dos dez entra de uma vez; cada
tipo so ganha receita no job (`job/tipos_de_desafio.py`) depois de passar na
escada da regua, e o que falhar fica sem receita, como os tipos 7 e 10 das
damas.

⚠️ **As sete medidas nascem nos DOIS lados na mesma resposta**: aqui e em
`arena-sagaz-frontend/lib/core/feitos/catalogo_feitos.dart`, com o manifesto
`contratos/catalogo_feitos.json` regerado (cadeado 4,
`tests/unitarios/test_catalogo_feito_paridade.py`). Uma chave que existisse de
um lado so nao daria erro em lugar nenhum ate a hora de pontuar.

⚠️ **A direcao e a leitura natural, e nao a do desafio** (a regra 2 do
catalogo): jogar no meio e bom jogo, entao `lances_na_coluna_central` e
`maior_melhor`, mesmo que o `quatro_sem_o_meio` a use com `<= 0` - la ela e
clausula, e nao pontua.

⚠️ **Aplicada pelo dono** (escrita no banco e comando dele): no `des` na T124,
antes do push que leva o job que gera o Quatro; no `prd` na virada (T138). O app
antigo nunca manda estes numeros, e o job so os usa com as receitas prontas.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0035_desafio_quatro"
down_revision: Union[str, None] = "0034_acoes_de_descuido_quatro"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Acrescenta os dez tipos e as sete medidas do Quatro em Linha."""
    op.execute(
        """
        INSERT INTO desafio.tb901_tipo_desafio
            (nu_tipo_desafio, co_tipo_desafio, no_tipo_desafio, co_jogo) VALUES
            (  40, 'quatro_vencer_em_n',     'Venca em N',             'quatro'),
            (  41, 'quatro_segurar_magno',   'Segure o Magno',         'quatro'),
            (  42, 'quatro_unica_coluna',    'A unica coluna',         'quatro'),
            (  43, 'quatro_vencer_diagonal', 'Venca com uma diagonal', 'quatro'),
            (  44, 'quatro_golpe_duplo',     'Golpe duplo',            'quatro'),
            (  45, 'quatro_linha_de_cinco',  'Linha de cinco',         'quatro'),
            (  46, 'quatro_encostadas',      'Pecas encostadas',       'quatro'),
            (  47, 'quatro_sem_o_meio',      'Sem a coluna do meio',   'quatro'),
            (  48, 'quatro_bloquear',        'Bloqueie as ameacas',    'quatro'),
            (  49, 'quatro_virada',          'A virada',               'quatro')
        """
    )
    op.execute(
        """
        INSERT INTO desafio.tb902_catalogo_feito
            (nu_feito, co_feito, no_feito, co_unidade, co_direcao,
             co_procedencia, co_jogo) VALUES
            (  50, 'pecas_encostadas',       'Pecas encostadas',
                'contagem',     'maior_melhor',   'tabuleiro', 'quatro'),
            (  51, 'pecas_encostadas_do_adversario', 'Pecas encostadas do adversario',
                'contagem',     'menor_melhor',   'tabuleiro', 'quatro'),
            (  52, 'vitoria_diagonal',       'Venceu com uma diagonal',
                'marco',        'marco_atingido', 'tabuleiro', 'quatro'),
            (  53, 'linhas_no_lance_final',  'Linhas fechadas no lance final',
                'contagem',     'maior_melhor',   'tabuleiro', 'quatro'),
            (  54, 'maior_linha',            'Maior linha',
                'contagem',     'maior_melhor',   'tabuleiro', 'quatro'),
            (  55, 'lances_na_coluna_central', 'Lances na coluna do meio',
                'contagem',     'maior_melhor',   'tabuleiro', 'quatro'),
            (  56, 'ameacas_bloqueadas',     'Ameacas bloqueadas',
                'contagem',     'maior_melhor',   'tabuleiro', 'quatro')
        """
    )


def downgrade() -> None:
    """Tira as linhas.

    ⚠️ Um desafio publicado aponta para o tipo, e o extrato de XP para a medida
    (chave estrangeira): o `DELETE` recusaria. O downgrade so cabe antes de o
    job gerar o primeiro desafio do Quatro.
    """
    op.execute(
        "DELETE FROM desafio.tb902_catalogo_feito WHERE nu_feito BETWEEN 50 AND 56"
    )
    op.execute(
        "DELETE FROM desafio.tb901_tipo_desafio WHERE nu_tipo_desafio BETWEEN 40 AND 49"
    )

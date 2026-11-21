"""O Desafio do Dia do xadrez: os onze tipos e as dezenove medidas.

Revision ID: 0040_desafio_xadrez
Revises: 0039_schema_jogo_xadrez
Create Date: 2026-11-20

═══════════════════════════════════════════════════════════════════════════
O QUE ESTA MIGRACAO FAZ
═══════════════════════════════════════════════════════════════════════════

So INSERT em duas dimensoes que ja existem (`data-model.md` §3 da spec 012,
validado pelo dono na folha de aval de 14/11/2026, §8zzzz17):

- `desafio.tb901_tipo_desafio`: os tipos 60 a 70, todos do jogo `xadrez`. A
  faixa 60 deixa livres os numeros dos jogos que ja existem (o maior em uso e
  o 51, da 0037). Conferida livre contra o head da `main` (0038) e a 0039 no
  dia em que esta migracao foi escrita (20/11/2026).
- `desafio.tb902_catalogo_feito`: as medidas 60 a 78 (10 e o Pontinhos, 20 a
  velha, 30 as damas, 40 as de sessao, 50 o Quatro). Sao dezenove, e por isso
  passam do bloco de dez: o proximo jogo comeca no 80.

⚠️ **Por tipo de peca, e nao um total ponderado** (a pergunta F da spec): as
medidas 60 a 69 contam pecas comidas e perdidas por tipo, e quem pondera e o
XP. Uma medida ponderada no banco mudaria de sentido a cada ajuste de peso.

⚠️ **Tipo no banco nao e tipo no ar.** O INSERT dos onze entra de uma vez; cada
tipo so ganha receita no job (`job/tipos_de_desafio.py`) depois de passar na
regua (T077), e o que falhar fica sem receita, como os tipos 7 e 10 das damas.

⚠️ **As dezenove medidas nascem nos DOIS lados na mesma resposta**: aqui e em
`arena-sagaz-frontend/lib/core/feitos/catalogo_feitos.dart`, com o manifesto
`contratos/catalogo_feitos.json` regerado (cadeado 4,
`tests/unitarios/test_catalogo_feito_paridade.py`).

⚠️ **A direcao e a leitura natural, e nao a do desafio** (a regra 2 do
catalogo): perder peca e pior, entao `pecas_perdidas_*` e `menor_melhor`, mesmo
quando um desafio a usa como clausula.

⚠️ **Aplicada pelo dono** (escrita no banco e comando dele): no `des` na T068
(2a ida), antes do push que leva o job que gera o xadrez; no `prd` na virada
(fase 6). O app antigo nunca manda estes numeros, e o job so os usa com as
receitas prontas.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0040_desafio_xadrez"
down_revision: Union[str, None] = "0039_schema_jogo_xadrez"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Acrescenta os onze tipos e as dezenove medidas do xadrez."""
    op.execute(
        """
        INSERT INTO desafio.tb901_tipo_desafio
            (nu_tipo_desafio, co_tipo_desafio, no_tipo_desafio, co_jogo) VALUES
            (  60, 'xadrez_espia_comer',      'Coma com a espia',           'xadrez'),
            (  61, 'xadrez_espia_proteger',   'Proteja a espia',            'xadrez'),
            (  62, 'xadrez_espia_atravessar', 'Leve a espia ao outro lado', 'xadrez'),
            (  63, 'xadrez_espia_xeque',      'Xeques da espia',            'xadrez'),
            (  64, 'xadrez_espia_alvo',       'A espia come o alvo',        'xadrez'),
            (  65, 'xadrez_comer_com',        'Coma usando uma peca',       'xadrez'),
            (  66, 'xadrez_nao_perder',       'Nao perca pecas',            'xadrez'),
            (  67, 'xadrez_xeques_seguidos',  'Xeques seguidos',            'xadrez'),
            (  68, 'xadrez_sem_levar_xeque',  'Sem levar xeque',            'xadrez'),
            (  69, 'xadrez_troca',            'A troca',                    'xadrez'),
            (  70, 'xadrez_dar_mate',         'De xeque-mate',              'xadrez')
        """
    )
    op.execute(
        """
        INSERT INTO desafio.tb902_catalogo_feito
            (nu_feito, co_feito, no_feito, co_unidade, co_direcao,
             co_procedencia, co_jogo) VALUES
            (  60, 'pecas_comidas_peao',         'Peoes comidos',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  61, 'pecas_comidas_cavalo',       'Cavalos comidos',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  62, 'pecas_comidas_bispo',        'Bispos comidos',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  63, 'pecas_comidas_torre',        'Torres comidas',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  64, 'pecas_comidas_dama',         'Damas comidas',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  65, 'pecas_perdidas_peao',        'Peoes perdidos',
                'contagem', 'menor_melhor',   'tabuleiro', 'xadrez'),
            (  66, 'pecas_perdidas_cavalo',      'Cavalos perdidos',
                'contagem', 'menor_melhor',   'tabuleiro', 'xadrez'),
            (  67, 'pecas_perdidas_bispo',       'Bispos perdidos',
                'contagem', 'menor_melhor',   'tabuleiro', 'xadrez'),
            (  68, 'pecas_perdidas_torre',       'Torres perdidas',
                'contagem', 'menor_melhor',   'tabuleiro', 'xadrez'),
            (  69, 'pecas_perdidas_dama',        'Damas perdidas',
                'contagem', 'menor_melhor',   'tabuleiro', 'xadrez'),
            (  70, 'capturas_da_espia',          'Capturas da espia',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  71, 'xeques_da_espia',            'Xeques da espia',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  72, 'espia_comida',               'Espia comida',
                'contagem', 'menor_melhor',   'tabuleiro', 'xadrez'),
            (  73, 'espia_na_ultima_fileira',    'Espia na ultima fileira',
                'marco',    'marco_atingido', 'tabuleiro', 'xadrez'),
            (  74, 'alvo_comido_pela_espia',     'Alvo comido pela espia',
                'marco',    'marco_atingido', 'tabuleiro', 'xadrez'),
            (  75, 'capturas_da_classe_marcada', 'Capturas da classe marcada',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  76, 'maior_sequencia_de_xeques',  'Maior sequencia de xeques',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez'),
            (  77, 'xeques_recebidos',           'Xeques recebidos',
                'contagem', 'menor_melhor',   'tabuleiro', 'xadrez'),
            (  78, 'trocas_feitas',              'Trocas feitas',
                'contagem', 'maior_melhor',   'tabuleiro', 'xadrez')
        """
    )


def downgrade() -> None:
    """Tira as linhas.

    ⚠️ Um desafio publicado aponta para o tipo, e o extrato de XP para a medida
    (chave estrangeira): o `DELETE` recusaria. O downgrade so cabe antes de o
    job gerar o primeiro desafio do xadrez.
    """
    op.execute(
        "DELETE FROM desafio.tb902_catalogo_feito WHERE nu_feito BETWEEN 60 AND 78"
    )
    op.execute(
        "DELETE FROM desafio.tb901_tipo_desafio WHERE nu_tipo_desafio BETWEEN 60 AND 70"
    )

"""Os tres tipos de Pontinhos que a medicao aprovou: 12, 14 e 15.

Revision ID: 0024_tres_tipos_de_pontinhos
Revises: 0023_cadeia_longa
Create Date: 2026-09-14

═══════════════════════════════════════════════════════════════════════════
O PEDIDO DO DONO, 14/09/2026
═══════════════════════════════════════════════════════════════════════════

> *"implemente quaisquer desafios novos que ainda nao estejam implementados,
> consolide todos os tipos de desafios que planejamos, disponibilize os mesmos
> no 'catalogo' de desafios que o JOB-DESAFIO possa gerar"*

═══════════════════════════════════════════════════════════════════════════
⛔ NENHUM DOS TRES ENTRA POR PARECER BOA IDEIA — OS TRES FORAM MEDIDOS
═══════════════════════════════════════════════════════════════════════════

Rodada de 254 segundos em 14/09/2026 (`medir_variantes_do_editorial.py
em-avaliacao`, 3 dias x 20 tentativas por candidato):

    economia_de_lances  {caixas:5, lances:8}  ✅ FOLGA     (3 de 3)  10,1 meios-lances
    economia_de_lances  {caixas:5, lances:7}  ✅ FOLGA     (3 de 3)  10,1
    economia_de_lances  {caixas:4, lances:6}  ✅ FOLGA     (3 de 3)   9,0
    troca_favoravel     {ganhar:5, ceder:2}   ⚠️ APERTADO  (2 de 3)  10,0
    troca_favoravel     {ganhar:4, ceder:2}   ✅ FOLGA     (3 de 3)   7,6
    paciencia           {lances: 3}           ✅ FOLGA     (3 de 3)   5,0

⚠️ **As solucoes de 10 meios-lances sao as segundas mais longas do catalogo**,
atras so do `chegar_ao_placar` — o criterio 6 do dono (*"de preferencia muitos
lances ate chegar a conclusao"*, `DECISOES-do-dono.md` §8k-0).

═══════════════════════════════════════════════════════════════════════════
⚠️ OS NUMEROS 12, 14 E 15 NAO SAO ESCOLHA DESTA MIGRACAO
═══════════════════════════════════════════════════════════════════════════

Eles vem de `job/tipos_propostos.py`, que os reservou quando as propostas foram
escritas, e a `0023` deixou isso por escrito: *"os numeros de 11 a 21 ja estao
tomados pelas onze propostas (…) reaproveitar um deles faria duas coisas
diferentes responderem pelo mesmo `nu_tipo_desafio`"*.

⛔ **O 13 fica vago de proposito.** Ele e do `pontinhos_escada_em_um_turno`, que
a medicao mostrou ser **duplicata** do `pontinhos_fechar_caixas` com `turnos: 1`
(e que da zero candidato em 24 tentativas). Preencher o buraco renumerando os
outros desfaria a reserva que a `0023` protege.

═══════════════════════════════════════════════════════════════════════════
⛔ E O TIPO 2 NAO ESTA AQUI, PORQUE ELE JA ESTAVA NO BANCO
═══════════════════════════════════════════════════════════════════════════

`pontinhos_nao_entregar` (numero 2) foi semeado pela `0018` e passou quatro dias
na dimensao **sem receita**. O que faltava nao era linha de banco: era a receita,
que entrou hoje em `job/tipos_de_desafio.py`.

⚠️ **E ela precisou de uma correcao que so a medicao revelou:** a clausula
*"o adversario nao fechou caixa"* ja e verdade **antes de ele jogar**, e o juiz
para no primeiro lance em que as clausulas valem — o desafio saia com solucao de
**1 meio-lance**, com qualquer numero no enunciado. A cura e uma clausula de
`lances_do_jogador >= n` na conjuncao, e ela nao custa vocabulario novo.

═══════════════════════════════════════════════════════════════════════════
✅ NENHUM FEITO NOVO, E E ISSO QUE TORNA ESTES TRES BARATOS
═══════════════════════════════════════════════════════════════════════════

As quatro medidas que eles consultam — `caixas_fechadas`, `caixas_do_adversario`,
`lances_do_jogador` e `maior_cadeia_capturada` — ja sao produzidas pelos **dois**
medidores, o de Python e o de Dart. ⛔ Ao contrario da `0023`, esta migracao nao
toca `tb902_catalogo_feito`.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0024_tres_tipos_de_pontinhos"
down_revision: Union[str, None] = "0023_cadeia_longa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Semeia os tipos 12, 14 e 15."""
    op.execute(
        """
        INSERT INTO desafio.tb901_tipo_desafio
            (nu_tipo_desafio, co_tipo_desafio, no_tipo_desafio, co_jogo) VALUES
            (  12, 'pontinhos_troca_favoravel',    'Troca favoravel',    'pontinhos'),
            (  14, 'pontinhos_economia_de_lances', 'Economia de lances', 'pontinhos'),
            (  15, 'pontinhos_paciencia',          'Paciencia',          'pontinhos')
        """
    )


def downgrade() -> None:
    """Tira as tres linhas.

    ⚠️ **So para o ambiente local**, como no resto do projeto — o teste de
    migracao aditiva ignora o `downgrade()`.

    ⛔ E ele so funciona enquanto ninguem tiver publicado um desafio destes
    tipos: a `0018` pos `FOREIGN KEY` na dimensao, entao o `DELETE` falha se
    houver desafio apontando. E o comportamento certo — apagar a dimensao por
    baixo de um desafio publicado deixaria a linha dele sem significado.
    """
    op.execute(
        "DELETE FROM desafio.tb901_tipo_desafio "
        "WHERE nu_tipo_desafio IN (12, 14, 15)"
    )

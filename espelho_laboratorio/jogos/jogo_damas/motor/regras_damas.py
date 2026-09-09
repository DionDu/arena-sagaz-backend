"""Gerador de lances: dada uma posição, **todos** os lances legais.

Esta é a peça mais perigosa do projeto. As cláusulas de captura do regulamento
**não dão erro quando implementadas errado** — dão um motor que joga *quase*
certo. E como a base de finais e o treino inteiro são construídos em cima deste
arquivo, um erro aqui se espalha em silêncio e reaparece semanas depois
disfarçado de "a IA está fraca".

Leia antes: `../docs/especificacao_regras_captura_damas.md`, que é a leitura do
texto normativo feita **separadamente deste código**. Este módulo tem de
concordar com aquela especificação; o teste
`../testes/test_regras_damas.py` confronta os dois. Se discordarem, a fonte
decide — é escrituração dupla, e é a única defesa contra um erro sem sintoma.

Os seis pontos que o gerador precisa acertar
--------------------------------------------
1. **Enumerar sequências completas, não saltos.** A Lei da Maioria compara
   lances inteiros, então a unidade de decisão é o lance inteiro.
2. **Carregar o estado da captura** na recursão: quais peças já foram tomadas —
   que **continuam no tabuleiro** — e onde a peça está agora.
3. **Não podar por casa visitada**, só por peça já capturada (Casa Cruz).
4. **Ramificar em cada casa de parada da dama**, não só na primeira.
5. **Decidir a promoção no fim**, e nunca deixar a pedra passar a se mover como
   dama no meio da própria sequência.
6. **Filtrar pelo máximo no final**, quando todas as sequências já existirem.

Clareza antes de velocidade
---------------------------
Este é o motor **de referência**, em Python. Ele existe para estar certo e para
ser lido — é ele que vai conferir o gerador em Dart, que é o que roda no
aparelho e que precisa ser rápido. Onde houve escolha entre um laço legível e um
truque de bits, escolhi o laço.
"""
from __future__ import annotations

from dataclasses import dataclass

from jogos.jogo_damas.motor.tabuleiro_damas import (
    CASAS_DE_COROACAO,
    DIRECOES_DE_AVANCO,
    Cor,
    Direcao,
    Peca,
    Tabuleiro,
    cor_da_peca,
    raio,
    vizinho,
)

_DAMAS = (Peca.DAMA_BRANCA, Peca.DAMA_PRETA)


# ---------------------------------------------------------------------------
# O regulamento como parâmetro
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Regulamento:
    """As regras que mudam de uma variante de damas para outra.

    "Damas" não é um jogo, é uma família. Em vez de escrever dois geradores, o
    gerador é um só e as diferenças entram por aqui — foi a decisão de escopo
    registrada em `../../../docs/historico_decisoes.md` (2026-07-24).

    Cada campo é uma pergunta cuja resposta muda o jogo:

    Attributes:
        dama_voa: a dama percorre a diagonal inteira (brasileiras) ou anda uma
            casa só (anglo-americanas)? É a diferença que dá nome às duas
            famílias.
        pedra_captura_para_tras: a pedra pode capturar de recuo? Nas brasileiras
            sim; nas anglo-americanas ela só captura para frente.
        captura_maxima_obrigatoria: a **Lei da Maioria**. Nas brasileiras é
            obrigatório tomar o maior número de peças; nas anglo-americanas
            basta capturar — qualquer captura serve.
        desempate_por_qualidade: a **Lei da Qualidade**, que só as
            portuguesas/espanholas têm (art. 3.7.b da Federação Portuguesa de
            Damas): quando duas capturas tomam o **mesmo número** de peças, é
            obrigatória a que toma a de melhor qualidade — dama antes de pedra.
            O art. 3.7.e esclarece o que "qualidade" mede: *"the obligation
            depends on the pieces **captured** and not on the pieces doing the
            capturing"* — conta o que sai do tabuleiro, não quem captura.
        coroacao_encerra_o_lance: nas anglo-americanas, a pedra que chega à
            fileira de coroação **para ali**, coroada, mesmo que houvesse mais
            capturas. Nas brasileiras ela atravessa e continua como pedra.
        quem_comeca: brancas nas brasileiras, pretas nas anglo-americanas.
        lances_sem_progresso_para_empate: quantos lances **de cada jogador** sem
            progresso encerram a partida empatada — art. 97b nas brasileiras
            (20), regra 1.27.2 do WCDF nas anglo-americanas (**40**, o dobro).
            Era constante global até 2026-07-28, e por isso o motor aplicava a
            regra brasileira em partida anglo-americana. Ver `empates_por_historico_damas`.
        repeticoes_para_empate: quantas ocorrências da mesma posição empatam. Três
            nas duas famílias (art. 98; WCDF 1.27.1), mas fica parametrizado
            porque a *coincidência* de hoje não é garantia de amanhã — e uma
            variante nova entrando com outro número não deve exigir caça a
            constante espalhada pelo motor.
        fonte: onde conferir estas respostas. Campo obrigatório de propósito —
            regra sem fonte é lembrança, e lembrança envelhece calada.
        oficial: se este regulamento reproduz um **texto normativo** de uma
            federação. Quase todos reproduzem, e para esses o `fonte` aponta um
            arquivo de `referencias/texto/` que o teste abre.

            O `False` existe para uma coisa só, e é melhor que ele exista a que
            uma variante de casa se disfarce de oficial: a **Damas de Casa** é
            uma simplificação que *nós* definimos, para o jeito como a maioria
            das pessoas joga em casa. Marcá-la aqui garante que ela nunca seja
            apresentada ao jogador — nem a um adversário de torneio — como se
            fosse regra de federação.
    """

    identificador: str
    nome: str
    dama_voa: bool
    pedra_captura_para_tras: bool
    captura_maxima_obrigatoria: bool
    coroacao_encerra_o_lance: bool
    quem_comeca: Cor
    fonte: str
    oficial: bool = True
    desempate_por_qualidade: bool = False
    lances_sem_progresso_para_empate: int = 20
    repeticoes_para_empate: int = 3

    empates_declarados_por_posicao: bool = False
    """Se os arts. 99 e 100 entram na **base de finais** — empates que o
    regulamento declara pela posição, sem contar lance nenhum.

    Até 2026-07-29 isto não era um campo: a retrógrada perguntava
    `identificador == "brasileira"`. Funcionava enquanto só as brasileiras os
    tinham, e quebrou calado no instante em que a **Damas de Casa** entrou — ela
    tem os mesmos empates declarados e teria recebido uma base de finais sem
    eles, ou seja, uma base que declara ganhos onde a modalidade manda empatar.

    É o mesmo defeito que a auditoria de 28/07 achou nas regras de empate por
    histórico: uma decisão de regulamento escrita como constante em vez de campo.
    Perguntar pela **capacidade**, e não pelo nome, é o que impede que a próxima
    modalidade repita isto."""

    artigo_da_repeticao: str = "art. 98"
    """Como citar a regra da posição repetida no motivo do fim da partida.

    Vai para a tag `[Termination]` do PDN, que outro programa vai ler — citar o
    artigo brasileiro numa partida anglo-americana é registro errado num arquivo
    de intercâmbio. Cada regulamento declara o seu em vez de haver um `if` por
    identificador em algum canto."""

    artigo_dos_lances_sem_progresso: str = "art. 97b"
    """Idem, para a regra dos lances sem progresso."""

    lances_tres_damas_contra_uma: int | None = None
    """FMJD 8.3 — três damas **ou mais** contra uma dama solitária: empate se o
    lado forte não capturar em tantos lances. `None` desliga a regra.

    Repare que ela **não** exige a grande diagonal, ao contrário do art. 100 do
    CBJD (que dá 5 lances e está gravado na base de finais). As duas coexistem, e
    a mais apertada decide."""

    maximo_de_pecas_por_lado_para_contar: int | None = None
    """FPD 3.8.b.(1) — **quando** o relógio dos lances sem progresso começa a andar.

    Aqui mora a diferença que faltava nas portuguesas, e ela é de *gatilho*, não
    de número: os dois regulamentos dão 20 lances, mas contam a partir de momentos
    diferentes.

    | | quando o contador anda |
    |---|---|
    | art. 97b (brasileiro) | **sempre** — todo lance que não seja de pedra nem captura conta |
    | FPD 3.8.b (português) | só depois que a posição vira final: *"a maximum of four pieces on each side, with at least one of those pieces being a king on both sides"* |

    `None` (o padrão) quer dizer "sem gatilho, conta sempre", que é o brasileiro
    e o anglo-americano. Um número liga a condição de entrada, e ela é conjunta
    com `exige_dama_dos_dois_lados_para_contar`.

    ⚠️ Fora do gatilho o contador não fica só parado: ele **zera**. É o que o
    texto pede ao dizer que a contagem *"begins immediately"* quando a posição
    surge — se ela desaparecer e voltar, começa de novo do zero."""

    exige_dama_dos_dois_lados_para_contar: bool = False
    """A outra metade do gatilho da FPD 3.8.b.(1): dama dos **dois** lados.

    Separado do campo acima porque são duas perguntas independentes — um
    regulamento futuro pode exigir uma e não a outra —, e porque um `bool` com
    nome não deixa dúvida sobre qual lado precisa da dama. É *cada* lado."""

    lances_da_forcada: int | None = None
    """FPD 3.8.a — a **«Forçada»**: três damas que ocupam o Rio contra uma dama
    solitária têm 12 lances para liquidá-la. `None` desliga a regra.

    O Rio é a grande diagonal (`tabuleiro_damas.RIO`), e a definição dele **não
    está no texto** do regulamento: está numa figura. Ver o docstring daquela
    constante.

    Três coisas que o texto diz e que valem repetir aqui, porque cada uma muda o
    código:

    1. *"The capturing move is included in the count"* — o lance que captura conta
       entre os 12; não são 12 lances **mais** o da captura.
    2. Se ninguém ocupa o Rio, a contagem **ainda não começou**: *"the count of
       forced-win moves shall only begin after the River has been occupied (the
       move that occupies the River is not counted among the 12 moves)"*.
    3. FPD 3.8.b.(4) — *"The 20-move rule does not apply to the Forçada"*. Na
       configuração de três damas contra uma, o relógio dos 20 lances **não
       corre**; quem decide é este.

    ⚠️ **Duas leituras que o texto não fecha, e que o código assume explicitamente:**

    - **"12 moves" são 12 lances do lado forte**, não 12 de cada lado. O art.
       3.8.b diz *"20 moves for each color"* quando quer dizer de cada lado; aqui
       não diz, e a leitura sem o "each color" é a mais apertada contra quem tem
       de ganhar — que é o propósito declarado do artigo.
    - **Começada, a contagem não reinicia** se o lado forte sair do Rio. O texto
       só descreve o início. Reiniciar seria uma brecha grosseira: bastaria sair
       e voltar ao Rio para ganhar mais 12 lances, indefinidamente."""

    artigo_da_forcada: str = "FPD 3.8.a"
    """Como citar a Forçada no motivo do fim da partida, para o PDN."""

    damas_da_forcada: int = 3
    """Quantas damas o lado forte tem na Forçada. É 3 no texto português, e fica
    parametrizado pela mesma razão que `repeticoes_para_empate`: o número de hoje
    não é promessa de amanhã, e caçá-lo depois dentro do módulo de empates é pior
    do que declará-lo agora."""

    lances_equilibrio_parado: tuple[tuple[int, int, int], ...] = ()
    """FMJD 8.5 — os dois lados com damas e o equilíbrio sem mudar (sem captura e
    sem promoção): empate depois de tantos lances.

    Cada item é `(mínimo de peças, máximo de peças, lances)`. O texto dá duas
    faixas: 30 lances em finais de 4–5 peças, 60 em finais de 6–7.

    ⚠️ O contador desta regra **não é o do art. 97b**. Lá, mover uma pedra zera;
    aqui, não — o que zera é captura ou promoção ("there was no capture and man
    did not become a king"). São dois relógios diferentes correndo juntos, e
    confundi-los faria a regra disparar cedo demais."""

    @property
    def meios_lances_sem_progresso_para_empate(self) -> int:
        """O mesmo limite em **meios-lances**, que é como a busca desce a árvore.

        A conversão fica aqui, num lugar só, porque o erro de fator 2 é fácil de
        cometer e difícil de notar: ele faz a regra disparar com metade ou o
        dobro dos lances, e a partida continua "parecendo" normal.
        """
        return 2 * self.lances_sem_progresso_para_empate


BRASILEIRAS = Regulamento(
    identificador="brasileira",
    nome="damas brasileiras",
    dama_voa=True,
    pedra_captura_para_tras=True,
    captura_maxima_obrigatoria=True,
    coroacao_encerra_o_lance=False,
    quem_comeca=Cor.BRANCAS,
    # Art. 97b: 20 lances de cada jogador só com movimentos de dama, sem captura
    # e sem deslocamento de pedra. Art. 98: a mesma posição pela terceira vez.
    lances_sem_progresso_para_empate=20,
    repeticoes_para_empate=3,
    # As duas regras da FMJD-64 que o CBJD **não contradiz** — apenas omite, por
    # o extrato que temos ter só 6 páginas. Decisão do dono em 2026-07-28.
    lances_tres_damas_contra_uma=15,          # FMJD 8.3
    lances_equilibrio_parado=((4, 5, 30), (6, 7, 60)),   # FMJD 8.5
    # Arts. 99 e 100: empates que o regulamento declara pela POSIÇÃO. Eles não
    # entram na busca — moram dentro da base de finais, ver `tablebase/`.
    empates_declarados_por_posicao=True,
    artigo_da_repeticao="art. 98",
    artigo_dos_lances_sem_progresso="art. 97b",
    fonte=(
        "Regras Oficiais de Jogo de Damas, CBD/FMJD, Anexo I — "
        "../referencias/texto/12_regras_oficiais_cbjd.md; e as regras 8.3 e 8.5 "
        "de ../referencias/texto/14_regras_fmjd64_classicas.md (FMJD-64), que o "
        "CBJD não contradiz"
    ),
)
"""O regulamento brasileiro, conferido contra **dois** textos normativos.

Onde os dois se contradizem — o art. 97b do CBJD diz 20 lances, o art. 8.4 da
FMJD diz 15 — vale o CBJD, que é a norma de território brasileiro. Onde a FMJD
acrescenta sem contradizer (8.3 e 8.5), a regra entra. Decisão registrada em
`docs/auditoria_cobertura_do_regulamento.md`."""

ANGLO_AMERICANAS = Regulamento(
    identificador="anglo",
    nome="damas anglo-americanas (checkers)",
    dama_voa=False,                        # WCDF 1.17 — a dama anda UMA casa
    pedra_captura_para_tras=False,         # WCDF 1.18 e 1.25
    captura_maxima_obrigatoria=False,      # WCDF 1.20 — sem Lei da Maioria
    coroacao_encerra_o_lance=True,         # WCDF 1.19
    quem_comeca=Cor.PRETAS,                # WCDF 1.14 — as vermelhas, que são as escuras
    # ⚠️ WCDF 1.27.2: **40** lances de cada jogador, o DOBRO do art. 97b
    # brasileiro. Até 2026-07-28 este número não existia — as regras de empate
    # eram constantes globais com o valor brasileiro, e o motor encerrava partida
    # anglo-americana na metade do tempo que o regulamento manda.
    lances_sem_progresso_para_empate=40,
    repeticoes_para_empate=3,              # WCDF 1.27.1
    # O WCDF não tem equivalente aos arts. 99/100 — não há empate declarado por
    # posição, e a base de finais anglo-americana é construída sem eles.
    empates_declarados_por_posicao=False,
    artigo_da_repeticao="WCDF 1.27.1",
    artigo_dos_lances_sem_progresso="WCDF 1.27.2",
    fonte=(
        "Revised Rules of Draughts, World Checkers & Draughts Federation — "
        "../referencias/texto/13_regras_wcdf_anglo.md (texto normativo no "
        "repositório, consultado em 2026-07-28 na publicação oficial da American "
        "Checker Federation, que remete a ela as regras de jogo)"
    ),
)
"""O regulamento anglo-americano, conferido contra o texto do WCDF em 2026-07-28.

Antes dessa data ele era "codificado a partir das regras correntes da ACF" e
carregava um aviso de que não tinha fonte. Os quatro parâmetros de jogo estavam
certos — o `perft` contra gabarito publicado já sugeria isso —, mas as regras de
**empate** estavam erradas, e nenhum `perft` pegaria: elas não mudam a contagem
de lances legais."""

PORTUGUESAS = Regulamento(
    identificador="portuguesa",
    nome="damas portuguesas (espanholas)",
    dama_voa=True,                         # FPD 3.2.a — "as many free squares as it wishes"
    pedra_captura_para_tras=False,         # FPD 3.4.a — "directly in front of it"
    captura_maxima_obrigatoria=True,       # FPD 3.7.a — regra da quantidade
    coroacao_encerra_o_lance=True,         # FPD 3.1.e — "the man's move ends upon reaching the back rank"
    desempate_por_qualidade=True,          # FPD 3.7.b — regra da qualidade, só aqui
    quem_comeca=Cor.BRANCAS,
    lances_sem_progresso_para_empate=20,   # FPD 3.8.b — o número bate com o brasileiro…
    # …mas o GATILHO não: lá conta sempre, aqui só depois que a posição vira um
    # final de no máximo 4 peças por lado com dama dos dois lados (3.8.b.1).
    maximo_de_pecas_por_lado_para_contar=4,
    exige_dama_dos_dois_lados_para_contar=True,
    lances_da_forcada=12,                  # FPD 3.8.a — três damas no Rio × uma dama
    damas_da_forcada=3,
    artigo_da_forcada="FPD 3.8.a",
    repeticoes_para_empate=3,              # FPD 5.3
    # Os arts. 99/100 do CBJD não têm equivalente aqui. O que a FPD tem no lugar é
    # a Forçada, que **não** é empate declarado por posição: ela é um relógio, e
    # por isso mora no histórico da partida, não na base de finais.
    empates_declarados_por_posicao=False,
    artigo_da_repeticao="FPD 5.3",
    artigo_dos_lances_sem_progresso="FPD 3.8.b",
    fonte=(
        "Rules of Portuguese Draughts (Spanish Draughts), Federação Portuguesa "
        "de Damas, em vigor desde 01/04/2026 — "
        "../referencias/texto/16_regras_portuguesas_espanholas_fmjd.md"
    ),
)
"""A **terceira família**, e ela não é uma variação de nenhuma das outras duas.

Foi tratada como "igual às brasileiras" pela decisão de escopo de 2026-07-24, e
isso se provou errado quando o texto normativo chegou (2026-07-28):

| | dama voa | pedra de recuo | coroação encerra | maioria | qualidade |
|---|---|---|---|---|---|
| brasileiras | ✔ | ✔ | ✘ | ✔ | ✘ |
| anglo-americanas | ✘ | ✘ | ✔ | ✘ | ✘ |
| **portuguesas** | ✔ | ✘ | ✔ | ✔ | **✔** |

**Quem começa não está escrito em nenhum artigo** — foi deduzido das aberturas
balotadas do Apêndice A, que é evidência forte: a primeira delas é `9-13, 21-17`,
e na numeração portuguesa (art. 2.2, que começa pelo lado das brancas) as casas
baixas são das brancas. Logo, brancas jogam primeiro.

⚠️ **Duas coisas deste regulamento que o motor ainda NÃO implementa**, e é melhor
dizer do que deixar parecer coberto:

1. **A condição de entrada da regra dos 20 lances** (3.8.b) é diferente da
   brasileira. Lá, conta-se enquanto só se movem damas; aqui, a contagem começa
   quando a posição tem **no máximo 4 peças de cada lado, com pelo menos uma dama
   de cada lado**, e reinicia se o final mudar (movimento de pedra ou captura).
   O número 20 bate; o gatilho, não.
2. **A "Forçada"** (3.8.a): 3 damas dominando o "Rio" contra 1 dama têm 12 lances
   para concluir. Depende do conceito de "Rio", que é nomenclatura própria deste
   regulamento e ainda não existe no código.

⚠️ **A numeração das casas do documento é o INVERSO da nossa** (art. 2.2: começa
pelo lado das brancas, que coroam em 29–32). Para transcrever posição ou abertura
de lá para cá: `casa_nossa = 33 - casa_do_documento`. Somada à grande diagonal,
que lá fica à direita (1.2) e aqui à esquerda, é fonte garantida de erro
silencioso.
"""

DAMAS_DE_CASA = Regulamento(
    identificador="casa",
    nome="damas de casa",
    # Tudo igual às brasileiras…
    dama_voa=True,
    pedra_captura_para_tras=True,
    coroacao_encerra_o_lance=False,
    quem_comeca=Cor.BRANCAS,
    lances_sem_progresso_para_empate=20,
    repeticoes_para_empate=3,
    lances_tres_damas_contra_uma=15,
    lances_equilibrio_parado=((4, 5, 30), (6, 7, 60)),
    empates_declarados_por_posicao=True,
    artigo_da_repeticao="art. 98",
    artigo_dos_lances_sem_progresso="art. 97b",
    # …menos ISTO, que é a variante inteira: sem a Lei da Maioria.
    captura_maxima_obrigatoria=False,
    oficial=False,
    fonte=(
        "NÃO É REGULAMENTO DE FEDERAÇÃO. É a variante simplificada definida por "
        "este projeto em 2026-07-29, por decisão do dono: as damas brasileiras "
        "sem a Lei da Maioria, que é como a maior parte das pessoas joga em casa "
        "no Brasil. Ver docs/modalidades_de_damas.md e o diário do plano."
    ),
)
"""**A quarta modalidade, e a única que não vem de federação nenhuma.**

Comer continua obrigatório — quem pode comer, come. O que sai é a obrigação de
comer o **maior número**: havendo duas capturas possíveis, o jogador escolhe.

Por que ela existe
------------------
O público principal do app não são damistas, são pessoas comuns *(diretriz do
dono, 2026-07-28)*. E muita gente no Brasil aprendeu damas em casa sem a Lei da
Maioria: come-se o que se quiser, e ninguém confere se havia captura maior.

Para essa pessoa, escolher "Damas Brasileiras" e ter o lance travado por uma
regra que ela não sabe que existe é **indistinguível de bug**. A saída não é
afrouxar o regulamento oficial — é oferecer, ao lado dele, a variante que ela já
conhece, com nome honesto.

O que muda no motor: **um campo**. Tudo o mais é idêntico às brasileiras, e isso
é de propósito — quanto menos diferenças, mais fácil explicar ao jogador o que
ele está escolhendo, e mais fácil provar por teste que a diferença é só essa.

⚠️ **Não medir o Sagaz aqui sem pensar.** A Lei da Maioria é o que torna as
brasileiras táticas; sem ela a árvore de busca é mais larga (mais capturas
legais em cada nó) e a avaliação treinada nas brasileiras não vale
automaticamente. Se um dia esta modalidade for oferecer 4 níveis, a prova é
medida nela, não herdada.
"""

REGULAMENTOS: dict[str, Regulamento] = {
    regulamento.identificador: regulamento
    for regulamento in (BRASILEIRAS, ANGLO_AMERICANAS, PORTUGUESAS, DAMAS_DE_CASA)
}
"""Os regulamentos implementados, por identificador.

| | dama voa | pedra de recuo | coroação encerra | maioria | qualidade | oficial |
|---|---|---|---|---|---|---|
| brasileiras | ✔ | ✔ | ✘ | ✔ | ✘ | ✔ |
| anglo-americanas | ✘ | ✘ | ✔ | ✘ | ✘ | ✔ |
| portuguesas/espanholas | ✔ | ✘ | ✔ | ✔ | **✔** | ✔ |
| damas de casa | ✔ | ✔ | ✘ | ✘ | ✘ | **✘** |

As três primeiras reproduzem texto normativo de federação, e o `fonte` de cada
uma aponta um arquivo de `referencias/texto/` que o teste abre. A quarta é nossa,
e o campo `oficial=False` existe para que ela nunca se disfarce de regra de
federação — ver `DAMAS_DE_CASA`.

**Qual idioma recebe qual.** `pt-BR` recebe as brasileiras (e a de casa como
alternativa); `es` recebe as **portuguesas/espanholas**, nunca as brasileiras —
são famílias diferentes, e servir o jogo errado é pior que oferecer um idioma a
menos. `en` recebe as anglo-americanas.
"""


# ---------------------------------------------------------------------------
# O lance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Lance:
    """Um lance legal: por onde a peça andou e o que ela tirou do tabuleiro.

    Guarda o **caminho inteiro**, e não só origem e destino, por duas razões
    práticas: numa captura de dama o destino não é determinado pela peça tomada
    (RESUMO 17), e sem o caminho não dá para desenhar a sequência nem para
    detectar a Casa Cruz.

    Attributes:
        caminho: as casas pisadas, da origem ao destino. Um lance simples tem
            duas casas; uma captura de N peças tem N+1. **Pode repetir casa** —
            é a Casa Cruz, e é legal.
        capturadas: as casas de onde saíram as peças tomadas, na ordem. Vazio
            num lance simples.
        vira_dama: se a peça termina promovida. Só é verdadeiro quando o lance
            **termina** na fileira de coroação — atravessar não promove.
    """

    caminho: tuple[int, ...]
    capturadas: tuple[int, ...] = ()
    vira_dama: bool = False

    @property
    def origem(self) -> int:
        return self.caminho[0]

    @property
    def destino(self) -> int:
        return self.caminho[-1]

    @property
    def e_captura(self) -> bool:
        return bool(self.capturadas)

    @property
    def quantas_capturas(self) -> int:
        """O número que a Lei da Maioria compara."""
        return len(self.capturadas)

    def __str__(self) -> str:
        """Notação legível: ``23-18`` para lance simples, ``30x23x16`` para captura.

        O traço para lance simples e o ``x`` para captura são a convenção do PDN,
        o formato padrão de partida de damas. A exportação PDN de verdade fica
        para a etapa 5; aqui o objetivo é log e mensagem de teste legíveis.
        """
        separador = "x" if self.e_captura else "-"
        return separador.join(str(casa) for casa in self.caminho)


# ---------------------------------------------------------------------------
# Geração
# ---------------------------------------------------------------------------


def _direcoes_de_captura(
    regulamento: Regulamento, cor: Cor, e_dama: bool
) -> tuple[Direcao, ...]:
    """Para que lados esta peça pode capturar.

    A dama sempre captura nos quatro. A pedra depende do regulamento: nas
    brasileiras ela captura de recuo ("A captura pode ser realizada tanto pra
    frente como pra trás"), nas anglo-americanas não.
    """
    if e_dama or regulamento.pedra_captura_para_tras:
        return tuple(Direcao)
    return DIRECOES_DE_AVANCO[cor]


def _saltos_possiveis(
    trabalho: Tabuleiro,
    regulamento: Regulamento,
    cor: Cor,
    posicao: int,
    e_dama: bool,
    capturadas: tuple[int, ...],
    condenadas_bloqueiam: bool = True,
) -> list[tuple[int, int]]:
    """Os saltos de captura disponíveis agora, como pares ``(vítima, destino)``.

    O tabuleiro `trabalho` já vem com a peça que se move **retirada da origem** —
    é isso que libera a casa de origem para ser repisada (Casa Cruz). As peças
    já capturadas **continuam nele**, e é isso que faz o Tema Turco funcionar
    sem nenhum código especial: elas simplesmente aparecem como casa ocupada.

    Args:
        condenadas_bloqueiam: **interruptor de diagnóstico, e só isso.** Com o
            padrão ``True`` vale o art. 15, que é a regra. Com ``False`` as peças
            já tomadas neste lance contam como **casa vazia**, produzindo os
            lances que existiriam se elas saíssem do tabuleiro na hora do salto.

            Ninguém joga com ele desligado: quem o usa é
            `explicacao_de_recusa_damas`, para responder ao jogador *"este
            caminho só está fechado por causa da peça que você acabou de comer"*.
            Comparar as duas gerações é a mesma técnica que aquele módulo já usa
            para descobrir a Lei da Maioria — deduzir observando o gerador, nunca
            reescrever a regra.
    """
    saltos: list[tuple[int, int]] = []

    def vazia(casa: int) -> bool:
        """Esta casa está livre para passar ou pousar?

        Com o art. 15 ligado (o normal), é a leitura crua do tabuleiro. Com ele
        desligado, uma condenada também conta como livre — que é justamente a
        diferença que a explicação quer medir.
        """
        if trabalho.ler(casa) is Peca.VAZIA:
            return True
        return not condenadas_bloqueiam and casa in capturadas

    for direcao in _direcoes_de_captura(regulamento, cor, e_dama):
        if e_dama and regulamento.dama_voa:
            # --- dama voadora: desliza até achar a primeira peça -------------
            diagonal = raio(posicao, direcao)
            indice = 0
            while indice < len(diagonal) and vazia(diagonal[indice]):
                indice += 1
            if indice == len(diagonal):
                continue                       # só casa vazia até a borda

            vitima = diagonal[indice]
            if cor_da_peca(trabalho.ler(vitima)) == cor:
                continue                       # peça nossa: a diagonal fecha aqui
            if vitima in capturadas:
                # Já tomada neste lance. Não pode ser tomada de novo E continua
                # ocupando a casa — logo, fecha a diagonal. É o Tema Turco.
                # (Com o interruptor desligado nem se chega aqui: `vazia` já a
                # terá atravessado como se a casa estivesse livre.)
                continue

            # Todas as casas livres depois da vítima são paradas possíveis.
            pouso = indice + 1
            while pouso < len(diagonal) and vazia(diagonal[pouso]):
                saltos.append((vitima, diagonal[pouso]))
                pouso += 1
        else:
            # --- pedra, ou dama curta: salto de exatamente duas casas --------
            vitima = vizinho(posicao, direcao)
            if vitima is None or vazia(vitima):
                continue
            if cor_da_peca(trabalho.ler(vitima)) == cor or vitima in capturadas:
                continue
            destino = vizinho(vitima, direcao)
            if destino is None or not vazia(destino):
                continue
            saltos.append((vitima, destino))

    return saltos


def _explorar_capturas(
    trabalho: Tabuleiro,
    regulamento: Regulamento,
    cor: Cor,
    posicao: int,
    e_dama: bool,
    caminho: tuple[int, ...],
    capturadas: tuple[int, ...],
    encontrados: list[Lance],
    condenadas_bloqueiam: bool = True,
) -> None:
    """Percorre em profundidade todas as continuações da captura.

    Só emite um `Lance` quando a sequência **não pode mais ser estendida** —
    nunca um prefixo. Parar no meio de uma cadeia não é um lance legal em
    nenhuma das duas famílias; o que muda entre elas é apenas se, entre as
    cadeias completas, é obrigatório escolher a maior.

    O parâmetro `e_dama` **não muda durante a recursão**. É a tradução literal do
    RESUMO 13: a pedra que atravessa a casa de coroação continua pedra até o fim
    do lance, e portanto continua saltando como pedra.
    """
    # Nas anglo-americanas a pedra que pisa a coroação para ali, coroada, mesmo
    # havendo mais capturas. Nas brasileiras esta condição é falsa e a recursão
    # simplesmente segue.
    if (
        regulamento.coroacao_encerra_o_lance
        and not e_dama
        and len(caminho) > 1
        and posicao in CASAS_DE_COROACAO[cor]
    ):
        encontrados.append(Lance(caminho, capturadas, vira_dama=True))
        return

    saltos = _saltos_possiveis(
        trabalho, regulamento, cor, posicao, e_dama, capturadas,
        condenadas_bloqueiam,
    )

    if not saltos:
        if len(caminho) > 1:      # houve pelo menos um salto: é um lance
            encontrados.append(
                Lance(
                    caminho,
                    capturadas,
                    # A promoção olha ONDE O LANCE TERMINOU, e só aqui.
                    vira_dama=not e_dama and posicao in CASAS_DE_COROACAO[cor],
                )
            )
        return

    for vitima, destino in saltos:
        _explorar_capturas(
            trabalho, regulamento, cor, destino, e_dama,
            caminho + (destino,),
            capturadas + (vitima,),
            encontrados,
            condenadas_bloqueiam,
        )


def _gerar_capturas(
    tabuleiro: Tabuleiro,
    regulamento: Regulamento,
    condenadas_bloqueiam: bool = True,
) -> list[Lance]:
    """Todas as sequências de captura completas de quem tem a vez, sem filtrar.

    Args:
        condenadas_bloqueiam: ver `_saltos_possiveis`. **Deixe no padrão** —
            desligá-lo produz lances que o regulamento não permite, e serve
            apenas para a explicação de recusa descobrir o que o art. 15 barrou.
    """
    cor = tabuleiro.vez
    encontrados: list[Lance] = []

    for origem in tabuleiro.casas_de(cor):
        peca = tabuleiro.ler(origem)
        # A peça sai do tabuleiro de trabalho: a casa de origem fica livre para o
        # resto do lance, que é o que permite uma cadeia voltar a pisá-la.
        trabalho = tabuleiro.copia()
        trabalho.escrever(origem, Peca.VAZIA)
        _explorar_capturas(
            trabalho, regulamento, cor, origem, peca in _DAMAS,
            (origem,), (), encontrados, condenadas_bloqueiam,
        )

    return encontrados


def _damas_capturadas(tabuleiro: Tabuleiro, lance: Lance) -> int:
    """Quantas das peças tomadas por este lance são **damas**.

    É o que a Lei da Qualidade mede (FPD 3.7.b). Consulta o tabuleiro **de
    antes** do lance, e isso é obrigatório: durante a geração as peças capturadas
    continuam no tabuleiro (Tema Turco), então é aqui que ainda dá para perguntar
    o que cada uma era.

    O art. 3.7.e diz explicitamente o que a regra mede: *"the obligation depends
    on the pieces **captured** and not on the pieces doing the capturing"* — a
    qualidade é do que sai do tabuleiro, não de quem toma.
    """
    return sum(1 for casa in lance.capturadas if tabuleiro.ler(casa) in _DAMAS)


def _gerar_lances_simples(tabuleiro: Tabuleiro, regulamento: Regulamento) -> list[Lance]:
    """Os lances sem captura. Só valem quando não há captura alguma disponível."""
    cor = tabuleiro.vez
    lances: list[Lance] = []

    for origem in tabuleiro.casas_de(cor):
        peca = tabuleiro.ler(origem)
        e_dama = peca in _DAMAS
        # A pedra "anda só para frente"; a dama anda para os quatro lados.
        direcoes = tuple(Direcao) if e_dama else DIRECOES_DE_AVANCO[cor]

        for direcao in direcoes:
            if e_dama and regulamento.dama_voa:
                # "quantas casas quiser dentro da mesma diagonal", até esbarrar.
                for destino in raio(origem, direcao):
                    if tabuleiro.ler(destino) is not Peca.VAZIA:
                        break
                    lances.append(Lance((origem, destino)))
            else:
                destino = vizinho(origem, direcao)
                if destino is not None and tabuleiro.ler(destino) is Peca.VAZIA:
                    lances.append(
                        Lance(
                            (origem, destino),
                            vira_dama=not e_dama and destino in CASAS_DE_COROACAO[cor],
                        )
                    )

    return lances


def gerar_lances(
    tabuleiro: Tabuleiro, regulamento: Regulamento = BRASILEIRAS
) -> tuple[Lance, ...]:
    """Todos os lances legais de quem tem a vez.

    A ordem das três decisões é a do regulamento, e ela importa:

    1. **Se há captura, é obrigatório capturar** ("A captura no jogo de damas é
       obrigatória. Não existe o sopro"). Lance simples nem chega a ser gerado.
    2. Entre as capturas, aplica-se a **Lei da Maioria** — mas só onde ela vale.
       Nas anglo-americanas todas as cadeias completas são legais.
    2b. E, só nas portuguesas/espanholas, a **Lei da Qualidade** desempata o que
       sobrou: entre capturas de mesmo número, obriga a que toma mais damas
       (FPD 3.7.b). A ordem entre 2 e 2b é a do regulamento e **não é
       comutativa**: quantidade primeiro, qualidade só como desempate. Inverter
       faria o motor preferir tomar uma dama a tomar três pedras, o que é lance
       ilegal ali.
    3. Sem captura nenhuma, valem os lances simples.

    Devolve tupla vazia quando não há lance legal. Isso **não** é um erro: é
    derrota de quem tem a vez, porque o objetivo do jogo é "imobilizar ou
    capturar todas as peças do adversário" — ficar sem lance perde igual a ficar
    sem peça.
    """
    capturas = _gerar_capturas(tabuleiro, regulamento)

    if capturas:
        if regulamento.captura_maxima_obrigatoria:
            maximo = max(lance.quantas_capturas for lance in capturas)
            capturas = [c for c in capturas if c.quantas_capturas == maximo]

            # A qualidade entra DEPOIS, e só desempata o que a quantidade deixou.
            if regulamento.desempate_por_qualidade:
                melhor = max(_damas_capturadas(tabuleiro, c) for c in capturas)
                capturas = [
                    c for c in capturas
                    if _damas_capturadas(tabuleiro, c) == melhor
                ]
        return tuple(capturas)

    return tuple(_gerar_lances_simples(tabuleiro, regulamento))


# ---------------------------------------------------------------------------
# Aplicar um lance
# ---------------------------------------------------------------------------


def aplicar_lance(tabuleiro: Tabuleiro, lance: Lance) -> Tabuleiro:
    """Devolve a posição **nova** resultante do lance, sem alterar a original.

    Aqui, sim, as peças capturadas saem do tabuleiro — todas de uma vez, ao fim
    do lance, que é exatamente o que o Tema Turco manda. Durante a geração elas
    ficaram; é só agora que somem.

    Devolve cópia em vez de mexer no lugar por clareza. O motor de busca em Dart
    vai precisar do *make/unmake* no mesmo objeto para ter desempenho — mas este
    é o motor de referência, e aqui a prioridade é não errar.
    """
    novo = tabuleiro.copia()
    peca = novo.ler(lance.origem)

    novo.escrever(lance.origem, Peca.VAZIA)
    for casa in lance.capturadas:
        novo.escrever(casa, Peca.VAZIA)

    if lance.vira_dama:
        peca = Peca.DAMA_BRANCA if tabuleiro.vez is Cor.BRANCAS else Peca.DAMA_PRETA
    novo.escrever(lance.destino, peca)

    novo.vez = Cor.PRETAS if tabuleiro.vez is Cor.BRANCAS else Cor.BRANCAS
    return novo


def contar_posicoes(
    tabuleiro: Tabuleiro, profundidade: int, regulamento: Regulamento = BRASILEIRAS
) -> int:
    """`perft`: quantas posições distintas existem até certa profundidade.

    Conta as **folhas** da árvore de lances legais. É o teste que prova que o
    gerador está certo — números para damas são publicados por terceiros, então
    bater com eles é conferência independente, não auto-referência.

    Cuidado ao comparar: `perft` só é comparável entre implementações que contam
    a mesma coisa. Aqui conta-se **folhas na profundidade pedida**, e uma posição
    sem lance legal contribui com zero (a partida acabou ali).

    Esta versão em Python é para **conferir**, não para medir velocidade — a
    medição da etapa 3 é em Dart, num aparelho de verdade.
    """
    if profundidade == 0:
        return 1

    lances = gerar_lances(tabuleiro, regulamento)
    if profundidade == 1:
        return len(lances)

    return sum(
        contar_posicoes(aplicar_lance(tabuleiro, lance), profundidade - 1, regulamento)
        for lance in lances
    )

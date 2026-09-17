"""O QUE O APLICATIVO BAIXA — a resposta de `/v1/desafios/*` (T042).

Espelha `specs/009-desafio-do-dia/contracts/desafio-publicado.md`.

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTE MODELO NAO E A LINHA DO BANCO, E A DIFERENCA E DE SEGURANCA
═══════════════════════════════════════════════════════════════════════════

`modelos_producao.Desafio` e a linha como ela vive em `tb001_desafio` — e ela
carrega `js_solucao`, o **gabarito**. ⛔ Ele **nunca** viaja antes de a pessoa
resolver (RF-DES-076): mandar a linha inteira entregaria o spoiler junto com o
enunciado, e nenhum aviso na tela consertaria isso.

Por isso a resposta e um modelo **proprio**, com os campos escritos um a um.
⛔ Nao troque isto por `Desafio.model_dump()` com uma lista de exclusao: excluir
e uma lista que envelhece calada, e a coluna nova do ano que vem entraria na
resposta sozinha. Incluir e uma lista que, quando envelhece, **falta** um campo —
e faltar da erro na hora, no aplicativo, em teste.

═══════════════════════════════════════════════════════════════════════════
O QUE MAIS FICA DE FORA, E POR QUE (a tabela do contrato)
═══════════════════════════════════════════════════════════════════════════

| ausente | por que |
|---|---|
| a **solucao** | o spoiler de graca (RF-DES-076); chega so em D+1 |
| a **dica** | e poder calculado **no aparelho** (RF-DES-054), nao conteudo publicado |
| os **lances do adversario** | ⛔ publicá-los restringiria o catalogo a finais (RF-DES-200). Quem joga e o motor do aparelho, e a **semente** e que o torna igual para todo mundo |
| a **frase** do objetivo montada | vai a **chave** e os valores, para o aplicativo renderizar no idioma da pessoa (RF-DES-176) |

═══════════════════════════════════════════════════════════════════════════
⚠️ CAMPO SO SE ACRESCENTA — NUNCA SE REMOVE NEM SE RENOMEIA
═══════════════════════════════════════════════════════════════════════════

Varias versoes do aplicativo convivem em campo lendo esta mesma resposta, e uma
delas so sai de circulacao com o force-update. Renomear um campo quebra as que
ja estao instaladas; acrescentar, nao — o cliente e obrigado a ignorar o que nao
conhece (diretriz de versionamento da API).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

#: A unica forma de verificacao que existe na v1 (RF-DES-191).
#:
#: ⚠️ **Ela viaja como campo, e nao fica implicita**, e essa e a 3a das cinco
#: conferencias de compatibilidade do contrato: o aplicativo confere se conhece a
#: forma **antes** de montar qualquer widget. Uma forma nova no futuro faria as
#: versoes antigas caírem na tela de atualizar, em vez de tentarem julgar com uma
#: regra que nao entendem.
#:
#: ⚠️ Ela nao e coluna do banco: `js_chegada` com `versao: 1` **e** esta forma.
#: Uma coluna a mais poderia discordar do conteudo do JSON ao lado dela.
FORMA_VERIFICACAO_V1 = "clausulas"

#: O nome da colecao a que este desafio pertence.
#:
#: ⚠️ **O desafio e transversal ao hub; o Desafio do Dia e a primeira colecao**
#: (determinação do dono, 04/09/2026). O campo existe desde ja para que o dia em
#: que um torneio aparecer nao exija versao nova do aplicativo so para dizer de
#: onde aquele desafio veio.
COLECAO_DESAFIO_DO_DIA = "desafio_do_dia"


class ObjetivoPublicado(BaseModel):
    """O enunciado, como **chave de i18n** e valores.

    ⛔ **Nunca a frase pronta** (RF-DES-176): ela viajaria num idioma so, e quem
    baixou o aplicativo em espanhol veria o desafio em portugues. E ⛔ nunca uma
    frase montada por concatenacao no aplicativo — a ordem das palavras muda
    entre idiomas.

    ⚠️ **A chave e a unica razao real de publicar versao nova** (exercicio §8):
    a **regra** e dado (variar `3 → 5` pecas reusa a chave e nao publica nada); o
    **texto** e codigo. Chave desconhecida cai na tela de atualizar.
    """

    chave: str
    valores: dict[str, Any] = Field(default_factory=dict)


class MedidaDeSaidaPublicada(BaseModel):
    """Uma linha de `desafio.tb003_feito_desafio`: o que este desafio pontua.

    ⚠️ **Sao elas que fecham a 4a parcela de `Q` no aparelho** (RF-DES-173): o
    merito vale 0,25, e cada uma tem um peso **relativo dentro desses 0,25** — um
    `0,600` vira `0,150` na conta final. Sem esta lista, o aplicativo mede
    tentativas, tempo e dica sozinho, e o merito fica sem regua.

    ⛔ **A DIRECAO NAO VEM AQUI, de proposito.** Ela ja esta declarada nos dois
    lados, em `tb902_catalogo_feito.co_direcao` e em
    `lib/core/feitos/catalogo_feitos.dart`, e manda-la junto seria escreve-la uma
    segunda vez — no dia em que as duas discordassem ninguem perceberia, porque
    uma parcela na direcao errada **nao da erro**: so paga mais a quem jogou pior.

    ⚠️ **Nem o `nu_feito`**: o identificador numerico e da dimensao do banco, e
    o aplicativo conhece as medidas pela **chave**. Publicar o numero criaria uma
    segunda identidade para a mesma coisa.
    """

    #: A chave no catalogo de feitos. ⚠️ Chave desconhecida do aplicativo e dado
    #: invalido, e nao campo novo a tolerar (RF-DES-033).
    chave: str

    #: O peso **relativo dentro do merito**, de 0 a 1. Os de um desafio somam
    #: `1,000` — conferido na geracao por `job/medidas_de_saida.conferir`.
    peso: float = Field(ge=0.0, le=1.0)

    #: Como a medida crua vira um numero entre 0 e 1.
    #:
    #: ⚠️ `nenhuma` e a medida **exibida e nao pontuada** (peso zero): ela
    #: aparece no Raio-X sem mexer na nota.
    normalizacao: Literal["faixa", "fracao", "nenhuma"]

    #: Os limites da `faixa`; `null` nas outras. ⚠️ O maximo costuma ser o
    #: **proprio alvo do desafio**, e nao o total do tabuleiro: fechar quatro
    #: caixas quando o pedido eram quatro e nota cheia.
    minimo: Optional[float] = None
    maximo: Optional[float] = None

    #: A chave da medida que serve de denominador na `fracao`; `null` nas outras.
    #:
    #: ⚠️ **O denominador e OUTRA medida da mesma partida**, e por isso nao e um
    #: numero do desafio: ele muda a cada resolucao.
    sobre: Optional[str] = None


class DesafioPublicado(BaseModel):
    """Um desafio como o aplicativo o recebe.

    ⚠️ **`encerra_em` e `agora_no_servidor` chegam JUNTOS, e sao dois de
    proposito** (RF-DES-008). O aplicativo guarda a **diferenca** contra um
    relogio monotonico (`Stopwatch`) e conta a partir dela — o relogio de parede
    do aparelho nao entra na conta, porque ele pode estar errado, adiantado, ou
    mudar de fuso no meio da partida.

    ⚠️ **E o UTC nao aparece na tela, em lugar nenhum**: nem hora, nem nome de
    fuso, nem "encerra as 21h no seu horario". A pessoa le *"faltam 4h37"* e mais
    nada (decisao do dono, 03/09/2026).
    """

    id_desafio: UUID
    jogo: str
    modalidade: Optional[str] = None
    tipo: str
    forma_verificacao: Literal["clausulas"] = FORMA_VERIFICACAO_V1
    parametros: dict[str, Any]

    # ── A posicao ────────────────────────────────────────────────────────────
    #
    # ⚠️ **EXATAMENTE UM dos dois vem preenchido**, e `formato_posicao` diz qual.
    # O contrato escrito em 04/09/2026 so exemplificava as damas, e por isso so
    # mostrava `tabuleiro`; o Pontinhos nao cabe numa string, porque a posse de
    # uma caixa e **historico** e nao esta no tabuleiro. A precisao entrou no
    # `.md` do contrato junto com esta implementacao.
    #
    # ⛔ Os dois preenchidos ao mesmo tempo seriam duas fontes para a mesma
    # coisa — e a que estivesse errada mandaria.
    formato_posicao: Literal["sequencia_lances", "fen"]
    tabuleiro: Optional[str] = None
    posicao: Optional[dict[str, Any]] = None

    #: O tamanho do tabuleiro no Pontinhos (`null` nas damas). E o `co_variante`
    #: com o nome que o contrato lhe deu.
    tamanho: Optional[str] = None
    variante: str

    objetivo: ObjetivoPublicado

    #: Quem joga contra — entra no enunciado e escolhe o perfil do motor.
    personagem: str
    #: ⚠️ **O MESMO adversario para todo mundo.** Sem a semente publicada, dois
    #: aparelhos jogariam contra CPUs diferentes e o quadro do dia compararia
    #: partidas que nao sao a mesma.
    semente: int

    versao_minima_app: str
    versao_perfil: str
    teto_log_meios_lances: int

    # ── A regua de tempo (RF-DES-223) ────────────────────────────────────────
    #
    # ⚠️ **Sao o contra o que "rapido" e medido**, e por isso viajam: a parcela
    # `q_tempo` de `Q` e `(teto - t) / (teto - piso)`, cortada em [0, 1]
    # (`data-model.md`, "A direcao: tres parcelas correm ao contrario"), e ela
    # **fecha no aparelho** — SC-002 exige veredito e XP sem rede no caminho
    # critico. Sem os dois campos aqui, o aplicativo teria de arbitrar uma regua
    # propria, e o XP sairia errado **em silencio**.
    #
    # ⚠️ Sao **por desafio**, e nao constantes: o piso e o gabarito jogado
    # direto, o teto e onde a parcela zera. Um final de 3 lances e uma abertura
    # de 12 nao pedem a mesma pressa — uma constante faria os dois pagarem igual.
    #
    # ⛔ **Obrigatorios, sem valor padrao.** As colunas sao `NOT NULL` desde a
    # migracao `0018` e `ck007_regua_tempo` ja garante `0 < piso < teto`. Um
    # padrao aqui (30 s / 180 s) transformaria uma consulta que esquecesse as
    # colunas numa resposta **plausivel e errada**, que e o defeito que
    # RF-DES-223 manda vigiar; faltando, o erro estoura aqui, em teste.
    tempo_piso_ms: int
    tempo_teto_ms: int

    # ── As medidas de saida (RF-DES-173) ─────────────────────────────────────
    #
    # ⚠️ **A 4a parcela de `Q`**, e o segundo buraco achado do mesmo jeito que a
    # regua de tempo: escrevendo o consumidor. As linhas existem em
    # `tb003_feito_desafio` desde a migracao `0018`, o job as grava, e ate
    # 16/09/2026 nenhuma delas chegava ao aplicativo — que, sem elas, nao tem como
    # fechar o merito de `Q` no aparelho (SC-002).
    #
    # ⛔ **Pelo menos uma, e sem valor padrao.** Um desafio sem medida de saida
    # teria o Raio-X vazio e o merito sem do que ser calculado; o `conferir` do
    # job ja recusa publicar assim, e aqui a falta estoura na leitura em vez de
    # virar uma resposta plausivel com merito zero para todo mundo.
    medidas_de_saida: list[MedidaDeSaidaPublicada] = Field(min_length=1)

    encerra_em: datetime
    agora_no_servidor: datetime

    reprise: bool = False
    colecao: str = COLECAO_DESAFIO_DO_DIA

    #: O vinculo dia↔desafio. ⚠️ **E ele que o envio de resolucao carrega**
    #: (`id_desafio_dia` no contrato de envio): a resolucao conta **num evento**,
    #: e nao num desafio solto.
    id_desafio_dia: UUID


class ProximosPublicados(BaseModel):
    """O cache invisivel: os desafios dos proximos dias (RF-DES-120).

    ⚠️ **"Invisivel" e sobre EXIBIR, e nao sobre ter** (RF-DES-009). O
    pre-carregamento existe para que o metro sem rede nao tire o desafio de
    ninguem; o que o aplicativo nao pode e **exibir, prever ou sinalizar** um
    desafio futuro — nem *"amanha tem damas"*, nem contador de quantos estao
    prontos.

    ⛔ A garantia mora no aplicativo, e nao aqui: o servidor nao tem como impedir
    a tela de mostrar o que ja baixou. O que o servidor faz e **nao dar mais do
    que o necessario** — a lista e curta, e cada item so vale a partir do seu
    proprio `encerra_em`.
    """

    agora_no_servidor: datetime
    desafios: list[DesafioPublicado]

"""O QUE O APLICATIVO ENVIA — `POST /v1/desafios/*` (T043).

Espelha `specs/009-desafio-do-dia/contracts/envio-resolucao.md`.

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTE PAYLOAD NAO CARREGA OS LANCES — E ISSO E O REQUISITO
═══════════════════════════════════════════════════════════════════════════

**A resolucao e uma partida** (RF-DES-186). Os lances sobem pelo evento de
partida que o aplicativo **ja envia hoje** — `partida.tb001_partida` +
`tb002_jogada` + a extensao daquele jogo —, com `co_modo = 'desafio'` e
`ic_pontua = FALSE`. Este payload manda o **`co_evento`** daquela partida e mais
nada de lance.

⛔ Mandar os lances aqui criaria uma segunda fonte da verdade para a mesma coisa,
e jogaria fora, **de graca**, o replay, a extensao por jogo, a auditoria pelo
arbitro e o registro de poder na jogada cancelada — tudo ja em producao.

═══════════════════════════════════════════════════════════════════════════
⛔ NENHUM ITEM DE `feitos` CARREGA XP (RF-DES-170)
═══════════════════════════════════════════════════════════════════════════

O extrato guarda `damas_coroadas = 1`; **jamais** `+4 XP`. Quem converte medida
em nota, e nota em XP, e a **colecao** — e e isso que permite ao mesmo desafio
pagar diferente em duas colecoes, e permite **reponderar** os pesos de `Q` em
campo sem recalcular medida nenhuma (SC-021).

═══════════════════════════════════════════════════════════════════════════
⚠️ VALIDACAO AQUI E "DADO IMPOSSIVEL", E NUNCA "DISCORDO DO JULGAMENTO"
═══════════════════════════════════════════════════════════════════════════

O Pydantic recusa `pontuacao` fora de 18–30 e `qualidade` fora de [0,1]
(RF-DES-033). ⛔ Mas ele **nao** recusa uma resolucao porque o servidor acha que
ela nao merecia: **vale o aplicativo** (RF-DES-032, D-05). Discordancia vira
alerta no painel, e a pessoa continua no quadro — quem viu *"resolvido!"* e
depois nao se encontra no quadro nao conclui "fui pego"; conclui "esse aplicativo
e bugado".
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from api.desafios.modelos_evento import XP_PISO_POR_RESOLVER, XP_TETO_DO_DIA


class FeitoMedido(BaseModel):
    """Uma medida da partida — ⛔ **nunca** um XP.

    ⚠️ `chave` tem de existir no catalogo (`desafio.tb902_catalogo_feito`, a mesma
    lista de `lib/core/feitos/catalogo_feitos.dart`). Chave desconhecida e **dado
    invalido**, e nao tolerancia a campo novo: e o oposto. Uma chave inventada
    faria `Q` ordenar pessoas por medidas de significados diferentes.
    """

    chave: str = Field(min_length=1, max_length=40)
    #: ⚠️ `float` e nao `int`: `tempo_ate_resolver` vem em milissegundos, mas uma
    #: medida futura pode ser fracionaria. O banco guarda `NUMERIC(12,3)`.
    valor: float


class OrigemDoEnvio(BaseModel):
    """De onde veio: conta ou convidado.

    ⚠️ **Convidado tambem joga o desafio** — o que ele nao faz e reagir
    (RF-DES-084, que exige identidade para honrar "uma reacao por pessoa"). O
    `lote` e o mesmo identificador que a sincronizacao ja usa para juntar o
    historico do convidado a conta quando ele se cadastra.
    """

    tipo: Literal["conta", "convidado"]
    lote: Optional[str] = None


class EnvioDeResolucao(BaseModel):
    """O corpo de `POST /v1/desafios/{id_desafio}/resolucao`.

    ⚠️ **`nu_lance_cumpre_desafio` e o `nu_ordem` da jogada, e nao o `nu_lance`**
    (RF-DES-214). `nu_ordem` e sequencia continua de eventos: nunca recua e nunca
    se repete. `nu_lance` recua quando alguem desfaz uma jogada, e pode repetir —
    como ponteiro para uma linha so, ele seria uma armadilha esperando o dia em
    que "voltar jogada" chegue ao desafio.

    ⚠️ **A coluna e `NOT NULL`**: payload sem ela e dado invalido, e rejeitar e
    melhor que gravar um zero de fachada — um zero passaria pelo banco e faria o
    Raio-X apontar para um lance que nao existe.
    """

    id_desafio_dia: UUID
    veredito: Literal["resolvido", "tentativa"]

    tentativas: int = Field(ge=1)
    tempo_ms: int = Field(ge=0)
    dicas_usadas: int = Field(ge=0, le=2)

    #: `Q`, calculada **no aplicativo** (RF-DES-030). O servidor a guarda e a
    #: audita depois; ⛔ nao a recalcula para decidir se aceita.
    qualidade: float = Field(ge=0.0, le=1.0)

    #: ⚠️ **Sem teto aqui** (RF-DES-155): 18 a 30 e a faixa de **um** desafio. O
    #: teto de 30/dia e da colecao, e entra como linha de `ajuste` negativa — nao
    #: como corte neste numero.
    pontuacao: int = Field(ge=XP_PISO_POR_RESOLVER, le=XP_TETO_DO_DIA)

    #: ⚠️ A partida que **este mesmo aplicativo ja enviou** pelo log. E o unico
    #: elo com os lances.
    co_evento_partida: str = Field(min_length=1, max_length=64)

    #: O `nu_ordem` do lance que cumpriu o objetivo (RF-DES-214).
    nu_lance_cumpre_desafio: int = Field(gt=0)

    feitos: list[FeitoMedido] = Field(default_factory=list)
    versao_catalogo_feitos: int = Field(ge=1)

    resolvido_em: datetime
    origem: OrigemDoEnvio


class RespostaDeResolucao(BaseModel):
    """O que a rota devolve.

    ⚠️ **A resposta nao desmente o aplicativo.** `aceita: true` significa *"recebi
    e gravei"*, e nao *"conferi"* — a validacao roda **fora do caminho da
    requisicao** (RF-DES-036), em lote e com atraso. E auditoria, nao liberacao.
    """

    id_resolucao: Optional[UUID] = None
    aceita: bool = True
    #: ⚠️ Reenviar a mesma resolucao responde `200` com `ja_existia: true`. Nao ha
    #: UUID de requisicao a inventar: a chave natural e `(desafio, pessoa)`, e ela
    #: e **exata** porque um desafio e publicado uma vez so (RF-DES-152).
    ja_existia: bool = False


class EnvioDeDica(BaseModel):
    """O corpo de `POST /v1/desafios/{id_desafio}/dica`.

    ⚠️ **Registrado no instante em que o premiado se COMPLETA** — a rede ja esta
    la naquele momento. ⛔ Premiado interrompido **nao consome** (RF-DES-056), e
    por isso quem decide chamar esta rota e o callback de recompensa concedida, e
    nao a abertura do anuncio.

    ⚠️ **O teto de duas dicas e por DESAFIO** (RF-DES-057), e o contador vive no
    servidor: fechar o aplicativo encerra a tentativa, nao o dia, e um contador
    local daria dicas infinitas a quem reabrisse.
    """

    id_desafio_dia: UUID
    co_evento_partida: str = Field(min_length=1, max_length=64)
    #: 1 = regiao ou peca · 2 = o lance. ⚠️ Sao duas coisas diferentes, e a
    #: segunda so faz sentido depois da primeira.
    grau: int = Field(ge=1, le=2)
    consumida_em: datetime




class MotorDoAparelho(BaseModel):
    """Um motor que o aparelho tinha no instante em que o desafio nao coube.

    ⚠️ **Um registro por (jogo, motor)** — e nao um campo por motor. As damas
    carregam hoje dois (`dart` e `rust`); um jogo novo pode trazer outro par, e
    um campo fixo faria jogo novo exigir migracao.

    ⛔ **O vocabulario de `co_motor` e ABERTO, de proposito.** Um aplicativo mais
    novo que este servidor vai reportar motor que ele nunca ouviu falar. Recusar
    a linha perderia o diagnostico exatamente quando ele e mais interessante —
    entao o servidor guarda o que veio, e quem le lida com o desconhecido.
    """

    co_jogo: str = Field(min_length=1, max_length=30)
    co_motor: str = Field(min_length=1, max_length=20)
    co_versao: str = Field(min_length=1, max_length=20)


class EnvioDeDesafioImpedido(BaseModel):
    """O corpo de `POST /v1/desafios/impedido`.

    ⚠️ **Registra o dia em que o desafio NAO COUBE na versao do aplicativo**
    (RF-DES-024/028) — jogo que ele nao tem, tipo que nao conhece, chave de i18n
    ausente. ⛔ **O dia nao pode contar contra a pessoa**: a chama sobrevive, e o
    caminho e o mesmo que ja a alimenta.

    ⚠️ Sim, isso da credito de chama a quem so abriu o aplicativo naquele dia — e
    e **deliberado**: a chama e gentil por decisao de produto, e o caso e estreito
    (so existe quando ha desafio incompativel no ar).

    ⚠️ **Nao ha `id_desafio_dia` obrigatorio**: quem cai aqui pode nem ter
    conseguido ler a resposta do desafio (chave desconhecida, versao minima
    maior). Exigi-lo faria justamente o caso que a rota existe para cobrir
    falhar.

    ⛔ **Versao do aplicativo e plataforma NAO estao aqui.** Elas ja chegam nos
    cabecalhos obrigatorios `X-App-Version`/`X-Platform`, e aceita-las tambem no
    corpo criaria uma segunda fonte que pode discordar da primeira — o aplicativo
    passaria a ter dois lugares para errar, e o diagnostico nao saberia em qual
    acreditar.
    """

    id_desafio_dia: Optional[UUID] = None
    motivo: Literal[
        "jogo_desconhecido",
        "modalidade_desconhecida",
        "forma_desconhecida",
        "chave_desconhecida",
        "versao_insuficiente",
    ]
    #: ⚠️ **O VALOR que o aplicativo nao reconheceu** — o codigo do jogo, da
    #: modalidade, da forma, ou a chave de i18n ausente.
    #:
    #: Sem ele, `motivo` diz a CATEGORIA e nunca QUAL: a linha provaria que
    #: alguem foi barrado sem dizer por que de forma acionavel, que e meio
    #: caminho para a tabela que ninguem consulta.
    desconhecido: Optional[str] = Field(default=None, max_length=60)
    visitado_em: datetime
    #: O deslocamento do fuso do jogador, em MINUTOS.
    #:
    #: ⚠️ A chama e contada por **dias LOCAIS** (`dh` UTC + offset do jogador), e
    #: sem o offset o servidor creditaria a visita no dia UTC — que pode ser
    #: ontem ou amanha para quem visitou.
    nu_offset_minuto: Optional[int] = Field(default=None, ge=-840, le=840)
    #: Os motores do aparelho. Vazio quando o aplicativo nao souber informar.
    motores: Optional[list[MotorDoAparelho]] = None

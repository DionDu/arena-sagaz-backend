"""As regras do registro do aparelho, sem banco e sem HTTP (T118 da spec 010).

Tudo o que aqui se decide é **função pura**: recebe valores, devolve valores, e
não fala com ninguém. É isso que deixa testar cada regra com números escolhidos
a dedo, sem Postgres e sem montar requisição - e é o que impede a mesma regra
de nascer duas vezes, uma na rota de leitura do desafio e outra na rota dos
detalhes.

O que mora aqui:

* **a versão** - como se lê o `X-App-Version` e qual de duas é a maior;
* **o aparelho** - o código que o app 1.4 manda, e a linha LEGADA que o
  servidor sintetiza para o app 1.3, que não manda código nenhum;
* **o fuso** - o deslocamento que o app 1.4 manda no cabeçalho;
* **o detalhe do espaço** - quando ele é guardado e quando vira `NULL`.

O porquê de cada tabela está no cabeçalho da migração `0036_log_aparelho` e no
`data-model.md` §4 da spec 010.
"""
from __future__ import annotations

import re
import uuid
from typing import Mapping, Optional

# ═══════════════════════════════════════════════════════════════════════════
# A versão do app
# ═══════════════════════════════════════════════════════════════════════════

#: A forma aceita do `X-App-Version`: até três números separados por ponto, e
#: um número de build opcional depois do `+` (`1.3.1`, `1.4.0+17`).
#:
#: ⚠️ **É uma regex de propósito estreita.** A versão gravada é comparada com a
#: próxima, e só se compara o que se sabe ler; um texto livre ("1.4.0-beta",
#: "dev") não tem ordem, e gravá-lo deixaria a linha do dia sem como subir. O
#: app em campo manda o `PackageInfo.version`, que é sempre desta forma. Os
#: tetos de dígitos (6 e 9) só existem para nenhum número estourar e para o
#: texto inteiro caber nos 20 caracteres da coluna `co_versao_app`.
_FORMA_DA_VERSAO = re.compile(r"^(\d{1,6})(?:\.(\d{1,6}))?(?:\.(\d{1,6}))?(?:\+(\d{1,9}))?$")

#: A largura de `log.tb004_aparelho_dia.co_versao_app`.
LARGURA_DA_VERSAO = 20


def chave_da_versao(texto: Optional[str]) -> Optional[tuple[int, int, int, int]]:
    """A versão como **quatro números comparáveis**, ou `None` se ela não se lê.

    `(maior, menor, correção, build)`, com o que faltar valendo zero: `1.3`
    vira `(1, 3, 0, 0)` e `1.4.0+17` vira `(1, 4, 0, 17)`.

    ⚠️ **Por que números, e não o texto.** Comparar texto erra justamente na
    virada que importa: `"1.10.0" < "1.9.0"` é verdade para o Python (o `"1"`
    vem antes do `"9"`), e a adoção leria a versão 1.10 como mais velha que a
    1.9. A tupla compara número a número, da esquerda para a direita - que é
    como uma versão se lê.

    Args:
        texto: o valor do cabeçalho `X-App-Version`.

    Returns:
        A tupla, ou `None` quando o texto falta, é longo demais para a coluna ou
        não tem a forma de uma versão.
    """
    if not texto or len(texto) > LARGURA_DA_VERSAO:
        return None
    casou = _FORMA_DA_VERSAO.match(texto.strip())
    if casou is None:
        return None
    # `casou.groups()` devolve os quatro grupos da regex; o que não apareceu no
    # texto vem `None`, e vira zero aqui.
    maior, menor, correcao, build = (int(g) if g else 0 for g in casou.groups())
    return (maior, menor, correcao, build)


def versao_maior(nova: str, antiga: str) -> bool:
    """`True` quando [nova] é **estritamente** maior que [antiga].

    É a pergunta que o registro do dia faz antes de trocar a versão gravada: a
    linha guarda a MAIOR vista no dia, então uma leitura com versão igual ou
    menor não muda nada (quem atualiza o app no meio do dia sobe; nada desce).

    ⚠️ Uma versão que não se lê nunca é maior: ela nem chega a ser gravada (a
    rota a descarta antes), e uma gravada antes desta regra existir perde para
    qualquer versão legível.
    """
    chave_nova = chave_da_versao(nova)
    if chave_nova is None:
        return False
    chave_antiga = chave_da_versao(antiga)
    if chave_antiga is None:
        return True
    return chave_nova > chave_antiga


# ═══════════════════════════════════════════════════════════════════════════
# O aparelho
# ═══════════════════════════════════════════════════════════════════════════

#: O "espaço de nomes" do UUID da linha legada.
#:
#: Um UUID versão 5 é o SHA-1 de um espaço de nomes mais um texto: o mesmo par
#: dá sempre o mesmo UUID. O espaço daqui foi derivado uma vez, de um texto que
#: diz o que ele é (`uuid5(NAMESPACE_URL, "arena-sagaz:log.tb003_aparelho:legado")`),
#: e está escrito por extenso para ninguém o recalcular de outro jeito.
#:
#: ⛔ **Nunca mude este valor.** Ele é o que faz o app 1.3 de uma pessoa cair
#: sempre na mesma linha; trocá-lo faria cada aparelho legado aparecer DUAS
#: vezes na conta da adoção (a linha velha e a nova), e nada daria erro. O
#: teste `test_o_espaco_da_linha_legada_nao_muda` o trava.
ESPACO_DA_LINHA_LEGADA = uuid.UUID("9ff1ea6f-6540-556f-879f-7a48f54bc5c3")


def id_aparelho_legado(id_usuario: str, plataforma: str) -> uuid.UUID:
    """O `id_aparelho` que o servidor **sintetiza** para um app sem o código.

    O app 1.3 em campo não manda código de instalação, mas tem de entrar na
    amostra da adoção (senão ela leria 100% no dia do lançamento). Para ele o
    aparelho é *"esta conta nesta plataforma"*: `uuid5(conta | plataforma)`.

    ⚠️ **Determinístico, e por isso idempotente**: a mesma pessoa no mesmo
    Android dá sempre o mesmo UUID, então abrir o app cinco vezes no dia dá uma
    linha só, sem tabela de-para nenhuma. Quem tem um Android e um iPad conta
    duas vezes, com a versão de cada um - que é o que a adoção quer contar.

    ⚠️ E ele **nunca colide** com o código de um app 1.4: este é versão 5, e o
    do app é versão 4 (`id_aparelho_do_cabecalho` recusa qualquer outra).

    Args:
        id_usuario: o `id_usuario` interno da conta (o UUID de
            `conta.tb001_usuario`), e não o uid do Firebase.
        plataforma: `android`, `ios` ou `web`, do `X-Platform`.
    """
    # Minúsculas nas duas pontas: o mesmo UUID escrito em caixa diferente
    # daria outro SHA-1, e a mesma pessoa viraria dois aparelhos.
    return uuid.uuid5(
        ESPACO_DA_LINHA_LEGADA, f"{str(id_usuario).lower()}|{plataforma.lower()}"
    )


def id_aparelho_do_cabecalho(texto: Optional[str]) -> Optional[uuid.UUID]:
    """O código de instalação do cabeçalho `X-Install-Id`, ou `None`.

    Só vale um **UUID versão 4**, que é o que o app gera na 1ª abertura. Um
    texto que não é UUID, ou um UUID de outra versão, vale como ausente.

    ⚠️ **Por que recusar as outras versões.** A linha legada é versão 5; sem
    esta recusa, um app (ou alguém curioso com a API) que mandasse um UUID v5
    escreveria na linha legada de outra pessoa.

    ⚠️ E **ausente não é erro** na leitura do desafio: um código ilegível cai
    no caminho do app 1.3 (a linha legada, ou nada para o convidado), e o
    desafio continua chegando. Quem recusa com 400 é só a rota dos detalhes,
    que sem aparelho não tem onde gravar.
    """
    if not texto:
        return None
    try:
        lido = uuid.UUID(texto.strip())
    except ValueError:
        return None
    return lido if lido.version == 4 else None


# ═══════════════════════════════════════════════════════════════════════════
# O fuso
# ═══════════════════════════════════════════════════════════════════════════

#: O maior deslocamento de fuso que existe no mundo, em minutos (UTC+14, Kiribati;
#: e UTC-12 do outro lado, dentro do mesmo teto). A mesma faixa dos `CHECK` de
#: `nu_offset_minuto` nas outras tabelas.
OFFSET_MAXIMO_MINUTOS = 840


def offset_do_cabecalho(texto: Optional[str]) -> Optional[int]:
    """O deslocamento do fuso do aparelho, em minutos, do cabeçalho `X-Utc-Offset`.

    Quantos minutos o relógio da pessoa está **à frente** de UTC: o Brasil manda
    `-180`. `None` quando falta, não é número inteiro ou sai da faixa de
    `±840` - e aí quem decide o dia é o fuso conhecido da pessoa, ou UTC (ver
    `ServicoAparelho`).
    """
    if texto is None:
        return None
    try:
        minutos = int(texto.strip())
    except ValueError:
        return None
    if abs(minutos) > OFFSET_MAXIMO_MINUTOS:
        return None
    return minutos


# ═══════════════════════════════════════════════════════════════════════════
# O espaço ocupado pelo app
# ═══════════════════════════════════════════════════════════════════════════

#: As pastas que o detalhe do espaço conhece, no espírito da tela *Espaço em
#: disco (DES)* do Perfil. ⚠️ **Vocabulário fechado** (`data-model.md` §4.2):
#: uma chave fora daqui é **descartada**, e não recusada - um app mais novo que
#: meça uma pasta a mais não pode perder o dia inteiro por isso.
PASTAS_DO_ESPACO = frozenset(
    {"cache", "tmp", "suporte", "banco", "base_damas", "outros"}
)


def detalhe_do_espaco_para_guardar(
    *,
    total_kb: Optional[int],
    detalhe: Optional[Mapping[str, int]],
    plataforma: str,
    limites_mb: Mapping[str, int],
) -> Optional[dict[str, int]]:
    """O detalhe por pasta que vai para `js_espaco_app`, ou `None`.

    ⚠️ **Quem decide é o servidor, e não o app** (pedido do dono, §8zzz): o app
    manda o detalhe todo dia (uns 80 bytes), e ele só é guardado quando o total
    **passa** do limite da plataforma - que é exatamente quando alguém vai
    querer saber o porquê. Abaixo disso fica `NULL`, e não custa nada. Um
    número no app só mudaria com versão nova; aqui, muda com uma variável do
    Railway.

    Args:
        total_kb: o total que o app ocupa, em KB.
        detalhe: o KB de cada pasta, como o app mandou.
        plataforma: `android`, `ios` ou `web`.
        limites_mb: o limite de cada plataforma, em MB
            (`ESPACO_APP_DETALHE_MB_ANDROID` e `_IOS`). Plataforma sem limite
            (o `web` do desenvolvimento) nunca guarda.

    Returns:
        O detalhe só com as pastas conhecidas e valores não negativos, ou
        `None` quando o total não passa do limite ou falta um dos dois.
    """
    if total_kb is None or not detalhe:
        return None
    limite_mb = limites_mb.get(plataforma)
    if limite_mb is None:
        return None
    # 1 MB = 1024 KB. "Passa do limite" é estritamente acima: no limite exato,
    # o app ainda está dentro do que se considerou normal.
    if total_kb <= limite_mb * 1024:
        return None
    return {
        pasta: int(kb)
        for pasta, kb in detalhe.items()
        if pasta in PASTAS_DO_ESPACO and isinstance(kb, int) and kb >= 0
    }

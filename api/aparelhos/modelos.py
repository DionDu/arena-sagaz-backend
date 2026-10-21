"""O corpo do `POST /v1/aparelhos/detalhes`, e o que ele aceita (T118).

Pydantic é a biblioteca que o FastAPI usa para validar o JSON que chega: cada
campo declarado aqui vira uma regra, e o que não bater volta como `422` sem a
rota ser chamada.

⚠️ **Cada teto espelha a largura de uma coluna** de `log.tb003_aparelho` ou
`log.tb004_aparelho_dia` (migração `0036_log_aparelho`): um valor que passasse
aqui e estourasse a coluna viraria um `500` no meio da noite, em vez de um
`422` claro na hora. O app (T118a) corta os textos nesses mesmos tetos antes
de mandar.

⚠️ **O que NÃO está aqui é tão importante quanto o que está.**

* Não há `plataforma`, `versao_app` nem `idioma`: os três já viajam em todo
  pedido, nos cabeçalhos `X-Platform`, `X-App-Version` e `Accept-Language`.
  Pedi-los duas vezes criaria duas fontes para o mesmo dado, e a segunda é a
  que fica errada quando as duas discordam.
* Não há o código do aparelho: ele vem no cabeçalho `X-Install-Id`, como em
  todo pedido da 1.4.
* Não há identificador de hardware (IMEI, `androidId`,
  `identifierForVendor`), nem a memória **disponível**, nem o espaço **livre**
  em disco - este último porque a Apple só libera a leitura para uso dentro do
  aparelho, e proíbe enviá-la (§8zzz).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

#: O maior `SMALLINT` do Postgres. Núcleos e pontos de tela cabem com folga; o
#: teto existe para um número absurdo voltar 422, e não estourar a coluna.
_SMALLINT = 32767
#: O maior `INTEGER` do Postgres: 2 TB em KB, e 2 PB em MB.
_INTEGER = 2_147_483_647


class DetalhesDoAparelho(BaseModel):
    """O que o app 1.4 conta do aparelho, uma vez por dia, na abertura.

    Todos os campos são **opcionais**: um aparelho que não informa um (o iOS
    não tem o nome do processador; um Android antigo não tem o SoC) não perde
    os outros.
    """

    # ── O aparelho (log.tb003_aparelho) ─────────────────────────────────────
    fabricante: Optional[str] = Field(default=None, max_length=40, description="Ex.: 'samsung', 'Apple'.")
    modelo: Optional[str] = Field(default=None, max_length=80, description="Ex.: 'SM-A065M', 'iPhone15,4'.")
    abi: Optional[str] = Field(default=None, max_length=20, description="Ex.: 'arm64-v8a'.")
    processador: Optional[str] = Field(
        default=None,
        max_length=60,
        description="O SoC (Android 12 em diante). No iOS o modelo já diz o chip.",
    )
    nucleos: Optional[int] = Field(default=None, ge=1, le=_SMALLINT)
    ram_mb: Optional[int] = Field(default=None, ge=0, le=_INTEGER, description="A memória TOTAL, em MB.")
    tela_largura_dp: Optional[int] = Field(default=None, ge=1, le=_SMALLINT)
    tela_altura_dp: Optional[int] = Field(default=None, ge=1, le=_SMALLINT)
    # `NUMERIC(4,2)` vai até 99,99. `lt=100` (menor que) e não `le`, porque
    # 100,00 já não cabe.
    densidade_tela: Optional[float] = Field(
        default=None, gt=0, lt=100, description="Pixels por ponto lógico."
    )
    instancia_analytics: Optional[str] = Field(
        default=None,
        max_length=64,
        description="O appInstanceId do Firebase Analytics; nulo sem consentimento.",
    )

    # ── O dia (log.tb004_aparelho_dia) ──────────────────────────────────────
    versao_so: Optional[str] = Field(default=None, max_length=40, description="Ex.: 'Android 14 (SDK 34)'.")
    espaco_app_kb: Optional[int] = Field(
        default=None, ge=0, le=_INTEGER, description="Quanto o app ocupa, no total, em KB."
    )
    # O detalhe por pasta, SEMPRE (quem decide guardá-lo é o servidor). As
    # chaves conhecidas estão em `regras.PASTAS_DO_ESPACO`; a desconhecida é
    # descartada lá, e não recusada aqui. `max_length` num dicionário conta as
    # chaves: o vocabulário tem seis, e 20 é só sanidade.
    espaco_app: Optional[dict[str, int]] = Field(
        default=None, max_length=20, description="KB por pasta: cache, tmp, suporte..."
    )

    def colunas_do_aparelho(self) -> dict[str, object]:
        """Os campos do aparelho com o nome das colunas da `tb003`.

        A tradução mora aqui, junto da declaração dos campos, para que um
        campo novo não seja esquecido na metade do caminho.
        """
        # ⚠️ `Decimal` a partir do TEXTO arredondado: o `NUMERIC` do Postgres
        # recebe o número exato que se vê (2,63), e não o binário aproximado
        # de um `float` (2,6299999...).
        densidade = (
            Decimal(str(round(self.densidade_tela, 2)))
            if self.densidade_tela is not None
            else None
        )
        return {
            "no_fabricante": self.fabricante,
            "no_modelo": self.modelo,
            "co_abi": self.abi,
            "no_processador": self.processador,
            "qt_nucleos": self.nucleos,
            "nu_ram_mb": self.ram_mb,
            "nu_tela_largura_dp": self.tela_largura_dp,
            "nu_tela_altura_dp": self.tela_altura_dp,
            "nu_densidade_tela": densidade,
            "co_instancia_analytics": self.instancia_analytics,
        }


class DetalhesRegistrados(BaseModel):
    """A resposta, e ela é deliberadamente pobre.

    O app **não faz nada** com ela: a chamada é *fire-and-forget* (a regra 3 da
    0016), e qualquer coisa que ele precisasse tratar viraria um caminho de
    erro numa funcionalidade que existe justamente para não atrapalhar. Os
    campos servem ao suporte e aos testes.
    """

    registrado: bool = True
    #: O dia em que a linha caiu - o dia LOCAL do aparelho.
    dia_local: date
    #: Se o detalhe por pasta foi guardado (o total passou do limite).
    detalhe_do_espaco_guardado: bool

"""O CARIMBO: de onde veio cada número que o motor produziu (RF-DES-164/146).

═══════════════════════════════════════════════════════════════════════════
A LIÇÃO DE 26/08/2026, ESCRITA AQUI PARA NÃO SE REPETIR
═══════════════════════════════════════════════════════════════════════════

Naquele dia se descobriu, nas partidas, que sem `co_versao_motor` gravado
**recalibrar apaga a evidência de como o número saiu**. O histórico fica ilegível:
uma medição de três semanas atrás e uma de ontem parecem a mesma coisa, embora
tenham sido feitas por motores diferentes, com réguas diferentes.

O Desafio do Dia tem o mesmo problema, e pior: um desafio aprovado há vinte dias
foi calibrado com a régua **daquele** dia (RF-DES-146). Se a régua mudar e nada
disser qual foi usada, o painel de curadoria compara maçã com laranja em silêncio.

⚠️ **Entra desde o dia 1**, antes mesmo de haver Remote Config de dificuldade:
é barato agora e **impossível de retroagir** depois.

═══════════════════════════════════════════════════════════════════════════
O QUE O CARIMBO CARREGA
═══════════════════════════════════════════════════════════════════════════

    co_jogo           'pontinhos' | 'damas'
    co_modalidade     'brasileiras' nas damas; NULO no Pontinhos, que não tem
    co_nivel          o degrau da escada (cacau · pita · tex · sagaz)
    co_versao_motor   'pontinhos-py-2.1.0' — quem gerou e calibrou
    co_versao_perfil  'perfil-2026-09'     — com que régua

Os nomes das chaves são os das colunas do `data-model.md` de propósito: quem lê
uma linha do banco e quem lê este arquivo estão olhando a mesma coisa, e não
precisam de um dicionário no meio.

⛔ **O carimbo não sabe o que é desafio.** Ele descreve **o produtor**, não o
produto: nada de identificador de desafio, de dia ou de coleção aqui dentro —
isso é do schema `desafio`, e a camada de motores não o conhece (RF-DES-165).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from motores.nucleo.papeis import NivelDeMotor

# Um identificador de versão é curto, sem espaço e cabe em VARCHAR(40) — o
# tamanho declarado no `data-model.md` para `co_versao_motor` e
# `co_versao_perfil`. Recusamos o que não caberia, aqui, em vez de descobrir no
# `INSERT`: a mensagem do banco diria "value too long for type character
# varying(40)" sem dizer de qual coluna nem de qual motor.
TAMANHO_MAXIMO_VERSAO = 40
FORMA_DA_VERSAO = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# Os jogos que esta entrega conhece. ⚠️ É uma tupla e não um enum de propósito:
# `co_jogo` é `VARCHAR(30)` no banco, e a lista de jogos do hub cresce — um enum
# aqui obrigaria a mexer na camada comum para acrescentar um jogo.
JOGOS_CONHECIDOS = ("pontinhos", "damas", "velha")


def _validar_versao(valor: str, campo: str) -> str:
    """Recusa versão vazia, longa demais ou com forma estranha.

    A forma exigida — minúsculas, dígitos, ponto, hífen e sublinhado — não é
    capricho: esses identificadores viram parte de chave única no banco
    (`un001_perfil`) e aparecem em log e painel. Maiúscula misturada faria
    `Pontinhos-PY-2.1.0` e `pontinhos-py-2.1.0` conviverem como se fossem duas
    coisas.
    """
    if not valor:
        raise ValueError(f"{campo} não pode ser vazio (RF-DES-164).")
    if len(valor) > TAMANHO_MAXIMO_VERSAO:
        raise ValueError(
            f"{campo} tem {len(valor)} caracteres e a coluna aceita "
            f"{TAMANHO_MAXIMO_VERSAO}: {valor!r}"
        )
    if not FORMA_DA_VERSAO.match(valor):
        raise ValueError(
            f"{campo} fora da forma esperada (minúsculas, dígitos, . _ -): {valor!r}"
        )
    return valor


@dataclass(frozen=True, slots=True)
class Carimbo:
    """Quem produziu, com que régua, em que nível — imutável.

    `frozen=True` é o ponto: um carimbo que pudesse ser alterado depois de
    emitido não provaria nada. Se a produção mudar, emite-se **outro** carimbo.

    Atributos:
        co_jogo: chave do jogo, como no banco (`pontinhos`, `damas`).
        co_nivel: o degrau da escada usado na produção.
        co_versao_motor: identificador do motor que gerou e calibrou.
        co_versao_perfil: identificador da régua de dificuldade vigente.
        co_modalidade: regulamento, quando o jogo tem. `None` no Pontinhos —
            e `None` é diferente de string vazia: no banco a coluna é anulável
            justamente porque "não se aplica" não é o mesmo que "não informado".
    """

    co_jogo: str
    co_nivel: NivelDeMotor
    co_versao_motor: str
    co_versao_perfil: str
    co_modalidade: str | None = None

    def __post_init__(self) -> None:
        """Valida na construção — o carimbo errado tem de doer cedo.

        ⚠️ Num `dataclass` com `frozen=True` não se pode atribuir a um campo aqui
        dentro; só validar. É de propósito: normalizar em silêncio (baixar caixa,
        aparar espaço) esconderia o erro de quem chamou, e o valor gravado
        deixaria de ser o valor escrito.
        """
        if self.co_jogo not in JOGOS_CONHECIDOS:
            raise ValueError(
                f"co_jogo desconhecido: {self.co_jogo!r}. "
                f"Conhecidos: {', '.join(JOGOS_CONHECIDOS)}. "
                "Jogo novo entra em JOGOS_CONHECIDOS junto com o seu motor."
            )
        if not isinstance(self.co_nivel, NivelDeMotor):
            raise TypeError(
                f"co_nivel precisa ser NivelDeMotor, veio {type(self.co_nivel).__name__}. "
                "Texto solto aqui deixaria 'sagas' passar por 'sagaz'."
            )
        _validar_versao(self.co_versao_motor, "co_versao_motor")
        _validar_versao(self.co_versao_perfil, "co_versao_perfil")
        if self.co_modalidade is not None:
            _validar_versao(self.co_modalidade, "co_modalidade")

    def para_colunas(self) -> dict[str, Any]:
        """O carimbo na forma exata das colunas do banco.

        ⚠️ `co_nivel` sai como **texto** (`'sagaz'`), não como o objeto do enum:
        quem escreve no banco não deve precisar conhecer o tipo Python da camada
        de motores para gravar uma linha.
        """
        return {
            "co_jogo": self.co_jogo,
            "co_modalidade": self.co_modalidade,
            "co_nivel": self.co_nivel.value,
            "co_versao_motor": self.co_versao_motor,
            "co_versao_perfil": self.co_versao_perfil,
        }

    def com_nivel(self, nivel: NivelDeMotor) -> "Carimbo":
        """O mesmo produtor, outro degrau — um carimbo NOVO.

        A régua mede o mesmo candidato nos quatro níveis (Bloco D). Sem isto,
        cada medição precisaria repetir motor, perfil e modalidade à mão, e
        bastaria uma repetição errada para a evidência apontar para o lugar
        errado.
        """
        return Carimbo(
            co_jogo=self.co_jogo,
            co_nivel=nivel,
            co_versao_motor=self.co_versao_motor,
            co_versao_perfil=self.co_versao_perfil,
            co_modalidade=self.co_modalidade,
        )

    def __str__(self) -> str:
        """Uma linha legível para log — a modalidade só aparece se existir."""
        modalidade = f"/{self.co_modalidade}" if self.co_modalidade else ""
        return (
            f"{self.co_jogo}{modalidade} nível={self.co_nivel.value} "
            f"motor={self.co_versao_motor} perfil={self.co_versao_perfil}"
        )

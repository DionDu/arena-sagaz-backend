"""Acesso a `log.tb002_diagnostico_motor_nativo`.

Segue a regra de ouro do projeto: **escrita na tabela, leitura pela VIEW**, e
sempre com parâmetros nomeados (`:nome`) — nunca interpolação de string, que é
por onde entra SQL injection.
"""
from __future__ import annotations

import hashlib
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ⚠️ AS COLUNAS QUE DEFINEM UMA "CONFIGURAÇÃO", e a ordem importa.
#
# É este conjunto que decide quando dois relatos são o **mesmo problema**. Ele
# está aqui, num só lugar, e não espalhado numa expressão SQL: mudar o critério
# é uma decisão, e ela tem de ser visível.
#
# ⚠️ **`id_usuario` NÃO está na lista**, e é deliberado: a tabela conta
# configurações quebradas, não pessoas. Dois irmãos com o mesmo celular têm o
# mesmo problema uma vez, não duas.
#
# ⚠️ **`de_motivo` também não**: ele carrega a mensagem do sistema, que varia
# entre execuções (endereços, caminhos). Incluí-lo faria a assinatura mudar
# sozinha, e a garantia de "uma linha por configuração" sumiria em silêncio —
# o pior tipo de defeito, porque o único sintoma é a tabela crescer.
COLUNAS_DA_ASSINATURA = (
    "co_jogo",
    "co_motor",
    "co_motivo",
    "co_plataforma",
    "co_versao_so",
    "no_modelo_aparelho",
    "co_abi",
    "co_versao_app",
    "co_versao_motor",
    "co_versao_binario_encontrada",
    "co_flavor",
    "co_modo_build",
)


def calcular_assinatura(dados: dict[str, Any]) -> str:
    """SHA-256 das colunas que definem a configuração — 64 caracteres hex.

    ⚠️ **Calculada no SERVIDOR, e nunca recebida do app.** Se viesse de fora,
    uma build com defeito (ou alguém curioso com o endpoint) poderia mandar
    assinaturas aleatórias e derrubar a garantia inteira — e a regra passaria a
    existir em tantas versões quantas builds houvesse em campo.

    O `|` separa os campos e o `\\x00` marca o nulo. Sem um separador explícito,
    `('ab', 'c')` e `('a', 'bc')` dariam o mesmo hash — colisão que juntaria
    duas configurações diferentes numa linha só, e ninguém perceberia.
    """
    partes = []
    for coluna in COLUNAS_DA_ASSINATURA:
        valor = dados.get(coluna)
        partes.append("\x00" if valor is None else str(valor))
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


class RepositorioDiagnostico:
    """Grava relatos de motor nativo indisponível."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def id_usuario_por_identidade(
        self, co_identidade_externa: str
    ) -> Optional[Any]:
        """Resolve o `id_usuario` interno a partir do `uid` do Firebase.

        `None` quando ainda não há conta para esse uid — e isso **não impede o
        registro**: o relato vale igual sem dono. Ver a regra 2 no cabeçalho da
        migração 0016.
        """
        sql = text(
            "SELECT id_usuario FROM conta.vw001_usuario "
            "WHERE co_identidade_externa = :uid"
        )
        resultado = await self.sessao.execute(sql, {"uid": co_identidade_externa})
        linha = resultado.mappings().first()
        return linha["id_usuario"] if linha else None

    async def registrar_motor_nativo(
        self, dados: dict[str, Any]
    ) -> tuple[str, int]:
        """Insere ou **incrementa** o relato, e devolve `(id, qt_ocorrencias)`.

        ═══════════════════════════════════════════════════════════════════
        ⚠️ ESTE UPSERT É A GARANTIA DE QUE A TABELA NÃO INCHA
        ═══════════════════════════════════════════════════════════════════

        A pergunta do dono em 27/08/2026 foi: *"O que vai garantir aí que um
        mesmo telefone de 1 usuário não vai ficar alimentando essa tabela
        indefinidamente com o mesmo registro?"*

        A resposta é esta linha: `ON CONFLICT (co_assinatura) DO UPDATE`. O
        dedupe do app é **economia de rede** e pode ser perdido (reinstalação,
        "limpar dados", um envio que falhou e corretamente não foi marcado); o
        `UNIQUE` daqui é a **garantia**, e ela não se perde.

        Um telefone que relate mil vezes deixa `qt_ocorrencias = 1000` numa
        linha só. E isso não é só economia de espaço: é o que faz a consulta
        *"quantas configurações estão quebradas?"* continuar respondendo a
        pergunta que se fez, em vez de *"quantas vezes alguém reinstalou o app
        num aparelho quebrado"*.

        **O que o `DO UPDATE` atualiza, e por quê cada um:**

        * `qt_ocorrencias` — o contador, que é o dado novo;
        * `dh_ultimo` — responde *"isto ainda está acontecendo?"*. Nada é
          apagado aqui, então sem ele uma configuração consertada há meses
          continuaria parecendo ativa;
        * `de_motivo` — fica o texto **mais recente**. Ele não entra na
          assinatura justamente por variar, e a variação mais nova é a mais
          útil para investigar;
        * `id_usuario` — o **último** que relatou, e só quando há um.
          `COALESCE` na ordem `novo, antigo` mantém o anterior quando o relato
          novo é de convidado: perder um dono conhecido por causa de um relato
          anônimo seria trocar informação por ausência.

        ⚠️ **`dh_primeiro` NÃO é atualizado.** É ele que diz desde quando a
        configuração está quebrada — sobrescrevê-lo apagaria a única medida de
        há quanto tempo o problema existe.
        """
        completo = {**dados, "co_assinatura": calcular_assinatura(dados)}

        sql = text(
            """
            INSERT INTO log.tb002_diagnostico_motor_nativo
                (co_assinatura, id_usuario, co_jogo, co_motor, co_motivo,
                 de_motivo, co_versao_motor, co_versao_binario_esperada,
                 co_versao_binario_encontrada, co_plataforma, co_versao_so,
                 no_modelo_aparelho, co_abi, co_versao_app, co_flavor,
                 co_modo_build)
            VALUES
                (:co_assinatura, :id_usuario, :co_jogo, :co_motor, :co_motivo,
                 :de_motivo, :co_versao_motor, :co_versao_binario_esperada,
                 :co_versao_binario_encontrada, :co_plataforma, :co_versao_so,
                 :no_modelo_aparelho, :co_abi, :co_versao_app, :co_flavor,
                 :co_modo_build)
            ON CONFLICT (co_assinatura) DO UPDATE SET
                qt_ocorrencias = log.tb002_diagnostico_motor_nativo.qt_ocorrencias + 1,
                dh_ultimo      = now(),
                de_motivo      = EXCLUDED.de_motivo,
                id_usuario     = COALESCE(
                                     EXCLUDED.id_usuario,
                                     log.tb002_diagnostico_motor_nativo.id_usuario
                                 )
            RETURNING id_diagnostico, qt_ocorrencias
            """
        )
        resultado = await self.sessao.execute(sql, completo)
        linha = resultado.mappings().one()
        return str(linha["id_diagnostico"]), int(linha["qt_ocorrencias"])

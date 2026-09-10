"""O dia em que o desafio NAO COUBE no aplicativo da pessoa (RF-DES-024/028).

⚠️ **Esta e a peca que protege a CHAMA**, e nao um registro de telemetria. Quem
abre o aplicativo num dia cujo desafio exige versao que ela nao tem ⛔ **nao pode
perder a sequencia por isso** — e como a chama e **derivada** (um conjunto de
dias lido do historico, e nunca um contador), a unica forma de proteger o dia e
oferecer **mais uma fonte de dias**. E o que a linha gravada aqui e.

⚠️ **O dia e o do RELOGIO DA PESSOA.** O aplicativo manda o instante em UTC e o
deslocamento do fuso em minutos; quem soma os dois e decide a data e o servidor,
uma vez, aqui. Deixar isso para a consulta faria a mesma conta existir em todo
lugar que lesse a tabela — e uma visita as 21h no Brasil cairia no **dia
seguinte** em UTC, que e literalmente o defeito que a chama ja teve uma vez.

⚠️ **A versao minima exigida e lida do BANCO, e nao do corpo.** O aplicativo diz
o que ele **tem**; o que se **exigia** e do servidor. Aceitar os dois lados do
mesmo par pela mesma porta faria o diagnostico depender de quem esta sendo
diagnosticado.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional


from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_envio import EnvioDeDesafioImpedido

#: A versao do formato de `js_motores`.
#:
#: ⚠️ Na mesma convencao de `js_chegada`: e ela que permite mudar a forma da
#: lista sem que quem le tenha de adivinhar qual versao esta lendo.
VERSAO_DO_FORMATO_DE_MOTORES = 1


def dia_local(dh_visita: datetime, nu_offset_minuto: Optional[int]) -> date:
    """A data no relogio de quem visitou.

    ⚠️ **O offset e do JOGADOR, e nao do servidor.** O Railway roda em UTC, e
    `datetime.now().date()` no servidor responderia a pergunta errada — a de que
    dia era **la**, quando o que decide a chama e que dia era **para ela**.

    Args:
        dh_visita: o instante da visita, em UTC.
        nu_offset_minuto: quantos minutos o fuso dela esta a frente de UTC
            (negativo para o oeste; o Brasil e -180). `None` significa *"o
            aplicativo nao soube dizer"*, e ai vale o dia UTC — que e o melhor
            palpite disponivel, e nunca pior do que nao gravar linha nenhuma.

    Returns:
        A data local.
    """
    # `astimezone(utc)` normaliza qualquer instante consciente de fuso; um
    # datetime "ingenuo" (sem fuso) e assumido como UTC, que e o que o contrato
    # da rota promete.
    if dh_visita.tzinfo is None:
        instante = dh_visita.replace(tzinfo=timezone.utc)
    else:
        instante = dh_visita.astimezone(timezone.utc)

    if nu_offset_minuto:
        instante = instante + timedelta(minutes=nu_offset_minuto)
    return instante.date()


def montar_js_motores(envio: EnvioDeDesafioImpedido) -> Optional[str]:
    """O `js_motores` pronto para o `INSERT`, ou `None` quando nao ha motores.

    ⚠️ **Lista, e nao dicionario por jogo** — a mesma forma que uma tabela filha
    teria, e por isso `jsonb_to_recordset` a abre em linhas quando a pergunta for
    agregada. Um `{"damas": {"rust": "0.4.0"}}` poria o nome do jogo na *posicao
    de chave*, e toda consulta passaria a ter de saber os jogos de antemao.

    ⛔ **Nada e filtrado por vocabulario.** Um aplicativo mais novo que este
    servidor reporta motor que ele nunca ouviu falar, e descartar perderia o
    diagnostico exatamente quando ele e mais interessante.
    """
    if not envio.motores:
        return None
    return json.dumps(
        {
            "versao": VERSAO_DO_FORMATO_DE_MOTORES,
            "motores": [
                {
                    "co_jogo": motor.co_jogo,
                    "co_motor": motor.co_motor,
                    "co_versao": motor.co_versao,
                }
                for motor in envio.motores
            ],
        },
        ensure_ascii=False,
    )


#: ⚠️ `ON CONFLICT DO NOTHING` e a escolha CERTA aqui, ao contrario do ingestor
#: de partidas: um dia impedido **nao tem segunda versao**. Abrir o aplicativo
#: cinco vezes no mesmo dia grava uma linha, e a segunda chamada nao e erro —
#: e o mesmo fato, contado de novo.
#:
#: ⚠️ A **versao minima exigida** entra por subconsulta, e nao por parametro: e
#: o outro lado do par de diagnostico, e ele e do SERVIDOR. Quando
#: `id_desafio_dia` vem nulo (quem nem conseguiu ler a resposta do desafio), a
#: subconsulta devolve `NULL`, que e a verdade — nao se sabe o que se exigia.
SQL_GRAVAR_IMPEDIDO = """
INSERT INTO desafio_dia.tb007_desafio_impedido
       (id_usuario, dt_dia_local, dh_visita, nu_offset_minuto,
        id_desafio_dia, co_motivo, co_desconhecido,
        co_versao_app, co_plataforma, co_versao_minima_exigida, js_motores)
VALUES (:id_usuario, :dt_dia_local, :dh_visita, :nu_offset_minuto,
        :id_desafio_dia, :co_motivo, :co_desconhecido,
        :co_versao_app, :co_plataforma,
        (SELECT d.co_versao_minima
           FROM desafio_dia.vw001_desafio_dia dd
           JOIN desafio.vw001_desafio d ON d.id_desafio = dd.id_desafio
          WHERE dd.id_desafio_dia = :id_desafio_dia),
        CAST(:js_motores AS JSONB))
ON CONFLICT (id_usuario, dt_dia_local) DO NOTHING
RETURNING id_desafio_impedido
"""


class RepositorioImpedido:
    """A escrita de `desafio_dia.tb007_desafio_impedido`. ⛔ Nao fecha a transacao."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def gravar(
        self,
        *,
        id_usuario: str,
        envio: EnvioDeDesafioImpedido,
        co_versao_app: str,
        co_plataforma: str,
    ) -> bool:
        """Grava o dia impedido. `False` quando ele ja estava gravado.

        ⚠️ **`False` nao e erro.** O aplicativo reenvia por fila, e a pessoa pode
        abrir a tela varias vezes no mesmo dia; o `un001_dia_impedido` absorve
        tudo isso, e a rota responde 204 nos dois casos.

        Args:
            id_usuario: o id **interno** (UUID), e ⛔ nunca o uid do Firebase —
                a coluna e uma chave estrangeira para `conta.tb001_usuario`.
            envio: o corpo validado da requisicao.
            co_versao_app: de `X-App-Version`.
            co_plataforma: de `X-Platform`.
        """
        parametros: dict[str, Any] = {
            "id_usuario": id_usuario,
            "dt_dia_local": dia_local(envio.visitado_em, envio.nu_offset_minuto),
            "dh_visita": envio.visitado_em,
            "nu_offset_minuto": envio.nu_offset_minuto,
            "id_desafio_dia": envio.id_desafio_dia,
            "co_motivo": envio.motivo,
            "co_desconhecido": envio.desconhecido,
            "co_versao_app": co_versao_app,
            "co_plataforma": co_plataforma,
            "js_motores": montar_js_motores(envio),
        }
        resultado = await self.sessao.execute(
            text(SQL_GRAVAR_IMPEDIDO), parametros
        )
        return resultado.first() is not None


#: As duas fontes de dias da chama, unidas.
#:
#: ⛔ **Isto NAO e um contador**, e essa e a decisao inteira: a correcao de
#: 08/2026 parou de persistir o total de dias justamente porque a segunda copia
#: da verdade era a origem do defeito. O dia impedido entra como **mais uma
#: linha de historico**, do mesmo jeito que uma partida — e o proximo recalculo
#: autoritativo continua sendo a unica autoridade.
SQL_DIAS_IMPEDIDOS = """
SELECT dt_dia_local AS dia
  FROM desafio_dia.vw007_desafio_impedido
 WHERE id_usuario = :id_usuario
"""


async def dias_impedidos(sessao: AsyncSession, *, id_usuario: str) -> list[date]:
    """Os dias que a pessoa **abriu** sem poder desafiar.

    ⚠️ Existe para `recalcular_chama` uni-los aos dias das partidas concluidas.
    Devolve lista (e nao conjunto) para que o chamador decida como unir — a
    ordem nao importa, mas a forma de juntar e dele.
    """
    resultado = await sessao.execute(
        text(SQL_DIAS_IMPEDIDOS), {"id_usuario": id_usuario}
    )
    return [linha.dia for linha in resultado]


__all__ = [
    "VERSAO_DO_FORMATO_DE_MOTORES",
    "SQL_GRAVAR_IMPEDIDO",
    "SQL_DIAS_IMPEDIDOS",
    "RepositorioImpedido",
    "dia_local",
    "montar_js_motores",
    "dias_impedidos",
]

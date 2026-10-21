"""Acesso a `log.tb003_aparelho` e `log.tb004_aparelho_dia` (T118 da spec 010).

Segue a regra de ouro do projeto: **escrita na tabela, leitura pela VIEW**, e
sempre com parâmetros nomeados (`:nome`) - nunca interpolação de string, que é
por onde entra SQL injection.

⚠️ **O SQL mora em constantes do módulo**, e não dentro dos métodos. É o que
deixa o teste rodá-lo de verdade num SQLite de memória
(`tests/unitarios/test_repositorio_aparelho.py`) com uma única troca, documentada
lá: o `CAST(... AS JSONB)`, que o SQLite não conhece.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.aparelhos.regras import versao_maior

#: Quantas voltas o registro do dia dá antes de desistir (ver `registrar_dia`).
#: Duas leituras do MESMO aparelho no MESMO instante já são raras; três seguidas
#: perdendo a corrida não acontecem - e, se acontecerem, perder uma leitura da
#: amostra é melhor do que prender a requisição num laço.
VOLTAS_DO_REGISTRO = 3


# ── O aparelho ───────────────────────────────────────────────────────────────

#: A linha do aparelho, sem os detalhes. `DO NOTHING`: quem só abriu o desafio
#: não sabe nada do aparelho, e não pode apagar o que a rota dos detalhes já
#: gravou.
SQL_GARANTIR_APARELHO = """
    INSERT INTO log.tb003_aparelho (id_aparelho, ic_legado, co_plataforma)
    VALUES (:id_aparelho, :ic_legado, :co_plataforma)
    ON CONFLICT (id_aparelho) DO NOTHING
"""

#: A linha do aparelho COM os detalhes. Cada detalhe é sobrescrito pelo mais
#: recente, inclusive com `NULL`: o `appInstanceId` some quando a pessoa recusa
#: o consentimento do Analytics, e manter o antigo seria guardar o que ela
#: recusou. ⚠️ A plataforma e o `ic_legado` NÃO são atualizados: uma instalação
#: não muda de sistema, e a linha legada nunca recebe detalhes (ela não tem
#: código para a rota dos detalhes a achar).
SQL_GRAVAR_DETALHES = """
    INSERT INTO log.tb003_aparelho
        (id_aparelho, ic_legado, co_plataforma, no_fabricante, no_modelo,
         co_abi, no_processador, qt_nucleos, nu_ram_mb, nu_tela_largura_dp,
         nu_tela_altura_dp, nu_densidade_tela, co_instancia_analytics)
    VALUES
        (:id_aparelho, FALSE, :co_plataforma, :no_fabricante, :no_modelo,
         :co_abi, :no_processador, :qt_nucleos, :nu_ram_mb, :nu_tela_largura_dp,
         :nu_tela_altura_dp, :nu_densidade_tela, :co_instancia_analytics)
    ON CONFLICT (id_aparelho) DO UPDATE SET
        no_fabricante          = EXCLUDED.no_fabricante,
        no_modelo              = EXCLUDED.no_modelo,
        co_abi                 = EXCLUDED.co_abi,
        no_processador         = EXCLUDED.no_processador,
        qt_nucleos             = EXCLUDED.qt_nucleos,
        nu_ram_mb              = EXCLUDED.nu_ram_mb,
        nu_tela_largura_dp     = EXCLUDED.nu_tela_largura_dp,
        nu_tela_altura_dp      = EXCLUDED.nu_tela_altura_dp,
        nu_densidade_tela      = EXCLUDED.nu_densidade_tela,
        co_instancia_analytics = EXCLUDED.co_instancia_analytics
"""


# ── O dia ────────────────────────────────────────────────────────────────────

SQL_VERSAO_DO_DIA = """
    SELECT co_versao_app
      FROM log.vw004_aparelho_dia
     WHERE id_aparelho = :id_aparelho
       AND dt_dia_local = :dt_dia_local
"""

#: A 1ª leitura do dia. `DO NOTHING` + `RETURNING`: se outra leitura do mesmo
#: aparelho criou a linha um instante antes, nada volta, e o registro dá mais
#: uma volta - agora pelo caminho do `UPDATE`, que compara as versões.
SQL_INSERIR_DIA = """
    INSERT INTO log.tb004_aparelho_dia
        (id_aparelho, dt_dia_local, id_usuario, co_versao_app, co_versao_so,
         co_idioma, nu_espaco_app_kb, js_espaco_app)
    VALUES
        (:id_aparelho, :dt_dia_local, :id_usuario, :co_versao_app, :co_versao_so,
         :co_idioma, :nu_espaco_app_kb, CAST(:js_espaco_app AS JSONB))
    ON CONFLICT (id_aparelho, dt_dia_local) DO NOTHING
    RETURNING id_aparelho
"""

#: As leituras seguintes do dia.
#:
#: ⚠️ **O `WHERE co_versao_app = :versao_lida` é a trava.** A versão final é
#: decidida em Python (a regra de qual é maior vive em `regras.py`, e não numa
#: segunda escrita em SQL), e só é gravada se a linha ainda tiver a versão que
#: foi lida. Se outra leitura a trocou no meio, nada volta e o registro relê.
#: Sem essa trava, duas leituras cruzadas poderiam fazer a versão DESCER - a
#: menor gravando por cima da maior que acabou de chegar.
#:
#: O resto, campo a campo:
#: * `id_usuario`: o último **conhecido**. Uma leitura de convidado depois de
#:   uma logada não apaga a pessoa do dia;
#: * `co_versao_so` e `co_idioma`: o mais recente, quando veio;
#: * o espaço: só a rota dos detalhes o informa (`:com_espaco`). A leitura do
#:   desafio não sabe dele, e não pode apagar o que os detalhes gravaram.
SQL_ATUALIZAR_DIA = """
    UPDATE log.tb004_aparelho_dia
       SET co_versao_app    = :co_versao_app,
           id_usuario       = COALESCE(:id_usuario, id_usuario),
           co_versao_so     = COALESCE(:co_versao_so, co_versao_so),
           co_idioma        = COALESCE(:co_idioma, co_idioma),
           nu_espaco_app_kb = CASE WHEN :com_espaco
                                   THEN :nu_espaco_app_kb
                                   ELSE nu_espaco_app_kb END,
           js_espaco_app    = CASE WHEN :com_espaco
                                   THEN CAST(:js_espaco_app AS JSONB)
                                   ELSE js_espaco_app END
     WHERE id_aparelho = :id_aparelho
       AND dt_dia_local = :dt_dia_local
       AND co_versao_app = :versao_lida
    RETURNING id_aparelho
"""


# ── A pessoa ─────────────────────────────────────────────────────────────────

SQL_ID_USUARIO = """
    SELECT id_usuario FROM conta.vw001_usuario
     WHERE co_identidade_externa = :uid
"""

#: O fuso da última partida da pessoa: o mesmo relógio que a chama usa
#: (`nu_offset_minuto_j1`, gravado em cada partida desde a 0006).
SQL_ULTIMO_OFFSET = """
    SELECT nu_offset_minuto_j1
      FROM partida.vw001_partida
     WHERE id_usuario = :id_usuario
       AND nu_offset_minuto_j1 IS NOT NULL
     ORDER BY dh_inicio DESC
     LIMIT 1
"""


class ErroDoRegistroDoDia(RuntimeError):
    """O registro do dia perdeu a corrida [VOLTAS_DO_REGISTRO] vezes seguidas.

    Existe para a falha ter **nome** no log: quem chama a engole (o registro
    nunca derruba a leitura do desafio), mas ela não pode sumir calada.
    """


class RepositorioAparelho:
    """Grava o aparelho e o dia dele, e lê o que o registro precisa saber."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def id_usuario_por_identidade(self, uid: str) -> Optional[str]:
        """O `id_usuario` interno a partir do uid do Firebase.

        `None` quando a conta ainda não existe aqui (o perfil não foi
        completado): para o registro, essa pessoa é um convidado.
        """
        resultado = await self.sessao.execute(text(SQL_ID_USUARIO), {"uid": uid})
        linha = resultado.mappings().first()
        return str(linha["id_usuario"]) if linha else None

    async def ultimo_offset_da_pessoa(self, id_usuario: str) -> Optional[int]:
        """O fuso da última partida da pessoa, ou `None` se ela nunca jogou.

        ⚠️ É o fuso do app 1.3, que não o manda em cabeçalho: o melhor palpite
        disponível é o relógio da última partida dela. Quem nunca jogou cai no
        dia UTC (ver `ServicoAparelho.registrar_visita`).
        """
        resultado = await self.sessao.execute(
            text(SQL_ULTIMO_OFFSET), {"id_usuario": id_usuario}
        )
        linha = resultado.mappings().first()
        return int(linha["nu_offset_minuto_j1"]) if linha else None

    async def garantir_aparelho(
        self, *, id_aparelho: str, ic_legado: bool, co_plataforma: str
    ) -> None:
        """Cria a linha do aparelho, se ainda não existe. Nunca a altera."""
        await self.sessao.execute(
            text(SQL_GARANTIR_APARELHO),
            {
                "id_aparelho": id_aparelho,
                "ic_legado": ic_legado,
                "co_plataforma": co_plataforma,
            },
        )

    async def gravar_detalhes(
        self, *, id_aparelho: str, co_plataforma: str, detalhes: dict[str, Any]
    ) -> None:
        """Cria ou atualiza a linha do aparelho com os detalhes que o app mandou.

        [detalhes] tem as chaves das colunas (`no_fabricante`, `qt_nucleos`...);
        a que faltar vai como `NULL`.
        """
        colunas = (
            "no_fabricante",
            "no_modelo",
            "co_abi",
            "no_processador",
            "qt_nucleos",
            "nu_ram_mb",
            "nu_tela_largura_dp",
            "nu_tela_altura_dp",
            "nu_densidade_tela",
            "co_instancia_analytics",
        )
        parametros = {coluna: detalhes.get(coluna) for coluna in colunas}
        await self.sessao.execute(
            text(SQL_GRAVAR_DETALHES),
            {**parametros, "id_aparelho": id_aparelho, "co_plataforma": co_plataforma},
        )

    async def registrar_dia(
        self,
        *,
        id_aparelho: str,
        dt_dia_local: date,
        id_usuario: Optional[str],
        co_versao_app: str,
        co_idioma: Optional[str],
        co_versao_so: Optional[str] = None,
        com_espaco: bool = False,
        nu_espaco_app_kb: Optional[int] = None,
        js_espaco_app: Optional[dict[str, int]] = None,
    ) -> str:
        """Grava a linha do dia do aparelho e devolve a versão que ficou nela.

        ═══════════════════════════════════════════════════════════════════
        ⚠️ UMA LINHA POR APARELHO POR DIA, COM A MAIOR VERSÃO
        ═══════════════════════════════════════════════════════════════════

        A garantia de "uma linha" é a chave primária `(id_aparelho,
        dt_dia_local)`: abrir o app cinco vezes no dia cai sempre na mesma.

        A garantia de "a maior versão" é esta volta, que é um *compare-and-swap*
        (troca só se ninguém trocou antes):

        1. lê a versão que a linha tem hoje;
        2. sem linha, tenta criá-la - e, se outra leitura a criou no mesmo
           instante, volta ao passo 1;
        3. com linha, decide em Python qual é a maior e grava **só se a linha
           ainda tem a versão lida** - e, se não tem, volta ao passo 1.

        ⚠️ Por que não um `ON CONFLICT DO UPDATE ... WHERE nova > antiga` de
        uma vez só, como no `data-model.md` §4.3: a comparação de versões em
        SQL teria de partir o texto em números (`1.10.0` > `1.9.0`, que o texto
        erra), e essa seria uma segunda escrita da regra de `regras.py`. A
        volta chega ao mesmo resultado com a regra num lugar só.

        [com_espaco] diz se esta chamada traz o espaço ocupado (só a rota dos
        detalhes traz); sem ele, o espaço gravado antes fica como está.

        Raises:
            ErroDoRegistroDoDia: a corrida foi perdida [VOLTAS_DO_REGISTRO]
                vezes seguidas.
        """
        # O JSONB viaja como TEXTO e o `CAST` do SQL o converte: é a forma que
        # o projeto já usa (`impedido.py`, `repositorio_envio.py`), e evita
        # depender de como cada driver adapta um dicionário.
        js_texto = (
            json.dumps(js_espaco_app, sort_keys=True)
            if js_espaco_app is not None
            else None
        )
        base = {
            "id_aparelho": id_aparelho,
            "dt_dia_local": dt_dia_local,
            "id_usuario": id_usuario,
            "co_versao_so": co_versao_so,
            "co_idioma": co_idioma,
            "nu_espaco_app_kb": nu_espaco_app_kb if com_espaco else None,
            "js_espaco_app": js_texto if com_espaco else None,
        }

        for _ in range(VOLTAS_DO_REGISTRO):
            lida = await self.sessao.execute(
                text(SQL_VERSAO_DO_DIA),
                {"id_aparelho": id_aparelho, "dt_dia_local": dt_dia_local},
            )
            linha = lida.mappings().first()

            if linha is None:
                criada = await self.sessao.execute(
                    text(SQL_INSERIR_DIA), {**base, "co_versao_app": co_versao_app}
                )
                if criada.first() is not None:
                    return co_versao_app
                # Outra leitura criou a linha no meio: relê e compara.
                continue

            versao_lida = str(linha["co_versao_app"])
            final = co_versao_app if versao_maior(co_versao_app, versao_lida) else versao_lida
            trocada = await self.sessao.execute(
                text(SQL_ATUALIZAR_DIA),
                {
                    **base,
                    "co_versao_app": final,
                    "versao_lida": versao_lida,
                    "com_espaco": com_espaco,
                },
            )
            if trocada.first() is not None:
                return final
            # A versão mudou entre a leitura e a escrita: relê.

        raise ErroDoRegistroDoDia(
            f"o dia {dt_dia_local} do aparelho {id_aparelho} perdeu a corrida "
            f"{VOLTAS_DO_REGISTRO} vezes seguidas"
        )

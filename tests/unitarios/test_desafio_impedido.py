"""O dia em que o desafio NAO COUBE no aplicativo — a tabela, a rota, a chama.

⚠️ **Tres coisas sao provadas aqui, e as tres ja falharam em algum lugar deste
projeto:**

  1. o **dia local** — a chama ja teve o defeito de contar em UTC, e uma partida
     das 21h no Brasil caia no dia seguinte;
  2. o **`CHECK` mais estreito que o cabecalho** — um `co_plataforma IN
     ('android','ios')` transformaria requisicao VALIDA (`web`) em erro de banco,
     e nada no CI acusaria;
  3. o **uid do Firebase gravado como `id_usuario`** — os dois sao "o usuario"
     na conversa, e sao coisas diferentes no banco.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from api.desafios.impedido import (
    SQL_DIAS_IMPEDIDOS,
    SQL_GRAVAR_IMPEDIDO,
    VERSAO_DO_FORMATO_DE_MOTORES,
    dia_local,
    montar_js_motores,
)
from api.desafios.modelos_envio import EnvioDeDesafioImpedido
from api.nucleo.dependencias import PLATAFORMAS_VALIDAS

RAIZ = Path(__file__).resolve().parents[2]
MIGRACAO = RAIZ / "migrations" / "versions" / "0021_desafio_impedido.py"
ROTAS = RAIZ / "api" / "desafios" / "rotas.py"


def _envio(**extra) -> EnvioDeDesafioImpedido:
    """Um envio valido minimo, com o que o caso quiser por cima."""
    base = {
        "motivo": "jogo_desconhecido",
        "visitado_em": datetime(2026, 9, 10, 23, 30, tzinfo=timezone.utc),
    }
    base.update(extra)
    return EnvioDeDesafioImpedido(**base)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O dia e o do RELOGIO DA PESSOA
# ═══════════════════════════════════════════════════════════════════════════


def test_o_dia_usa_o_fuso_de_quem_visitou():
    """⚠️ **O defeito que a chama JA TEVE, do outro lado.**

    23h30 UTC de 10/09 e **20h30 de 10/09** no Brasil (UTC-3). Contar em UTC
    daria 10/09 aqui por sorte; o caso que denuncia e o contrario — ver o
    seguinte.
    """
    assert dia_local(
        datetime(2026, 9, 10, 23, 30, tzinfo=timezone.utc), -180
    ) == date(2026, 9, 10)


def test_o_dia_VIRA_quando_o_fuso_manda():
    """⚠️ 01h de 11/09 em UTC ainda e **10/09** no Brasil.

    ⛔ Sem o offset, esta visita creditaria o dia 11 — e a pessoa que abriu o
    aplicativo na noite do dia 10 perderia a chama do dia 10.
    """
    assert dia_local(
        datetime(2026, 9, 11, 1, 0, tzinfo=timezone.utc), -180
    ) == date(2026, 9, 10)


def test_o_dia_avanca_para_quem_esta_a_leste():
    """O outro sentido: Toquio (UTC+9) as 22h UTC ja e o dia seguinte."""
    assert dia_local(
        datetime(2026, 9, 10, 22, 0, tzinfo=timezone.utc), 540
    ) == date(2026, 9, 11)


def test_sem_offset_vale_o_dia_utc():
    """⚠️ `None` e *"o aplicativo nao soube dizer"*, e nao um erro.

    O dia UTC e o melhor palpite disponivel — e nunca pior do que nao gravar
    linha nenhuma, que faria a pessoa perder a chama de verdade.
    """
    assert dia_local(
        datetime(2026, 9, 10, 23, 30, tzinfo=timezone.utc), None
    ) == date(2026, 9, 10)


def test_datetime_ingenuo_e_lido_como_utc():
    """Um instante sem fuso e o que o contrato da rota promete: UTC."""
    assert dia_local(datetime(2026, 9, 11, 1, 0), -180) == date(2026, 9, 10)


# ═══════════════════════════════════════════════════════════════════════════
# 2. `js_motores` — lista, versionada, e de vocabulario ABERTO
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_motores_o_json_e_nulo():
    """⛔ Nao se grava `{"motores": []}`: *"nao informou"* e *"informou que nao
    tem nenhum"* sao fatos diferentes, e um deles seria mentira."""
    assert montar_js_motores(_envio()) is None


def test_os_motores_viram_uma_LISTA_versionada():
    """⚠️ **Lista, e nao dicionario por jogo.**

    E a mesma forma que uma tabela filha teria, e e por isso que
    `jsonb_to_recordset` a abre em linhas. Um `{"damas": {"rust": "0.4.0"}}`
    poria o nome do jogo na POSICAO DE CHAVE, e toda consulta agregada passaria
    a ter de saber os jogos de antemao.
    """
    dado = json.loads(
        montar_js_motores(
            _envio(
                motores=[
                    {"co_jogo": "damas", "co_motor": "dart", "co_versao": "1.4.0"},
                    {"co_jogo": "damas", "co_motor": "rust", "co_versao": "0.4.0"},
                ]
            )
        )
    )
    assert dado["versao"] == VERSAO_DO_FORMATO_DE_MOTORES
    assert isinstance(dado["motores"], list)
    assert dado["motores"][1] == {
        "co_jogo": "damas",
        "co_motor": "rust",
        "co_versao": "0.4.0",
    }


def test_um_motor_DESCONHECIDO_e_guardado_e_nao_recusado():
    """⛔ **O vocabulario e aberto de proposito.**

    Um aplicativo mais novo que este servidor reporta motor que ele nunca ouviu
    falar — e recusar a linha perderia o diagnostico exatamente quando ele e
    mais interessante. Este caso existe para que ninguem "conserte" isso
    acrescentando uma lista de motores validos.
    """
    dado = json.loads(
        montar_js_motores(
            _envio(
                motores=[
                    {"co_jogo": "xadrez", "co_motor": "wasm", "co_versao": "9.9.9"}
                ]
            )
        )
    )
    assert dado["motores"] == [
        {"co_jogo": "xadrez", "co_motor": "wasm", "co_versao": "9.9.9"}
    ]


# ═══════════════════════════════════════════════════════════════════════════
# 3. O modelo do corpo
# ═══════════════════════════════════════════════════════════════════════════


def test_o_id_do_dia_e_OPCIONAL():
    """⚠️ Quem cai aqui pode nem ter conseguido ler a resposta do desafio.

    ⛔ Exigi-lo faria falhar justamente o caso que a rota existe para cobrir.
    """
    assert _envio().id_desafio_dia is None


def test_motivo_fora_do_vocabulario_e_recusado():
    """O `CHECK` da coluna e o `Literal` do modelo dizem a mesma coisa — e o
    modelo recusa **antes** de o banco precisar recusar."""
    with pytest.raises(Exception):
        _envio(motivo="porque_sim")


def test_o_corpo_NAO_aceita_versao_do_aplicativo():
    """⛔ **Versao e plataforma sao dos CABECALHOS.**

    Aceita-las tambem no corpo criaria uma segunda fonte que pode discordar da
    primeira: o aplicativo teria dois lugares para errar, e o diagnostico nao
    saberia em qual acreditar.
    """
    campos = set(EnvioDeDesafioImpedido.model_fields)
    assert "co_versao_app" not in campos
    assert "co_plataforma" not in campos
    assert "versao_app" not in campos


# ═══════════════════════════════════════════════════════════════════════════
# 4. O SQL
# ═══════════════════════════════════════════════════════════════════════════


def test_a_gravacao_e_idempotente():
    """⚠️ Abrir o aplicativo cinco vezes no mesmo dia grava UMA linha.

    E aqui `DO NOTHING` e a escolha certa, ao contrario do ingestor de partidas:
    um dia impedido **nao tem segunda versao**.
    """
    assert "ON CONFLICT (id_usuario, dt_dia_local) DO NOTHING" in SQL_GRAVAR_IMPEDIDO


def test_a_versao_exigida_vem_do_BANCO():
    """⚠️ O outro lado do par de diagnostico e do **servidor**.

    Aceita-la do corpo faria o diagnostico depender de quem esta sendo
    diagnosticado.
    """
    assert "co_versao_minima" in SQL_GRAVAR_IMPEDIDO
    assert "vw001_desafio" in SQL_GRAVAR_IMPEDIDO
    assert ":co_versao_minima_exigida" not in SQL_GRAVAR_IMPEDIDO


def test_a_leitura_e_pela_VIEW():
    """A convencao do projeto: escrita na tabela, leitura sempre pela VIEW."""
    assert "vw007_desafio_impedido" in SQL_DIAS_IMPEDIDOS


def test_a_chama_UNE_as_duas_fontes():
    """🔒 Sem isto a tabela existiria e **nao serviria para nada**.

    ⚠️ O defeito seria mudo: as linhas apareceriam no banco, e a chama da pessoa
    continuaria quebrando — ninguem ligaria as duas coisas.
    """
    fonte = (RAIZ / "api" / "sincronizacao" / "repositorio.py").read_text(
        encoding="utf-8"
    )
    assert "vw007_desafio_impedido" in fonte, (
        "⛔ `recalcular_chama` parou de unir os dias impedidos. A tabela vira "
        "deposito, e a chama volta a quebrar para quem nao pode participar."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5. 🔒 Os dois cadeados
# ═══════════════════════════════════════════════════════════════════════════


def test_o_CHECK_da_plataforma_bate_com_o_CABECALHO():
    """🔒 **Um `CHECK` mais estreito que o cabecalho e uma bomba-relogio.**

    ⚠️ O primeiro rascunho desta migracao aceitava so `android` e `ios`, e
    `PLATAFORMAS_VALIDAS` tem **tres** valores: uma requisicao perfeitamente
    valida vinda de `web` viraria erro de banco — um 500 que nenhum teste de
    unidade veria, porque os testes nao passam pelo Postgres.

    ⚠️ E o mesmo padrao "contrato x realidade" do cadeado da uniao de XP: os
    dois lugares tem de dizer a mesma coisa, e quem os aproximar de novo tem de
    fazer isso **de proposito**.
    """
    fonte = MIGRACAO.read_text(encoding="utf-8")
    casa = re.search(
        r"ck002_plataforma CHECK \(co_plataforma IS NULL\s*OR co_plataforma IN \(([^)]*)\)",
        fonte,
    )
    assert casa, "⛔ o CHECK da plataforma sumiu da migracao"
    do_check = set(re.findall(r"'([a-z]+)'", casa.group(1)))
    assert do_check == PLATAFORMAS_VALIDAS, (
        f"o CHECK aceita {sorted(do_check)} e o cabecalho aceita "
        f"{sorted(PLATAFORMAS_VALIDAS)}. ⛔ O lado mais estreito transforma "
        "requisicao valida em erro de banco."
    )


def test_nenhuma_rota_grava_o_uid_do_FIREBASE_como_id_usuario():
    """🔒 **O uid do Firebase NAO e o `id_usuario`.**

    ⚠️ **Este cadeado nasce de um defeito real, achado em 10/09/2026**, nas
    rotas que eu mesmo tinha entregue: elas passavam `identidade.uid` — a string
    do Firebase — para colunas `UUID` que sao chave estrangeira de
    `conta.tb001_usuario`. Toda resolucao e toda dica teriam estourado no `des`,
    e ⛔ **a suite passava**, porque os testes trocam a dependencia por um fake e
    nunca veem o tipo real.

    Quem resolve o id interno e `usuario_autenticado` / `usuario_opcional`
    (`api/nucleo/dependencias_conta_nuvem.py`), que busca a linha pelo
    `co_identidade_externa`.

    ⚠️ **Le `ast`, e nao texto** — a licao repetida seis vezes neste projeto: um
    `"identidade.uid" in fonte` reprovaria esta propria docstring, que menciona o
    defeito justamente para explica-lo.
    """
    arvore = ast.parse(ROTAS.read_text(encoding="utf-8"))
    culpadas: list[str] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        for argumento in no.keywords:
            if argumento.arg != "id_usuario":
                continue
            valor = argumento.value
            # `id_usuario=identidade.uid` — direto.
            if isinstance(valor, ast.Attribute) and valor.attr == "uid":
                culpadas.append(f"linha {valor.lineno}")
            # `id_usuario=identidade.uid if identidade else None` — o ternario.
            if isinstance(valor, ast.IfExp):
                for ramo in (valor.body, valor.orelse):
                    if isinstance(ramo, ast.Attribute) and ramo.attr == "uid":
                        culpadas.append(f"linha {ramo.lineno}")

    assert not culpadas, (
        f"⛔ {ROTAS.name} passa o uid do Firebase como id_usuario em "
        f"{', '.join(culpadas)}. Use `usuario_autenticado`/`usuario_opcional` e "
        "`dono.id_usuario` — a coluna e UUID e aponta para conta.tb001_usuario."
    )


def test_o_cadeado_do_uid_ENXERGA_o_defeito():
    """⚠️ **Um cadeado que nunca viu o defeito nao prova nada.**

    Este caso mostra o cadeado acima reprovando o codigo errado — sem ele, um
    `ast.walk` que deixasse de achar `ast.Call` passaria verde para sempre.
    """
    codigo = (
        "servico.registrar(id_desafio=x, id_usuario=identidade.uid, envio=e)\n"
        "outro.montar(id_usuario=identidade.uid if identidade else None)\n"
    )
    arvore = ast.parse(codigo)
    achados = 0
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        for argumento in no.keywords:
            if argumento.arg != "id_usuario":
                continue
            valor = argumento.value
            if isinstance(valor, ast.Attribute) and valor.attr == "uid":
                achados += 1
            if isinstance(valor, ast.IfExp):
                for ramo in (valor.body, valor.orelse):
                    if isinstance(ramo, ast.Attribute) and ramo.attr == "uid":
                        achados += 1
    assert achados == 2, (
        "a varredura deixou de enxergar o padrao que ela existe para pegar"
    )

"""T024/T025 - os modelos de `api/desafios/` nao podem divergir das migracoes.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

Os vocabularios do Desafio do Dia estao escritos **duas vezes**: como `CHECK` na
migracao e como `Literal` no modelo. Isso e proposital — o `CHECK` guarda o banco
e o `Literal` guarda o codigo, e cada um pega o erro num momento diferente.

O preco de escrever duas vezes e que as duas copias podem se separar, e a
separacao **nao da erro**: o Pydantic aceitaria um valor que o banco recusa (a
linha falha no `INSERT`, longe de onde o defeito esta), ou recusaria um valor que
o banco aceita (linhas legitimas viram 422 sem explicacao).

Estes testes leem o `CHECK` da migracao e o `Literal` do modelo e exigem que os
dois digam a mesma coisa.

⚠️ **Nao ha banco aqui.** Le-se o arquivo de migracao, que ainda e proposta.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from api.desafios import modelos_evento as ev
from api.desafios import modelos_producao as prod

RAIZ = Path(__file__).resolve().parents[2]
MIG_DESAFIO = RAIZ / "migrations" / "versions" / "0018_schema_desafio.py"
MIG_DESAFIO_DIA = RAIZ / "migrations" / "versions" / "0019_schema_desafio_dia.py"


def _valores_do_check(migracao: Path, constraint: str) -> set[str]:
    """Os literais de um `CHECK (... IN ('a', 'b'))` da migracao.

    Procura pelo nome da constraint e recorta ate o `IN (...)` seguinte. E frouxo
    de proposito: se o formato do arquivo mudar a ponto de isto nao casar, o
    teste falha por "constraint nao encontrada", que e um aviso claro — bem
    melhor que devolver um conjunto vazio e passar.
    """
    fonte = migracao.read_text(encoding="utf-8")
    casa = re.search(
        rf"CONSTRAINT\s+{constraint}\s+CHECK\s*\([^)]*?IN\s*\((.*?)\)",
        fonte,
        re.S | re.I,
    )
    assert casa, f"{constraint} nao encontrada em {migracao.name}"
    return set(re.findall(r"'([a-z_]+)'", casa.group(1)))


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os vocabularios do schema `desafio`
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "constraint, literal, apelido",
    [
        ("ck001_formato_posicao", prod.FormatoPosicao, "FormatoPosicao"),
        ("ck002_personagem", prod.Personagem, "Personagem"),
        ("ck003_curadoria", prod.EstadoCuradoria, "EstadoCuradoria"),
    ],
)
def test_o_literal_bate_com_o_check_de_tb001(constraint, literal, apelido) -> None:
    """Cada `Literal` do modelo tem exatamente os valores do `CHECK`."""
    do_banco = _valores_do_check(MIG_DESAFIO, constraint)
    do_codigo = set(get_args(literal))
    assert do_codigo == do_banco, (
        f"{apelido} divergiu de {constraint}: "
        f"so no codigo={do_codigo - do_banco} · so no banco={do_banco - do_codigo}"
    )


def test_a_normalizacao_bate_com_o_check_composto() -> None:
    """`ck003_faixa` e um `CHECK` de tres ramos, um por normalizacao.

    Ele nao tem a forma `IN (...)`, entao a leitura e outra: procura-se
    `co_normalizacao = 'x'` em cada ramo. E o cadeado importa justamente aqui —
    este e o `CHECK` mais dificil de ler do schema, e o mais facil de deixar
    para tras ao acrescentar uma normalizacao nova.
    """
    fonte = MIG_DESAFIO.read_text(encoding="utf-8")
    do_banco = set(re.findall(r"co_normalizacao\s*=\s*'([a-z_]+)'", fonte))
    do_codigo = set(get_args(prod.Normalizacao))
    assert do_codigo == do_banco, (
        f"Normalizacao divergiu do ck003_faixa: "
        f"so no codigo={do_codigo - do_banco} · so no banco={do_banco - do_codigo}"
    )


@pytest.mark.parametrize(
    "constraint, literal, apelido",
    [
        ("ck001_direcao", prod.DirecaoFeito, "DirecaoFeito"),
        ("ck002_procedencia", prod.ProcedenciaFeito, "ProcedenciaFeito"),
    ],
)
def test_o_literal_bate_com_o_check_do_catalogo(constraint, literal, apelido) -> None:
    """O catalogo de feitos tem duas listas fechadas, e as duas viajam ao app."""
    do_banco = _valores_do_check(MIG_DESAFIO, constraint)
    do_codigo = set(get_args(literal))
    assert do_codigo == do_banco, (
        f"{apelido} divergiu de {constraint}: "
        f"so no codigo={do_codigo - do_banco} · so no banco={do_banco - do_codigo}"
    )


def test_marco_atingido_continua_no_vocabulario() -> None:
    """🔒 A direcao que faltava, e que custou duas correcoes §8b em 09/09/2026.

    Ela nao e um detalhe: e a direcao de "venceu", "empatou", "partida perfeita"
    e "desafio concluido" — quatro das dezesseis chaves do catalogo. Sem ela, o
    cadeado 4 reprova e nenhum desafio de marco pode ser escrito.
    """
    assert "marco_atingido" in get_args(prod.DirecaoFeito)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Os vocabularios do schema `desafio_dia`
# ═══════════════════════════════════════════════════════════════════════════


def test_a_auditoria_bate_com_o_check() -> None:
    """Os tres estados do que o servidor achou quando reconferiu."""
    do_banco = _valores_do_check(MIG_DESAFIO_DIA, "ck003_auditoria")
    do_codigo = set(get_args(ev.EstadoAuditoria))
    assert do_codigo == do_banco, (
        f"so no codigo={do_codigo - do_banco} · so no banco={do_banco - do_codigo}"
    )


def test_os_numeros_de_tipo_de_xp_batem_com_a_dimensao() -> None:
    """🔒 As constantes `XP_*` sao os `nu_tipo_xp` semeados pela migracao.

    ⚠️ Um numero de dimensao **nunca muda de significado** depois de gravado.
    Se alguem reordenar a lista da migracao, as constantes daqui passariam a
    apontar para outra coisa — e o extrato de XP mostraria "parcela de tempo"
    onde ha merito, sem erro nenhum.
    """
    fonte = MIG_DESAFIO_DIA.read_text(encoding="utf-8")
    casa = re.search(
        r"INSERT INTO desafio_dia\.tb901_tipo_xp_desafio(.*?);", fonte, re.S
    )
    assert casa, "o INSERT da dimensao de tipo de XP nao foi encontrado"
    # Pares (numero, codigo) das tuplas semeadas.
    do_banco = {
        codigo: int(numero)
        for numero, codigo in re.findall(r"\(\s*(\d+),\s*'([a-z_]+)'", casa.group(1))
    }

    do_codigo = {
        "base": ev.XP_BASE,
        "tentativas": ev.XP_TENTATIVAS,
        "tempo": ev.XP_TEMPO,
        "dica": ev.XP_DICA,
        "merito": ev.XP_MERITO,
        "medida": ev.XP_MEDIDA,
        "consolo": ev.XP_CONSOLO,
        "ajuste": ev.XP_AJUSTE,
        "desconhecido": ev.XP_DESCONHECIDO,
    }
    assert do_codigo == do_banco, (
        f"as constantes XP_* divergiram da dimensao.\n"
        f"  codigo={do_codigo}\n  banco ={do_banco}"
    )


def test_os_dois_tipos_com_feito_sao_os_do_check() -> None:
    """`TIPOS_XP_COM_FEITO` espelha o `ck003_feito` da migracao.

    O `CHECK` diz `(nu_feito IS NULL) <> (nu_tipo_xp IN (5, 6))`. Se um tipo novo
    passar a carregar feito, e preciso mexer nos dois — e este teste e quem
    lembra.
    """
    fonte = MIG_DESAFIO_DIA.read_text(encoding="utf-8")
    casa = re.search(r"nu_tipo_xp\s+IN\s*\(([\d,\s]+)\)", fonte)
    assert casa, "o ck003_feito nao foi encontrado"
    do_banco = tuple(int(n) for n in re.findall(r"\d+", casa.group(1)))
    assert ev.TIPOS_XP_COM_FEITO == do_banco, (
        f"codigo={ev.TIPOS_XP_COM_FEITO} · banco={do_banco}"
    )


def test_o_piso_e_o_teto_batem_com_o_check_de_nu_xp() -> None:
    """18 e 30 estao no `CHECK` da resolucao, e sao regra de produto.

    18 = piso por resolver (`XP = 18 + 12 x Q`, com `Q` em [0,1]).
    30 = teto do dia, que e **da colecao** e entra como linha de ajuste.
    """
    fonte = MIG_DESAFIO_DIA.read_text(encoding="utf-8")
    casa = re.search(r"nu_xp\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)", fonte)
    assert casa, "o ck001_xp da resolucao nao foi encontrado"
    assert (int(casa.group(1)), int(casa.group(2))) == (
        ev.XP_PISO_POR_RESOLVER,
        ev.XP_TETO_DO_DIA,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. As VIEWs declaradas existem mesmo
# ═══════════════════════════════════════════════════════════════════════════


def _views_criadas_por_todas_as_migracoes() -> set[str]:
    """Toda VIEW criada por QUALQUER migracao, em minusculas.

    ⚠️ **Varre a pasta, e nao um arquivo escolhido a mao** (11/09/2026, T049e).
    Ate aqui o cadeado comparava as constantes `VW_` de `modelos_producao` com a
    `0018` e as de `modelos_evento` com a `0019` — e a `0022` criou a
    `desafio.vw904_motor`, que existe de verdade e seria acusada de nao existir.

    ⚠️ **O defeito do outro sentido e pior**, e e o que este arquivo ja carrega
    na docstring de `migracoes_dos_schemas`: uma VIEW criada numa migracao nova e
    apagada por engano de uma constante continuaria "conferida" contra um arquivo
    que nao a menciona. Varrer tudo resolve os dois.
    """
    criadas: set[str] = set()
    for arquivo in sorted(MIG_DESAFIO.parent.glob("[0-9]*.py")):
        fonte = arquivo.read_text(encoding="utf-8")
        criadas |= {
            nome.lower()
            for nome in re.findall(
                r"CREATE VIEW\s+([a-z_][a-z0-9_.]*)", fonte, re.I
            )
        }
    return criadas


@pytest.mark.parametrize(
    "modulo",
    [prod, ev],
    ids=["desafio", "desafio_dia"],
)
def test_toda_VW_declarada_e_criada_pela_migracao(modulo) -> None:
    """🔒 Uma constante apontando para VIEW inexistente so falha em runtime.

    E falha longe: no primeiro `SELECT` que a use, com um erro de "relation does
    not exist" que nao diz quem escreveu o nome errado.
    """
    criadas = _views_criadas_por_todas_as_migracoes()
    declaradas = {
        valor
        for nome, valor in vars(modulo).items()
        if nome.startswith("VW_") and isinstance(valor, str)
    }
    assert declaradas, "o modulo nao declara VIEW nenhuma"
    faltando = declaradas - criadas
    assert not faltando, f"VIEWs declaradas que a migracao nao cria: {faltando}"


def test_toda_TB_declarada_e_criada_pela_migracao() -> None:
    """O mesmo, para as tabelas em que a API escreve.

    ⚠️ So `modelos_evento` declara tabela, e e de proposito: no schema `desafio`
    quem escreve e o job, e uma constante com o nome da tabela ali seria um
    convite a le-la direto, furando a convencao de ler pela VIEW.
    """
    fonte = MIG_DESAFIO_DIA.read_text(encoding="utf-8")
    criadas = {
        nome.lower()
        for nome in re.findall(r"CREATE TABLE\s+([a-z_][a-z0-9_.]*)", fonte, re.I)
    }
    declaradas = {
        valor
        for nome, valor in vars(ev).items()
        if nome.startswith("TB_") and isinstance(valor, str)
    }
    assert declaradas
    assert not declaradas - criadas, f"faltando: {declaradas - criadas}"

    assert not [
        nome for nome in vars(prod) if nome.startswith("TB_")
    ], "modelos_producao declarou tabela — a API nao escreve no schema `desafio`"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Os modelos aceitam o que devem e recusam o que nao devem
# ═══════════════════════════════════════════════════════════════════════════


def test_a_taxa_da_regua_e_calculada_e_nao_guardada() -> None:
    """14 de 20 = 0,7. Guardar a divisao permitiria os tres numeros discordarem."""
    from datetime import datetime, timezone

    medicao = prod.MedicaoDaRegua(
        co_personagem="pita",
        nu_execucoes=20,
        nu_resolveu=14,
        co_versao_perfil="perfil-2026-09",
        co_versao_motor="pontinhos-py-abcdef12",
        dh_medicao=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )
    assert medicao.taxa == pytest.approx(0.7)


def test_personagem_fora_da_lista_e_recusado() -> None:
    """O `Literal` recusa antes de o banco precisar recusar.

    ⚠️ E a diferenca importa: aqui o erro aponta para quem montou o objeto; no
    banco, ele apareceria como um `INSERT` que falha dentro do job, com o
    diagnostico a duas camadas de distancia de onde o valor nasceu.
    """
    from datetime import datetime, timezone

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        prod.MedicaoDaRegua(
            co_personagem="magno_jr",  # nao existe
            nu_execucoes=20,
            nu_resolveu=14,
            co_versao_perfil="perfil-2026-09",
            co_versao_motor="pontinhos-py-abcdef12",
            dh_medicao=datetime(2026, 9, 9, tzinfo=timezone.utc),
        )


def test_a_linha_de_merito_sabe_que_e_de_feito() -> None:
    """`e_linha_de_feito` espelha o `ck003_feito`, e existe para nao repetir 5 e 6."""
    from datetime import datetime, timezone
    from decimal import Decimal
    from uuid import uuid4

    comum = dict(
        id_xp_desafio=uuid4(),
        id_desafio_dia=uuid4(),
        id_usuario=uuid4(),
        vr_xp=Decimal("1.800"),
        dh_registro=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )
    merito = ev.LinhaDeXp(
        **comum, nu_tipo_xp=ev.XP_MERITO, co_tipo_xp="merito", nu_feito=10
    )
    tempo = ev.LinhaDeXp(**comum, nu_tipo_xp=ev.XP_TEMPO, co_tipo_xp="tempo")

    assert merito.e_linha_de_feito is True
    assert tempo.e_linha_de_feito is False


def test_o_xp_da_resolucao_fica_entre_o_piso_e_o_teto() -> None:
    """Menos de 18 seria XP abaixo do piso de quem resolveu; mais de 30, do teto."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from pydantic import ValidationError

    comum = dict(
        id_resolucao=uuid4(),
        id_desafio_dia=uuid4(),
        id_usuario=uuid4(),
        id_tentativa=uuid4(),
        nu_lance_cumpre_desafio=7,
        nu_versao_catalogo=1,
        dh_resolucao=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )
    assert ev.Resolucao(**comum, nu_xp=27).nu_xp == 27
    for fora in (17, 31):
        with pytest.raises(ValidationError):
            ev.Resolucao(**comum, nu_xp=fora)

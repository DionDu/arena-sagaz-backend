"""🔒 CADEADO 4 — o catalogo de feitos do BANCO contra o do APLICATIVO (T026).

═══════════════════════════════════════════════════════════════════════════
⛔ NIVEL DE CI: ESTE CADEADO NUNCA PULA
═══════════════════════════════════════════════════════════════════════════

Nao ha `skip` aqui, nem condicional, nem "se o arquivo existir". Se o manifesto
sumir, o teste **falha** — e e o comportamento correto: um cadeado que se
desliga sozinho quando o alvo some e um cadeado que nao guarda nada.

⚠️ **E ele nao precisa do outro repositorio no disco.** Essa e a licao inteira do
RF-DES-143a: "o CI compara entre os repositorios" nao e executavel, porque cada
repositorio roda sozinho. O que e executavel e cada lado conferir a **sua** copia
contra um manifesto versionado — `contratos/catalogo_feitos.json`, que viaja com
este repositorio.

    fonte da verdade   lib/core/feitos/catalogo_feitos.dart   (o aplicativo)
            ↓ dart run tool/gerar_manifesto_feitos.dart
    manifesto          contratos/catalogo_feitos.json         (as duas copias)
            ↓ este teste
    banco              migracao 0018, dimensao tb902_catalogo_feito

═══════════════════════════════════════════════════════════════════════════
O QUE ELE PEGA, E QUE NADA MAIS PEGARIA
═══════════════════════════════════════════════════════════════════════════

Uma chave que exista de um lado e nao do outro **nao da erro em lugar nenhum**
ate a hora de pontuar — e ai falha no aparelho de alguem, com o desafio ja
resolvido. Foi por isso que o dono desfez o JSON solto: *"um catalogo que ninguem
referencia nao e catalogo"*.

E a divergencia mais silenciosa de todas e a de **direcao**: um feito marcado
`maior_melhor` de um lado e `menor_melhor` do outro nao produz erro nenhum. So
paga mais XP a quem jogou pior.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MANIFESTO = RAIZ / "contratos" / "catalogo_feitos.json"
#: Onde as migracoes vivem.
#:
#: ⛔ **Todas elas, e nao so a `0018`.** Ate 12/09/2026 este cadeado olhava so a
#: migracao que semeou a dimensao — o que estava certo enquanto ela era a unica a
#: mexer no catalogo. Deixou de estar quando `maior_cadeia_capturada` entrou pela
#: `0023`: ⚠️ **migracao aplicada nao se edita**, entao chave nova sempre chega
#: por arquivo novo, e um cadeado presa a um arquivo so acusaria divergencia em
#: toda chave futura — e ensinaria a ignora-lo.
MIGRACOES = RAIZ / "migrations" / "versions"

# As colunas da dimensao, na ordem em que a migracao as insere.
COLUNAS = (
    "nu_feito",
    "co_feito",
    "no_feito",
    "co_unidade",
    "co_direcao",
    "co_procedencia",
    "co_jogo",
)


def _do_manifesto() -> dict[int, dict[str, object]]:
    """As linhas do manifesto, indexadas por `nu_feito`.

    ⛔ Sem `skipif`: manifesto ausente e **falha**, nao motivo para pular.
    """
    assert MANIFESTO.is_file(), (
        f"o manifesto do catalogo de feitos nao esta em {MANIFESTO}. "
        "Ele e gerado no frontend por `dart run tool/gerar_manifesto_feitos.dart`, "
        "que escreve as duas copias. Sem ele, este cadeado nao tem contra o que "
        "comparar — e por isso ele FALHA em vez de pular."
    )
    dados = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    return {linha["nu_feito"]: linha for linha in dados["feitos"]}


def _da_migracao() -> dict[int, dict[str, object]]:
    """As linhas que as migracoes semeiam em `tb902_catalogo_feito`.

    Le os `INSERT` dos arquivos. Nao ha banco nesta suite, e nao precisa haver: o
    que se quer guardar e o que as migracoes **dizem**, que e o que o banco vai
    ter.

    ⚠️ **Le INSERT, e so INSERT.** Um `DELETE` ou um `UPDATE` numa migracao
    futura passaria despercebido aqui. E aceitavel porque a dimensao e semeada,
    nunca remendada — e porque o `downgrade` da `0023` explica por que apagar uma
    linha ja apontada por um desafio publicado nao e uma operacao normal.
    """
    assert MIGRACOES.is_dir(), f"as migracoes nao estao em {MIGRACOES}"

    corpo = ""
    encontrou = False
    for arquivo in sorted(MIGRACOES.glob("*.py")):
        fonte = arquivo.read_text(encoding="utf-8")
        for casa in re.finditer(
            r"INSERT INTO desafio\.tb902_catalogo_feito(.*?)\"\"\"", fonte, re.S
        ):
            corpo += casa.group(1)
            encontrou = True

    assert encontrou, (
        "nenhum INSERT de tb902_catalogo_feito foi encontrado nas migracoes. "
        "Ou ele sumiu, ou o formato mudou a ponto de este cadeado ter deixado "
        "de olhar — as duas coisas sao problema."
    )

    linhas: dict[int, dict[str, object]] = {}
    # Cada tupla e `( numero, 'co', 'no', 'unidade', 'direcao', 'proc', jogo)`,
    # e ela atravessa duas linhas no arquivo. `[^()]*` casa tudo menos
    # parenteses, que e o que separa uma tupla da seguinte.
    for tupla in re.findall(r"\(\s*(\d+,[^()]*?)\)", corpo, re.S):
        valores = _valores(tupla)
        assert len(valores) == len(COLUNAS), (
            f"tupla com {len(valores)} valores, esperado {len(COLUNAS)}: {tupla!r}"
        )
        registro = dict(zip(COLUNAS, valores))
        linhas[int(registro["nu_feito"])] = registro
    return linhas


def _valores(tupla: str) -> list[object]:
    """Separa os valores de uma tupla de `VALUES`, respeitando as aspas.

    Simples de proposito: os valores deste `INSERT` sao numero, texto entre aspas
    simples ou `NULL` — nao ha virgula dentro de texto, nem funcao, nem
    subconsulta. Se um dia houver, o `assert` de contagem acima acusa.
    """
    saida: list[object] = []
    for bruto in tupla.split(","):
        limpo = bruto.strip()
        if not limpo:
            continue
        if limpo.upper() == "NULL":
            saida.append(None)
        elif limpo.startswith("'"):
            saida.append(limpo.strip("'"))
        else:
            saida.append(int(limpo))
    return saida


# ═══════════════════════════════════════════════════════════════════════════
# Os casos
# ═══════════════════════════════════════════════════════════════════════════


def test_a_varredura_enxerga_alguma_coisa() -> None:
    """Antes de guardar, provar que esta olhando.

    Um cadeado que compara dois conjuntos vazios passa sempre. Este caso e o que
    o impede de virar decoracao no dia em que um dos dois formatos mudar.
    """
    assert len(_do_manifesto()) >= 10, "o manifesto veio quase vazio"
    assert len(_da_migracao()) >= 10, "a leitura da migracao veio quase vazia"


def test_as_MESMAS_chaves_dos_dois_lados() -> None:
    """🔒 Nenhuma chave a mais, nenhuma a menos.

    ⚠️ Chave que so existe no banco e coluna que ninguem escreve. Chave que so
    existe no aplicativo e uma FK que vai estourar no primeiro desafio que a use.
    """
    manifesto = _do_manifesto()
    migracao = _da_migracao()

    so_no_banco = {n: migracao[n]["co_feito"] for n in migracao.keys() - manifesto.keys()}
    so_no_app = {n: manifesto[n]["co_feito"] for n in manifesto.keys() - migracao.keys()}

    assert not so_no_banco and not so_no_app, (
        "o catalogo de feitos divergiu entre o aplicativo e o banco.\n"
        f"  so na migracao (0018): {so_no_banco}\n"
        f"  so no manifesto (app): {so_no_app}\n"
        "Conserto: rode `dart run tool/gerar_manifesto_feitos.dart` no frontend "
        "e alinhe o INSERT da 0018 com o manifesto."
    )


@pytest.mark.parametrize("coluna", ["co_feito", "co_unidade", "co_direcao", "co_procedencia", "co_jogo"])
def test_cada_coluna_bate_chave_a_chave(coluna: str) -> None:
    """🔒 Um caso por coluna, para a falha dizer QUAL atributo divergiu.

    ⚠️ **`co_direcao` e o mais perigoso dos cinco.** Um feito marcado
    `maior_melhor` de um lado e `menor_melhor` do outro nao produz erro nenhum —
    so paga mais XP a quem jogou pior. E `co_procedencia` vem logo atras: trocar
    `sessao` por `tabuleiro` faria o servidor tentar recalcular o tempo a partir
    do log de lances, achar "divergencia" onde nao ha, e encher de ruido o alerta
    que a curadoria precisa ler.
    """
    manifesto = _do_manifesto()
    migracao = _da_migracao()

    divergentes = {
        numero: (manifesto[numero][coluna], migracao[numero][coluna])
        for numero in manifesto.keys() & migracao.keys()
        if manifesto[numero][coluna] != migracao[numero][coluna]
    }
    assert not divergentes, (
        f"`{coluna}` divergiu (nu_feito: app x banco): {divergentes}"
    )


def test_o_sentinela_9999_esta_nos_dois() -> None:
    """⛔ Inegociavel, e a licao e da `0011`.

    Sem um destino valido, um aplicativo MAIS NOVO que o backend estoura a FK,
    toma 500, e o evento fica preso **para sempre** na fila de sincronizacao
    daquele aparelho — a partida da pessoa nunca sobe.
    """
    for lado, linhas in (("manifesto", _do_manifesto()), ("migracao", _da_migracao())):
        assert 9999 in linhas, f"o sentinela 9999 nao esta no {lado}"
        assert linhas[9999]["co_feito"] == "desconhecido"


def test_a_numeracao_por_blocos_foi_respeitada() -> None:
    """Comuns 1-9, Pontinhos 10-19, velha 20-29, damas 30-39, sessao 40-49.

    ⚠️ Nao e organizacao por gosto: um `nu_feito` **nunca muda de significado**
    depois de gravado, entao numeracao corrida obrigaria a intercalar um jogo
    novo no meio dos numeros de outro — e a numeracao deixaria de dizer nada.

    O bloco e definido pelo `co_jogo` da linha, nao pelo numero: assim o teste
    pega tanto o numero fora do bloco quanto o jogo trocado.
    """
    faixas = {
        None: (1, 9),
        "pontinhos": (10, 19),
        "velha": (20, 29),
        "damas": (30, 39),
    }
    fora: list[str] = []
    for numero, linha in _do_manifesto().items():
        if numero == 9999:
            continue
        jogo = linha["co_jogo"]
        if jogo is None:
            # Feito comum: 1-9 se for de tabuleiro, 40-49 se for de sessao.
            faixa = (40, 49) if linha["co_procedencia"] == "sessao" else faixas[None]
        else:
            assert jogo in faixas, f"jogo desconhecido no catalogo: {jogo!r}"
            faixa = faixas[jogo]
        if not faixa[0] <= numero <= faixa[1]:
            fora.append(
                f"{linha['co_feito']} (nu_feito={numero}, jogo={jogo}) "
                f"deveria estar em {faixa}"
            )
    assert not fora, "numeros fora do bloco: " + "; ".join(fora)


def test_o_manifesto_diz_de_onde_veio() -> None:
    """O arquivo tem de se identificar — quem o encontrar daqui a um ano precisa
    saber que ele e gerado, e por quem.

    Um JSON sem procedencia vira "arquivo que alguem editou a mao um dia", e a
    proxima pessoa o edita a mao de novo.
    """
    dados = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    assert "gerar_manifesto_feitos.dart" in dados["de_documento"]
    assert dados["co_fonte_da_verdade"].endswith("catalogo_feitos.dart")
    assert isinstance(dados["nu_versao_catalogo"], int)

"""T018 - a imagem e o servico do JOB EM BATCH do Desafio do Dia (RF-DES-011a).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTES TESTES EXISTEM
═══════════════════════════════════════════════════════════════════════════

Nao ha Docker nesta maquina (conferido em 09/09/2026), entao NENHUM teste aqui
constroi imagem. O que eles fazem e diferente, e e o que da para provar sem
Docker: **ler os arquivos que descrevem a imagem** e falhar quando eles deixam
de dizer o que precisam dizer.

Isso cobre uma classe de defeito bem especifica - a que **nao da erro**:

  - alguem acrescenta `fastapi` ao `requirements_job.txt` "para reaproveitar um
    modelo Pydantic" e a imagem do job vira meia API;
  - alguem apaga a linha do portao de runtime do `Dockerfile.job` porque "o
    build estava lento", e a partir dai a calibracao do desafio pode sair de um
    adversario que nao e o adversario do aplicativo (RF-DES-018b);
  - alguem poe `espelho_laboratorio/` no `.dockerignore` para "enxugar a imagem
    da API", e o job perde a `.tflite` - o build continua verde, e o job so
    quebra no Railway, uma vez por dia, as 6 da manha;
  - alguem sobe o SQLAlchemy num `requirements` e esquece o outro, e o MESMO
    codigo passa a se comportar diferente conforme a imagem;
  - alguem copia o `railway.json` da API para o servico do job, e o Railway sobe
    uma SEGUNDA API - deploy verde, healthcheck verde, desafio nunca gerado.

⚠️ Nenhuma dessas linhas quebra teste nenhum hoje. E esse o ponto.

═══════════════════════════════════════════════════════════════════════════
O QUE ELES NAO PROVAM
═══════════════════════════════════════════════════════════════════════════

Que a imagem CONSTROI, e que o `ai-edge-litert` executa em `linux/amd64`. Isso
so o build no Railway responde, e e exatamente o que o portao dentro do
`Dockerfile.job` existe para fechar.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# `parents[2]` sobe tres niveis a partir deste arquivo:
#   tests/unitarios/test_imagem_do_job.py -> tests/unitarios -> tests -> raiz
RAIZ = Path(__file__).resolve().parents[2]

DOCKERFILE_API = RAIZ / "Dockerfile"
DOCKERFILE_JOB = RAIZ / "Dockerfile.job"
REQUIREMENTS_API = RAIZ / "requirements_api.txt"
REQUIREMENTS_JOB = RAIZ / "requirements_job.txt"
RAILWAY_API = RAIZ / "railway.json"
RAILWAY_JOB = RAIZ / "railway.job.json"
DOCKERIGNORE = RAIZ / ".dockerignore"


# ═══════════════════════════════════════════════════════════════════════════
# Auxiliares de leitura
# ═══════════════════════════════════════════════════════════════════════════


def linhas_de_instrucao(dockerfile: Path) -> list[str]:
    """Devolve as linhas do Dockerfile que sao INSTRUCAO, sem os comentarios.

    Por que filtrar: os comentarios deste projeto sao longos e citam os proprios
    nomes que os testes procuram (`fastapi`, `uvicorn`, `tensorflow`). Um teste
    que procurasse o texto cru encontraria a explicacao de por que a coisa NAO
    entra e se auto-reprovaria - foi assim que os cadeados do BLOCO 1 quebraram
    antes de serem reescritos.
    """
    saida: list[str] = []
    for linha in dockerfile.read_text(encoding="utf-8").splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#"):
            continue
        saida.append(limpa)
    return saida


def pacotes_declarados(requirements: Path) -> dict[str, str]:
    """Le um `requirements.txt` e devolve {nome em minusculas: versao}.

    Ignora comentarios, linhas vazias e as diretivas `-r outro.txt`. Aceita so a
    forma `pacote==versao`, que e a unica usada neste repositorio - e se alguem
    escrever `pacote>=versao`, o teste de versoes casadas abaixo acusa, o que e
    o comportamento desejado (faixa de versao nao e reproduzivel).
    """
    achados: dict[str, str] = {}
    for linha in requirements.read_text(encoding="utf-8").splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#") or limpa.startswith("-"):
            continue
        if "==" not in limpa:
            achados[limpa.lower()] = ""
            continue
        nome, versao = limpa.split("==", 1)
        achados[nome.strip().lower()] = versao.strip()
    return achados


def padroes_do_dockerignore() -> list[str]:
    """Os padroes ativos do `.dockerignore`, sem comentarios nem linhas vazias."""
    return [
        linha.strip()
        for linha in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    ]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os arquivos existem
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "caminho",
    [DOCKERFILE_JOB, REQUIREMENTS_JOB, RAILWAY_JOB],
    ids=["Dockerfile.job", "requirements_job.txt", "railway.job.json"],
)
def test_os_tres_arquivos_do_job_existem(caminho: Path) -> None:
    """Sem os tres, nao ha terceiro servico - so a intencao de ter um."""
    assert caminho.is_file(), f"faltando: {caminho.relative_to(RAIZ)}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. O Dockerfile.job
# ═══════════════════════════════════════════════════════════════════════════


def test_a_base_e_a_mesma_da_api() -> None:
    """Python 3.11-slim nos dois, e nao e gosto: quem manda e o `ai-edge-litert`.

    O runtime de inferencia publica wheel para `cp311` em `linux/amd64`; ele e a
    dependencia mais estreita do conjunto (`research.md` §R-03). Se um dia a base
    do job subir sozinha, o wheel deixa de resolver e o build quebra por um
    motivo que ninguem vai associar a esta linha.
    """
    base_job = [ln for ln in linhas_de_instrucao(DOCKERFILE_JOB) if ln.startswith("FROM ")]
    base_api = [ln for ln in linhas_de_instrucao(DOCKERFILE_API) if ln.startswith("FROM ")]
    assert base_job == ["FROM python:3.11-slim"], f"base do job: {base_job}"
    assert base_job == base_api, (
        "as duas imagens deixaram de compartilhar a base: "
        f"API={base_api} · job={base_job}"
    )


def test_o_job_instala_o_requirements_dele_e_nao_o_da_api() -> None:
    """Um `requirements` por imagem - a licao do `ipython` que nao cabia em 3.11."""
    instrucoes = " ".join(linhas_de_instrucao(DOCKERFILE_JOB))
    assert "requirements_job.txt" in instrucoes
    assert "requirements_api.txt" not in instrucoes, (
        "o Dockerfile.job passou a instalar a lista da API - as duas imagens "
        "voltaram a ser uma so"
    )


def test_o_portao_de_runtime_esta_no_build() -> None:
    """🔒 A linha que impede a imagem de calcular diferente do aplicativo.

    E a UNICA execucao em `linux/amd64` que o projeto tem: a maquina do dono nao
    tem Docker nem WSL. Ela precisa ser um `RUN` - um `CMD` ou `ENTRYPOINT` so
    rodaria na hora de executar, quando a imagem ruim ja estaria publicada.
    """
    portao = [
        ln
        for ln in linhas_de_instrucao(DOCKERFILE_JOB)
        if ln.startswith("RUN ") and "conferir_runtime_inferencia.py" in ln
    ]
    assert portao, (
        "o Dockerfile.job perdeu o portao da T001. Sem ele, uma versao nova do "
        "`ai-edge-litert` pode calibrar o desafio contra um adversario que NAO e "
        "o adversario que a pessoa enfrenta (RF-DES-018b), e nada denuncia."
    )
    assert "--runtime litert" in portao[0], (
        "o portao precisa conferir o runtime DA IMAGEM (`--runtime litert`); "
        f"encontrado: {portao[0]}"
    )


def test_o_portao_roda_depois_de_copiar_o_codigo() -> None:
    """Ordem importa: o script e a `.tflite` precisam ja estar dentro da imagem.

    Se o `RUN` do portao subisse para antes do `COPY . .`, ele falharia por
    arquivo faltando - um vermelho pelo motivo errado, que ensinaria a desligar
    o portao em vez de investigar.
    """
    instrucoes = linhas_de_instrucao(DOCKERFILE_JOB)
    indice_copia = next(i for i, ln in enumerate(instrucoes) if ln.startswith("COPY . "))
    indice_portao = next(
        i for i, ln in enumerate(instrucoes) if "conferir_runtime_inferencia.py" in ln
    )
    assert indice_copia < indice_portao, (
        "o portao roda ANTES de o codigo entrar na imagem - ele vai falhar por "
        "arquivo faltando, nao por divergencia de numero"
    )


def test_o_job_nao_escuta_porta_nenhuma() -> None:
    """RF-DES-011a: sem porta, sem rota, sem healthcheck.

    O job e a API se falam pelo Postgres. Um `EXPOSE` ou um `uvicorn` no `CMD`
    seriam a primeira pedra de um caminho que a spec fechou de proposito.
    """
    instrucoes = linhas_de_instrucao(DOCKERFILE_JOB)
    assert not [ln for ln in instrucoes if ln.startswith("EXPOSE")], (
        "o Dockerfile.job ganhou um EXPOSE - o job nao serve HTTP"
    )
    comandos = [ln for ln in instrucoes if ln.startswith(("CMD", "ENTRYPOINT"))]
    assert comandos, "o Dockerfile.job ficou sem CMD"
    for comando in comandos:
        assert "uvicorn" not in comando, f"o job virou servidor HTTP: {comando}"
        assert "PORT" not in comando, f"o job passou a ler $PORT: {comando}"
    assert any("job" in c for c in comandos), (
        f"o CMD nao aponta para o pacote `job`: {comandos}"
    )


def test_o_job_nao_roda_como_root() -> None:
    """Defesa em profundidade (MEL-01), igual a da API."""
    instrucoes = linhas_de_instrucao(DOCKERFILE_JOB)
    usuarios = [ln for ln in instrucoes if ln.startswith("USER ")]
    assert usuarios, "o Dockerfile.job roda como root"
    assert usuarios[-1] != "USER root", f"ultimo USER: {usuarios[-1]}"


def test_o_pacote_job_e_executavel_por_modulo() -> None:
    """`python -m job` precisa achar um `__main__.py` - e o CMD da imagem."""
    assert (RAIZ / "job" / "__init__.py").is_file()
    assert (RAIZ / "job" / "__main__.py").is_file(), (
        "o CMD do Dockerfile.job e `python -m job`, e sem `job/__main__.py` isso "
        "falha no container, nao aqui"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. O requirements_job.txt
# ═══════════════════════════════════════════════════════════════════════════


def test_o_runtime_de_inferencia_esta_preso_por_versao() -> None:
    """A versao medida pela T001 e a que vale - faixa de versao nao serve.

    `>=` deixaria o build de amanha instalar uma versao que ninguem comparou com
    o `tensorflow.lite` do aplicativo. O portao pegaria a divergencia, sim - mas
    so depois de alguem gastar um build descobrindo o porque.
    """
    pacotes = pacotes_declarados(REQUIREMENTS_JOB)
    assert "ai-edge-litert" in pacotes, "o job perdeu o runtime de inferencia"
    assert pacotes["ai-edge-litert"] == "2.2.0", (
        "a versao do `ai-edge-litert` mudou. Isso NAO e proibido - mas exige "
        "rodar `scripts/conferir_runtime_inferencia.py` e atualizar o registro "
        "em `docs/historico_decisoes.md`. Atualize este teste junto, "
        f"conscientemente. Encontrado: {pacotes['ai-edge-litert']!r}"
    )
    assert "numpy" in pacotes, "sem numpy nao ha como montar o tensor de entrada"


@pytest.mark.parametrize(
    "proibido, motivo",
    [
        ("fastapi", "o job NAO fala HTTP (RF-DES-011a)"),
        ("uvicorn", "o job NAO fala HTTP (RF-DES-011a)"),
        ("starlette", "o job NAO fala HTTP (RF-DES-011a)"),
        ("tensorflow", "a imagem RODA a rede, nao a treina - TF e o plano B"),
        ("tensorflow-cpu", "a imagem RODA a rede, nao a treina - TF e o plano B"),
        ("firebase-admin", "quem autentica pessoa e a API; o job nao ve ninguem"),
    ],
)
def test_o_que_nao_pode_entrar_na_imagem_do_job(proibido: str, motivo: str) -> None:
    """Cada linha aqui e uma fronteira que a spec desenhou - nao economia de MB."""
    assert proibido not in pacotes_declarados(REQUIREMENTS_JOB), (
        f"`{proibido}` entrou no requirements_job.txt: {motivo}"
    )


def test_a_api_nao_ganhou_o_runtime_de_inferencia() -> None:
    """O outro sentido da mesma fronteira, e o mais facil de esquecer.

    A API nunca abre a `.tflite`. Se o runtime aparecer na lista dela, alguem
    resolveu um erro de import no lugar errado - e a imagem enxuta de proposito
    (o comentario do `Dockerfile` diz isso desde 2026-07) engordou por engano.
    """
    assert "ai-edge-litert" not in pacotes_declarados(REQUIREMENTS_API)


def test_as_versoes_em_comum_nao_divergem_entre_as_duas_imagens() -> None:
    """🔒 O MESMO codigo nao pode se comportar diferente conforme a imagem.

    O job importa os *models* SQLAlchemy de `api/desafios/`. Duas versoes de
    SQLAlchemy no mesmo repositorio fariam o `INSERT` do job e o `SELECT` da API
    passarem por bibliotecas diferentes - e a divergencia apareceria como dado
    estranho no banco, nunca como erro de import.
    """
    api = pacotes_declarados(REQUIREMENTS_API)
    job = pacotes_declarados(REQUIREMENTS_JOB)

    divergentes = {
        nome: (api[nome], job[nome])
        for nome in set(api) & set(job)
        if api[nome] != job[nome]
    }
    assert not divergentes, (
        "pacotes com versoes diferentes nas duas imagens "
        f"(nome: API x job): {divergentes}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. O railway.job.json
# ═══════════════════════════════════════════════════════════════════════════


def test_o_servico_do_job_aponta_para_a_imagem_do_job() -> None:
    """Sem `dockerfilePath`, o Railway constroi o `Dockerfile` da API."""
    config = json.loads(RAILWAY_JOB.read_text(encoding="utf-8"))
    assert config["build"]["builder"] == "DOCKERFILE"
    assert config["build"]["dockerfilePath"] == "Dockerfile.job"


def test_terminar_e_sucesso() -> None:
    """`NEVER` e a diferenca entre um job e um servidor.

    Com `ON_FAILURE` ou `ALWAYS`, o container que termina o trabalho seria
    reiniciado - e o job rodaria em laco, gerando candidatos para sempre e
    queimando o teto do Railway.
    """
    config = json.loads(RAILWAY_JOB.read_text(encoding="utf-8"))
    assert config["deploy"]["restartPolicyType"] == "NEVER"


def test_o_job_nao_tem_healthcheck() -> None:
    """Healthcheck pressupoe porta; o job nao tem nenhuma (RF-DES-011a)."""
    config = json.loads(RAILWAY_JOB.read_text(encoding="utf-8"))
    assert "healthcheckPath" not in config["deploy"], (
        "o servico do job ganhou healthcheck - o Railway vai marcar como "
        "'nao saudavel' um job que simplesmente terminou o trabalho"
    )


def test_o_cron_existe_e_e_um_cron() -> None:
    """Quem acorda o job e o cron nativo do Railway (RF-DES-011a).

    ⚠️ O horario e cadencia de OPERACAO, nao regra de produto: RF-DES-011 diz
    que "a frequencia do job nao e a frequencia do desafio". Quem garante que
    nenhum dia fica descoberto e a folga de 7 a 30 dias da T038.
    """
    config = json.loads(RAILWAY_JOB.read_text(encoding="utf-8"))
    cron = config["deploy"].get("cronSchedule")
    assert cron, "o servico do job ficou sem cron - ninguem o acorda"
    # Cinco campos separados por espaco: minuto, hora, dia, mes, dia-da-semana.
    assert re.fullmatch(r"\S+( \S+){4}", cron), f"cron malformado: {cron!r}"


def test_os_dois_servicos_sao_arquivos_DIFERENTES() -> None:
    """🔒 O passo que nao da erro quando e esquecido.

    Se o servico do job for apontado para `railway.json`, o Railway sobe uma
    SEGUNDA API: deploy verde, healthcheck verde, e o desafio do dia nunca
    gerado. Este teste garante ao menos que os dois arquivos continuam dizendo
    coisas diferentes - o apontamento em si so existe no console, e por isso
    virou item do `checklist-producao.md`.
    """
    api = json.loads(RAILWAY_API.read_text(encoding="utf-8"))
    job = json.loads(RAILWAY_JOB.read_text(encoding="utf-8"))
    assert api != job
    assert "healthcheckPath" in api["deploy"], (
        "a API perdeu o healthcheck - se os dois arquivos convergirem, o erro de "
        "apontamento no console deixa de ser detectavel"
    )
    assert api["deploy"]["restartPolicyType"] != job["deploy"]["restartPolicyType"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. O .dockerignore, que serve as DUAS imagens
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "caminho, motivo",
    [
        ("espelho_laboratorio", "o job precisa da .tflite de 19,8 MB (RF-DES-148)"),
        ("scripts", "o portao de build roda scripts/conferir_runtime_inferencia.py"),
        ("motores", "e a camada que o job importa para jogar"),
        ("job", "e o codigo do proprio job"),
        ("requirements_job.txt", "e a lista que a imagem do job instala"),
    ],
)
def test_o_dockerignore_nao_barra_o_que_o_job_precisa(caminho: str, motivo: str) -> None:
    """🔒 A falha silenciosa mais cara desta tarefa.

    O Docker le o `.dockerignore` do CONTEXTO, nao do Dockerfile: as duas
    imagens compartilham a mesma lista. Alguem "enxugando a imagem da API"
    poderia excluir o espelho daqui - o build continuaria verde nas duas, e o
    job so quebraria no Railway, uma vez por dia, as 6 da manha.
    """
    padroes = padroes_do_dockerignore()
    barrados = [p for p in padroes if p.rstrip("/") == caminho.rstrip("/")]
    assert not barrados, (
        f"`{caminho}` esta no .dockerignore e nao pode estar: {motivo}. "
        f"Padrao encontrado: {barrados}"
    )

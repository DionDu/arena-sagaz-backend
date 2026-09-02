"""O corpo do `POST /v1/diagnosticos/motor-nativo`, e o que ele aceita.

Pydantic é a biblioteca que o FastAPI usa para validar o JSON que chega: cada
campo declarado aqui vira uma regra, e o que não bater volta como `422` sem a
rota ser chamada.

⚠️ **O que NÃO está aqui é tão importante quanto o que está.** Não há
`plataforma` nem `versao_app` no corpo: os dois já viajam em **todo** pedido do
app, nos cabeçalhos `X-Platform` e `X-App-Version`, que a diretriz de
versionamento da API torna obrigatórios. Pedi-los duas vezes criaria duas fontes
para o mesmo dado, e a segunda é a que fica errada quando as duas discordam.

⚠️ **E não há identificador de aparelho.** Nem IMEI, nem `androidId`, nem
`identifierForVendor`. Modelo e ABI bastam para saber qual build refazer, e não
permitem seguir uma pessoa — diagnóstico precisa de padrão, não de identidade.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ── Os conjuntos fechados ────────────────────────────────────────────────────
#
# `Literal[...]` do Python é a forma de dizer "só estes valores". O Pydantic o
# transforma em validação, e ele espelha, um a um, os `CHECK` da migração 0016 —
# porque um valor que passasse aqui e batesse no `CHECK` do banco viraria um
# `500` no meio da noite, em vez de um `422` claro na hora.

# Quais motores nativos existem. `tflite` ainda não relata nada; está na lista
# porque a tabela é do app e não das damas, e acrescentá-lo depois obrigaria a
# mexer no `CHECK` de uma tabela em produção.
MotorNativo = Literal["rust", "tflite"]

# ⚠️ `plataforma_sem_motor` NÃO é defeito: é o que a VM do `flutter test` e
# qualquer desktop respondem. Está na lista para não cair em
# `falha_desconhecida` e poluir a contagem do que importa.
MotivoDaIndisponibilidade = Literal[
    "biblioteca_ausente",  # o `.so` não foi achado (ABI fora das compiladas)
    "simbolo_ausente",  # abriu a biblioteca, faltou uma função dentro dela
    "plataforma_sem_motor",  # não há binário para esta plataforma, e está certo
    "versao_insuficiente",  # carregou, mas é mais velho do que o app exige
    "falha_desconhecida",  # o `catch` pegou algo que não se classificou
]


class DiagnosticoMotorNativoRequest(BaseModel):
    """Um relato de que o motor nativo não está disponível neste aparelho."""

    # ── O que falhou ────────────────────────────────────────────────────────
    # ⚠️ 30, e não 20: é a largura de `co_jogo` em `partida.tb001_partida` e nas
    # duas tabelas do schema `log_treino`. O dono pegou a divergência em 27/08 —
    # *"Precisa manter um padrão de dados nos campos correlatos."* Larguras
    # diferentes para a mesma coisa são a primeira rachadura de um `JOIN` que um
    # dia trunca.
    jogo: str = Field(
        max_length=30,
        description="Qual jogo tentou usar o motor nativo. Hoje só 'damas'.",
    )
    motor: MotorNativo = Field(description="Qual motor nativo não carregou.")

    # ── Por quê ─────────────────────────────────────────────────────────────
    motivo: MotivoDaIndisponibilidade = Field(
        description="A categoria, que é o que se agrupa numa consulta."
    )
    # O texto cru que a ponte produziu. É ele que diz ONDE olhar quando a
    # categoria não basta — carrega o nome do símbolo que faltou, o caminho, a
    # mensagem do `dlopen`.
    #
    # ⚠️ **O teto era 300 e virou 4000, e a pergunta do dono foi boa:** *"de
    # motivo com varchar(300) é suficiente para trazer todo o stacktrace de um
    # erro?"*. **Não era.** Um stacktrace de Dart tem alguns milhares de
    # caracteres, e 300 mal cobrem a primeira linha.
    #
    # A coluna virou `TEXT` (sem teto) na migração 0016. Este `max_length`
    # continua existindo, mas agora ele é **sanidade**, e não espelho de coluna:
    # ele impede que um defeito no app despeje megabytes num endpoint que aceita
    # convidado sem login. 4000 comporta um stacktrace inteiro com folga.
    detalhe: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="O texto cru do erro (mensagem e, se houver, stacktrace).",
    )

    # ⚠️ A versão do motor **lógico** (Dart) — `dart_1.3.0`, a mesma string do
    # `co_versao_motor` do log de partida. É a TERCEIRA versão, e ela não se
    # confunde com as duas do binário: o `.so`/`.a` é compilado por script à
    # parte, então "Dart novo com binário velho" é um estado real (foi o do iOS
    # entre 26 e 27/08/2026).
    versao_motor: Optional[str] = Field(
        default=None,
        max_length=40,
        description="Versão do motor lógico, ex.: 'dart_1.3.0'.",
    )

    # ── As duas versões do binário ──────────────────────────────────────────
    #
    # ⚠️ `versao_binario_encontrada` é NULA no caso mais comum — o binário não
    # carregou, então não houve a quem perguntar. É essa a diferença entre
    # "faltou o arquivo" e "o arquivo é velho", e ela não se recupera depois.
    versao_binario_esperada: Optional[str] = Field(
        default=None,
        max_length=20,
        description="O mínimo que o app exige (ex.: '0.3.0').",
    )
    versao_binario_encontrada: Optional[str] = Field(
        default=None,
        max_length=20,
        description="O que o binário declarou, ou nulo se ele nem carregou.",
    )

    # ── Onde ────────────────────────────────────────────────────────────────
    versao_so: Optional[str] = Field(
        default=None, max_length=40, description="Ex.: 'Android 13 (SDK 33)'."
    )
    modelo_aparelho: Optional[str] = Field(
        default=None, max_length=80, description="Ex.: 'samsung SM-A045M'."
    )
    abi: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Ex.: 'arm64-v8a'. Com a plataforma, diz qual build refazer.",
    )

    # ── Qual build do app ───────────────────────────────────────────────────
    #
    # A versão do app vem do cabeçalho; estes dois não têm cabeçalho próprio.
    # Sem eles não se separa "quantos aparelhos quebrados" de "quantos aparelhos
    # quebrados que ainda não atualizaram".
    flavor: Optional[Literal["des", "prd"]] = Field(
        default=None, description="Qual dos dois apps: 'des' ou 'prd'."
    )
    modo_build: Optional[Literal["debug", "profile", "release"]] = Field(
        default=None, description="Como o app foi compilado."
    )


class DiagnosticoResposta(BaseModel):
    """A resposta, e ela é deliberadamente pobre.

    O app **não faz nada** com ela: a chamada é *fire-and-forget*, e qualquer
    coisa que ele precisasse tratar viraria um caminho de erro numa
    funcionalidade que existe justamente para não atrapalhar. O `id` volta só
    para o suporte poder cruzar um relato com uma linha da tabela.
    """

    id_diagnostico: str

    # Quantas vezes esta MESMA configuração já foi relatada — `1` na primeira
    # vez. A tabela guarda uma linha por configuração, não uma por relato (ver o
    # cabeçalho da migração 0016), e este número é o contador dela.
    #
    # ⚠️ Serve ao **operador**, não ao app: dá para bater um relato de suporte
    # ("meu Sagaz sumiu") contra a linha certa sem abrir o banco.
    ocorrencias: int = 1

    registrado: bool = True

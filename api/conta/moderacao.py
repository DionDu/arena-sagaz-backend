"""Moderação do nome de exibição — tarefa T058.

O nome de exibição é o único texto livre que a pessoa escolhe e que pode aparecer
para outros jogadores (ranking, partida 2 jogadores). Por isso passa por uma
**moderação mínima** antes de ser gravado:

- comprimento entre 2 e 40 caracteres (após remover espaços nas pontas);
- não pode ser só espaços/vazio;
- não pode conter um termo de uma **lista de bloqueio** simples.

⚠️ Esta é uma defesa de primeira linha, propositalmente conservadora e fácil de
estender. Moderação robusta (variações com números/símbolos, múltiplos idiomas,
serviço externo) fica registrada como evolução futura — ver `tasks.md`.
"""
from __future__ import annotations

from api.nucleo.excecoes import ErroNegocio

# Limites de tamanho (o banco aceita até 40; exigimos ao menos 2 caracteres
# visíveis para evitar nomes vazios/single-char sem sentido).
TAMANHO_MINIMO = 2
TAMANHO_MAXIMO = 40

# Lista de bloqueio mínima (substrings proibidas, sem diferenciar maiúsc./minúsc.).
# Mantida curta e óbvia de propósito; ampliar aqui conforme necessário.
TERMOS_BLOQUEADOS = (
    "admin",
    "arena sagaz",
    "moderador",
)


def validar_nome_exibicao(nome: str) -> str:
    """Valida e **normaliza** o nome de exibição; devolve a versão limpa.

    Remove espaços das pontas e colapsa espaços internos repetidos. Lança
    [ErroNegocio] (422) com um `codigo` específico se algo estiver fora das
    regras — a UI traduz esse código para uma mensagem amigável.
    """
    # Colapsa qualquer sequência de espaços em um só e remove das pontas.
    limpo = " ".join(nome.split())

    if len(limpo) < TAMANHO_MINIMO:
        raise ErroNegocio(
            "Nome muito curto.",
            "nome_muito_curto",
            status_http=422,
        )
    if len(limpo) > TAMANHO_MAXIMO:
        raise ErroNegocio(
            "Nome muito longo.",
            "nome_muito_longo",
            status_http=422,
        )

    rebaixado = limpo.lower()
    for termo in TERMOS_BLOQUEADOS:
        if termo in rebaixado:
            raise ErroNegocio(
                "Esse nome não é permitido.",
                "nome_nao_permitido",
                status_http=422,
            )

    return limpo

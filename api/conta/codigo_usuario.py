"""Geração do código de usuário (`co_usuario`) — FR-004a.

São **8 caracteres** de um alfabeto restrito, escolhido para:

- **NÃO ter vogais** (a, e, i, o, u) → torna quase impossível formar palavras
  reais ou ofensivas por acidente (ex.: evita algo como ``gay024``);
- **NÃO ter caracteres confundíveis** (``0``/``O``, ``1``/``l``/``I``) → fica
  legível, sem ambiguidade ao ditar/anotar.

Alfabeto final: consoantes ``bcdfghjkmnpqrstvwxyz`` + dígitos ``23456789``
(28 símbolos → 28**8 ≈ 3,8 × 10**11 combinações). A unicidade no banco é
garantida pela constraint ``UNIQUE`` + retentativa no serviço de conta.
"""
import secrets

# Alfabeto sem vogais e sem caracteres confundíveis (0, O, 1, l, I removidos).
ALFABETO: str = "bcdfghjkmnpqrstvwxyz23456789"

# Comprimento do código.
TAMANHO: int = 8

# Defesa extra: padrões a rejeitar mesmo no alfabeto seguro. Como não há vogais,
# formar uma palavra real é muito difícil — a lista é mínima de propósito e pode
# crescer se algum padrão indesejado aparecer.
_DENYLIST: frozenset[str] = frozenset()


def gerar_codigo_usuario() -> str:
    """Gera um código aleatório de 8 caracteres do alfabeto seguro.

    Usa o módulo ``secrets`` (gerador criptográfico), mais adequado que
    ``random`` para algo que identifica o usuário e é usado em antifraude.
    Repete a geração caso (improvável) caia num termo da denylist.
    """
    while True:
        codigo = "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO))
        if not _contem_termo_proibido(codigo):
            return codigo


def _contem_termo_proibido(codigo: str) -> bool:
    """Indica se o código contém algum termo da denylist (defesa extra)."""
    return any(termo in codigo for termo in _DENYLIST)

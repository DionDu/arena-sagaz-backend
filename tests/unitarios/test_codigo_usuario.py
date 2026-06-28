"""Testes do gerador de código de usuário (`co_usuario`) — FR-004a."""
from api.conta.codigo_usuario import ALFABETO, TAMANHO, gerar_codigo_usuario

# Conjunto de caracteres proibidos: vogais + confundíveis.
_PROIBIDOS = set("aeiouAEIOU0O1lI")


def test_tamanho_e_alfabeto():
    """Todo código tem 8 chars, todos dentro do alfabeto seguro."""
    for _ in range(2000):
        codigo = gerar_codigo_usuario()
        assert len(codigo) == TAMANHO
        assert all(ch in ALFABETO for ch in codigo)


def test_sem_vogais_e_sem_confundiveis():
    """Nenhum código contém vogal ou caractere confundível (0/O/1/l/I)."""
    for _ in range(2000):
        codigo = gerar_codigo_usuario()
        assert not (set(codigo) & _PROIBIDOS)


def test_alta_variabilidade():
    """Com 28**8 combinações, 1000 amostras quase não colidem."""
    amostras = {gerar_codigo_usuario() for _ in range(1000)}
    assert len(amostras) > 995

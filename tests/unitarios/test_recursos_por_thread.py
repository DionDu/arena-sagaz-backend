"""Os cadeados do registro de recursos por thread.

═══════════════════════════════════════════════════════════════════════════
O DEFEITO QUE ESTES CASOS GUARDAM
═══════════════════════════════════════════════════════════════════════════

Em 25/09/2026, depois de gerar 7 dias de desafios pelo painel de curadoria, o PC
do dono tinha **81 processos do motor Dart vivos, 5,4 GB de RAM e zero de CPU em
15 s de observação** — um pool de 8 threads por candidato, e nenhum dos motores
fechado quando o pool terminou. O `atexit` só fecharia na saída do Python, e o
painel fica no ar por horas.

⚠️ **O que estes casos medem não é o motor, é a regra:** fecha-se o recurso de
quem morreu, ⛔ **nunca** o de quem está vivo — fechar o motor de uma thread no
meio de uma busca daria resposta truncada, e sem erro nenhum.
"""

from __future__ import annotations

import threading

from motores.nucleo import recursos_por_thread


class RecursoFalso:
    """Um "recurso" que só anota se foi fechado, e quantas vezes.

    ⚠️ Não é um motor: o registro é **genérico de propósito** (a régua mede
    qualquer jogo e não pode conhecer damas), e um duplo assim é a prova de que
    ele não sabe o que está fechando.
    """

    def __init__(self) -> None:
        self.vezes_fechado = 0
        self.vai_falhar = False

    def encerrar(self) -> None:
        self.vezes_fechado += 1
        if self.vai_falhar:
            raise RuntimeError("este recurso nao fecha limpo")

    @property
    def fechado(self) -> bool:
        return self.vezes_fechado > 0


def _registrar_numa_thread_que_morre(recurso: RecursoFalso) -> None:
    """Registra `recurso` dentro de uma thread e espera ela **terminar**.

    O `join()` é o ponto todo do auxiliar: depois dele a thread está morta, que é
    a condição que a limpeza procura.
    """
    thread = threading.Thread(target=lambda: recursos_por_thread.registrar(recurso))
    thread.start()
    thread.join()
    assert not thread.is_alive(), "a thread do auxiliar deveria ter terminado"


def test_o_recurso_de_uma_thread_MORTA_e_fechado() -> None:
    """🔒 O caso central: a thread acabou, o processo filho dela não pode ficar."""
    recurso = RecursoFalso()
    _registrar_numa_thread_que_morre(recurso)

    fechados = recursos_por_thread.liberar_de_threads_mortas()

    assert recurso.fechado, "o recurso de uma thread morta continuou aberto"
    assert fechados >= 1, "a limpeza nao contou o que fechou"


def test_o_recurso_de_uma_thread_VIVA_nao_e_tocado() -> None:
    """⛔ Fechar o motor de quem esta calculando daria resposta truncada.

    A thread deste caso fica presa num `Event` até a limpeza rodar — ou seja, ela
    está **viva** no instante exato em que a varredura acontece.
    """
    recurso = RecursoFalso()
    pode_terminar = threading.Event()
    ja_registrou = threading.Event()

    def corpo() -> None:
        recursos_por_thread.registrar(recurso)
        ja_registrou.set()
        pode_terminar.wait(timeout=10)

    thread = threading.Thread(target=corpo)
    thread.start()
    try:
        assert ja_registrou.wait(timeout=10), "a thread nao chegou a registrar"
        recursos_por_thread.liberar_de_threads_mortas()
        assert not recurso.fechado, (
            "a limpeza fechou o recurso de uma thread que ainda estava viva"
        )
    finally:
        # Solta a thread mesmo se o caso falhar, senão ela ficaria pendurada.
        pode_terminar.set()
        thread.join(timeout=10)

    # E depois que ela morre, o mesmo recurso passa a ser fechável.
    recursos_por_thread.liberar_de_threads_mortas()
    assert recurso.fechado, "morta a thread, o recurso dela deveria fechar"


def test_o_recurso_da_PROPRIA_thread_que_limpa_nao_e_fechado() -> None:
    """⛔ Quem pede a limpeza esta, por definicao, vivo.

    Na régua é a thread principal que chama a limpeza ao fim do pool — se ela
    fechasse o próprio recurso, a medição seguinte subiria um motor novo a cada
    candidato, sem ninguém entender por quê.
    """
    meu = RecursoFalso()
    recursos_por_thread.registrar(meu)
    try:
        recursos_por_thread.liberar_de_threads_mortas()
        assert not meu.fechado, "a limpeza fechou o recurso de quem a chamou"
    finally:
        # Não deixa lixo para os casos seguintes.
        recursos_por_thread._abertos[:] = [
            (t, r) for t, r in recursos_por_thread._abertos if r is not meu
        ]


def test_um_recurso_fechado_SAI_da_lista() -> None:
    """⛔ Fechar duas vezes o mesmo recurso e sinal de lista que nao encolhe.

    Se o recurso permanecesse registrado, cada limpeza seguinte o fecharia de
    novo, e a lista cresceria para sempre — que é a forma do vazamento original.
    """
    recurso = RecursoFalso()
    _registrar_numa_thread_que_morre(recurso)

    recursos_por_thread.liberar_de_threads_mortas()
    recursos_por_thread.liberar_de_threads_mortas()

    assert recurso.vezes_fechado == 1, (
        f"o recurso foi fechado {recurso.vezes_fechado} vezes — ele nao saiu da lista"
    )


def test_uma_falha_ao_fechar_NAO_derruba_a_limpeza() -> None:
    """⚠️ A limpeza roda depois de uma medicao que ja terminou.

    Um motor que não morre limpo não pode custar o candidato inteiro — e o recurso
    tem de sair da lista de qualquer jeito, senão fica pendurado para sempre.
    """
    problematico = RecursoFalso()
    problematico.vai_falhar = True
    bem_comportado = RecursoFalso()
    _registrar_numa_thread_que_morre(problematico)
    _registrar_numa_thread_que_morre(bem_comportado)

    # ⛔ Sem `pytest.raises`: o ponto do caso e que NAO levanta.
    recursos_por_thread.liberar_de_threads_mortas()

    assert problematico.vezes_fechado == 1
    assert bem_comportado.fechado, (
        "a falha de um recurso impediu o seguinte de ser fechado"
    )
    # E nenhum dos dois continua registrado.
    recursos_por_thread.liberar_de_threads_mortas()
    assert problematico.vezes_fechado == 1, "o que falhou ficou pendurado na lista"


def test_a_lista_nao_cresce_com_o_NUMERO_DE_POOLS() -> None:
    """🔒 A forma exata do vazamento de 25/09: 7 dias, 8 threads, 81 motores.

    Simula dez "pools" de quatro threads cada, com limpeza entre eles. Sem a
    limpeza seriam 40 recursos abertos; com ela, no máximo os do pool corrente.
    """
    antes = recursos_por_thread.quantos_abertos()
    recursos: list[RecursoFalso] = []

    for _ in range(10):
        deste_pool = [RecursoFalso() for _ in range(4)]
        recursos.extend(deste_pool)
        threads = [
            threading.Thread(target=recursos_por_thread.registrar, args=(r,))
            for r in deste_pool
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        recursos_por_thread.liberar_de_threads_mortas()

    depois = recursos_por_thread.quantos_abertos()
    assert depois == antes, (
        f"sobraram {depois - antes} recurso(s) registrado(s) depois de dez pools"
    )
    assert all(r.fechado for r in recursos), "algum recurso dos pools ficou aberto"

"""A regra de quanto tempo cada backup fica no Drive (`backup/retencao.py`).

Dois níveis de prova:

1. **as bordas**, caso a caso: a etiqueta de cada tipo de dia, e o último dia em
   que cada etiqueta fica e o primeiro em que sai;
2. **a simulação**, que é o que o dono pediu de verdade: o serviço rodando todo
   dia durante 200 dias, com a faxina de cada dia, e as **garantias** conferidas
   em cada um dos dias depois do aquecimento. Uma regra pode acertar cada borda e
   ainda deixar um buraco no calendário - é a simulação que pega isso.
"""

from datetime import date, timedelta

import pytest

from backup import retencao
from backup.retencao import DIARIO, MENSAL, SEMANAL

# 2026-10-01 é quinta; 2026-10-04 é domingo; 2026-11-01 é domingo E dia 1º.
QUINTA_DIA_1 = date(2026, 10, 1)
DOMINGO = date(2026, 10, 4)
SEGUNDA = date(2026, 10, 5)
DOMINGO_DIA_1 = date(2026, 11, 1)


class TestEtiqueta:
    def test_dia_1_e_mensal(self):
        assert retencao.etiqueta_do_dia(QUINTA_DIA_1) == MENSAL

    def test_domingo_e_semanal(self):
        assert DOMINGO.weekday() == 6  # confere a premissa do calendário
        assert retencao.etiqueta_do_dia(DOMINGO) == SEMANAL

    def test_dia_comum_e_diario(self):
        assert retencao.etiqueta_do_dia(SEGUNDA) == DIARIO

    def test_dia_1_que_cai_no_domingo_e_mensal(self):
        """O prazo mais longo vence: o domingo dia 1º fica 92 dias, e não 35."""
        assert DOMINGO_DIA_1.weekday() == 6
        assert retencao.etiqueta_do_dia(DOMINGO_DIA_1) == MENSAL

    def test_os_prazos_sao_os_da_decisao_do_dono(self):
        """DECISOES §8zv: 7 diários, ~4 semanais (35 dias), ~3 mensais (92 dias).

        Os números entram escritos aqui, e não lidos da constante: um caso que
        lesse `PRAZO_EM_DIAS` passaria com qualquer valor.
        """
        assert retencao.PRAZO_EM_DIAS == {DIARIO: 7, SEMANAL: 35, MENSAL: 92}


class TestNome:
    def test_ida_e_volta(self):
        nome = retencao.nome_do_arquivo(DOMINGO)
        assert nome == "arena-sagaz-prd_2026-10-04_semanal.dump.gpg"
        assert retencao.ler_nome(nome) == (DOMINGO, SEMANAL)

    @pytest.mark.parametrize(
        "nome",
        [
            "foto.jpg",
            "arena-sagaz-prd_2026-10-04_semanal.dump",  # sem a extensão do gpg
            "arena-sagaz-des_2026-10-04_semanal.dump.gpg",  # outro banco
            "arena-sagaz-prd_2026-10-04_anual.dump.gpg",  # etiqueta desconhecida
            "arena-sagaz-prd_2026-02-30_diario.dump.gpg",  # data impossível
            "copia de arena-sagaz-prd_2026-10-04_semanal.dump.gpg",  # prefixo a mais
            "arena-sagaz-prd_2026-10-04_semanal.dump.gpg.bak",  # sufixo a mais
        ],
    )
    def test_nome_que_nao_e_nosso_nao_se_le(self, nome):
        assert retencao.ler_nome(nome) is None

    @pytest.mark.parametrize(
        "nome",
        [
            "foto.jpg",
            "arena-sagaz-prd_2026-02-30_diario.dump.gpg",
            "arena-sagaz-prd_2020-01-02_anual.dump.gpg",
        ],
    )
    def test_nome_que_nao_e_nosso_nunca_e_apagado(self, nome):
        """Mesmo velho: o que não se entende fica (a mensagem do cabeçalho)."""
        assert not retencao.deve_apagar(nome, date(2030, 1, 1))


class TestBordas:
    @pytest.mark.parametrize(
        "dia, prazo",
        [(SEGUNDA, 7), (DOMINGO, 35), (QUINTA_DIA_1, 92)],
    )
    def test_fica_no_ultimo_dia_do_prazo_e_sai_no_seguinte(self, dia, prazo):
        nome = retencao.nome_do_arquivo(dia)
        assert not retencao.deve_apagar(nome, dia + timedelta(days=prazo))
        assert retencao.deve_apagar(nome, dia + timedelta(days=prazo + 1))

    def test_o_backup_de_hoje_fica(self):
        nome = retencao.nome_do_arquivo(SEGUNDA)
        assert not retencao.deve_apagar(nome, SEGUNDA)

    def test_data_no_futuro_fica(self):
        """Só com relógio errado; guardar é o lado seguro."""
        nome = retencao.nome_do_arquivo(SEGUNDA)
        assert not retencao.deve_apagar(nome, SEGUNDA - timedelta(days=400))

    def test_a_etiqueta_e_lida_do_nome_e_nao_recalculada(self):
        """Um arquivo que nasceu "mensal" é julgado como mensal, mesmo que a data
        dele não seja dia 1º - a etiqueta é a do nascimento (cabeçalho)."""
        nome = "arena-sagaz-prd_2026-10-05_mensal.dump.gpg"  # segunda, não dia 1º
        assert not retencao.deve_apagar(nome, SEGUNDA + timedelta(days=50))

    def test_nomes_a_apagar_filtra_a_lista(self):
        hoje = date(2026, 10, 20)
        velho = retencao.nome_do_arquivo(SEGUNDA)  # diário de 15 dias: sai
        novo = retencao.nome_do_arquivo(date(2026, 10, 19))  # diário de 1 dia: fica
        assert retencao.nomes_a_apagar([velho, novo, "foto.jpg"], hoje) == [velho]


class TestSimulacaoDeMesesDeServico:
    """O serviço rodando todo dia: o que fica na pasta, e o que isso garante."""

    INICIO = date(2026, 10, 7)
    DIAS = 200
    # Depois de 92 dias as três camadas estão cheias; antes disso, as garantias
    # mais longas ainda não podem valer (não há backup tão velho).
    AQUECIMENTO = 93

    @classmethod
    def _rodar(cls) -> dict[date, list[date]]:
        """Devolve, para cada dia, as datas dos backups que ficaram na pasta."""
        pasta: list[str] = []
        retrato: dict[date, list[date]] = {}
        for n in range(cls.DIAS):
            hoje = cls.INICIO + timedelta(days=n)
            pasta.append(retencao.nome_do_arquivo(hoje))
            apagar = set(retencao.nomes_a_apagar(pasta, hoje))
            pasta = [nome for nome in pasta if nome not in apagar]
            retrato[hoje] = sorted(retencao.ler_nome(nome)[0] for nome in pasta)
        return retrato

    def _dias_cheios(self):
        retrato = self._rodar()
        return [(d, r) for d, r in retrato.items() if (d - self.INICIO).days >= self.AQUECIMENTO]

    def test_existe_o_backup_de_cada_um_dos_ultimos_7_dias(self):
        for hoje, datas in self._dias_cheios():
            for idade in range(0, 8):
                assert hoje - timedelta(days=idade) in datas, (hoje, idade)

    def test_ate_5_semanas_nenhum_buraco_passa_de_7_dias(self):
        """Falha notada em até 5 semanas: há um backup no máximo 7 dias antes dela."""
        for hoje, datas in self._dias_cheios():
            ate_35 = [d for d in datas if (hoje - d).days <= 35]
            assert (hoje - min(ate_35)).days >= 28, hoje  # a camada chega a ~5 semanas
            buracos = [(b - a).days for a, b in zip(ate_35, ate_35[1:])]
            assert max(buracos) <= 7, (hoje, buracos)

    def test_ha_sempre_um_entre_d14_e_d21_e_outro_entre_d28_e_d35(self):
        """O "D-15" e o "D-30" da proposta inicial do dono, garantidos todo dia."""
        for hoje, datas in self._dias_cheios():
            idades = [(hoje - d).days for d in datas]
            assert any(14 <= i <= 21 for i in idades), hoje
            assert any(28 <= i <= 35 for i in idades), hoje

    def test_ate_3_meses_nenhum_buraco_passa_de_um_mes(self):
        for hoje, datas in self._dias_cheios():
            assert (hoje - min(datas)).days >= 61, hoje  # o mais velho passa de 2 meses
            buracos = [(b - a).days for a, b in zip(datas, datas[1:])]
            assert max(buracos) <= 31, (hoje, buracos)

    def test_a_pasta_fica_em_torno_de_15_arquivos(self):
        """8 diários (hoje e D-1..D-7) + ~4 semanais + ~3 mensais, com sobreposição.

        Medido nesta simulação em 06/10/2026: entre 14 e 15 arquivos por dia.
        """
        contagens = [len(datas) for _, datas in self._dias_cheios()]
        assert 13 <= min(contagens) and max(contagens) <= 16, (min(contagens), max(contagens))

from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

_TOTAL_CAIXAS = {"pequeno": 12, "medio": 20, "grande": 35}


class SincronizarPartidaEntrada(BaseModel):
    modo_jogo: Literal["vs_cpu", "vs_humano_local"]
    tamanho_tabuleiro: Literal["pequeno", "medio", "grande"]
    dificuldade: Optional[Literal["facil", "normal", "sagaz"]] = None
    caixas_jogador: int
    caixas_adversario: int
    resultado: Literal["vitoria", "derrota", "empate"]

    @model_validator(mode="after")
    def validar_dificuldade_e_caixas(self):
        if self.modo_jogo == "vs_cpu" and not self.dificuldade:
            raise ValueError("Dificuldade é obrigatória para modo vs_cpu.")
        if self.modo_jogo == "vs_humano_local" and self.dificuldade:
            raise ValueError("Dificuldade deve ser nula para modo vs_humano_local.")

        total_esperado = _TOTAL_CAIXAS[self.tamanho_tabuleiro]
        total_real = self.caixas_jogador + self.caixas_adversario
        if total_real != total_esperado:
            raise ValueError(
                f"CAIXAS_INVALIDAS: soma de caixas ({self.caixas_jogador} + "
                f"{self.caixas_adversario} = {total_real}) não corresponde ao "
                f"tabuleiro '{self.tamanho_tabuleiro}' (esperado: {total_esperado})."
            )
        return self


class PartidaSaida(BaseModel):
    id: str
    xp_obtido: int
    pontuacao_obtida: int
    nivel_anterior: int
    nivel_atual: int
    xp_total: int
    posicao_ranking: Optional[int]
    trofeus_conquistados: list = []

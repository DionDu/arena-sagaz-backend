from pydantic import BaseModel


class EntradaRankingSaida(BaseModel):
    posicao: int
    apelido: str
    nivel: int
    pontuacao_total: int
    vitorias: int
    partidas_jogadas: int


class RankingSaida(BaseModel):
    total: int
    pagina: int
    tamanho: int
    jogadores: list[EntradaRankingSaida]

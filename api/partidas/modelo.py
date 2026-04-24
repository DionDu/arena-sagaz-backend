import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.banco.base import Base


class Partida(Base):
    __tablename__ = "partidas"
    __table_args__ = (
        CheckConstraint("modo_jogo IN ('vs_cpu', 'vs_humano_local')", name="ck_partidas_modo_jogo"),
        CheckConstraint("tamanho_tabuleiro IN ('pequeno', 'medio', 'grande')", name="ck_partidas_tamanho"),
        CheckConstraint("dificuldade IN ('facil', 'normal', 'sagaz') OR dificuldade IS NULL", name="ck_partidas_dificuldade"),
        CheckConstraint("resultado IN ('vitoria', 'derrota', 'empate')", name="ck_partidas_resultado"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    usuario_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True)
    modo_jogo: Mapped[str] = mapped_column(String(20), nullable=False)
    tamanho_tabuleiro: Mapped[str] = mapped_column(String(10), nullable=False)
    dificuldade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    caixas_jogador: Mapped[int] = mapped_column(Integer, nullable=False)
    caixas_adversario: Mapped[int] = mapped_column(Integer, nullable=False)
    resultado: Mapped[str] = mapped_column(String(10), nullable=False)
    xp_obtido: Mapped[int] = mapped_column(Integer, nullable=False)
    pontuacao_obtida: Mapped[int] = mapped_column(Integer, nullable=False)
    jogado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)

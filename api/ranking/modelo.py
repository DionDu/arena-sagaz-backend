import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.banco.base import Base


class Ranking(Base):
    __tablename__ = "ranking"
    __table_args__ = (
        UniqueConstraint("usuario_id", name="uq_ranking_usuario_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    usuario_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    pontuacao_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    partidas_jogadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vitorias: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

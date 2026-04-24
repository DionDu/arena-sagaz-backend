import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.banco.base import Base


class Trofeu(Base):
    __tablename__ = "trofeus"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    criterio: Mapped[str] = mapped_column(String(255), nullable=False)


class UsuarioTrofeu(Base):
    __tablename__ = "usuario_trofeus"
    __table_args__ = (
        PrimaryKeyConstraint("usuario_id", "trofeu_id"),
    )

    usuario_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    trofeu_id: Mapped[str] = mapped_column(String(36), ForeignKey("trofeus.id", ondelete="CASCADE"), nullable=False)
    conquistado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

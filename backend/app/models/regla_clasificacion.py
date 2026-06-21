from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class ReglaClasificacion(Base):
    __tablename__ = "reglas_clasificacion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    cedula: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    cabys: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    rol: Mapped[str | None] = mapped_column(String(10), nullable=True)  # compra|venta (solo regla de cédula sola)
    clasificacion: Mapped[str] = mapped_column(String(40), nullable=False)
    sub_clasificacion: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

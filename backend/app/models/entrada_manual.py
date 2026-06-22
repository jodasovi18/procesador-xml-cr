from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Integer, String, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class EntradaManual(Base):
    __tablename__ = "entradas_manuales"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    periodo: Mapped[str] = mapped_column(String(6), nullable=False, index=True)  # YYYYMM
    rol: Mapped[str] = mapped_column(String(10), nullable=False)  # compra | venta
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 5), nullable=False, default=Decimal("0"))
    tarifa: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=Decimal("0"))  # % IVA
    no_sujeto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deducible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # solo compras
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

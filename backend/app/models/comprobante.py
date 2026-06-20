from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class Comprobante(Base):
    __tablename__ = "comprobantes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), nullable=True, index=True)
    clave: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    tipo_doc: Mapped[str] = mapped_column(String(40), nullable=False)
    consecutivo: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    periodo: Mapped[str] = mapped_column(String(6), nullable=False, index=True)  # YYYYMM (de la fecha)
    rol: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 'compra' | 'venta'
    emisor_nombre: Mapped[str] = mapped_column(String(255), default="")
    emisor_cedula: Mapped[str] = mapped_column(String(20), default="", index=True)
    receptor_nombre: Mapped[str] = mapped_column(String(255), default="")
    receptor_cedula: Mapped[str] = mapped_column(String(20), default="", index=True)
    moneda: Mapped[str] = mapped_column(String(3), default="CRC")
    tipo_cambio: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("1"))
    total_gravado: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_exento: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_exonerado: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_no_sujeto: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_iva: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    total_comprobante: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    estado_hacienda: Mapped[str | None] = mapped_column(String(20), nullable=True)
    xml_raw: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    lineas: Mapped[list["LineaComprobante"]] = relationship(
        back_populates="comprobante", cascade="all, delete-orphan")

class LineaComprobante(Base):
    __tablename__ = "lineas_comprobante"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comprobante_id: Mapped[int] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="CASCADE"), nullable=False, index=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    cabys: Mapped[str] = mapped_column(String(20), default="")
    detalle: Mapped[str] = mapped_column(Text, default="")
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    base_imponible: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    tarifa_codigo: Mapped[str] = mapped_column(String(4), default="")
    tarifa_pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    iva_monto: Mapped[Decimal] = mapped_column(Numeric(18, 5), default=Decimal("0"))
    clasificacion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sub_clasificacion: Mapped[str | None] = mapped_column(String(60), nullable=True)
    comprobante: Mapped["Comprobante"] = relationship(back_populates="lineas")

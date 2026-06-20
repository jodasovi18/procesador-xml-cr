"""Resumen por categoría tributaria sobre las líneas guardadas.
Categoría: 'No Sujeto' para esos códigos, si no '{tipo} {tarifa_label}'."""
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.comprobante import Comprobante, LineaComprobante

def build_resumen(db: Session, cliente_id: int, periodo: str, rol: str) -> dict[str, dict[str, Decimal]]:
    stmt = (
        select(LineaComprobante)
        .join(Comprobante, LineaComprobante.comprobante_id == Comprobante.id)
        .where(
            Comprobante.cliente_id == cliente_id,
            Comprobante.periodo == periodo,
            Comprobante.rol == rol,
        )
    )
    cats: dict[str, dict[str, Decimal]] = {}
    for ln in db.scalars(stmt):
        if ln.tarifa_label == "No Sujeto":
            cat = "No Sujeto"
        else:
            cat = f"{ln.tipo} {ln.tarifa_label}".strip()
        d = cats.setdefault(cat, {"base": Decimal("0"), "iva": Decimal("0")})
        d["base"] += ln.base_imponible
        d["iva"] += ln.iva_monto
    return cats

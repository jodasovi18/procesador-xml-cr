"""Resumen por categoría tributaria sobre las líneas guardadas, con la capa de
clasificación aplicada al vuelo desde reglas_clasificacion.
- build_resumen: vista tributaria ({tipo} {tarifa}; No Sujeto; No Deducibles segregado).
- build_resumen_clasificacion: vista de gestión {clasificacion: {tarifa: {...}}}.
La clasificación se deriva por la cédula de la contraparte (emisor en compra,
receptor en venta) y el CABYS de la línea."""
from decimal import Decimal
from collections.abc import Iterator
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.comprobante import Comprobante, LineaComprobante
from app.models.regla_clasificacion import ReglaClasificacion
from app.motor.clasificacion import build_lookup, clasificar, SUBCATEGORIAS_NO_SUJETO


def _lineas_clasificadas(db: Session, cliente_id: int, periodo: str, rol: str,
                         excluir_tipos: set[str] | None = None
                         ) -> Iterator[tuple[LineaComprobante, str, str]]:
    """Itera (línea, clasificacion, sub_clasificacion) para el cliente/período/rol.
    excluir_tipos: tipos de comprobante (Comprobante.tipo_doc) a omitir (p.ej. tiquetes)."""
    # Se cargan TODAS las reglas del cliente (sin filtrar por rol en SQL):
    # build_lookup separa céd-sola por rol y clasificar elige; las reglas de cabys son rol-agnósticas.
    reglas = db.scalars(select(ReglaClasificacion).where(
        ReglaClasificacion.cliente_id == cliente_id))
    lookup = build_lookup(reglas)
    stmt = (
        select(LineaComprobante, Comprobante)
        .join(Comprobante, LineaComprobante.comprobante_id == Comprobante.id)
        .where(
            Comprobante.cliente_id == cliente_id,
            Comprobante.periodo == periodo,
            Comprobante.rol == rol,
        )
    )
    if excluir_tipos:
        stmt = stmt.where(Comprobante.tipo_doc.notin_(excluir_tipos))
    for ln, comp in db.execute(stmt):
        cedula = comp.emisor_cedula if rol == "compra" else comp.receptor_cedula
        clas, sub = clasificar(cedula, ln.cabys, rol, lookup)
        yield ln, clas, sub


def _acc(cats: dict, cat: str, base: Decimal, iva: Decimal) -> None:
    d = cats.setdefault(cat, {"base": Decimal("0"), "iva": Decimal("0")})
    d["base"] += base
    d["iva"] += iva


def build_resumen(db: Session, cliente_id: int, periodo: str, rol: str,
                  excluir_tipos: set[str] | None = None) -> dict[str, dict[str, Decimal]]:
    """Vista tributaria. No Deducible → bucket segregado; sub_clas Combustibles →
    No Sujeto (IVA 0, sin importar la tarifa XML); resto: {tipo} {tarifa} / No Sujeto.
    excluir_tipos: tipos de comprobante a omitir (p.ej. {'TiqueteElectronico'} para el crédito)."""
    cats: dict[str, dict[str, Decimal]] = {}
    for ln, clas, sub in _lineas_clasificadas(db, cliente_id, periodo, rol, excluir_tipos):
        if clas == "No Deducibles":
            _acc(cats, "No Deducibles", ln.base_imponible, ln.iva_monto)
        elif sub in SUBCATEGORIAS_NO_SUJETO:
            _acc(cats, "No Sujeto", ln.base_imponible, Decimal("0"))
        elif ln.tarifa_label == "No Sujeto":
            _acc(cats, "No Sujeto", ln.base_imponible, ln.iva_monto)
        else:
            _acc(cats, f"{ln.tipo} {ln.tarifa_label}".strip(), ln.base_imponible, ln.iva_monto)
    return cats


def build_resumen_clasificacion(db: Session, cliente_id: int, periodo: str, rol: str
                                ) -> dict[str, dict[str, dict[str, Decimal]]]:
    """Vista de gestión {clasificacion: {tarifa: {base, iva}}}.
    sub_clas Combustibles → tarifa 'No Sujeto' con IVA 0; resto usa tarifa_label."""
    result: dict[str, dict[str, dict[str, Decimal]]] = {}
    for ln, clas, sub in _lineas_clasificadas(db, cliente_id, periodo, rol):
        if sub in SUBCATEGORIAS_NO_SUJETO:
            tasa, iva = "No Sujeto", Decimal("0")
        else:
            tasa, iva = ln.tarifa_label, ln.iva_monto
        por_tasa = result.setdefault(clas, {})
        _acc(por_tasa, tasa, ln.base_imponible, iva)
    return result

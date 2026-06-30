"""Asistente de preclasificación: agrupa las líneas que quedan 'Sin Clasificar'
(según el engine de reglas) por CABYS o por cédula de la contraparte, para asignarlas
en lote. No escribe nada; solo agrega para mostrar."""
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.comprobante import Comprobante, LineaComprobante
from app.models.regla_clasificacion import ReglaClasificacion
from app.motor.clasificacion import build_lookup, clasificar


@dataclass
class Grupo:
    clave: str
    etiqueta: str
    lineas: int
    base: Decimal


def grupos_sin_clasificar(db: Session, cliente_id: int, periodo: str, rol: str,
                          por: str = "cabys") -> list[Grupo]:
    if por not in ("cabys", "cedula"):
        raise ValueError("por debe ser 'cabys' o 'cedula'")
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
    acc: dict[str, dict] = {}
    for ln, comp in db.execute(stmt):
        cedula = comp.emisor_cedula if rol == "compra" else comp.receptor_cedula
        clas, _ = clasificar(cedula, ln.cabys, rol, lookup)
        if clas != "Sin Clasificar":
            continue
        if por == "cabys":
            clave = (ln.cabys or "").strip()
            etiqueta = (ln.detalle or "").strip()
        else:
            clave = (cedula or "").strip()
            etiqueta = (comp.emisor_nombre if rol == "compra" else comp.receptor_nombre) or ""
        if not clave:
            continue
        g = acc.get(clave)
        if g is None:
            acc[clave] = {"etiqueta": etiqueta, "lineas": 1, "base": ln.base_imponible}
        else:
            g["lineas"] += 1
            g["base"] += ln.base_imponible
            if not g["etiqueta"] and etiqueta:
                g["etiqueta"] = etiqueta
    grupos = [Grupo(clave=k, etiqueta=v["etiqueta"], lineas=v["lineas"], base=v["base"])
              for k, v in acc.items()]
    grupos.sort(key=lambda g: g.base, reverse=True)
    return grupos

"""Engine de clasificación: lookup por prioridad (céd+cabys) > cabys > céd(+rol).
Port de build_clasificacion_lookup/classify_line del parse_xml.py viejo.
Las reglas de cédula sola se separan por rol; las de cabys son rol-agnósticas."""
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.models.regla_clasificacion import ReglaClasificacion

CLASIFICACIONES_VALID = {"Compras", "Gastos", "Bienes de Capital",
                         "No Deducibles", "Sin Clasificar"}
SUBCATEGORIAS_NO_SUJETO = {"Combustibles"}

@dataclass
class Lookup:
    by_ced_cabys: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    by_cabys: dict[str, tuple[str, str]] = field(default_factory=dict)
    by_ced: dict[str, tuple[str, str]] = field(default_factory=dict)
    by_ced_venta: dict[str, tuple[str, str]] = field(default_factory=dict)

def build_lookup(reglas: Iterable[ReglaClasificacion]) -> Lookup:
    lk = Lookup()
    for r in reglas:
        ced = (r.cedula or "").strip() or None
        cab = (r.cabys or "").strip() or None
        val = (r.clasificacion, (r.sub_clasificacion or "").strip())
        if ced and cab:
            lk.by_ced_cabys[(ced, cab)] = val
        elif ced:
            if r.rol == "venta":
                lk.by_ced_venta[ced] = val
            else:
                lk.by_ced[ced] = val
        elif cab:
            lk.by_cabys[cab] = val
    return lk

def clasificar(cedula: str | None, cabys: str | None, rol: str,
               lookup: Lookup) -> tuple[str, str]:
    ced = (cedula or "").strip() or None
    cab = (cabys or "").strip() or None
    if ced and cab and (ced, cab) in lookup.by_ced_cabys:
        return lookup.by_ced_cabys[(ced, cab)]
    if cab and cab in lookup.by_cabys:
        return lookup.by_cabys[cab]
    if ced:
        d = lookup.by_ced_venta if rol == "venta" else lookup.by_ced
        if ced in d:
            return d[ced]
    return ("Sin Clasificar", "")

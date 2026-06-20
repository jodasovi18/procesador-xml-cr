"""Transformaciones a nivel comprobante: conversión USD->CRC, signo negativo de
notas de crédito, y clasificación de líneas en Bienes/Servicios.
Port de _apply_transforms del parse_xml.py viejo. Devuelve una copia transformada."""
from decimal import Decimal
from app.motor.schemas import ComprobanteParsed

_SERV_UNITS = {"Sp", "h", "Al", "Os", "St", "I"}

_MONEY_FIELDS = [
    "total_serv_grav", "total_serv_exento", "total_serv_exon", "total_serv_no_sujeto",
    "total_merc_grav", "total_merc_exento", "total_merc_exon", "total_merc_no_sujeto",
    "total_gravado", "total_exento", "total_exonerado",
    "total_venta_neta", "total_descuentos", "total_iva",
    "total_otros_cargos", "total_comprobante",
]
_LINE_MONEY = ["monto_total", "descuento", "subtotal", "base_imponible",
               "iva_monto", "iva_neto", "precio_unitario"]

def apply_transforms(comp: ComprobanteParsed) -> ComprobanteParsed:
    c = comp.model_copy(deep=True)
    fx = c.tipo_cambio if (c.moneda == "USD" and c.tipo_cambio > 0) else Decimal("1")
    sign = Decimal("-1") if c.tipo_doc == "NotaCreditoElectronica" else Decimal("1")
    factor = fx * sign

    for fld in _MONEY_FIELDS:
        setattr(c, fld, getattr(c, fld) * factor)

    is_only_merc = abs(c.total_merc_grav) > 0 and c.total_serv_grav == 0
    is_only_serv = abs(c.total_serv_grav) > 0 and c.total_merc_grav == 0

    for ln in c.lineas:
        for lf in _LINE_MONEY:
            setattr(ln, lf, getattr(ln, lf) * factor)
        if sign == Decimal("-1"):
            ln.cantidad *= Decimal("-1")
        if is_only_merc:
            ln.tipo = "Bienes"
        elif is_only_serv:
            ln.tipo = "Servicios"
        else:
            ln.tipo = "Servicios" if getattr(ln, "unidad", "") in _SERV_UNITS else "Bienes"
    return c

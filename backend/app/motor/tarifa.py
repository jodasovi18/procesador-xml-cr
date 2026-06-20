"""Tratamiento de IVA por línea: tarifa efectiva, etiqueta y No Sujeto.
Port de TARIFA_MAP y la lógica de exoneración del parse_xml.py viejo.
El No Sujeto (códigos 10/11) NO lleva la etiqueta 'Combustibles' del sistema viejo."""
from decimal import Decimal
from pydantic import BaseModel
from app.motor.schemas import LineaParsed

TARIFA_MAP: dict[str, tuple[str, Decimal]] = {
    "01": ("Exento", Decimal("0")),
    "02": ("1%", Decimal("1")),
    "03": ("2%", Decimal("2")),
    "04": ("4%", Decimal("4")),
    "08": ("13%", Decimal("13")),
    "10": ("No Sujeto", Decimal("0")),
    "11": ("No Sujeto", Decimal("0")),
    "13": ("13%", Decimal("13")),
}
CODIGOS_NO_SUJETO = {"10", "11"}

def _pct_label(pct: Decimal) -> str:
    if pct == pct.to_integral_value():
        return f"{int(pct)}%"
    return f"{pct.normalize()}%"

class Tratamiento(BaseModel):
    label: str            # Exento | 1% | 2% | 4% | 13% | No Sujeto
    pct_efectiva: Decimal
    es_no_sujeto: bool

def tratamiento_linea(tarifa_codigo: str, tarifa_pct: Decimal,
                      exon_tarifa: Decimal = Decimal("0")) -> Tratamiento:
    if tarifa_codigo in CODIGOS_NO_SUJETO:
        return Tratamiento(label="No Sujeto", pct_efectiva=Decimal("0"), es_no_sujeto=True)
    pct = tarifa_pct
    if exon_tarifa > 0:
        pct = max(Decimal("0"), tarifa_pct - exon_tarifa)
    if pct > 0:
        return Tratamiento(label=_pct_label(pct), pct_efectiva=pct, es_no_sujeto=False)
    return Tratamiento(label="Exento", pct_efectiva=Decimal("0"), es_no_sujeto=False)

def tratamiento_de(linea: LineaParsed) -> Tratamiento:
    return tratamiento_linea(linea.tarifa_codigo, linea.tarifa_pct, linea.exon_tarifa)

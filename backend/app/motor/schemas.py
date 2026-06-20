from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel


class LineaParsed(BaseModel):
    numero: int
    cabys: str = ""
    detalle: str = ""
    cantidad: Decimal = Decimal("0")
    precio_unitario: Decimal = Decimal("0")
    monto_total: Decimal = Decimal("0")
    descuento: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")
    base_imponible: Decimal = Decimal("0")
    tarifa_codigo: str = ""
    tarifa_pct: Decimal = Decimal("0")
    iva_monto: Decimal = Decimal("0")
    iva_neto: Decimal = Decimal("0")
    exon_tarifa: Decimal = Decimal("0")
    exon_monto: Decimal = Decimal("0")
    tipo: str = ""   # Bienes | Servicios (lo asigna apply_transforms)


class ComprobanteParsed(BaseModel):
    clave: str
    tipo_doc: str
    consecutivo: str
    fecha: datetime
    cond_venta: str = ""
    emisor_nombre: str = ""
    emisor_cedula: str = ""
    receptor_nombre: str = ""
    receptor_cedula: str = ""
    moneda: str = "CRC"
    tipo_cambio: Decimal = Decimal("1")
    total_serv_grav: Decimal = Decimal("0")
    total_serv_exento: Decimal = Decimal("0")
    total_serv_exon: Decimal = Decimal("0")
    total_serv_no_sujeto: Decimal = Decimal("0")
    total_merc_grav: Decimal = Decimal("0")
    total_merc_exento: Decimal = Decimal("0")
    total_merc_exon: Decimal = Decimal("0")
    total_merc_no_sujeto: Decimal = Decimal("0")
    total_gravado: Decimal = Decimal("0")
    total_exento: Decimal = Decimal("0")
    total_exonerado: Decimal = Decimal("0")
    total_descuentos: Decimal = Decimal("0")
    total_venta_neta: Decimal = Decimal("0")
    total_iva: Decimal = Decimal("0")
    total_otros_cargos: Decimal = Decimal("0")
    total_comprobante: Decimal = Decimal("0")
    lineas: list[LineaParsed] = []

"""Pipeline de ingesta: mapeo de ComprobanteParsed a los modelos ORM,
aplicando transforms (signo NC, USD, Bienes/Servicios) y tarifa por línea."""
from datetime import datetime
from app.motor.schemas import ComprobanteParsed
from app.motor.transforms import apply_transforms
from app.motor.tarifa import tratamiento_de
from app.models.comprobante import Comprobante, LineaComprobante

def periodo_de(fecha: datetime) -> str:
    return f"{fecha.year}{fecha.month:02d}"

def construir_comprobante(comp: ComprobanteParsed, cliente_id: int | None,
                          rol: str | None, xml_raw: str) -> Comprobante:
    c = apply_transforms(comp)  # signo NC, USD, tipo Bienes/Servicios por línea
    orm = Comprobante(
        clave=c.clave, tipo_doc=c.tipo_doc, consecutivo=c.consecutivo,
        fecha=c.fecha, periodo=periodo_de(c.fecha), rol=rol, cliente_id=cliente_id,
        emisor_nombre=c.emisor_nombre, emisor_cedula=c.emisor_cedula,
        receptor_nombre=c.receptor_nombre, receptor_cedula=c.receptor_cedula,
        moneda=c.moneda, tipo_cambio=c.tipo_cambio,
        total_gravado=c.total_gravado, total_exento=c.total_exento,
        total_exonerado=c.total_exonerado,
        total_no_sujeto=c.total_serv_no_sujeto + c.total_merc_no_sujeto,
        total_iva=c.total_iva, total_comprobante=c.total_comprobante,
        xml_raw=xml_raw,
    )
    for ln in c.lineas:
        t = tratamiento_de(ln)
        orm.lineas.append(LineaComprobante(
            numero=ln.numero, cabys=ln.cabys, detalle=ln.detalle,
            cantidad=ln.cantidad, base_imponible=ln.base_imponible,
            tarifa_codigo=ln.tarifa_codigo, tarifa_pct=t.pct_efectiva,
            tarifa_label=t.label, tipo=ln.tipo, iva_monto=ln.iva_monto,
        ))
    return orm

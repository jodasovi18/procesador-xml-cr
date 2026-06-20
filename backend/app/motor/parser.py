"""
Port of the XML extractor from the legacy parse_xml.py (_extract_record, get_ns, sval, fval).
Element names are copied verbatim from the old file — do NOT change them.
Raw values only: no sign flips, no tarifa labels, no classification.
"""
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from app.motor.schemas import ComprobanteParsed, LineaParsed


# ── Namespace helper (ported from get_ns in legacy parse_xml.py) ──────────────

def _get_ns(root: ET.Element) -> str:
    if "}" in root.tag:
        return "{" + root.tag.split("}")[0].strip("{") + "}"
    return ""


# ── Value helpers (ported from sval / fval in legacy parse_xml.py) ───────────

def _sval(el: ET.Element | None, tag: str, nsp: str) -> str:
    if el is None:
        return ""
    return (el.findtext(f"{nsp}{tag}") or "").strip()


def _dval(el: ET.Element | None, tag: str, nsp: str) -> Decimal:
    """Like fval but returns Decimal instead of float."""
    if el is None:
        return Decimal("0")
    v = el.findtext(f"{nsp}{tag}")
    if v is None:
        return Decimal("0")
    try:
        return Decimal(str(v.strip()))
    except InvalidOperation:
        return Decimal("0")


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_comprobante_xml(xml_bytes: bytes) -> ComprobanteParsed:
    root = ET.fromstring(xml_bytes)
    nsp = _get_ns(root)

    # tipo_doc = local tag name of root (strip namespace)
    tipo_doc = root.tag.replace(nsp, "") if nsp else root.tag

    # Header fields (ported from _extract_record lines 901-904)
    clave      = _sval(root, "Clave", nsp)
    consec     = _sval(root, "NumeroConsecutivo", nsp)
    fecha_str  = _sval(root, "FechaEmision", nsp)
    cond_venta = _sval(root, "CondicionVenta", nsp)

    from datetime import datetime
    fecha = datetime.fromisoformat(fecha_str)

    # Emisor (ported from lines 906-912)
    emisor = root.find(f"{nsp}Emisor")
    emisor_nombre = _sval(emisor, "Nombre", nsp) if emisor is not None else ""
    emisor_cedula = ""
    if emisor is not None:
        ident = emisor.find(f"{nsp}Identificacion")
        if ident is not None:
            emisor_cedula = _sval(ident, "Numero", nsp)

    # Receptor (ported from lines 914-920)
    receptor = root.find(f"{nsp}Receptor")
    receptor_nombre = _sval(receptor, "Nombre", nsp) if receptor is not None else ""
    receptor_cedula = ""
    if receptor is not None:
        ident = receptor.find(f"{nsp}Identificacion")
        if ident is not None:
            receptor_cedula = _sval(ident, "Numero", nsp)

    # ResumenFactura — moneda (ported from lines 922-929)
    resumen = root.find(f"{nsp}ResumenFactura")
    moneda = "CRC"
    tipo_cambio = Decimal("1")
    if resumen is not None:
        ctm = resumen.find(f"{nsp}CodigoTipoMoneda")
        if ctm is not None:
            moneda = _sval(ctm, "CodigoMoneda", nsp) or "CRC"
            tc = _dval(ctm, "TipoCambio", nsp)
            # Decimal("0") es falsy: si TipoCambio falta o es 0 se asume 1 (port del viejo `or 1.0`).
            tipo_cambio = tc if tc else Decimal("1")

    # ResumenFactura — totales (ported from lines 931-951, exact element names)
    r = resumen if resumen is not None else root
    total_serv_grav      = _dval(r, "TotalServGravados", nsp)
    total_serv_exento    = _dval(r, "TotalServExentos", nsp)
    total_serv_exon      = _dval(r, "TotalServExonerado", nsp)
    total_serv_no_sujeto = _dval(r, "TotalServNoSujeto", nsp)
    total_merc_grav      = _dval(r, "TotalMercanciasGravadas", nsp)
    total_merc_exento    = _dval(r, "TotalMercanciasExentas", nsp)
    total_merc_exon      = _dval(r, "TotalMercExonerada", nsp)
    total_merc_no_sujeto = _dval(r, "TotalMercNoSujeta", nsp)
    total_gravado        = _dval(r, "TotalGravado", nsp)
    total_exento         = _dval(r, "TotalExento", nsp)
    total_exonerado      = _dval(r, "TotalExonerado", nsp)
    total_venta_neta     = _dval(r, "TotalVentaNeta", nsp)
    total_descuentos     = _dval(r, "TotalDescuentos", nsp)
    total_iva_bruto      = _dval(r, "TotalImpuesto", nsp)
    total_iva_devuelto   = _dval(r, "TotalIVADevuelto", nsp)
    total_iva            = max(Decimal("0"), total_iva_bruto - total_iva_devuelto)
    total_otros_cargos   = _dval(r, "TotalOtrosCargos", nsp)
    total_comprobante    = _dval(r, "TotalComprobante", nsp)

    # LineaDetalle (ported from lines 961-1014, exact element names)
    lineas: list[LineaParsed] = []
    for linea in root.iter(f"{nsp}LineaDetalle"):
        num_linea   = _sval(linea, "NumeroLinea", nsp)
        cabys       = _sval(linea, "CodigoCABYS", nsp)
        detalle     = _sval(linea, "Detalle", nsp)
        cantidad    = _dval(linea, "Cantidad", nsp)
        precio_unit = _dval(linea, "PrecioUnitario", nsp)
        monto_total = _dval(linea, "MontoTotal", nsp)
        # sum all Descuento/MontoDescuento children (ported from line 970)
        descuento   = sum(
            _dval(d, "MontoDescuento", nsp)
            for d in linea.findall(f"{nsp}Descuento")
        )
        subtotal    = _dval(linea, "SubTotal", nsp)
        base_imp    = _dval(linea, "BaseImponible", nsp)

        imp_cod_tarifa = ""
        imp_tarifa_pct = Decimal("0")
        imp_monto      = Decimal("0")
        imp_neto       = Decimal("0")
        exon_tarifa    = Decimal("0")
        exon_monto     = Decimal("0")

        # Impuesto children (ported from lines 979-1003)
        for imp in linea.findall(f"{nsp}Impuesto"):
            imp_cod_tarifa = _sval(imp, "CodigoTarifaIVA", nsp)
            try:
                imp_tarifa_pct = Decimal(str(_sval(imp, "Tarifa", nsp)))
            except InvalidOperation:
                imp_tarifa_pct = Decimal("0")
            monto_bruto = _dval(imp, "Monto", nsp)
            neto_xml    = _dval(imp, "ImpuestoNeto", nsp)

            # Exoneracion (ported from lines 992-1003)
            exon_el = imp.find(f"{nsp}Exoneracion")
            if exon_el is not None:
                exon_tarifa = _dval(exon_el, "TarifaExonerada", nsp)
                exon_monto  = _dval(exon_el, "MontoExoneracion", nsp)
                if neto_xml == Decimal("0") and exon_monto > Decimal("0"):
                    neto_xml = max(Decimal("0"), monto_bruto - exon_monto)

            imp_monto += monto_bruto
            imp_neto  += neto_xml

        lineas.append(LineaParsed(
            numero=int(num_linea) if num_linea.isdigit() else 0,
            cabys=cabys,
            detalle=detalle,
            cantidad=cantidad,
            precio_unitario=precio_unit,
            monto_total=monto_total,
            descuento=descuento,
            subtotal=subtotal,
            base_imponible=base_imp,
            tarifa_codigo=imp_cod_tarifa,
            tarifa_pct=imp_tarifa_pct,
            iva_monto=imp_monto,
            iva_neto=imp_neto,
            exon_tarifa=exon_tarifa,
            exon_monto=exon_monto,
        ))

    return ComprobanteParsed(
        clave=clave,
        tipo_doc=tipo_doc,
        consecutivo=consec,
        fecha=fecha,
        cond_venta=cond_venta,
        emisor_nombre=emisor_nombre,
        emisor_cedula=emisor_cedula,
        receptor_nombre=receptor_nombre,
        receptor_cedula=receptor_cedula,
        moneda=moneda,
        tipo_cambio=tipo_cambio,
        total_serv_grav=total_serv_grav,
        total_serv_exento=total_serv_exento,
        total_serv_exon=total_serv_exon,
        total_serv_no_sujeto=total_serv_no_sujeto,
        total_merc_grav=total_merc_grav,
        total_merc_exento=total_merc_exento,
        total_merc_exon=total_merc_exon,
        total_merc_no_sujeto=total_merc_no_sujeto,
        total_gravado=total_gravado,
        total_exento=total_exento,
        total_exonerado=total_exonerado,
        total_descuentos=total_descuentos,
        total_venta_neta=total_venta_neta,
        total_iva=total_iva,
        total_otros_cargos=total_otros_cargos,
        total_comprobante=total_comprobante,
        lineas=lineas,
    )

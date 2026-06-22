from datetime import datetime, timezone
from decimal import Decimal
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante, LineaComprobante
from app.motor.resumen import build_resumen

def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c

_seq = 0
def _mk_comp(db, cliente_id, *, rol, tipo_doc="FacturaElectronica", periodo="202605",
             tarifa_label="13%", tipo="Bienes", base="100", iva="13",
             emisor="3101", receptor="3102"):
    """Crea un Comprobante sintético con una línea (sin XML)."""
    global _seq
    _seq += 1
    c = Comprobante(
        clave=f"CLAVE{_seq}", tipo_doc=tipo_doc, consecutivo=str(_seq),
        fecha=datetime(2026, 5, 1, tzinfo=timezone.utc), periodo=periodo, rol=rol,
        cliente_id=cliente_id, emisor_cedula=emisor, receptor_cedula=receptor, xml_raw="<x/>")
    c.lineas.append(LineaComprobante(
        numero=1, cabys="0", detalle="d", cantidad=Decimal("1"),
        base_imponible=Decimal(base), tarifa_codigo="08", tarifa_pct=Decimal("13"),
        tarifa_label=tarifa_label, tipo=tipo, iva_monto=Decimal(iva)))
    db.add(c); db.commit(); db.refresh(c)
    return c

def test_build_resumen_excluir_tiquetes(db_session):
    cli = _cliente(db_session)
    _mk_comp(db_session, cli.id, rol="compra", tipo_doc="FacturaElectronica", base="100", iva="13")
    _mk_comp(db_session, cli.id, rol="compra", tipo_doc="TiqueteElectronico", base="50", iva="6.5")
    todos = build_resumen(db_session, cli.id, "202605", "compra")
    assert todos["Bienes 13%"]["base"] == Decimal("150")
    sin_tiq = build_resumen(db_session, cli.id, "202605", "compra",
                            excluir_tipos={"TiqueteElectronico"})
    assert sin_tiq["Bienes 13%"]["base"] == Decimal("100")
    assert sin_tiq["Bienes 13%"]["iva"] == Decimal("13")

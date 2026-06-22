from datetime import datetime, timezone
from decimal import Decimal
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante, LineaComprobante
from app.motor.resumen import build_resumen
from app.motor.d150 import build_d150, d150_ovi

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


def test_build_d150_precision_basico(db_session):
    cli = _cliente(db_session)
    _mk_comp(db_session, cli.id, rol="venta", base="1000", iva="130", tarifa_label="13%")
    _mk_comp(db_session, cli.id, rol="compra", base="200", iva="26", tarifa_label="13%")
    _mk_comp(db_session, cli.id, rol="compra", tipo_doc="TiqueteElectronico",
             base="50", iva="6.5", tarifa_label="13%")
    d = build_d150(db_session, cli.id, "202605")
    assert d["ventas"]["por_tasa"]["13%"]["iva"] == Decimal("130")
    assert d["ventas"]["total_impuesto"] == Decimal("130")
    assert d["compras"]["por_tasa"]["13%"]["base"] == Decimal("200")   # tiquete excluido
    assert d["compras"]["total_credito"] == Decimal("26")
    assert d["compras"]["tiquetes_excluidos_n"] == 1
    assert d["compras"]["tiquetes_excluidos_iva"] == Decimal("6.5")
    assert d["liquidacion"]["debito_fiscal"] == Decimal("130")
    assert d["liquidacion"]["credito_fiscal"] == Decimal("26")
    assert d["liquidacion"]["impuesto_neto"] == Decimal("104")
    assert d["liquidacion"]["estado"] == "a_pagar"


def test_build_d150_saldo_favor(db_session):
    cli = _cliente(db_session)
    _mk_comp(db_session, cli.id, rol="venta", base="100", iva="13", tarifa_label="13%")
    _mk_comp(db_session, cli.id, rol="compra", base="1000", iva="130", tarifa_label="13%")
    d = build_d150(db_session, cli.id, "202605")
    assert d["liquidacion"]["impuesto_neto"] == Decimal("-117")
    assert d["liquidacion"]["estado"] == "saldo_favor"


def test_build_d150_no_deducible_y_no_sujeto_fuera_del_credito(db_session):
    from app.models.regla_clasificacion import ReglaClasificacion
    cli = _cliente(db_session)
    # compra normal 13% (deducible) → crédito
    _mk_comp(db_session, cli.id, rol="compra", base="100", iva="13", tarifa_label="13%", emisor="PROV1")
    # compra de proveedor clasificado No Deducible → fuera del crédito
    _mk_comp(db_session, cli.id, rol="compra", base="500", iva="65", tarifa_label="13%", emisor="PROV2")
    db_session.add(ReglaClasificacion(cliente_id=cli.id, cedula="PROV2", clasificacion="No Deducibles"))
    # compra No Sujeto (tarifa_label "No Sujeto") → fuera del crédito
    _mk_comp(db_session, cli.id, rol="compra", base="300", iva="0", tarifa_label="No Sujeto", emisor="PROV3")
    db_session.commit()
    d = build_d150(db_session, cli.id, "202605")
    assert d["compras"]["por_tasa"]["13%"]["base"] == Decimal("100")   # solo el deducible
    assert d["compras"]["total_credito"] == Decimal("13")
    assert d["compras"]["no_deducibles"] == Decimal("500")
    assert d["compras"]["no_sujetas"] == Decimal("300")


def test_d150_ovi_redondeo(db_session):
    cli = _cliente(db_session)
    # base 1858.40 / iva 241.59 (como fe_almacen_leon): OVI base=1858, iva=round(1858.40*0.13)=242
    _mk_comp(db_session, cli.id, rol="compra", base="1858.40", iva="241.59", tarifa_label="13%")
    d = build_d150(db_session, cli.id, "202605")
    ovi = d150_ovi(d)
    assert d["compras"]["por_tasa"]["13%"]["iva"] == Decimal("241.59")  # preciso intacto
    assert ovi["compras"]["por_tasa"]["13%"]["base"] == 1858
    assert ovi["compras"]["por_tasa"]["13%"]["iva"] == 242
    assert ovi["compras"]["total_credito"] == 242
    assert ovi["liquidacion"]["credito_fiscal"] == 242
    assert ovi["liquidacion"]["impuesto_neto"] == -242   # sin ventas → débito 0
    assert ovi["liquidacion"]["estado"] == "saldo_favor"

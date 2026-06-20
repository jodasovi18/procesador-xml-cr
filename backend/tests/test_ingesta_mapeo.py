from pathlib import Path
from decimal import Decimal
from app.motor.parser import parse_comprobante_xml
from app.motor.ingesta import periodo_de, construir_comprobante

FIXT = Path(__file__).parent / "fixtures"

def test_periodo_de_la_fecha():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    assert periodo_de(comp.fecha) == "202605"

def test_construir_comprobante_compra():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    orm = construir_comprobante(comp, cliente_id=7, rol="compra", xml_raw="<xml/>")
    assert orm.clave == "50604052600310103004200100001010000324943131803899"
    assert orm.periodo == "202605"
    assert orm.rol == "compra"
    assert orm.cliente_id == 7
    assert orm.total_comprobante == Decimal("2099.99")
    assert len(orm.lineas) == 1
    ln = orm.lineas[0]
    assert ln.tarifa_label == "13%"
    assert ln.tarifa_pct == Decimal("13")
    assert ln.tipo == "Bienes"

def test_construir_comprobante_venta_no_sujeto():
    comp = parse_comprobante_xml((FIXT / "venta_nosujeto.xml").read_bytes())
    orm = construir_comprobante(comp, cliente_id=7, rol="venta", xml_raw="<xml/>")
    no_sujetas = [l for l in orm.lineas if l.tarifa_codigo == "10"]
    assert no_sujetas
    for l in no_sujetas:
        assert l.tarifa_label == "No Sujeto"

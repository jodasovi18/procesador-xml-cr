from pathlib import Path
from decimal import Decimal
from app.motor.parser import parse_comprobante_xml
from app.motor.tarifa import tratamiento_linea, tratamiento_de

FIXT = Path(__file__).parent / "fixtures"

def test_codigo_08_es_13pct():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    t = tratamiento_de(comp.lineas[0])
    assert t.label == "13%"
    assert t.pct_efectiva == Decimal("13")
    assert t.es_no_sujeto is False

def test_codigo_10_es_no_sujeto_sin_combustibles():
    comp = parse_comprobante_xml((FIXT / "venta_nosujeto.xml").read_bytes())
    no_sujetas = [l for l in comp.lineas if l.tarifa_codigo == "10"]
    assert no_sujetas, "el fixture debe tener al menos una linea codigo 10"
    for l in no_sujetas:
        t = tratamiento_de(l)
        assert t.label == "No Sujeto"          # EL FIX: nunca 'No Sujeto (Combustibles)'
        assert t.es_no_sujeto is True
        assert t.pct_efectiva == Decimal("0")

def test_exoneracion_resta_tarifa():
    # 13% con TarifaExonerada 12% -> 1% efectivo (Ley 9635 agropecuaria)
    t = tratamiento_linea("08", Decimal("13"), Decimal("12"))
    assert t.label == "1%"
    assert t.pct_efectiva == Decimal("1")
    assert t.es_no_sujeto is False

def test_codigo_01_exento():
    t = tratamiento_linea("01", Decimal("0"))
    assert t.label == "Exento"
    assert t.es_no_sujeto is False

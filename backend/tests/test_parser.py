from pathlib import Path
from decimal import Decimal
from app.motor.parser import parse_comprobante_xml

FIXT = Path(__file__).parent / "fixtures" / "fe_almacen_leon.xml"


def test_parse_fe_compra_real():
    comp = parse_comprobante_xml(FIXT.read_bytes())
    assert comp.tipo_doc == "FacturaElectronica"
    assert comp.clave == "50604052600310103004200100001010000324943131803899"
    assert comp.consecutivo == "00100001010000324943"
    assert comp.fecha.year == 2026 and comp.fecha.month == 5 and comp.fecha.day == 4
    assert comp.emisor_cedula == "3101030042"
    assert comp.receptor_cedula == "3102858282"
    assert comp.total_gravado == Decimal("1858.40")
    assert comp.total_iva == Decimal("241.59")
    assert comp.total_comprobante == Decimal("2099.99")
    assert len(comp.lineas) == 1
    ln = comp.lineas[0]
    assert ln.numero == 1
    assert ln.cabys == "4651006000000"
    assert ln.base_imponible == Decimal("1858.40")
    assert ln.tarifa_codigo == "08"
    assert ln.tarifa_pct == Decimal("13.00")

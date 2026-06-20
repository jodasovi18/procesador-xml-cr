from decimal import Decimal
from pathlib import Path
from app.motor.parser import parse_comprobante_xml
from app.motor.transforms import apply_transforms

FIXT = Path(__file__).parent / "fixtures"

def test_factura_compra_es_bienes_y_positiva():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    out = apply_transforms(comp)
    # No es nota de crédito: montos quedan positivos
    assert out.total_comprobante == Decimal("2099.99")
    # La factura es solo mercancías -> líneas tipo Bienes
    assert out.lineas[0].tipo == "Bienes"

def test_nota_credito_invierte_signo():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    # Forzamos el tipo a nota de crédito para probar el signo (mismo monto, signo negativo)
    comp.tipo_doc = "NotaCreditoElectronica"
    out = apply_transforms(comp)
    assert out.total_comprobante == Decimal("-2099.99")
    assert out.total_iva == Decimal("-241.59")

def test_usd_se_convierte_a_crc():
    comp = parse_comprobante_xml((FIXT / "fe_almacen_leon.xml").read_bytes())
    comp.moneda = "USD"
    comp.tipo_cambio = Decimal("500")
    out = apply_transforms(comp)
    assert out.total_comprobante == Decimal("2099.99") * Decimal("500")

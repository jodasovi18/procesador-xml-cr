from decimal import Decimal
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante, LineaComprobante
from app.models.regla_clasificacion import ReglaClasificacion
from app.motor.preclasificacion import grupos_sin_clasificar


def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c


def _comp_con_lineas(db, cliente_id, emisor_ced, emisor_nom, lineas):
    """lineas: list of (cabys, detalle, base)."""
    comp = Comprobante(cliente_id=cliente_id, clave=f"k{emisor_ced}{len(lineas)}{db.query(Comprobante).count()}",
                       tipo_doc="FacturaElectronica", consecutivo="1",
                       fecha=__import__("datetime").datetime(2026, 5, 1), periodo="202605", rol="compra",
                       emisor_cedula=emisor_ced, emisor_nombre=emisor_nom,
                       receptor_cedula="3102858282", receptor_nombre="Agrofinca", xml_raw="<x/>")
    db.add(comp); db.flush()
    for i, (cabys, detalle, base) in enumerate(lineas, 1):
        db.add(LineaComprobante(comprobante_id=comp.id, numero=i, cabys=cabys, detalle=detalle,
                                base_imponible=Decimal(base), tarifa_label="13%", tipo="Bienes",
                                iva_monto=Decimal("0")))
    db.commit()
    return comp


def test_agrupa_por_cabys(db_session):
    cli = _cliente(db_session)
    _comp_con_lineas(db_session, cli.id, "3101030042", "Insumos", [
        ("2310100000000", "Fertilizante", "100"),
        ("2310100000000", "Fertilizante NPK", "50"),
        ("3420100000000", "Diésel", "200"),
    ])
    grupos = grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "cabys")
    assert [g.clave for g in grupos] == ["3420100000000", "2310100000000"]
    fert = next(g for g in grupos if g.clave == "2310100000000")
    assert fert.lineas == 2
    assert fert.base == Decimal("150")
    assert fert.etiqueta


def test_agrupa_por_cedula(db_session):
    cli = _cliente(db_session)
    _comp_con_lineas(db_session, cli.id, "3101030042", "Insumos del Valle", [
        ("2310100000000", "Fertilizante", "100"),
    ])
    _comp_con_lineas(db_session, cli.id, "3102888777", "Transportes Sur", [
        ("8511000000000", "Flete", "300"),
    ])
    grupos = grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "cedula")
    assert [g.clave for g in grupos] == ["3102888777", "3101030042"]
    ins = next(g for g in grupos if g.clave == "3101030042")
    assert ins.etiqueta == "Insumos del Valle"
    assert ins.base == Decimal("100")


def test_excluye_lo_ya_cubierto_por_regla(db_session):
    cli = _cliente(db_session)
    _comp_con_lineas(db_session, cli.id, "3101030042", "Insumos", [
        ("2310100000000", "Fertilizante", "100"),
        ("3420100000000", "Diésel", "200"),
    ])
    db_session.add(ReglaClasificacion(cliente_id=cli.id, cabys="2310100000000", clasificacion="Compras"))
    db_session.commit()
    grupos = grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "cabys")
    assert [g.clave for g in grupos] == ["3420100000000"]


def test_omite_clave_vacia(db_session):
    cli = _cliente(db_session)
    _comp_con_lineas(db_session, cli.id, "3101030042", "Insumos", [("", "Sin cabys", "100")])
    assert grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "cabys") == []


def test_por_invalido(db_session):
    cli = _cliente(db_session)
    import pytest
    with pytest.raises(ValueError):
        grupos_sin_clasificar(db_session, cli.id, "202605", "compra", "otro")

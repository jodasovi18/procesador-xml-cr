from sqlalchemy import select
from app.models.cliente import Cliente
from app.models.regla_clasificacion import ReglaClasificacion

def test_persistir_regla(db_session):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    db_session.add(ReglaClasificacion(
        cliente_id=c.id, cedula="3101030042", clasificacion="No Deducibles"))
    db_session.commit()
    r = db_session.scalar(select(ReglaClasificacion).where(ReglaClasificacion.cliente_id == c.id))
    assert r.cedula == "3101030042"
    assert r.clasificacion == "No Deducibles"
    assert r.cabys is None
    assert r.rol is None
    assert r.sub_clasificacion is None

from decimal import Decimal
from sqlalchemy import select
from app.models.cliente import Cliente
from app.models.entrada_manual import EntradaManual

def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c

def test_persistir_entrada_manual(db_session):
    cli = _cliente(db_session)
    db_session.add(EntradaManual(
        cliente_id=cli.id, periodo="202605", rol="compra", descripcion="Subasta ganado",
        monto=Decimal("2000"), tarifa=Decimal("13"), no_sujeto=False, deducible=False))
    db_session.commit()
    e = db_session.scalar(select(EntradaManual).where(EntradaManual.cliente_id == cli.id))
    assert e.rol == "compra"
    assert e.monto == Decimal("2000")
    assert e.tarifa == Decimal("13")
    assert e.deducible is False
    assert e.no_sujeto is False
    assert e.descripcion == "Subasta ganado"

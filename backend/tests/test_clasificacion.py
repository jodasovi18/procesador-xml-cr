from app.models.regla_clasificacion import ReglaClasificacion
from app.motor.clasificacion import build_lookup, clasificar, CLASIFICACIONES_VALID, SUBCATEGORIAS_NO_SUJETO

def _r(**kw):
    # ReglaClasificacion sin sesión: solo un objeto en memoria
    return ReglaClasificacion(cliente_id=1, **kw)

def test_prioridad_ced_cabys_gana_a_cabys():
    lk = build_lookup([
        _r(cedula="123", cabys="ABC", clasificacion="Compras"),
        _r(cabys="ABC", clasificacion="Gastos"),
    ])
    assert clasificar("123", "ABC", "compra", lk) == ("Compras", "")

def test_prioridad_cabys_gana_a_ced():
    lk = build_lookup([
        _r(cabys="ABC", clasificacion="Gastos"),
        _r(cedula="123", clasificacion="Compras"),
    ])
    assert clasificar("123", "ABC", "compra", lk) == ("Gastos", "")

def test_separacion_de_rol():
    lk = build_lookup([
        _r(cedula="123", rol="compra", clasificacion="Compras"),
        _r(cedula="123", rol="venta", clasificacion="Gastos"),
    ])
    assert clasificar("123", None, "compra", lk) == ("Compras", "")
    assert clasificar("123", None, "venta", lk) == ("Gastos", "")

def test_sub_clasificacion_combustibles():
    lk = build_lookup([
        _r(cedula="123", clasificacion="Gastos", sub_clasificacion="Combustibles"),
    ])
    assert clasificar("123", None, "compra", lk) == ("Gastos", "Combustibles")
    assert "Combustibles" in SUBCATEGORIAS_NO_SUJETO

def test_fallback_sin_clasificar():
    lk = build_lookup([])
    assert clasificar("999", "ZZZ", "compra", lk) == ("Sin Clasificar", "")
    assert "Sin Clasificar" in CLASIFICACIONES_VALID

from sxml_agent.estado import Estado

def test_estado_vacio_si_no_existe(tmp_path):
    e = Estado.cargar(str(tmp_path / "estado.json"))
    assert e.ya_subido("abc") is False

def test_estado_marcar_guardar_recargar(tmp_path):
    ruta = str(tmp_path / "estado.json")
    e = Estado.cargar(ruta)
    e.marcar("abc"); e.guardar()
    e2 = Estado.cargar(ruta)
    assert e2.ya_subido("abc") is True
    assert e2.ya_subido("xyz") is False

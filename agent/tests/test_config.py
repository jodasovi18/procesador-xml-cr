from sxml_agent.config import cargar_config

def test_cargar_config(tmp_path):
    f = tmp_path / "agent.toml"
    f.write_text(
        'backend_url = "http://localhost:8000/"\n'
        'usuario = "agente"\n'
        'clave = "secreta"\n'
        'carpetas = ["C:/datos/a", "C:/datos/b"]\n'
        'lote_size = 50\n',
        encoding="utf-8")
    cfg = cargar_config(str(f))
    assert cfg.backend_url == "http://localhost:8000"   # sin barra final
    assert cfg.usuario == "agente"
    assert cfg.clave == "secreta"
    assert cfg.carpetas == ["C:/datos/a", "C:/datos/b"]
    assert cfg.lote_size == 50
    assert cfg.estado_path == "estado.json"   # default

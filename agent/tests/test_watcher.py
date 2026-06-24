from sxml_agent import run, watcher

def _cfg(tmp_path, intervalo=300):
    f = tmp_path / "agent.toml"
    f.write_text(
        f'backend_url = "http://x"\nusuario = "u"\nclave = "p"\n'
        f'carpetas = []\nintervalo = {intervalo}\n', encoding="utf-8")
    return str(f)

def test_vigilar_corre_max_corridas(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    llamadas = []
    def fake(p, api=None):
        llamadas.append(p)
        return {"tandas_fallidas": 0}
    monkeypatch.setattr(run, "ejecutar", fake)
    n = watcher.vigilar(cfg, max_corridas=3, dormir=lambda s: None)
    assert n == 3
    assert len(llamadas) == 3

def test_vigilar_continua_si_una_pasada_falla(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    llamadas = []
    def fake(p, api=None):
        llamadas.append(p)
        if len(llamadas) == 1:
            raise RuntimeError("backend caído")
        return {"tandas_fallidas": 0}
    monkeypatch.setattr(run, "ejecutar", fake)
    n = watcher.vigilar(cfg, max_corridas=2, dormir=lambda s: None)
    assert n == 2
    assert len(llamadas) == 2

def test_vigilar_usa_intervalo_override(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, intervalo=300)
    monkeypatch.setattr(run, "ejecutar", lambda p, api=None: {"tandas_fallidas": 0})
    esperas = []
    watcher.vigilar(cfg, intervalo=60, max_corridas=2, dormir=lambda s: esperas.append(s))
    assert esperas == [60]   # 2 pasadas → 1 sleep entre ellas, con el override (no cfg.intervalo=300)

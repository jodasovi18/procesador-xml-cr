import httpx
from sxml_agent.run import ejecutar
from sxml_agent import run as run_mod
from sxml_agent import __main__ as cli
from sxml_agent.cliente_api import ApiClient
from sxml_agent.estado import Estado
from sxml_agent.escaner import hash_archivo

def _api(handler):
    return ApiClient("http://x", client=httpx.Client(transport=httpx.MockTransport(handler)))

def _cfg(tmp_path, carpeta, estado_path, lote_size=10):
    f = tmp_path / "agent.toml"
    f.write_text(
        f'backend_url = "http://x"\nusuario = "u"\nclave = "p"\n'
        f'carpetas = [{carpeta!r}]\nlote_size = {lote_size}\nestado_path = {estado_path!r}\n',
        encoding="utf-8")
    return str(f)

def _ok_handler(req):
    if req.url.path == "/auth/login":
        return httpx.Response(200, json={"access_token": "TOK"})
    if req.url.path == "/api/ingesta/lote":
        return httpx.Response(200, json={"total": 2, "nuevos": 2, "actualizados": 0,
                                         "omitidos": 0, "errores": 0, "archivos": []})
    return httpx.Response(404)

def test_run_sube_nuevos_y_omite_en_segunda_corrida(tmp_path):
    datos = tmp_path / "datos"; datos.mkdir()
    (datos / "a.xml").write_text("<a/>", encoding="utf-8")
    (datos / "b.xml").write_text("<b/>", encoding="utf-8")
    estado_path = str(tmp_path / "estado.json")
    cfg = _cfg(tmp_path, str(datos), estado_path)
    r1 = ejecutar(cfg, api=_api(_ok_handler))
    assert r1["escaneados"] == 2
    assert r1["enviados"] == 2
    assert r1["nuevos"] == 2
    assert r1["ya_subidos_local"] == 0
    r2 = ejecutar(cfg, api=_api(_ok_handler))
    assert r2["enviados"] == 0
    assert r2["ya_subidos_local"] == 2

def test_run_tanda_fallida_no_marca(tmp_path):
    datos = tmp_path / "datos"; datos.mkdir()
    (datos / "a.xml").write_text("<a/>", encoding="utf-8")
    estado_path = str(tmp_path / "estado.json")
    cfg = _cfg(tmp_path, str(datos), estado_path)
    def handler(req):
        if req.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "TOK"})
        return httpx.Response(500)
    r = ejecutar(cfg, api=_api(handler))
    assert r["tandas_fallidas"] == 1
    assert r["enviados"] == 0
    e = Estado.cargar(estado_path)
    assert e.ya_subido(hash_archivo(datos / "a.xml")) is False

def test_run_relogin_en_401(tmp_path):
    datos = tmp_path / "datos"; datos.mkdir()
    (datos / "a.xml").write_text("<a/>", encoding="utf-8")
    cfg = _cfg(tmp_path, str(datos), str(tmp_path / "estado.json"))
    llamadas = {"login": 0, "lote": 0}
    def handler(req):
        if req.url.path == "/auth/login":
            llamadas["login"] += 1
            return httpx.Response(200, json={"access_token": "TOK"})
        llamadas["lote"] += 1
        if llamadas["lote"] == 1:
            return httpx.Response(401)
        return httpx.Response(200, json={"total": 1, "nuevos": 1, "actualizados": 0,
                                         "omitidos": 0, "errores": 0, "archivos": []})
    r = ejecutar(cfg, api=_api(handler))
    assert llamadas["login"] == 2
    assert r["enviados"] == 1
    assert r["nuevos"] == 1

def test_main_exit_code_ok(monkeypatch):
    monkeypatch.setattr(run_mod, "ejecutar", lambda cfg: {"tandas_fallidas": 0})
    assert cli.main(["--config", "x.toml"]) == 0

def test_main_exit_code_con_fallidas(monkeypatch):
    monkeypatch.setattr(run_mod, "ejecutar", lambda cfg: {"tandas_fallidas": 1})
    assert cli.main(["--config", "x.toml"]) == 1

from sxml_agent import watcher as watcher_mod

def test_main_watch_llama_vigilar(monkeypatch):
    capt = {}
    def fake_vigilar(p, intervalo=None):
        capt["p"] = p
        capt["intervalo"] = intervalo
    monkeypatch.setattr(watcher_mod, "vigilar", fake_vigilar)
    assert cli.main(["--config", "x.toml", "--watch", "--intervalo", "60"]) == 0
    assert capt["p"] == "x.toml"
    assert capt["intervalo"] == 60

def test_main_watch_keyboard_interrupt_exit_0(monkeypatch):
    def fake_vigilar(p, intervalo=None):
        raise KeyboardInterrupt
    monkeypatch.setattr(watcher_mod, "vigilar", fake_vigilar)
    assert cli.main(["--config", "x.toml", "--watch"]) == 0

def test_main_watch_exception_exit_2(monkeypatch):
    def fake_vigilar(p, intervalo=None):
        raise RuntimeError("backend down")
    monkeypatch.setattr(watcher_mod, "vigilar", fake_vigilar)
    assert cli.main(["--config", "x.toml", "--watch"]) == 2
